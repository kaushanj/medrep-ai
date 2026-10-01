"""Unit tests for Google ID-token authentication (mocked; no network)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from google.auth.exceptions import GoogleAuthError

from api.auth import require_google_user, verify_google_id_token
from main import app

client = TestClient(app)

VALID_CLAIMS = {
    "sub": "google-user-123",
    "email": "rep@example.com",
    "aud": "test-google-client-id.apps.googleusercontent.com",
}


@pytest.fixture(autouse=True)
def _clear_auth_override():
    """Ensure auth tests exercise the real dependency (chat tests override it)."""
    app.dependency_overrides.pop(require_google_user, None)
    yield
    app.dependency_overrides.pop(require_google_user, None)


@pytest.fixture
def google_client_id(monkeypatch):
    monkeypatch.setenv(
        "GOOGLE_CLIENT_ID",
        "test-google-client-id.apps.googleusercontent.com",
    )


def _assert_error(response, *, status: int, code: str, message: str):
    assert response.status_code == status
    body = response.json()
    assert body["error"]["code"] == code
    assert body["error"]["message"] == message
    assert body["error"]["request_id"]
    assert response.headers.get("x-request-id") == body["error"]["request_id"]


def test_missing_authorization_returns_401(google_client_id):
    response = client.post("/chat", json={"question": "What is Panadol used for?"})

    _assert_error(
        response,
        status=401,
        code="UNAUTHORIZED",
        message="Not authenticated.",
    )
    assert response.headers.get("www-authenticate") == "Bearer"


def test_non_bearer_scheme_returns_401(google_client_id):
    response = client.post(
        "/chat",
        json={"question": "What is Panadol used for?"},
        headers={"Authorization": "Basic sometoken"},
    )

    _assert_error(
        response,
        status=401,
        code="UNAUTHORIZED",
        message="Not authenticated.",
    )


def test_invalid_token_returns_401(google_client_id):
    with patch(
        "api.auth.id_token.verify_oauth2_token",
        side_effect=ValueError("Token used too early, or clock skew"),
    ):
        response = client.post(
            "/chat",
            json={"question": "What is Panadol used for?"},
            headers={"Authorization": "Bearer invalid-token"},
        )

    _assert_error(
        response,
        status=401,
        code="UNAUTHORIZED",
        message="Invalid authentication credentials.",
    )


def test_expired_token_returns_401(google_client_id):
    with patch(
        "api.auth.id_token.verify_oauth2_token",
        side_effect=ValueError("Token expired"),
    ):
        response = client.post(
            "/chat",
            json={"question": "What is Panadol used for?"},
            headers={"Authorization": "Bearer expired-token"},
        )

    _assert_error(
        response,
        status=401,
        code="UNAUTHORIZED",
        message="Invalid authentication credentials.",
    )


def test_wrong_audience_returns_401(google_client_id):
    with patch(
        "api.auth.id_token.verify_oauth2_token",
        side_effect=ValueError("Token has wrong audience"),
    ):
        response = client.post(
            "/chat",
            json={"question": "What is Panadol used for?"},
            headers={"Authorization": "Bearer wrong-aud-token"},
        )

    _assert_error(
        response,
        status=401,
        code="UNAUTHORIZED",
        message="Invalid authentication credentials.",
    )


def test_google_auth_error_returns_401(google_client_id):
    with patch(
        "api.auth.id_token.verify_oauth2_token",
        side_effect=GoogleAuthError("Wrong issuer."),
    ):
        response = client.post(
            "/chat",
            json={"question": "What is Panadol used for?"},
            headers={"Authorization": "Bearer bad-issuer-token"},
        )

    _assert_error(
        response,
        status=401,
        code="UNAUTHORIZED",
        message="Invalid authentication credentials.",
    )

@patch("main.ask_rag")
def test_valid_token_reaches_chat_handler(mock_ask_rag, google_client_id):
    mock_ask_rag.return_value = {
        "answer": "Panadol is used for pain relief.",
        "source": "panadol.pdf",
        "citations": [],
    }

    with patch(
        "api.auth.id_token.verify_oauth2_token",
        return_value=VALID_CLAIMS,
    ) as mock_verify:
        response = client.post(
            "/chat",
            json={"question": "What is Panadol used for?"},
            headers={"Authorization": "Bearer valid-google-id-token"},
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "Panadol is used for pain relief."
    mock_ask_rag.assert_called_once_with("What is Panadol used for?")
    mock_verify.assert_called_once()
    assert mock_verify.call_args.args[0] == "valid-google-id-token"
    assert mock_verify.call_args.kwargs["audience"] == (
        "test-google-client-id.apps.googleusercontent.com"
    )


def test_unset_google_client_id_returns_500(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)

    with patch(
        "api.auth.id_token.verify_oauth2_token",
    ) as mock_verify:
        response = client.post(
            "/chat",
            json={"question": "What is Panadol used for?"},
            headers={"Authorization": "Bearer some-token"},
        )

    _assert_error(
        response,
        status=500,
        code="INTERNAL_ERROR",
        message="Authentication is not configured.",
    )
    mock_verify.assert_not_called()

def test_verify_google_id_token_requires_client_id(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)

    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT_ID"):
        verify_google_id_token("any-token")


def test_verify_google_id_token_returns_claims(google_client_id):
    with patch(
        "api.auth.id_token.verify_oauth2_token",
        return_value=VALID_CLAIMS,
    ) as mock_verify:
        claims = verify_google_id_token("token-value")

    assert claims == VALID_CLAIMS
    mock_verify.assert_called_once()
    assert mock_verify.call_args.args[0] == "token-value"
    assert mock_verify.call_args.kwargs["audience"] == (
        "test-google-client-id.apps.googleusercontent.com"
    )
