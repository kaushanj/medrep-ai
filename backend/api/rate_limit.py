"""In-process sliding-window rate limiting for protected chat."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request

from api.auth import require_google_user

DEFAULT_REQUESTS = 20
DEFAULT_WINDOW_SECONDS = 60

RATE_LIMIT_MESSAGE = "Rate limit exceeded. Try again later."


class InMemoryRateLimiter:
    """Thread-safe sliding window of request timestamps per key."""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str, *, limit: int, window_seconds: float) -> bool:
        """Return True if the request is allowed; False if over the limit."""
        now = self._clock()
        cutoff = now - window_seconds
        with self._lock:
            timestamps = [t for t in self._hits.get(key, []) if t > cutoff]
            if len(timestamps) >= limit:
                self._hits[key] = timestamps
                return False
            timestamps.append(now)
            self._hits[key] = timestamps
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_limiter = InMemoryRateLimiter()


def reset_for_tests() -> None:
    """Clear the module-level limiter store (tests only)."""
    _limiter.reset()


def _positive_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    text = raw.strip()
    if not text:
        return default
    try:
        value = int(text)
    except ValueError:
        return default
    if value <= 0:
        return default
    return value


def chat_rate_limit_settings() -> tuple[int, int]:
    """Read limit/window from env; invalid or non-positive → defaults."""
    limit = _positive_int(
        os.environ.get("CHAT_RATE_LIMIT_REQUESTS"),
        DEFAULT_REQUESTS,
    )
    window = _positive_int(
        os.environ.get("CHAT_RATE_LIMIT_WINDOW_SECONDS"),
        DEFAULT_WINDOW_SECONDS,
    )
    return limit, window


def rate_limit_key(user: dict[str, Any], request: Request) -> str:
    """Prefer Google subject; fall back to client IP when sub is missing."""
    sub = user.get("sub")
    if isinstance(sub, str) and sub:
        return f"user:{sub}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def enforce_chat_rate_limit(
    request: Request,
    user: dict[str, Any] = Depends(require_google_user),
) -> None:
    """FastAPI dependency: after auth, enforce the chat rate limit."""
    limit, window = chat_rate_limit_settings()
    key = rate_limit_key(user, request)
    if not _limiter.allow(key, limit=limit, window_seconds=window):
        raise HTTPException(status_code=429, detail=RATE_LIMIT_MESSAGE)
