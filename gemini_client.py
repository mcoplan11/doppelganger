from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from personas import Persona
from qualtrics_client import Question


@dataclass
class BatchInput:
    """One persona's block worth of work for a batch round.

    `answerable` is the filtered list of questions that need a Gemini response.
    `key` is an opaque identifier the caller uses to correlate results back to
    state (e.g. session_id). `empty_response_if_no_answerable` is what to return
    if the block has no answerable questions (typically all-DB blocks)."""
    key: str
    persona: Persona
    answerable: list[Question]
    prior_answers: list[tuple[Question, Any]]
    read_context: list[Question]
    survey_name: str = ""


class GeminiClient:
    def __init__(self, api_key: str, model: str, temperature: float = 0.5):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._temperature = temperature

    def answer_block(
        self,
        persona: Persona,
        questions: list[Question],
        prior_answers: list[tuple[Question, Any]],
        read_context: list[Question] | None = None,
        survey_name: str = "",
    ) -> dict[str, Any]:
        answerable = [q for q in questions if _is_answerable(q)]
        if not answerable:
            return {}

        schema = _build_response_schema(answerable)
        prompt = _build_prompt(
            persona, answerable, prior_answers, read_context or [], survey_name
        )

        resp = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=self._temperature,
            ),
        )
        return json.loads(resp.text)

    # Gemini Batch API drops responses at high request counts — empirically
    # reliable up to ~50 items per job. Larger rounds are split into chunks.
    MAX_BATCH_CHUNK = 50

    def answer_blocks_batch(
        self,
        inputs: list[BatchInput],
        *,
        poll_interval_seconds: int = 30,
        max_wait_seconds: int = 2 * 3600,
        max_pending_seconds: int = 30 * 60,
        on_progress=None,
    ) -> dict[str, dict[str, Any] | None]:
        """Submit a batch of block-answers to Gemini Batch API; wait for completion.

        Returns {key: answers_dict or None on failure}. Keys with no answerable
        questions are returned with an empty dict immediately (no API call).
        Large rounds are automatically split into MAX_BATCH_CHUNK-sized jobs.
        """
        results: dict[str, dict[str, Any] | None] = {}

        # Separate inputs into those needing API calls vs trivially empty ones
        to_send: list[BatchInput] = []
        for inp in inputs:
            if not inp.answerable:
                results[inp.key] = {}
            else:
                to_send.append(inp)

        if not to_send:
            return results

        # Split into chunks to avoid Gemini dropping responses on large jobs.
        chunks = [
            to_send[i: i + self.MAX_BATCH_CHUNK]
            for i in range(0, len(to_send), self.MAX_BATCH_CHUNK)
        ]
        for chunk_idx, chunk in enumerate(chunks):
            chunk_label = (f"chunk {chunk_idx + 1}/{len(chunks)} "
                           if len(chunks) > 1 else "")
            results.update(self._submit_chunk(
                chunk, chunk_label, poll_interval_seconds,
                max_wait_seconds, max_pending_seconds, on_progress,
            ))
        return results

    def _submit_chunk(
        self,
        to_send: list[BatchInput],
        label: str,
        poll_interval_seconds: int,
        max_wait_seconds: int,
        max_pending_seconds: int,
        on_progress,
    ) -> dict[str, dict[str, Any] | None]:
        results: dict[str, dict[str, Any] | None] = {}
        inline_requests = [_build_inline_request(inp, self._temperature) for inp in to_send]

        last_exc: Exception | None = None
        for attempt in range(4):
            if attempt:
                wait = min(60, 10 * 2 ** (attempt - 1))
                print(f"  503 on batch create, retrying in {wait}s (attempt {attempt + 1}/4)...",
                      flush=True)
                time.sleep(wait)
            try:
                job = self._client.batches.create(
                    model=self._model,
                    src=inline_requests,
                    config={"display_name": f"sim-batch-{int(time.time())}"},
                )
                break
            except Exception as exc:
                msg = str(exc)
                if "503" in msg or "UNAVAILABLE" in msg:
                    last_exc = exc
                    continue
                raise
        else:
            raise last_exc  # type: ignore[misc]
        job_name = job.name
        if on_progress:
            on_progress(f"submitted {label}batch {job_name} with {len(to_send)} requests")

        terminal = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED",
                    "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
        # A job stuck in PENDING for too long has been dropped by Gemini's queue.
        # Trial runs use 30 min (fast failure feedback); full runs allow 60 min
        # since the model may be under demand and the stakes are higher.
        MAX_PENDING_SECONDS = max_pending_seconds
        start = time.time()
        pending_since: float | None = None
        while True:
            job = self._client.batches.get(name=job_name)
            state = job.state.name
            if state in terminal:
                break
            elapsed = time.time() - start
            if elapsed > max_wait_seconds:
                raise RuntimeError(
                    f"batch {job_name} exceeded max_wait_seconds={max_wait_seconds}"
                )
            if state == "JOB_STATE_PENDING":
                if pending_since is None:
                    pending_since = time.time()
                elif time.time() - pending_since > MAX_PENDING_SECONDS:
                    raise RuntimeError(
                        f"batch {job_name} stuck in PENDING for >{MAX_PENDING_SECONDS//60} min "
                        f"— Gemini queue appears stalled. Try again later."
                    )
            else:
                pending_since = None  # reset if it transitions out of pending
            if on_progress:
                on_progress(f"batch {job_name} state={state}, waiting...")
            time.sleep(poll_interval_seconds)

        if job.state.name != "JOB_STATE_SUCCEEDED":
            err = getattr(job, "error", None)
            raise RuntimeError(f"batch {job_name} ended in {job.state.name}: {err}")

        # Map responses back. Inline responses come back in submitted order.
        inline_responses = job.dest.inlined_responses or []
        if len(inline_responses) != len(to_send):
            raise RuntimeError(
                f"batch returned {len(inline_responses)} responses for {len(to_send)} requests"
            )
        for inp, inline_response in zip(to_send, inline_responses):
            if inline_response.response is None:
                results[inp.key] = None
                continue
            try:
                text = inline_response.response.text
                results[inp.key] = json.loads(text)
            except Exception:
                results[inp.key] = None
        return results


def _build_inline_request(inp: BatchInput, temperature: float) -> dict:
    schema = _build_response_schema(inp.answerable)
    prompt = _build_prompt(
        inp.persona, inp.answerable, inp.prior_answers, inp.read_context, inp.survey_name
    )
    return {
        "contents": [{"parts": [{"text": prompt}], "role": "user"}],
        "config": {
            "response_mime_type": "application/json",
            "response_schema": schema,
            "temperature": temperature,
        },
    }


def is_answerable(q: Question) -> bool:
    return _is_answerable(q)


def _is_answerable(q: Question) -> bool:
    if q.question_type in {"DB", "Timing", "Meta", "PGR", "SS"}:
        return False
    return bool(q.prompt_text)


def _build_prompt(
    persona: Persona,
    questions: list[Question],
    prior_answers: list[tuple[Question, Any]],
    read_context: list[Question],
    survey_name: str,
) -> str:
    lines = [
        "You are responding to a Qualtrics survey, staying fully in character as this persona:",
        "",
        f"PERSONA: {persona.name}",
        persona.description,
        "",
        "Answer as this persona would — with their biases, blind spots, and rhythm. "
        "Do not be artificially neutral or balanced.",
        "",
    ]
    if survey_name:
        lines.append(f"SURVEY: {survey_name}")
        lines.append("")

    if read_context:
        lines.append(
            "WHAT YOU'VE READ SO FAR (instructions and scenario shown to you in this order — "
            "no response required, but treat them as the situation you are now responding to):"
        )
        for i, q in enumerate(read_context, 1):
            lines.append(f"  ({i}) {q.prompt_text}")
        lines.append("")

    if prior_answers:
        lines.append("YOUR ANSWERS SO FAR (stay consistent with these):")
        for q, value in prior_answers:
            lines.append(f"  [{q.qid}] {q.prompt_text}")
            lines.append(f"    → {_format_answer_for_recap(q, value)}")
        lines.append("")

    lines.append("NEW QUESTIONS — answer each:")
    for q in questions:
        lines.append("")
        lines.append(f"[{q.qid}] ({q.question_type}/{q.selector}) {q.prompt_text}")
        if q.is_multiple_choice:
            for c in q.choices:
                lines.append(f"  - choice_id={c.choice_id} (recode={c.recode}): {c.text}")
            if q.allows_multiple_answers:
                lines.append("  (select one or more)")
            else:
                lines.append("  (select exactly one)")
        elif q.is_matrix:
            lines.append("  Rate each row on the scale below:")
            for s in q.sub_questions:
                lines.append(f"    row sub_id={s.choice_id}: {s.text}")
            for c in q.choices:
                lines.append(f"    scale choice_id={c.choice_id} (recode={c.recode}): {c.text}")

    lines.append("")
    lines.append("Return only JSON matching the provided schema.")
    return "\n".join(lines)


def _format_answer_for_recap(q: Question, value: Any) -> str:
    if q.is_multiple_choice:
        if isinstance(value, list):
            return ", ".join(_choice_text(q, cid) for cid in value)
        return _choice_text(q, value)
    if q.is_matrix and isinstance(value, dict):
        parts = []
        for sub_id, choice_id in value.items():
            sub_text = next((s.text for s in q.sub_questions if s.choice_id == sub_id), sub_id)
            parts.append(f"{sub_text}={_choice_text(q, choice_id)}")
        return "; ".join(parts)
    return str(value)


def _choice_text(q: Question, choice_id: str) -> str:
    c = next((c for c in q.choices if c.choice_id == choice_id), None)
    return c.text if c else f"<unknown:{choice_id}>"


def _build_response_schema(questions: list[Question]) -> dict[str, Any]:
    props: dict[str, Any] = {}
    required: list[str] = []
    for q in questions:
        props[q.qid] = _schema_for_question(q)
        required.append(q.qid)
    return {
        "type": "object",
        "properties": props,
        "required": required,
    }


def _schema_for_question(q: Question) -> dict[str, Any]:
    if q.is_multiple_choice:
        valid_ids = [c.choice_id for c in q.choices]
        if q.allows_multiple_answers:
            return {
                "type": "array",
                "items": {"type": "string", "enum": valid_ids},
            }
        return {"type": "string", "enum": valid_ids}
    if q.is_text_entry:
        return {"type": "string"}
    if q.is_matrix:
        sub_props = {}
        valid_ids = [c.choice_id for c in q.choices]
        for s in q.sub_questions:
            sub_props[s.choice_id] = {"type": "string", "enum": valid_ids}
        return {
            "type": "object",
            "properties": sub_props,
            "required": list(sub_props.keys()),
        }
    return {"type": "string"}
