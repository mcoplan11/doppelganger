"""Bridges the web app to the core qualtrics_ai simulator.

Runs as a background task (FastAPI BackgroundTasks). Updates the Run row
status/error/result_path as it progresses.

The simulator lives at the project root (parent of web/). We import it
directly rather than via subprocess so DB state can be updated live.
"""
import itertools
import json
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

SIMULATOR_ROOT = str(Path(__file__).resolve().parents[2])
if SIMULATOR_ROOT not in sys.path:
    sys.path.insert(0, SIMULATOR_ROOT)

import truststore
truststore.inject_into_ssl()

from sqlalchemy.orm import Session

from crypto import decrypt
from database import CreditBalance, Run, SessionLocal


def _db() -> Session:
    return SessionLocal()


def _is_cancelled(run_id: int) -> bool:
    db = _db()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        return run is not None and run.status == "cancelled"
    finally:
        db.close()


def _set_status(run_id: int, status: str, **kwargs) -> None:
    db = _db()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if run and run.status != "cancelled":
            run.status = status
            run.last_heartbeat_at = datetime.now(timezone.utc)
            for k, v in kwargs.items():
                setattr(run, k, v)
            db.commit()
    finally:
        db.close()


def _touch_heartbeat(run_id: int) -> None:
    """Bump last_heartbeat_at without changing status.

    The stuck-run reaper (main._reap_stuck_runs) treats a stale heartbeat as
    "the process died and orphaned this run." Progress-driven bumps alone are
    too coarse — a single long batch round or session can outlast the reaper
    threshold on a run that's perfectly alive. A steady heartbeat while the
    task is active makes the reaper fire only on genuinely dead processes.

    Only touches active rows so it can never resurrect a terminal state.
    """
    db = _db()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if run and run.status in ("converting", "running"):
            run.last_heartbeat_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


def _deduct_credits(user_id: int, amount: int) -> None:
    db = _db()
    try:
        bal = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        if bal and bal.balance >= amount:
            bal.balance -= amount
            bal.updated_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


def _friendly_error(exc: Exception, datacenter: str) -> str:
    """Translate known infrastructure errors into actionable user guidance.

    Raw API errors like 'probe failed unexpectedly: 404 ... SVY_1.2 NotFound'
    are useless to a non-technical researcher. Catch the ones we've actually
    seen in production and rewrite them with a concrete next step.
    """
    text = str(exc)
    # Transient Qualtrics gateway/internal error during conversion (QHRI_*, 5xx) —
    # distinct from the active-survey cap 404 below. probe_session already retries
    # these, so reaching here means retries were exhausted.
    if "probe failed" in text and any(s in text for s in ("502", "503", "504", "QHRI")):
        return (
            "Qualtrics had a temporary server error while preparing the AI survey "
            "copy (a gateway/internal error on their end). Nothing's wrong with "
            "your setup — wait a couple of minutes and start the run again."
        )
    if "probe failed unexpectedly: 404" in text or "SVY_1.2" in text:
        return (
            "Qualtrics wouldn't let us create the AI survey copy — your account "
            "looks like it's at its active-survey limit. Qualtrics caps how many "
            "surveys can be active at once, and each run needs to activate a fresh "
            "copy (one per AI model).\n\n"
            "How to fix — free up some active surveys:\n"
            f"1. Open https://{datacenter}.qualtrics.com/responses/#/surveys\n"
            "2. Deactivate surveys you're not actively collecting on — this keeps "
            "all of their responses. Old surveys ending in '- AI Copy' from past "
            "runs are good candidates.\n"
            "3. Only delete a survey if you're sure you no longer need its responses "
            "— deactivating is safer.\n"
            "4. Then start a new run here."
        )
    if "503" in text and ("UNAVAILABLE" in text or "overloaded" in text or "high demand" in text):
        return (
            "The AI model's servers are temporarily overloaded (a 503 from "
            "upstream). Nothing's wrong with your setup — wait a few minutes and "
            "try again."
        )
    if "401" in text and "qualtrics" in text.lower():
        return (
            "Qualtrics rejected your API token (401 Unauthorized). "
            "Double-check the token from Qualtrics → Account Settings → "
            "Qualtrics IDs → API Token, and confirm the datacenter matches "
            "(e.g. 'yul1' for yul1.qualtrics.com)."
        )
    # Converter couldn't make the survey AI-compatible (a feature/element we don't
    # auto-handle yet). Give the researcher a self-serve path AND keep the raw
    # detail so support can add a fix. The full traceback is also logged server-side.
    if "incompatib" in text.lower() or "BadSurvey" in text:
        ai_copy = getattr(exc, "ai_survey_id", None)
        lines = [
            "Your survey uses something our converter can't automatically make "
            "AI-compatible yet. We've logged the technical details so we can add "
            "support for it — you can also email them to support@doppelgangerlabs.com.",
        ]
        if ai_copy:
            link = f"https://{datacenter}.qualtrics.com/survey-builder/{ai_copy}/edit"
            lines += [
                "",
                "We kept the partial AI copy in your Qualtrics account so you can "
                "fix it yourself if you'd like:",
                f"  1. Open {link}",
                "  2. Remove or simplify the flagged question(s) / flow element(s) "
                "shown in the details below.",
                "  3. The copy holds no real data — delete it when done, then start "
                "a new run.",
            ]
        lines += ["", f"Technical details (for support): {text[:1500]}"]
        return "\n".join(lines)
    return text[:2000]


def _convert_survey(
    survey_id: str, base_url: str, token: str, copy_label: str | None = None
) -> str:
    """Mirror of convert_to_ai.main() as a callable. Returns the new AI-ready survey ID.

    ``copy_label`` is an anonymized model label ("Model A", …) appended to the
    copy name so a researcher can tell the per-model copies apart in their
    Qualtrics account WITHOUT learning which real LLM produced them.
    """
    from convert_to_ai import (
        ConverterError,
        Qualtrics as Converter,
        convert_matrix_to_mc,
        hard_strip,
        pre_activation_flow_strip,
        pre_activation_strip,
        pre_activation_trash_strip,
        pre_activation_validation_strip,
    )

    client = Converter(base_url, token)
    me = client.whoami()
    owner_id = me["userId"]
    src_name = client.get_survey_name(survey_id)
    copy_name = f"{src_name} - AI Copy [{copy_label}]" if copy_label else f"{src_name} - AI Copy"
    new_id = client.copy_survey(survey_id, copy_name, owner_id)
    try:
        pre_activation_trash_strip(client, new_id)
        convert_matrix_to_mc(client, new_id)
        pre_activation_strip(client, new_id, do_soft=True)
        pre_activation_validation_strip(client, new_id)
        pre_activation_flow_strip(client, new_id)
        client.activate(new_id)
        hard_strip(client, new_id)
        return new_id
    except ConverterError as exc:
        # Keep the partial copy so the researcher can inspect/clean it manually,
        # and attach its id so the error message can link straight to it. (These
        # failures are now rare — the converter auto-handles the common cases —
        # so leftover copies won't pile up the way auto-stripping every run would.)
        exc.ai_survey_id = new_id  # type: ignore[attr-defined]
        raise


def _cleanup_ai_copy(
    ai_survey_id: str | None,
    original_survey_id: str,
    base_url: str,
    token: str,
    run_id: int,
) -> None:
    """Delete the AI survey copy after a total-failure run (0 sessions completed).

    Guards (ALL must pass before deletion fires):
      1. ai_survey_id is not None or empty
      2. ai_survey_id != original_survey_id (never touch the source survey)
      3. Survey name fetched from Qualtrics contains '- AI Copy' (covers both
         the legacy '... - AI Copy' and the per-model '... - AI Copy [Model X]')

    Any failure in this function is caught and logged — it must never affect
    the run's final status or error message.
    """
    try:
        # Guard 1 — must have an AI copy ID
        if not ai_survey_id:
            print(f"[run {run_id}] cleanup skipped: no ai_survey_id", flush=True)
            return

        # Guard 2 — must not be the original survey
        if ai_survey_id == original_survey_id:
            print(
                f"[run {run_id}] cleanup ABORTED: ai_survey_id == original_survey_id "
                f"({ai_survey_id}). This should never happen.",
                flush=True,
            )
            return

        # Guard 3 — fetch the survey name and verify the '- AI Copy' suffix
        from convert_to_ai import Qualtrics as Converter
        client = Converter(base_url, token)
        try:
            name = client.get_survey_name(ai_survey_id)
        except Exception as e:
            print(f"[run {run_id}] cleanup skipped: could not fetch survey name for {ai_survey_id}: {e}", flush=True)
            return

        if "- AI Copy" not in name:
            print(
                f"[run {run_id}] cleanup ABORTED: survey {ai_survey_id} name {name!r} "
                f"does not contain '- AI Copy'. Refusing to delete.",
                flush=True,
            )
            return

        # All guards passed — safe to delete
        print(f"[run {run_id}] deleting failed AI copy {ai_survey_id} ({name!r})...", flush=True)
        client.delete_survey(ai_survey_id)
        print(f"[run {run_id}] AI copy {ai_survey_id} deleted.", flush=True)

    except Exception as e:
        # Deletion failure must never affect the run record
        print(f"[run {run_id}] cleanup error (non-fatal): {e}", flush=True)


def _save_survey_meta(output_dir: Path, survey) -> None:
    """Persist question metadata (labels, choices, recodes) so the results view
    can join saved answers back to human-readable labels after the run."""
    from gemini_client import is_answerable

    questions = []
    for q in survey.questions:
        if not is_answerable(q):
            continue
        questions.append({
            "qid": q.qid,
            "export_tag": q.export_tag,
            "prompt": q.prompt_text,
            "type": q.question_type,
            "multi_select": q.allows_multiple_answers,
            "choices": [
                {"choice_id": c.choice_id, "text": c.text, "recode": c.recode}
                for c in q.choices
            ],
            "sub_questions": [
                {"choice_id": s.choice_id, "text": s.text}
                for s in q.sub_questions
            ],
        })
    (output_dir / "survey_meta.json").write_text(
        json.dumps({"name": survey.name, "questions": questions}, indent=2)
    )


def run_simulation(run_id: int) -> None:
    """Entry point called as a FastAPI background task."""
    db = _db()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return
        user_id = run.user_id
        user_email = run.user.email if run.user else "unknown"
        original_survey_id = run.original_survey_id
        qualtrics_datacenter = run.qualtrics_datacenter
        qualtrics_token = decrypt(run.qualtrics_token_enc)
        n_participants = run.n_participants
        is_smoke = run.is_smoke_test
        started_at = datetime.now(timezone.utc)
    finally:
        db.close()

    # Liveness heartbeat: while this in-process task is alive, bump the run's
    # heartbeat every 60s so the stuck-run reaper doesn't false-positive on a
    # long-but-healthy run. The thread dies with the process, so a redeploy/OOM
    # that orphans the run correctly lets the heartbeat go stale and be reaped.
    stop_heartbeat = threading.Event()

    def _heartbeat_loop() -> None:
        while not stop_heartbeat.wait(60):
            try:
                _touch_heartbeat(run_id)
            except Exception as e:
                print(f"[run {run_id}] heartbeat error (non-fatal): {e}", flush=True)

    heartbeat = threading.Thread(target=_heartbeat_loop, daemon=True)
    heartbeat.start()

    try:
        _run_inner(
            run_id, user_id, user_email, original_survey_id,
            qualtrics_datacenter, qualtrics_token, n_participants, is_smoke,
            started_at,
        )
    except Exception as exc:
        import traceback
        print(
            f"[run {run_id}] simulation FAILED (survey={original_survey_id}):\n"
            f"{traceback.format_exc()}",
            flush=True,
        )
        if _is_cancelled(run_id):
            print(f"[run {run_id}] cancelled — skipping failure notification", flush=True)
            return
        friendly = _friendly_error(exc, qualtrics_datacenter)
        _set_status(
            run_id, "failed",
            error=friendly,
            completed_at=datetime.now(timezone.utc),
        )
        from email_client import send_run_notification
        send_run_notification(
            run_id=run_id,
            user_email=user_email,
            survey_id=original_survey_id,
            ai_survey_id=getattr(exc, "ai_survey_id", None),
            is_smoke=is_smoke,
            status="failed",
            credits_used=0,
            n_participants=n_participants,
            duration_seconds=int((datetime.now(timezone.utc) - started_at).total_seconds()),
            branch_counts={},
            error=friendly,
        )
    finally:
        stop_heartbeat.set()


def _run_inner(
    run_id: int,
    user_id: int,
    user_email: str,
    original_survey_id: str,
    qualtrics_datacenter: str,
    qualtrics_token: str,
    n_participants: int,
    is_smoke: bool,
    started_at: datetime,
) -> None:
    """Run the survey through every model in the ensemble.

    Same persona panel, one Qualtrics copy per model, results surfaced per
    model. Models are anonymized to the researcher (Model A/B/C); real model
    identities stay server-side (see ensemble.py). A single model failing
    (conversion or run) does not fail the whole run — it's recorded and the
    others proceed; the run is "done" as long as at least one model produced
    responses.
    """
    from ensemble import build_client, roster_for, use_batch_for
    from personas import DEFAULT_PERSONAS
    from qualtrics_client import QualtricsClient
    from simulator import run_many

    base_url = f"https://{qualtrics_datacenter}.qualtrics.com/API/v3"
    roster = roster_for(is_smoke)
    n_models = len(roster)

    persona_pool = list(itertools.islice(itertools.cycle(DEFAULT_PERSONAS), n_participants))
    output_base = Path(SIMULATOR_ROOT) / "responses" / f"web_run_{run_id}"
    output_base.mkdir(parents=True, exist_ok=True)

    _set_status(run_id, "converting")

    # Live progress across the whole ensemble. The models now run in parallel,
    # so each reports its own cumulative completed count and we sum the latest
    # value per model (under a lock) to keep the "X of N completed" bar honest.
    state_lock = threading.Lock()
    ai_survey_ids: dict[str, dict[str, str]] = {}   # slug -> {label, ai_survey_id}
    primary_ai_survey_id: str | None = None
    model_progress: dict[str, int] = {}             # slug -> latest cumulative completed

    def _register_copy(slug: str, label: str, ai_id: str) -> None:
        """Record a model's AI copy and surface it to the frontend immediately."""
        nonlocal primary_ai_survey_id
        with state_lock:
            ai_survey_ids[slug] = {"label": label, "ai_survey_id": ai_id}
            if primary_ai_survey_id is None:
                primary_ai_survey_id = ai_id
            _set_status(
                run_id, "running",
                ai_survey_id=primary_ai_survey_id,
                ai_survey_ids=json.dumps(ai_survey_ids),
            )

    def _report_progress(slug: str, done: int) -> None:
        with state_lock:
            model_progress[slug] = done
            overall = sum(model_progress.values())
            _set_status(run_id, "running",
                        credits_used=min(n_participants, overall // n_models))

    def _run_one_model(spec) -> dict:
        """Convert + run one model. Never raises: a single model's failure is
        captured and returned so the other models (and the run) survive it."""
        ai_survey_id: str | None = None
        survey_name: str | None = None
        try:
            model_dir = output_base / spec.slug
            model_dir.mkdir(parents=True, exist_ok=True)
            copy_label = None if is_smoke else spec.label
            ai_survey_id = _convert_survey(
                original_survey_id, base_url, qualtrics_token, copy_label
            )
            _register_copy(spec.slug, spec.label, ai_survey_id)

            qualtrics = QualtricsClient(base_url, qualtrics_token)
            survey = qualtrics.get_survey_definition(ai_survey_id)
            survey_name = getattr(survey, "name", None)
            _save_survey_meta(model_dir, survey)
            client = build_client(spec, temperature=0.5)

            runs = run_many(
                qualtrics=qualtrics,
                gemini=client,
                survey=survey,
                personas=persona_pool,
                runs_per_persona=1,
                out_dir=model_dir,
                use_batch=use_batch_for(spec, is_smoke),
                on_progress=lambda done, _slug=spec.slug: _report_progress(_slug, done),
                max_pending_seconds=30 * 60 if is_smoke else 10 * 60,
                is_cancelled=lambda: _is_cancelled(run_id),
            )
        except Exception as exc:
            import traceback
            print(f"[run {run_id}] model {spec.label} ({spec.model}) FAILED:\n"
                  f"{traceback.format_exc()}", flush=True)
            # _convert_survey attaches the partial copy id to the exception when
            # it fails mid-conversion (after copy_survey, before returning), so
            # the local ai_survey_id is still None here. Recover it so we clean
            # up and report the copy instead of leaking an orphan in the account.
            if ai_survey_id is None:
                ai_survey_id = getattr(exc, "ai_survey_id", None)
            _cleanup_ai_copy(ai_survey_id, original_survey_id, base_url, qualtrics_token, run_id)
            return {
                "label": spec.label, "slug": spec.slug, "model": spec.model,
                "ai_survey_id": ai_survey_id, "n_completed": 0, "failed": 0,
                "results_error": _friendly_error(exc, qualtrics_datacenter),
                "notify_error": str(exc)[:500],
                "results": {"available": False, "questions": []},
                "branch_counts": {}, "survey_name": survey_name,
            }

        completed = [r for r in runs if r.completed]
        failed = len(runs) - len(completed)
        branch_counts = Counter(r.branch_description or "unknown" for r in completed)

        model_error = None
        if failed:
            samples = [f"[{r.persona.name}] {r.error}"
                       for r in runs if not r.completed and r.error][:3]
            model_error = f"{failed}/{len(runs)} sessions failed. " + (
                " | ".join(samples) if samples else "no error detail captured")

        try:
            from results import build_results
            per_model_results = build_results(model_dir)
        except Exception as e:
            print(f"[run {run_id}] {spec.label} results build failed (non-fatal): {e}", flush=True)
            per_model_results = {"available": False, "questions": []}

        # A model that produced nothing has an empty copy — remove it.
        if not completed:
            _cleanup_ai_copy(ai_survey_id, original_survey_id, base_url, qualtrics_token, run_id)

        return {
            "label": spec.label, "slug": spec.slug, "model": spec.model,
            "ai_survey_id": ai_survey_id, "n_completed": len(completed), "failed": failed,
            "results_error": model_error, "notify_error": model_error,
            "results": per_model_results,
            "branch_counts": dict(branch_counts) if completed else {},
            "survey_name": survey_name,
        }

    if _is_cancelled(run_id):
        print(f"[run {run_id}] cancelled — stopping before model runs", flush=True)
        return

    # Run every model concurrently — they're fully independent (own Qualtrics
    # copy, own client), so total wall-clock ≈ the slowest single model rather
    # than the sum of all three. pool.map preserves roster order, so Model A/B/C
    # labels stay stable regardless of which model finishes first.
    with ThreadPoolExecutor(max_workers=n_models) as pool:
        model_outcomes = list(pool.map(_run_one_model, roster))

    if _is_cancelled(run_id):
        print(f"[run {run_id}] cancelled — skipping credit deduction and notification", flush=True)
        return

    model_results = [
        {"label": r["label"], "slug": r["slug"], "ai_survey_id": r["ai_survey_id"],
         "n_completed": r["n_completed"], "failed": r["failed"],
         "error": r["results_error"], "results": r["results"]}
        for r in model_outcomes
    ]
    model_notify = [
        {"label": r["label"], "model": r["model"], "ai_survey_id": r["ai_survey_id"],
         "n_completed": r["n_completed"], "failed": r["failed"], "error": r["notify_error"]}
        for r in model_outcomes
    ]
    representative_branches = next(
        (r["branch_counts"] for r in model_outcomes
         if r["n_completed"] > 0 and r["branch_counts"]), None
    )
    run_survey_name = next(
        (r["survey_name"] for r in model_outcomes if r["survey_name"]), None
    )

    total_completed = sum(m["n_completed"] for m in model_results)
    final_status = "done" if total_completed > 0 else "failed"

    # Credits: one charge per persona for the whole ensemble run, regardless of
    # how many models it fans out to (the 3× model cost is absorbed).
    credits_charged = n_participants if (final_status == "done" and not is_smoke) else 0
    if credits_charged:
        _deduct_credits(user_id, credits_charged)

    result_index_path = str(output_base / "index.json")
    with open(result_index_path, "w") as f:
        json.dump({
            "run_id": run_id,
            "ensemble": True,
            "total_completed": total_completed,
            "models": [
                {k: m[k] for k in ("label", "slug", "ai_survey_id", "n_completed", "failed")}
                for m in model_results
            ],
        }, f, indent=2)

    results_json_str: str | None = None
    if final_status == "done":
        results_payload = {
            "ensemble": True,
            "n_completed": total_completed,
            "models": [
                {
                    "label": m["label"], "slug": m["slug"],
                    "ai_survey_id": m["ai_survey_id"],
                    "n_completed": m["n_completed"], "failed": m["failed"],
                    "error": m["error"], "results": m["results"],
                }
                for m in model_results
            ],
        }
        # AI results-interpreter: an in-production model decision that reads the
        # anonymized distributions and flags pretest issues. Best-effort — never
        # let it block completion or credit deduction.
        try:
            from interpreter import generate_interpretation
            interp = generate_interpretation(
                run_survey_name, n_participants, results_payload["models"]
            )
            if interp:
                results_payload["interpretation"] = interp
                print(f"[run {run_id}] AI interpretation attached.", flush=True)
        except Exception as e:
            print(f"[run {run_id}] interpretation failed (non-fatal): {e}", flush=True)
        results_json_str = json.dumps(results_payload)

    # Run-level error summary: only surface if the whole run failed, or a model
    # was completely lost. Per-session failures live in each model's block.
    error_msg = None
    lost = [m["label"] for m in model_results if m["n_completed"] == 0]
    if final_status == "failed":
        first = next((m["error"] for m in model_results if m["error"]), None)
        error_msg = first or "No model produced any responses."
    elif lost:
        error_msg = f"{len(lost)} of {len(roster)} models produced no data: {', '.join(lost)}."

    _set_status(
        run_id, final_status,
        credits_used=credits_charged if not is_smoke else 0,
        result_path=result_index_path,
        branch_summary=json.dumps(representative_branches or {}),
        ai_survey_ids=json.dumps(ai_survey_ids),
        completed_at=datetime.now(timezone.utc),
        error=error_msg,
        results_json=results_json_str,
    )

    from email_client import send_run_notification
    send_run_notification(
        run_id=run_id,
        user_email=user_email,
        survey_id=original_survey_id,
        ai_survey_id=primary_ai_survey_id,
        is_smoke=is_smoke,
        status=final_status,
        credits_used=credits_charged,
        n_participants=n_participants,
        duration_seconds=int((datetime.now(timezone.utc) - started_at).total_seconds()),
        branch_counts=representative_branches or {},
        error=error_msg,
        models=model_notify,
    )
