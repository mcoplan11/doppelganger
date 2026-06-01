from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gemini_client import BatchInput, GeminiClient, is_answerable
from personas import Persona
from qualtrics_client import QualtricsClient, Question, SessionBlock, SurveyDefinition


# Default cross-persona-batch threshold: above this, run_many switches to the
# Gemini Batch API (50% cost). Below, sync round-trips (fast for smoke tests).
DEFAULT_BATCH_THRESHOLD = 20


_NUMERIC_HINTS = (
    "percent", "%", "0-100", "0 to 100",
    "please enter the number", "enter your age", "in years",
    "how many", "how much",
)


def _looks_numeric(q: Question) -> bool:
    text = (q.prompt_text or "").lower()
    return any(h in text for h in _NUMERIC_HINTS)


def _extract_number(value: Any) -> str:
    # Pull the first integer (incl. negatives) from the LLM's free-form response,
    # so answers like "60%", "around 50", or "$25" get reduced to the numeric
    # value Qualtrics's text-entry validation will accept.
    m = re.search(r"-?\d+", str(value))
    return m.group(0) if m else str(value)


@dataclass
class SessionRun:
    persona: Persona
    session_id: str
    branch_id: str | None
    branch_description: str | None
    embedded_data: dict[str, Any] = field(default_factory=dict)
    answers: dict[str, Any] = field(default_factory=dict)
    completed: bool = False
    error: str | None = None


def run_session(
    qualtrics: QualtricsClient,
    gemini: GeminiClient,
    survey: SurveyDefinition,
    persona: Persona,
) -> SessionRun:
    """Start a Qualtrics session, have the persona answer every block until done."""
    run = SessionRun(
        persona=persona,
        session_id="",
        branch_id=None,
        branch_description=None,
    )

    answer_history: list[tuple[Question, Any]] = []
    # Descriptive (DB) blocks carry scenario/instruction text — they're not
    # answered but they prime the persona for later questions. Accumulate them
    # in reading order so each call to the LLM sees the same context the
    # respondent would have read on screen by that point.
    read_context: list[Question] = []
    try:
        block = qualtrics.start_session(survey)
        run.session_id = block.session_id
        run.branch_id = _detect_branch(survey, block)
        run.branch_description = _branch_description(survey, run.branch_id)
        run.embedded_data = dict(block.embedded_data or {})

        current_block = block
        while not current_block.done:
            for q in current_block.questions:
                if q.question_type == "DB" and q.prompt_text:
                    read_context.append(q)

            answers = gemini.answer_block(
                persona=persona,
                questions=current_block.questions,
                prior_answers=answer_history,
                read_context=read_context,
                survey_name=survey.name,
            )

            for q in current_block.questions:
                if q.qid in answers:
                    run.answers[q.qid] = answers[q.qid]
                    answer_history.append((q, answers[q.qid]))

            submission = _gemini_answers_to_qualtrics(current_block.questions, answers)
            current_block = qualtrics.advance_session(survey, run.session_id, submission)

            # Embedded data values can be set partway through the flow (e.g.
            # by a Randomizer after a consent block). Refresh from the latest
            # session state so we capture the assignment whenever it lands.
            if current_block.embedded_data:
                run.embedded_data.update(current_block.embedded_data)
            if run.branch_id is None:
                run.branch_id = _detect_branch(survey, current_block)
                run.branch_description = _branch_description(survey, run.branch_id)

        run.completed = True
    except Exception as e:
        run.error = f"{type(e).__name__}: {e}"
    return run


def run_many(
    qualtrics: QualtricsClient,
    gemini: GeminiClient,
    survey: SurveyDefinition,
    personas: list[Persona],
    runs_per_persona: int,
    out_dir: "Path | None" = None,
    use_batch: bool | None = None,
    batch_threshold: int = DEFAULT_BATCH_THRESHOLD,
) -> list[SessionRun]:
    """Run each persona through the survey N times.

    Default (`use_batch=None`): auto-detect. Switches to the Gemini Batch API
    (50% cost discount) when total sessions > batch_threshold; uses per-persona
    sync calls otherwise. Pass use_batch=True/False to override explicitly.
    """
    total_sessions = len(personas) * runs_per_persona
    if use_batch is None:
        use_batch = total_sessions > batch_threshold

    if use_batch:
        print(f"Using Gemini Batch API "
              f"({total_sessions} sessions > threshold {batch_threshold} = batch mode).",
              flush=True)
        return _run_many_batched(qualtrics, gemini, survey, personas, runs_per_persona, out_dir)
    return _run_many_sync(qualtrics, gemini, survey, personas, runs_per_persona, out_dir)


def _save_run(out_dir: "Path | None", idx: int, run: SessionRun) -> None:
    if out_dir is None:
        return
    artifact = {
        "session_id": run.session_id,
        "persona": run.persona.name,
        "branch_id": run.branch_id,
        "branch_description": run.branch_description,
        "embedded_data": run.embedded_data,
        "completed": run.completed,
        "error": run.error,
        "answers": run.answers,
    }
    suffix = "completed" if run.completed else "failed"
    (out_dir / f"{idx:03d}_{run.persona.name}_{suffix}.json").write_text(
        json.dumps(artifact, indent=2)
    )


def _run_many_sync(
    qualtrics: QualtricsClient,
    gemini: GeminiClient,
    survey: SurveyDefinition,
    personas: list[Persona],
    runs_per_persona: int,
    out_dir: "Path | None",
) -> list[SessionRun]:
    runs: list[SessionRun] = []
    idx = 0
    for persona in personas:
        for i in range(runs_per_persona):
            idx += 1
            print(f"\n[{persona.name} {i + 1}/{runs_per_persona}] starting session...", flush=True)
            run = run_session(qualtrics, gemini, survey, persona)
            runs.append(run)
            status = "completed" if run.completed else f"FAILED ({run.error})"
            branch = f" branch={run.branch_description!r}" if run.branch_description else ""
            print(f"  → {status}{branch}", flush=True)
            _save_run(out_dir, idx, run)
    return runs


@dataclass
class _BatchState:
    """Per-session running state for the cross-persona batched runner."""
    idx: int
    persona: Persona
    run: SessionRun
    current_block: SessionBlock | None = None
    answer_history: list[tuple[Question, Any]] = field(default_factory=list)
    read_context: list[Question] = field(default_factory=list)


def _run_many_batched(
    qualtrics: QualtricsClient,
    gemini: GeminiClient,
    survey: SurveyDefinition,
    personas: list[Persona],
    runs_per_persona: int,
    out_dir: "Path | None",
) -> list[SessionRun]:
    """Cross-persona batched runner.

    Pattern: start all sessions sync. Then loop — collect each active session's
    current-block questions into a single Gemini batch request, wait for the
    batch round to resolve, distribute answers back, then advance each
    session's Qualtrics state. Repeat until every session is done or errored.
    """
    states: list[_BatchState] = []
    flat_idx = 0
    print(f"Phase 1: starting {len(personas) * runs_per_persona} Qualtrics sessions...",
          flush=True)
    for persona in personas:
        for i in range(runs_per_persona):
            flat_idx += 1
            run = SessionRun(persona=persona, session_id="", branch_id=None,
                             branch_description=None)
            state = _BatchState(idx=flat_idx, persona=persona, run=run)
            try:
                block = qualtrics.start_session(survey)
                run.session_id = block.session_id
                run.branch_id = _detect_branch(survey, block)
                run.branch_description = _branch_description(survey, run.branch_id)
                run.embedded_data = dict(block.embedded_data or {})
                state.current_block = block
            except Exception as e:
                run.error = f"{type(e).__name__}: {e}"
                _save_run(out_dir, flat_idx, run)
            states.append(state)
    print(f"Sessions started. {sum(1 for s in states if s.run.error)} failed at start.",
          flush=True)

    round_idx = 0
    while True:
        active = [s for s in states
                  if not s.run.completed and not s.run.error
                  and s.current_block is not None and not s.current_block.done]
        if not active:
            break
        round_idx += 1

        # Build one BatchInput per (session, answerable question).
        # Splitting into single-question requests keeps each JSON schema to
        # exactly one required property — the Gemini Batch API silently drops
        # keys from multi-property required schemas, causing Qualtrics 400s.
        # Per-question results are merged back into per-session dicts below.
        inputs: list[BatchInput] = []
        # composite_key = "{session_id}::{qid}" → (state, question)
        key_map: dict[str, tuple[_BatchState, Question]] = {}
        # Sessions whose current block has no answerable questions
        db_only: list[_BatchState] = []

        for s in active:
            for q in s.current_block.questions:
                if q.question_type == "DB" and q.prompt_text:
                    s.read_context.append(q)
            answerable = [q for q in s.current_block.questions if is_answerable(q)]
            if not answerable:
                db_only.append(s)
                continue
            for q in answerable:
                composite_key = f"{s.run.session_id}::{q.qid}"
                inputs.append(BatchInput(
                    key=composite_key,
                    persona=s.persona,
                    answerable=[q],
                    prior_answers=list(s.answer_history),
                    read_context=list(s.read_context),
                    survey_name=survey.name,
                ))
                key_map[composite_key] = (s, q)

        n_q = len(inputs)
        print(f"\n--- Round {round_idx}: {len(active)} active sessions "
              f"({n_q} question requests) ---", flush=True)
        if db_only:
            print(f"  ({len(db_only)} sessions on all-DB blocks — no Gemini call needed)",
                  flush=True)

        # Merge per-question answers back into per-session dicts.
        # DB-only sessions get an empty answers dict so they still advance.
        session_merged: dict[str, dict[str, Any]] = {
            s.run.session_id: {} for s in db_only
        }
        session_error: dict[str, str] = {}

        if inputs:
            try:
                raw = gemini.answer_blocks_batch(
                    inputs,
                    poll_interval_seconds=30,
                    on_progress=lambda msg: print(f"  {msg}", flush=True),
                )
            except Exception as e:
                print(f"  BATCH ERROR: {e}", file=sys.stderr, flush=True)
                for s in active:
                    s.run.error = f"batch error: {e}"
                    _save_run(out_dir, s.idx, s.run)
                break

            # Collect batch results; queue any missing/empty answers for a
            # second batch pass (avoids sync calls, keeps 50% cost discount).
            retry_inputs: list[BatchInput] = []
            retry_key_map: dict[str, tuple[_BatchState, Question]] = {}
            for composite_key, single_ans in raw.items():
                s, q = key_map[composite_key]
                sid = s.run.session_id
                if single_ans and q.qid in single_ans:
                    session_merged.setdefault(sid, {}).update(single_ans)
                else:
                    retry_key = f"{sid}::retry::{q.qid}"
                    retry_inputs.append(BatchInput(
                        key=retry_key,
                        persona=s.persona,
                        answerable=[q],
                        prior_answers=list(s.answer_history),
                        read_context=list(s.read_context),
                        survey_name=survey.name,
                    ))
                    retry_key_map[retry_key] = (s, q)

            if retry_inputs:
                print(f"  Batch retry: {len(retry_inputs)} questions with empty responses...",
                      flush=True)
                try:
                    retry_raw = gemini.answer_blocks_batch(
                        retry_inputs,
                        poll_interval_seconds=30,
                        on_progress=lambda msg: print(f"    {msg}", flush=True),
                    )
                    for retry_key, single_ans in retry_raw.items():
                        s, q = retry_key_map[retry_key]
                        sid = s.run.session_id
                        if single_ans and q.qid in single_ans:
                            session_merged.setdefault(sid, {}).update(single_ans)
                        else:
                            session_error[sid] = f"batch retry still empty for {q.qid}"
                except Exception as e:
                    for retry_key in retry_inputs:
                        s, q = retry_key_map[retry_key.key]
                        session_error[s.run.session_id] = f"batch retry error: {e}"

        # Advance each session's Qualtrics state.
        for s in active:
            sid = s.run.session_id
            if sid in session_error:
                s.run.error = session_error[sid]
                _save_run(out_dir, s.idx, s.run)
                continue

            answers = session_merged.get(sid, {})

            for q in s.current_block.questions:
                if q.qid in answers:
                    s.run.answers[q.qid] = answers[q.qid]
                    s.answer_history.append((q, answers[q.qid]))

            submission = _gemini_answers_to_qualtrics(s.current_block.questions, answers)
            try:
                next_block = qualtrics.advance_session(survey, s.run.session_id, submission)
            except Exception as e:
                s.run.error = f"{type(e).__name__}: {e}"
                _save_run(out_dir, s.idx, s.run)
                continue

            if next_block.embedded_data:
                s.run.embedded_data.update(next_block.embedded_data)
            if s.run.branch_id is None:
                s.run.branch_id = _detect_branch(survey, next_block)
                s.run.branch_description = _branch_description(survey, s.run.branch_id)
            s.current_block = next_block
            if next_block.done:
                s.run.completed = True
                _save_run(out_dir, s.idx, s.run)
                print(f"  ✓ {s.persona.name}: completed", flush=True)

        # NOTE: we intentionally do NOT save in-progress sessions mid-batch.
        # Doing so creates duplicate `_failed` files that get superseded by
        # `_completed` files later in the run. Crash-recovery for long-running
        # batched sessions is a future feature (see project memory if added).

    completed = sum(1 for s in states if s.run.completed)
    failed = sum(1 for s in states if s.run.error)
    print(f"\nBatched run done. {completed} completed, {failed} failed.", flush=True)
    return [s.run for s in states]


def _detect_branch(survey: SurveyDefinition, block: SessionBlock) -> str | None:
    # First try: the arm contains the question's block directly (simple case).
    for q in block.questions:
        branch_id = survey.branch_for_qid(q.qid)
        if branch_id:
            return branch_id
    # Fallback: the randomizer arms set embedded data (the common Qualtrics
    # pattern where arms are EmbeddedData setters and downstream Branch elements
    # do the actual routing). Match the session's embedded_data against each
    # arm's declared embedded_data signature.
    session_ed = block.embedded_data or {}
    for arm in survey.branches:
        if not arm.embedded_data:
            continue
        if all(str(session_ed.get(k)) == str(v) for k, v in arm.embedded_data.items()):
            return arm.branch_id
    return None


def _branch_description(survey: SurveyDefinition, branch_id: str | None) -> str | None:
    if not branch_id:
        return None
    for b in survey.branches:
        if b.branch_id == branch_id:
            return b.description
    return branch_id


def _gemini_answers_to_qualtrics(
    questions: list[Question],
    answers: dict[str, Any],
) -> dict[str, Any]:
    # Sessions API answer shape (verified by probing the live API; the legacy
    # POST /responses bulk endpoint uses a different format with recode ints
    # and QIDN_choiceN keys — do not reach for that here).
    #   MC:     {qid: {choiceId: {"selected": true}, ...}}
    #   TE:     {qid: "free text"}
    #   Matrix: {qid: {subId: {choiceId: {"selected": true}}}}   (per-row single-select)
    out: dict[str, Any] = {}
    questions_by_qid = {q.qid: q for q in questions}

    for qid, value in answers.items():
        q = questions_by_qid.get(qid)
        if not q:
            continue

        if q.is_multiple_choice:
            if q.allows_multiple_answers and isinstance(value, list):
                out[qid] = {str(cid): {"selected": True} for cid in value}
            else:
                out[qid] = {str(value): {"selected": True}}

        elif q.is_text_entry:
            out[qid] = _extract_number(value) if _looks_numeric(q) else str(value)

        elif q.is_matrix and isinstance(value, dict):
            out[qid] = {
                str(sub_id): {str(choice_id): {"selected": True}}
                for sub_id, choice_id in value.items()
            }

        else:
            out[qid] = value

    return out


def summarize_run(run: SessionRun, survey: SurveyDefinition) -> str:
    status = "completed" if run.completed else f"FAILED ({run.error})"
    lines = [
        f"=== {run.persona.name} ===",
        f"branch: {run.branch_description or '<none / no randomizer>'}",
        f"status: {status}",
        "",
    ]
    for qid, value in run.answers.items():
        q = survey.question(qid)
        if not q:
            continue
        lines.append(f"[{qid}] {q.prompt_text}")
        if q.is_multiple_choice:
            if isinstance(value, list):
                texts = [_choice_text(q, cid) for cid in value]
                lines.append(f"  → {', '.join(texts)}")
            else:
                lines.append(f"  → {_choice_text(q, value)}")
        elif q.is_matrix and isinstance(value, dict):
            for sub_id, choice_id in value.items():
                sub_text = next((s.text for s in q.sub_questions if s.choice_id == sub_id), sub_id)
                lines.append(f"  {sub_text} → {_choice_text(q, choice_id)}")
        else:
            lines.append(f"  → {value}")
        lines.append("")
    return "\n".join(lines)


def _choice_text(q: Question, choice_id: str) -> str:
    c = next((c for c in q.choices if c.choice_id == choice_id), None)
    return c.text if c else f"<unknown:{choice_id}>"
