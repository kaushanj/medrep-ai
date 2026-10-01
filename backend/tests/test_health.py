"""Health endpoint: lightweight, unauthenticated, no AI deps."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_returns_200_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "x-request-id" in response.headers


def test_health_does_not_require_auth():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_does_not_call_ai_dependencies():
    with (
        patch("main.ask_rag", side_effect=RuntimeError("should not call ask_rag")),
        patch(
            "main.opensearch_client",
            side_effect=RuntimeError("should not call opensearch"),
        ),
        patch(
            "main._bedrock_runtime",
            side_effect=RuntimeError("should not call bedrock"),
        ),
    ):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
