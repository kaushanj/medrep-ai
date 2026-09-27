from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_chat_returns_answer_and_source():
    response = client.post(
        "/chat",
        json={"question": "What is Panadol used for?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "You asked: What is Panadol used for?",
        "source": "test.pdf",
    }


def test_chat_missing_question_returns_422():
    response = client.post("/chat", json={})

    assert response.status_code == 422


def test_chat_empty_question_returns_stub_answer():
    response = client.post("/chat", json={"question": ""})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "You asked: ",
        "source": "test.pdf",
    }
