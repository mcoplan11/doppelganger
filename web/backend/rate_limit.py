"""Tiny in-memory sliding-window rate limiter.

Deliberately dependency-free and process-local: enough to blunt scripted abuse
(email bombing, Resend-quota burn) without adding Redis or a new library. If the
app runs on multiple instances the limits apply per-instance, which only makes
them looser — acceptable for a best-effort abuse backstop, never a hard quota.

Callers should treat this as advisory and fail OPEN (allow on error) so the
limiter can never take down a real request path.
"""
import threading
import time
from collections import defaultdict, deque
from typing import Sequence, Tuple

# (key, max_events, window_seconds)
Rule = Tuple[str, int, float]

# How often (in calls) to sweep expired/empty buckets so the dict doesn't grow
# unbounded when abuse cycles through many distinct emails/IPs.
_PRUNE_EVERY = 1000


class SlidingWindowLimiter:
    """Fixed-set-of-rules sliding window, keyed by arbitrary strings."""

    def __init__(self) -> None:
        self._events: "defaultdict[str, deque]" = defaultdict(deque)
        self._lock = threading.Lock()
        self._calls_since_prune = 0

    def allow(self, rules: Sequence[Rule], now: float | None = None) -> bool:
        """Return True if ALL rules are within budget, recording the event.

        Events are only recorded when every rule passes, so a request rejected
        by one rule does not inflate the counters of the others.
        """
        now = time.monotonic() if now is None else now
        with self._lock:
            self._calls_since_prune += 1
            if self._calls_since_prune >= _PRUNE_EVERY:
                self._prune(now)

            # Peek: evict expired events and check every rule before recording.
            for key, limit, window in rules:
                dq = self._events[key]
                cutoff = now - window
                while dq and dq[0] <= cutoff:
                    dq.popleft()
                if len(dq) >= limit:
                    return False

            # All rules have headroom — record the event against each.
            for key, _limit, _window in rules:
                self._events[key].append(now)
            return True

    def _prune(self, now: float) -> None:
        """Drop buckets whose events have all aged out (holds _lock)."""
        self._calls_since_prune = 0
        for key in list(self._events.keys()):
            dq = self._events[key]
            # Evict against the widest window we plausibly use; anything older
            # than an hour is certainly expired for our rules.
            cutoff = now - 3600
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if not dq:
                del self._events[key]
