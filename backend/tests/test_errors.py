"""Consistent API error envelopes and safe unexpected-error handling."""

import logging
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.auth import require_google_user
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


def test_validation_error_returns_envelope():
    response = client.post("/chat", json={})

    assert response.status_code == 422
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Request validation failed."
    assert body["error"]["request_id"]
    assert response.headers.get("x-request-id") == body["error"]["request_id"]
    assert "detail" not in body


def test_http_exception_503_returns_service_unavailable_envelope():
    with patch("main.ask_rag", side_effect=RuntimeError("bedrock down")):
        response = client.post(
            "/chat",
            json={"question": "What is Panadol used for?"},
        )

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert body["error"]["message"] == "The AI service is temporarily unavailable."
    assert body["error"]["request_id"]
    assert "detail" not in body


def test_unexpected_exception_returns_controlled_500(caplog):
    """Route a bare Exception through the unhandled handler."""

    @app.get("/_test_boom")
    def _boom():
        raise RuntimeError("secret stack internals")

    boom_client = TestClient(app, raise_server_exceptions=False)
    try:
        with caplog.at_level(logging.ERROR):
            response = boom_client.get(
                "/_test_boom",
                headers={
                    "X-Request-ID": "err-corr-001",
                    "Authorization": "Bearer super-secret-token",
                },
            )
    finally:
        app.router.routes[:] = [
            r for r in app.router.routes if getattr(r, "path", None) != "/_test_boom"
        ]

    assert response.status_code == 500
    body = response.json()
    assert body == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "Something went wrong.",
            "request_id": "err-corr-001",
        }
    }
    assert "secret stack internals" not in response.text
    assert "super-secret-token" not in caplog.text
    assert "err-corr-001" in caplog.text


def test_http_exception_preserves_www_authenticate():
    app.dependency_overrides.pop(require_google_user, None)

    response = client.post("/chat", json={"question": "What is Panadol used for?"})

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert body["error"]["message"] == "Not authenticated."


def test_framework_404_returns_envelope():
    response = client.get(
        "/no-such-route",
        headers={"X-Request-ID": "not-found-001"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Not Found",
            "request_id": "not-found-001",
        }
    }
    assert response.headers.get("x-request-id") == "not-found-001"
    assert "detail" not in body


def test_framework_405_returns_envelope():
    response = client.put(
        "/health",
        headers={"X-Request-ID": "method-not-allowed-001"},
    )

    assert response.status_code == 405
    body = response.json()
    assert body == {
        "error": {
            "code": "METHOD_NOT_ALLOWED",
            "message": "Method Not Allowed",
            "request_id": "method-not-allowed-001",
        }
    }
    assert response.headers.get("x-request-id") == "method-not-allowed-001"
    assert "detail" not in body
