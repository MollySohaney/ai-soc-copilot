"""Purpose: Bound expensive request rates and in-flight work per identity."""

from __future__ import annotations

import hashlib
import math
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable


@dataclass
class AbuseLease:
    """Release one acquired concurrency slot exactly once."""

    _limiter: "AbuseLimiter"
    _key: str
    _released: bool = False

    def release(self) -> None:
        if not self._released:
            self._released = True
            self._limiter.release(self._key)


class AbuseLimiter:
    """Provide thread-safe fixed-window and concurrent request limits in one process."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._active: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    @staticmethod
    def key(*, scope: str, identity: str) -> str:
        material = f"{scope}|{identity}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    def acquire(
        self,
        key: str,
        *,
        max_requests: int,
        window_seconds: int,
        max_concurrent: int,
    ) -> tuple[AbuseLease | None, int]:
        now = self._clock()
        with self._lock:
            requests = self._requests[key]
            cutoff = now - window_seconds
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= max_requests:
                return None, max(1, math.ceil(requests[0] + window_seconds - now))
            if self._active[key] >= max_concurrent:
                return None, 1
            requests.append(now)
            self._active[key] += 1
            return AbuseLease(self, key), 0

    def release(self, key: str) -> None:
        with self._lock:
            if self._active.get(key, 0) <= 1:
                self._active.pop(key, None)
            else:
                self._active[key] -= 1

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()
            self._active.clear()


_ABUSE_LIMITER = AbuseLimiter()


def get_abuse_limiter() -> AbuseLimiter:
    """Return the process-local abuse limiter."""
    return _ABUSE_LIMITER
