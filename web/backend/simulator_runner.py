"""Bridges the web app to the core qualtrics_ai simulator.

Runs as a background task (FastAPI BackgroundTasks). Updates the Run row
status/error/result_path as it progresses.

The simulator lives at /path/to/qualtrics_ai/ (parent of this web/ dir).
We import it directly rather than subprocess so we share the same process
and can update DB state live.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add the simulator root to sys.path so we can import its modules
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


def run_simulation(run_id: int) -> None:
    """Entry point called as a background task."""
    db = _db()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return
        run_id = run.id
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
        _set_status(run_id, "failed", error=str(exc)[:2000],
                    completed_at=datetime.now(timezone.utc))


def _run_inner(
    run_id: int,
    user_id: int,
    original_survey_id: str,
    qualtrics_datacenter: str,
    qualtrics_token: str,
    n_participants: int,
    is_smoke: bool,
) -> None:
    from convert_to_ai import convert_survey
    from personas import load_personas
    from simulator import run_many

    base_url = f"https://{qualtrics_datacenter}.qualtrics.com"

    # ── Step 1: Convert survey ────────────────────────────────────────────────
    _set_status(run_id, "converting")
    ai_survey_id = convert_survey(
        survey_id=original_survey_id,
        base_url=base_url,
        token=qualtrics_token,
    )
    _set_status(run_id, "running", ai_survey_id=ai_survey_id)

    # ── Step 2: Load personas ─────────────────────────────────────────────────
    personas_path = Path(SIMULATOR_ROOT) / "responses" / "generated_personas.json"
    all_personas = load_personas(str(personas_path))

    # Slice to requested count (cycle if more requested than available)
    import itertools
    persona_pool = list(itertools.islice(itertools.cycle(all_personas), n_participants))

    # ── Step 3: Run simulation ────────────────────────────────────────────────
    output_dir = Path(SIMULATOR_ROOT) / "responses" / f"web_run_{run_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = run_many(
        survey_id=ai_survey_id,
        base_url=base_url,
        token=qualtrics_token,
        gemini_api_key=settings.gemini_api_key,
        gemini_model=settings.gemini_model,
        personas=persona_pool,
        output_dir=str(output_dir),
        batch_threshold=20,
    )

    # ── Step 4: Summarise and persist ─────────────────────────────────────────
    completed = [r for r in results if r.get("completed")]
    failed_count = len(results) - len(completed)
    credits_used = len(completed)

    # Branch distribution
    from collections import Counter
    branch_counts = Counter(r.get("branch_description", "unknown") for r in completed)

    result_index_path = str(output_dir / "index.json")
    with open(result_index_path, "w") as f:
        json.dump({
            "run_id": run_id,
            "completed": credits_used,
            "failed": failed_count,
            "branch_distribution": dict(branch_counts),
        }, f, indent=2)

    # Deduct credits only for successful participants
    if credits_used > 0 and not is_smoke:
        _deduct_credits(user_id, credits_used)

    status = "done" if failed_count == 0 else ("done" if credits_used > 0 else "failed")
    _set_status(
        run_id, status,
        credits_used=credits_used,
        result_path=result_index_path,
        branch_summary=json.dumps(dict(branch_counts)),
        completed_at=datetime.now(timezone.utc),
        error=f"{failed_count} sessions failed" if failed_count else None,
    )
