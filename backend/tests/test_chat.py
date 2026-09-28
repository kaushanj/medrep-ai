from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@patch("main.ask_rag")
def test_chat_returns_answer_and_source(mock_ask_rag):
    mock_ask_rag.return_value = {
        "answer": "Panadol is used for pain relief.",
        "source": "panadol.pdf",
    }

    response = client.post(
        "/chat",
        json={"question": "What is Panadol used for?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Panadol is used for pain relief.",
        "source": "panadol.pdf",
    }
    mock_ask_rag.assert_called_once_with("What is Panadol used for?")


def test_chat_missing_question_returns_422():
    response = client.post("/chat", json={})

    assert response.status_code == 422


@patch("main.ask_rag")
def test_chat_empty_question_returns_answer(mock_ask_rag):
    mock_ask_rag.return_value = {
        "answer": "No relevant documents found.",
        "source": "",
    }

    response = client.post("/chat", json={"question": ""})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "No relevant documents found.",
        "source": "",
    }
    mock_ask_rag.assert_called_once_with("")
