from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.auth import require_google_user
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _bypass_google_auth():
    """Agent-chat tests stay auth-agnostic; real auth is covered in test_auth.py."""
    app.dependency_overrides[require_google_user] = lambda: {
        "sub": "test-user",
        "email": "test@example.com",
    }
    yield
    app.dependency_overrides.pop(require_google_user, None)


@patch("main.build_bedrock_model_with_internal_docs_tool")
@patch("main.ask_agent")
def test_agent_chat_returns_answer(mock_ask_agent, mock_build_model):
    model = MagicMock(name="bound_model")
    mock_build_model.return_value = model
    mock_ask_agent.return_value = {
        "answer": "Ozempic is used for type 2 diabetes.",
        "source": "ozempic.pdf",
        "citations": [
            {
                "product_name": "Ozempic",
                "document_type": "pdf",
                "source_filename": "ozempic.pdf",
                "s3_key": "ozempic/ozempic.pdf",
                "page_number": 1,
                "section_name": "Indications",
                "document_version": "v1",
                "effective_date": "2023-06-01",
            }
        ],
    }

    response = client.post(
        "/agent-chat",
        json={"question": "What is Ozempic used for?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Ozempic is used for type 2 diabetes.",
        "source": "ozempic.pdf",
        "citations": [
            {
                "product_name": "Ozempic",
                "document_type": "pdf",
                "source_filename": "ozempic.pdf",
                "s3_key": "ozempic/ozempic.pdf",
                "page_number": 1,
                "section_name": "Indications",
                "document_version": "v1",
                "effective_date": "2023-06-01",
            }
        ],
    }
    mock_build_model.assert_called_once_with()
    mock_ask_agent.assert_called_once_with("What is Ozempic used for?", model)


@patch("main.build_bedrock_model_with_internal_docs_tool")
@patch("main.ask_agent")
def test_agent_chat_unexpected_failure_returns_503(mock_ask_agent, mock_build_model):
    mock_build_model.return_value = MagicMock()
    mock_ask_agent.side_effect = RuntimeError("bedrock down")

    response = client.post(
        "/agent-chat",
        json={"question": "What is Ozempic used for?"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert body["error"]["message"] == "The AI service is temporarily unavailable."
