"""In-memory sliding-window throttle for failed logins (single API process, hackathon scale).

Two limits, both counting FAILED attempts only:
- per (email, client IP): slows password guessing against one account;
- per client IP: slows spraying one password across many accounts.
A successful login clears the (email, IP) counter. State lives in the process: it resets on
restart and is not shared between replicas (a shared store such as Redis would be the next step).
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable

MAX_TRACKED_KEYS = 10_000


class LoginThrottle:
    def __init__(self, max_per_account: int = 5, max_per_ip: int = 20, window_seconds: int = 900,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._limits = {"acct": max_per_account, "ip": max_per_ip}
        self._window = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _keys(email: str, ip: str) -> dict[str, str]:
        return {"acct": f"acct:{email.strip().lower()}|{ip}", "ip": f"ip:{ip}"}

    def _recent(self, key: str, now: float) -> deque[float]:
        q = self._failures.get(key)
        if q is None:
            return deque()
        while q and q[0] <= now - self._window:
            q.popleft()
        if not q:
            del self._failures[key]
        return q

    def retry_after(self, email: str, ip: str) -> int | None:
        """Seconds until the next attempt is allowed, or None if allowed now."""
        now = self._clock()
        with self._lock:
            waits = []
            for kind, key in self._keys(email, ip).items():
                q = self._recent(key, now)
                if len(q) >= self._limits[kind]:
                    waits.append(q[0] + self._window - now)
            return max(1, math.ceil(max(waits))) if waits else None

    def record_failure(self, email: str, ip: str) -> None:
        now = self._clock()
        with self._lock:
            if len(self._failures) >= MAX_TRACKED_KEYS:  # bound memory: drop expired entries
                for key in list(self._failures):
                    self._recent(key, now)
            for key in self._keys(email, ip).values():
                self._failures.setdefault(key, deque()).append(now)

    def reset(self, email: str, ip: str) -> None:
        with self._lock:
            self._failures.pop(self._keys(email, ip)["acct"], None)
