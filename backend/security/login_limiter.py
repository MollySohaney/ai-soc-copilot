"""Purpose: Bound repeated local login failures without persisting credentials."""

from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict, deque


class LoginAttemptLimiter:
    """Track failed login attempts in one process using monotonic time."""

    def __init__(self) -> None:
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def key(*, client_host: str, username: str) -> str:
        """Avoid retaining a plaintext username in the limiter key."""
        material = f"{client_host}|{username.strip().lower()}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    def is_allowed(self, key: str, *, max_attempts: int, window_seconds: int) -> bool:
        """Return whether another attempt fits in the configured failure window."""
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts[key]
            self._prune(attempts, now=now, window_seconds=window_seconds)
            return len(attempts) < max_attempts

    def record_failure(self, key: str, *, window_seconds: int) -> None:
        """Record one failed attempt after removing expired entries."""
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts[key]
            self._prune(attempts, now=now, window_seconds=window_seconds)
            attempts.append(now)

    def clear(self, key: str) -> None:
        """Clear failures after successful authentication."""
        with self._lock:
            self._attempts.pop(key, None)

    def reset(self) -> None:
        """Clear all in-memory state, primarily for deterministic tests."""
        with self._lock:
            self._attempts.clear()

    @staticmethod
    def _prune(attempts: deque[float], *, now: float, window_seconds: int) -> None:
        cutoff = now - window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()


_LOGIN_LIMITER = LoginAttemptLimiter()


def get_login_limiter() -> LoginAttemptLimiter:
    """Return the process-local login failure limiter."""
    return _LOGIN_LIMITER
