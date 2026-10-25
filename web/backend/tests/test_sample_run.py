"""Tests for the pre-seeded sample run (sample_run.py + its API surface).

Uses an in-memory DB — asserts the seeded row is a completed, zero-credit
ensemble run whose stored payloads round-trip through the /runs endpoints in
the exact shapes the frontend consumes (EnsembleResults, RespondentData, CSV).
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m  # noqa: E402
from auth import get_current_user
from database import Base, CreditBalance, Run, User, get_db
from sample_run import MODELS, SAMPLE_SURVEY_LABEL, backfill_sample_runs, create_sample_run


@pytest.fixture
def ctx():
    """In-memory DB with one user + seeded sample run. Yields (client, db, user)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    user = User(email="new-user@example.com")
    db.add(user)
    db.flush()
    db.add(CreditBalance(user_id=user.id, balance=200))
    db.commit()
    create_sample_run(db, user.id)

    def override_db():
        yield db

    m.app.dependency_overrides[get_db] = override_db
    m.app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(m.app)
    try:
        yield client, db, user
    finally:
        m.app.dependency_overrides.clear()
        db.close()


def test_sample_run_listed_as_done_and_free(ctx):
    client, _, _ = ctx
    runs = client.get("/runs").json()
    assert len(runs) == 1
    run = runs[0]
    assert run["is_sample"] is True
    assert run["status"] == "done"
    assert run["credits_used"] == 0
    assert run["original_survey_id"] == SAMPLE_SURVEY_LABEL
    assert sum(run["branch_distribution"].values()) == run["n_participants"]


def test_sample_results_match_ensemble_shape(ctx):
    client, _, _ = ctx
    run_id = client.get("/runs").json()[0]["id"]
    results = client.get(f"/runs/{run_id}/results").json()

    assert results["ensemble"] is True
    assert [m_["label"] for m_ in results["models"]] == [label for _, label in MODELS]
    for model in results["models"]:
        r = model["results"]
        assert r["available"] is True
        assert r["has_conditions"] is True
        assert len(r["conditions"]) == 2
        for q in r["questions"]:
            assert q["overall"]["n"] == model["n_completed"]
            if q["overall"]["kind"] == "choice" and q["overall"]["mean"] is not None:
                # Per-condition means must be derivable from the same scale.
                for cond in q["by_condition"]:
                    assert 1 <= cond["mean"] <= 7
    assert results["interpretation"]["headline"]


def test_sample_responses_feed_the_grids(ctx):
    client, _, _ = ctx
    run_id = client.get("/runs").json()[0]["id"]
    data = client.get(f"/runs/{run_id}/responses").json()

    assert data["available"] is True
    assert data["columns"][:3] == ["model", "persona", "branch"]
    # 3 models × 12 personas, every row fully answered.
    assert len(data["rows"]) == 36
    assert {r["model"] for r in data["rows"]} == {label for _, label in MODELS}
    for row in data["rows"]:
        for col in data["columns"]:
            assert row[col] not in (None, "")

    csv_resp = client.get(f"/runs/{run_id}/download")
    assert csv_resp.status_code == 200
    assert len(csv_resp.text.strip().splitlines()) == 37  # header + 36 rows


def test_backfill_seeds_only_users_without_a_sample(ctx):
    _, db, seeded_user = ctx
    # Two pre-existing accounts from before the feature: one with a real run,
    # one with nothing. Neither has a sample run.
    old_with_run = User(email="old-with-run@example.com")
    old_empty = User(email="old-empty@example.com")
    db.add_all([old_with_run, old_empty])
    db.flush()
    db.add(Run(
        user_id=old_with_run.id,
        original_survey_id="SV_real123",
        qualtrics_datacenter="yul1",
        qualtrics_token_enc="enc",
        n_participants=5,
        status="done",
    ))
    db.commit()

    assert backfill_sample_runs(db) == 2
    for user in (seeded_user, old_with_run, old_empty):
        samples = db.query(Run).filter(
            Run.user_id == user.id, Run.is_sample.is_(True)
        ).count()
        assert samples == 1

    # Idempotent: a second boot seeds nothing.
    assert backfill_sample_runs(db) == 0
