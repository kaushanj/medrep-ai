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


def test_chat_full_rag_flow_returns_answer_and_source():
    question = "What is Panadol used for?"
    embedding = [0.1, 0.2]
    chunk_text = "Panadol is for pain."
    chunk_source = "panadol.pdf"
    grounded_answer = "Panadol is used for pain relief."
    call_order = []

    def embed(q):
        call_order.append("embed")
        return embedding

    def search(emb):
        call_order.append("search")
        return [{"text": chunk_text, "source": chunk_source}]

    def generate(q, context):
        call_order.append("generate")
        return grounded_answer

    with (
        patch("services.rag.embed_question", side_effect=embed) as mock_embed,
        patch("services.rag.search_opensearch", side_effect=search) as mock_search,
        patch("services.rag.generate_answer", side_effect=generate) as mock_generate,
    ):
        response = client.post("/chat", json={"question": question})

    assert response.status_code == 200
    assert response.json() == {
        "answer": grounded_answer,
        "source": chunk_source,
    }
    mock_embed.assert_called_once_with(question)
    mock_search.assert_called_once_with(embedding)
    mock_generate.assert_called_once_with(question, chunk_text)
    assert call_order == ["embed", "search", "generate"]
