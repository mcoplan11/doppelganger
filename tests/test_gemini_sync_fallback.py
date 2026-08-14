"""Unit tests for GeminiClient._answer_blocks_sync_fallback concurrency.

This is the Vertex path (no inline Batch API), which previously answered one
block at a time — turning a single 600-session round into thousands of serial
calls. It now fans the independent calls out across a bounded thread pool.

The tests avoid any network/credentials by constructing the client via
object.__new__ and monkeypatching answer_block.
"""
import threading
import time

from gemini_client import BatchInput, GeminiClient


def _make_client(workers: int) -> GeminiClient:
    """A GeminiClient with just the attributes the fallback touches — no
    genai.Client / credentials needed."""
    client = object.__new__(GeminiClient)
    client._sync_workers = workers
    return client


def _make_input(key: str, *, answerable: bool = True) -> BatchInput:
    # answer_block is mocked, so the question payload only needs to be truthy.
    return BatchInput(
        key=key,
        persona=object(),
        answerable=[object()] if answerable else [],
        prior_answers=[],
        read_context=[],
        survey_name="t",
    )


def test_results_mapping_and_empty_and_error_semantics(monkeypatch):
    def fake_answer_block(self, persona, questions, prior_answers, **kw):
        # key isn't passed in; encode the answer off the persona identity via a
        # side channel is overkill — just return a marker and rely on ordering
        # through pool.map (which preserves input order).
        return {"ans": "ok"}

    client = _make_client(workers=4)
    monkeypatch.setattr(GeminiClient, "answer_block", fake_answer_block)

    inputs = [
        _make_input("a"),
        _make_input("db-only", answerable=False),
        _make_input("b"),
    ]
    out = client._answer_blocks_sync_fallback(inputs)

    # answerable keys get the mocked answer; DB-only keys get {} with no call.
    assert out["a"] == {"ans": "ok"}
    assert out["b"] == {"ans": "ok"}
    assert out["db-only"] == {}
    assert set(out) == {"a", "b", "db-only"}


def test_exception_maps_to_none(monkeypatch):
    def boom(self, *a, **k):
        raise RuntimeError("model exploded")

    client = _make_client(workers=2)
    monkeypatch.setattr(GeminiClient, "answer_block", boom)

    out = client._answer_blocks_sync_fallback([_make_input("x")])
    assert out == {"x": None}


def test_calls_run_concurrently(monkeypatch):
    """With N>=workers slow calls, observed in-flight concurrency must exceed 1
    — proving the pool isn't serializing them."""
    lock = threading.Lock()
    inflight = 0
    peak = 0

    def slow(self, *a, **k):
        nonlocal inflight, peak
        with lock:
            inflight += 1
            peak = max(peak, inflight)
        time.sleep(0.1)
        with lock:
            inflight -= 1
        return {"ans": "ok"}

    client = _make_client(workers=4)
    monkeypatch.setattr(GeminiClient, "answer_block", slow)

    inputs = [_make_input(str(i)) for i in range(8)]
    out = client._answer_blocks_sync_fallback(inputs)

    assert len(out) == 8
    assert all(v == {"ans": "ok"} for v in out.values())
    assert peak > 1, f"expected concurrent execution, peak inflight was {peak}"
