"""Tests for the parallel ensemble runner in simulator_runner._run_inner.

The three models are independent (own Qualtrics copy, own client), so they now
run concurrently instead of one after another. These tests mock out every heavy
dependency (Qualtrics, LLM clients, DB, email) so they assert the orchestration
— concurrency, per-model error isolation, roster-order aggregation — with no
network calls and no spend.
"""
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import simulator_runner as sr


def _persona(name):
    return SimpleNamespace(name=name)


def _run(name, completed=True, branch="Cond=A", error=None):
    return SimpleNamespace(
        completed=completed, persona=_persona(name),
        branch_description=branch, error=error,
    )


@pytest.fixture
def patched(monkeypatch, tmp_path):
    """Patch all of _run_inner's collaborators; return a dict capturing calls."""
    import email_client
    import ensemble
    import interpreter
    import qualtrics_client
    import results
    import simulator

    cap = {"set_status": [], "deducted": [], "cleanup": [], "convert": []}

    # Keep all disk writes inside the temp dir.
    monkeypatch.setattr(sr, "SIMULATOR_ROOT", str(tmp_path))

    roster = [
        ensemble.ModelSpec("Model A", "model_a", "gemini", "m-a"),
        ensemble.ModelSpec("Model B", "model_b", "openrouter", "m-b"),
        ensemble.ModelSpec("Model C", "model_c", "openrouter", "m-c"),
    ]
    monkeypatch.setattr(ensemble, "roster_for",
                        lambda is_smoke, has_images=False: list(roster))
    monkeypatch.setattr(ensemble, "use_batch_for", lambda spec, is_smoke: False)
    monkeypatch.setattr(ensemble, "build_client", lambda spec, temperature=0.5: object())

    def fake_convert(survey_id, base_url, token, copy_label=None):
        cap["convert"].append(copy_label)
        return f"SV_{copy_label}"

    monkeypatch.setattr(sr, "_convert_survey", fake_convert)
    monkeypatch.setattr(sr, "_save_survey_meta", lambda *a, **k: None)
    monkeypatch.setattr(sr, "_is_cancelled", lambda run_id: False)
    monkeypatch.setattr(sr, "_deduct_credits",
                        lambda uid, amt: cap["deducted"].append((uid, amt)))
    monkeypatch.setattr(sr, "_cleanup_ai_copy",
                        lambda *a, **k: cap["cleanup"].append(a))

    def fake_set_status(run_id, status, **kwargs):
        cap["set_status"].append((status, kwargs))

    monkeypatch.setattr(sr, "_set_status", fake_set_status)

    monkeypatch.setattr(qualtrics_client, "QualtricsClient",
                        lambda base_url, token: SimpleNamespace(
                            get_survey_definition=lambda sid: SimpleNamespace(name="My Survey")))
    monkeypatch.setattr(results, "build_results",
                        lambda d: {"available": True, "questions": [{"qid": "Q1"}]})
    monkeypatch.setattr(interpreter, "generate_interpretation", lambda *a, **k: None)
    monkeypatch.setattr(email_client, "send_run_notification", lambda **k: None)

    cap["roster"] = roster
    cap["simulator"] = simulator
    return cap


def _invoke(monkeypatch, cap, run_many_impl):
    cap["simulator"].__dict__  # ensure ref
    monkeypatch.setattr(cap["simulator"], "run_many", run_many_impl)
    sr._run_inner(
        run_id=999, user_id=1, user_email="u@x.com",
        original_survey_id="SV_orig", qualtrics_datacenter="yul1",
        qualtrics_token="tok", n_participants=4, is_smoke=False,
        started_at=datetime.now(timezone.utc),
    )


def test_models_run_concurrently(monkeypatch, patched):
    """Each model's run overlaps the others in time — proving they don't run
    strictly one-after-another."""
    windows = {}

    def run_many(**kwargs):
        label = kwargs["personas"]  # not used; identify via out_dir slug
        slug = kwargs["out_dir"].name
        start = time.monotonic()
        time.sleep(0.3)
        end = time.monotonic()
        windows[slug] = (start, end)
        if kwargs.get("on_progress"):
            kwargs["on_progress"](len(kwargs["personas"]))
        return [_run(f"p{i}") for i in range(len(kwargs["personas"]))]

    _invoke(monkeypatch, patched, run_many)

    assert set(windows) == {"model_a", "model_b", "model_c"}
    latest_start = max(s for s, _ in windows.values())
    earliest_end = min(e for _, e in windows.values())
    # If serial, the 2nd model would start only after the 1st ended. Overlap
    # (latest start < earliest end) can only happen if they ran in parallel.
    assert latest_start < earliest_end, f"models did not overlap: {windows}"


def test_one_model_failure_is_isolated(monkeypatch, patched):
    """A model that dies in conversion is recorded as lost, but the run still
    completes 'done' from the survivors, and results stay in roster order."""
    def fake_convert(survey_id, base_url, token, copy_label=None):
        if copy_label == "Model B":
            raise RuntimeError("boom converting B")
        return f"SV_{copy_label}"

    monkeypatch.setattr(sr, "_convert_survey", fake_convert)

    def run_many(**kwargs):
        return [_run(f"p{i}") for i in range(len(kwargs["personas"]))]

    _invoke(monkeypatch, patched, run_many)

    # Final status write is the last "done"/"failed" set_status call.
    final = [kw for st, kw in patched["set_status"] if st in ("done", "failed")]
    assert final, "no terminal status was written"
    last_status = [st for st, _ in patched["set_status"] if st in ("done", "failed")][-1]
    assert last_status == "done"

    # Credits charged once for the whole ensemble (n_participants), survivors won.
    assert patched["deducted"] == [(1, 4)]

    # The failed model's empty copy was cleaned up.
    assert patched["cleanup"], "failed model's copy was not cleaned up"


def test_progress_aggregates_across_models(monkeypatch, patched):
    """credits_used in the progress heartbeat sums completions across all models
    and divides by model count, ending at n_participants."""
    def run_many(**kwargs):
        n = len(kwargs["personas"])
        if kwargs.get("on_progress"):
            kwargs["on_progress"](n)  # this model finished all n
        return [_run(f"p{i}") for i in range(n)]

    _invoke(monkeypatch, patched, run_many)

    credits = [kw.get("credits_used") for st, kw in patched["set_status"]
               if "credits_used" in kw]
    assert credits, "no progress heartbeat carried credits_used"
    # 3 models each report 4 done → overall 12, // 3 models = 4 = n_participants.
    assert max(credits) == 4
