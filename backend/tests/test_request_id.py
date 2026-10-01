"""Request ID middleware: generate, validate, propagate, echo on responses."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth import require_google_user
from api.middleware import is_valid_request_id, resolve_request_id
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _bypass_google_auth():
    app.dependency_overrides[require_google_user] = lambda: {
        "sub": "test-user",
        "email": "test@example.com",
    }
    yield
    app.dependency_overrides.pop(require_google_user, None)


def test_is_valid_request_id_rejects_empty_whitespace_and_control():
    assert is_valid_request_id(None) is False
    assert is_valid_request_id("") is False
    assert is_valid_request_id("has space") is False
    assert is_valid_request_id("bad\nid") is False
    assert is_valid_request_id("x" * 129) is False


def test_is_valid_request_id_accepts_uuid_like():
    assert is_valid_request_id("550e8400-e29b-41d4-a716-446655440000") is True
    assert is_valid_request_id("client-req-1") is True


def test_resolve_request_id_generates_when_missing_or_invalid():
    generated = resolve_request_id(None)
    assert is_valid_request_id(generated)
    assert resolve_request_id("not valid") != "not valid"
    assert is_valid_request_id(resolve_request_id("not valid"))


def test_missing_request_id_header_generates_one():
    response = client.get("/health")

    assert response.status_code == 200
    request_id = response.headers.get("x-request-id")
    assert request_id
    assert is_valid_request_id(request_id)


def test_invalid_request_id_header_generates_new_one():
    response = client.get(
        "/health",
        headers={"X-Request-ID": "has whitespace"},
    )

    assert response.status_code == 200
    request_id = response.headers.get("x-request-id")
    assert request_id != "has whitespace"
    assert is_valid_request_id(request_id)


def test_valid_request_id_is_propagated():
    incoming = "550e8400-e29b-41d4-a716-446655440000"
    response = client.get("/health", headers={"X-Request-ID": incoming})

    assert response.status_code == 200
    assert response.headers.get("x-request-id") == incoming


@patch("main.ask_rag")
def test_request_id_header_on_success_and_error(mock_ask_rag):
    mock_ask_rag.return_value = {
        "answer": "ok",
        "source": "panadol.pdf",
        "citations": [],
    }
    incoming = "client-correlation-id-01"

    ok = client.post(
        "/chat",
        json={"question": "What is Panadol used for?"},
        headers={"X-Request-ID": incoming},
    )
    assert ok.status_code == 200
    assert ok.headers.get("x-request-id") == incoming

    bad = client.post(
        "/chat",
        json={},
        headers={"X-Request-ID": incoming},
    )
    assert bad.status_code == 422
    assert bad.headers.get("x-request-id") == incoming
    assert bad.json()["error"]["request_id"] == incoming
