"""Bridges the web app to the core qualtrics_ai simulator.

Runs as a background task (FastAPI BackgroundTasks). Updates the Run row
status/error/result_path as it progresses.

The simulator lives at the project root (parent of web/). We import it
directly rather than via subprocess so DB state can be updated live.
"""
import itertools
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SIMULATOR_ROOT = str(Path(__file__).resolve().parents[2])
if SIMULATOR_ROOT not in sys.path:
    sys.path.insert(0, SIMULATOR_ROOT)

import truststore
truststore.inject_into_ssl()

from sqlalchemy.orm import Session

from app_config import settings
from crypto import decrypt
from database import CreditBalance, Run, SessionLocal


def _db() -> Session:
    return SessionLocal()


def _set_status(run_id: int, status: str, **kwargs) -> None:
    db = _db()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if run:
            run.status = status
            for k, v in kwargs.items():
                setattr(run, k, v)
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


def _convert_survey(survey_id: str, base_url: str, token: str) -> str:
    """Mirror of convert_to_ai.main() as a callable. Returns the new AI-ready survey ID."""
    from convert_to_ai import (
        ConverterError,
        Qualtrics as Converter,
        hard_strip,
        pre_activation_strip,
    )

    client = Converter(base_url, token)
    me = client.whoami()
    owner_id = me["userId"]
    src_name = client.get_survey_name(survey_id)
    new_id = client.copy_survey(survey_id, f"{src_name} - AI Copy", owner_id)
    try:
        pre_activation_strip(client, new_id, do_soft=True)
        client.activate(new_id)
        hard_strip(client, new_id)
        return new_id
    except ConverterError:
        try:
            client.delete_survey(new_id)
        except Exception:
            pass
        raise


def run_simulation(run_id: int) -> None:
    """Entry point called as a FastAPI background task."""
    db = _db()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return
        user_id = run.user_id
        original_survey_id = run.original_survey_id
        qualtrics_datacenter = run.qualtrics_datacenter
        qualtrics_token = decrypt(run.qualtrics_token_enc)
        n_participants = run.n_participants
        is_smoke = run.is_smoke_test
    finally:
        db.close()

    try:
        _run_inner(
            run_id, user_id, original_survey_id,
            qualtrics_datacenter, qualtrics_token, n_participants, is_smoke,
        )
    except Exception as exc:
        _set_status(
            run_id, "failed",
            error=str(exc)[:2000],
            completed_at=datetime.now(timezone.utc),
        )


def _run_inner(
    run_id: int,
    user_id: int,
    original_survey_id: str,
    qualtrics_datacenter: str,
    qualtrics_token: str,
    n_participants: int,
    is_smoke: bool,
) -> None:
    from gemini_client import GeminiClient
    from personas import DEFAULT_PERSONAS
    from qualtrics_client import QualtricsClient
    from simulator import run_many

    base_url = f"https://{qualtrics_datacenter}.qualtrics.com/API/v3"

    _set_status(run_id, "converting")
    ai_survey_id = _convert_survey(original_survey_id, base_url, qualtrics_token)

    _set_status(run_id, "running", ai_survey_id=ai_survey_id)
    qualtrics = QualtricsClient(base_url, qualtrics_token)
    gemini = GeminiClient(settings.gemini_api_key, settings.gemini_model, temperature=0.5)
    survey = qualtrics.get_survey_definition(ai_survey_id)

    persona_pool = list(itertools.islice(itertools.cycle(DEFAULT_PERSONAS), n_participants))

    output_dir = Path(SIMULATOR_ROOT) / "responses" / f"web_run_{run_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Smoke tests force sync mode for fast feedback; real runs let run_many auto-pick.
    use_batch = False if is_smoke else None

    runs = run_many(
        qualtrics=qualtrics,
        gemini=gemini,
        survey=survey,
        personas=persona_pool,
        runs_per_persona=1,
        out_dir=output_dir,
        use_batch=use_batch,
    )

    completed = [r for r in runs if r.completed]
    failed_count = len(runs) - len(completed)
    credits_used = len(completed)
    branch_counts = Counter(r.branch_description or "unknown" for r in completed)

    result_index_path = str(output_dir / "index.json")
    with open(result_index_path, "w") as f:
        json.dump({
            "run_id": run_id,
            "completed": credits_used,
            "failed": failed_count,
            "branch_distribution": dict(branch_counts),
        }, f, indent=2)

    if credits_used > 0 and not is_smoke:
        _deduct_credits(user_id, credits_used)

    # When sessions fail, surface the actual per-session errors so the
    # dashboard shows something diagnosable instead of just a count.
    error_msg = None
    if failed_count:
        sample_errors = [
            f"[{r.persona.name}] {r.error}"
            for r in runs if not r.completed and r.error
        ][:3]
        error_msg = f"{failed_count}/{len(runs)} sessions failed. " + (
            " | ".join(sample_errors) if sample_errors else "no error detail captured"
        )

    final_status = "done" if credits_used > 0 else "failed"
    _set_status(
        run_id, final_status,
        credits_used=credits_used,
        result_path=result_index_path,
        branch_summary=json.dumps(dict(branch_counts)),
        completed_at=datetime.now(timezone.utc),
        error=error_msg,
    )
