"""Unit and API tests for in-process chat rate limiting (deterministic clocks)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth import require_google_user
from api.rate_limit import (
    DEFAULT_REQUESTS,
    DEFAULT_WINDOW_SECONDS,
    InMemoryRateLimiter,
    RATE_LIMIT_MESSAGE,
    chat_rate_limit_settings,
    rate_limit_key,
)
from main import app

client = TestClient(app)


@pytest.fixture
def auth_as():
    """Override Google auth to return a given `sub` for the duration of a test."""

    def _set(sub: str):
        app.dependency_overrides[require_google_user] = lambda: {
            "sub": sub,
            "email": f"{sub}@example.com",
        }

    yield _set
    app.dependency_overrides.pop(require_google_user, None)


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


# --- Unit: InMemoryRateLimiter ---


def test_sliding_window_allows_up_to_limit_then_rejects():
    clock = _FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)

    assert limiter.allow("user:a", limit=3, window_seconds=10) is True
    assert limiter.allow("user:a", limit=3, window_seconds=10) is True
    assert limiter.allow("user:a", limit=3, window_seconds=10) is True
    assert limiter.allow("user:a", limit=3, window_seconds=10) is False


def test_sliding_window_allows_again_after_window_elapses():
    clock = _FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)

    for _ in range(3):
        assert limiter.allow("user:a", limit=3, window_seconds=10) is True
    assert limiter.allow("user:a", limit=3, window_seconds=10) is False

    clock.advance(10.1)
    assert limiter.allow("user:a", limit=3, window_seconds=10) is True


def test_different_keys_do_not_share_bucket():
    clock = _FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)

    for _ in range(2):
        assert limiter.allow("user:a", limit=2, window_seconds=60) is True
    assert limiter.allow("user:a", limit=2, window_seconds=60) is False
    assert limiter.allow("user:b", limit=2, window_seconds=60) is True


def test_chat_rate_limit_settings_defaults_and_invalid(monkeypatch):
    monkeypatch.delenv("CHAT_RATE_LIMIT_REQUESTS", raising=False)
    monkeypatch.delenv("CHAT_RATE_LIMIT_WINDOW_SECONDS", raising=False)
    assert chat_rate_limit_settings() == (DEFAULT_REQUESTS, DEFAULT_WINDOW_SECONDS)

    monkeypatch.setenv("CHAT_RATE_LIMIT_REQUESTS", "0")
    monkeypatch.setenv("CHAT_RATE_LIMIT_WINDOW_SECONDS", "-5")
    assert chat_rate_limit_settings() == (DEFAULT_REQUESTS, DEFAULT_WINDOW_SECONDS)

    monkeypatch.setenv("CHAT_RATE_LIMIT_REQUESTS", "not-a-number")
    monkeypatch.setenv("CHAT_RATE_LIMIT_WINDOW_SECONDS", "abc")
    assert chat_rate_limit_settings() == (DEFAULT_REQUESTS, DEFAULT_WINDOW_SECONDS)

    monkeypatch.setenv("CHAT_RATE_LIMIT_REQUESTS", "5")
    monkeypatch.setenv("CHAT_RATE_LIMIT_WINDOW_SECONDS", "30")
    assert chat_rate_limit_settings() == (5, 30)


def test_rate_limit_key_prefers_sub_over_ip():
    class _Client:
        host = "203.0.113.10"

    class _Req:
        client = _Client()

    assert rate_limit_key({"sub": "google-123"}, _Req()) == "user:google-123"
    assert rate_limit_key({"sub": ""}, _Req()) == "ip:203.0.113.10"
    assert rate_limit_key({}, _Req()) == "ip:203.0.113.10"

    class _NoClient:
        client = None

    assert rate_limit_key({"sub": None}, _NoClient()) == "ip:unknown"


# --- API: POST /chat ---


@patch("main.ask_rag")
def test_chat_under_limit_succeeds(mock_ask_rag, auth_as, monkeypatch):
    monkeypatch.setenv("CHAT_RATE_LIMIT_REQUESTS", "3")
    monkeypatch.setenv("CHAT_RATE_LIMIT_WINDOW_SECONDS", "60")
    auth_as("user-under-limit")
    mock_ask_rag.return_value = {
        "answer": "ok",
        "source": "panadol.pdf",
        "citations": [],
    }

    for _ in range(3):
        response = client.post("/chat", json={"question": "What is Panadol used for?"})
        assert response.status_code == 200

    assert mock_ask_rag.call_count == 3


@patch("main.ask_rag")
def test_chat_over_limit_returns_429(mock_ask_rag, auth_as, monkeypatch):
    monkeypatch.setenv("CHAT_RATE_LIMIT_REQUESTS", "2")
    monkeypatch.setenv("CHAT_RATE_LIMIT_WINDOW_SECONDS", "60")
    auth_as("user-over-limit")
    mock_ask_rag.return_value = {
        "answer": "ok",
        "source": "panadol.pdf",
        "citations": [],
    }

    assert (
        client.post("/chat", json={"question": "q1"}).status_code == 200
    )
    assert (
        client.post("/chat", json={"question": "q2"}).status_code == 200
    )
    response = client.post("/chat", json={"question": "q3"})

    assert response.status_code == 429
    body = response.json()
    assert body["error"]["code"] == "TOO_MANY_REQUESTS"
    assert body["error"]["message"] == RATE_LIMIT_MESSAGE
    assert body["error"]["request_id"]
    assert response.headers.get("x-request-id") == body["error"]["request_id"]
    assert mock_ask_rag.call_count == 2


@patch("main.ask_rag")
def test_chat_rate_limit_is_per_user(mock_ask_rag, auth_as, monkeypatch):
    monkeypatch.setenv("CHAT_RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("CHAT_RATE_LIMIT_WINDOW_SECONDS", "60")
    mock_ask_rag.return_value = {
        "answer": "ok",
        "source": "panadol.pdf",
        "citations": [],
    }

    auth_as("user-a")
    assert (
        client.post("/chat", json={"question": "from a"}).status_code == 200
    )
    assert (
        client.post("/chat", json={"question": "from a again"}).status_code
        == 429
    )

    auth_as("user-b")
    response = client.post("/chat", json={"question": "from b"})
    assert response.status_code == 200
    assert mock_ask_rag.call_count == 2
