from unittest.mock import patch

import rag


def test_ask_rag_returns_answer_and_source():
    with (
        patch("rag.embed_question", return_value=[0.1, 0.2]) as mock_embed,
        patch(
            "rag.search_opensearch",
            return_value=[{"text": "Panadol is for pain.", "source": "panadol.pdf"}],
        ) as mock_search,
        patch(
            "rag.generate_answer",
            return_value="Panadol is used for pain relief.",
        ) as mock_generate,
    ):
        result = rag.ask_rag("What is Panadol used for?")

    assert result == {
        "answer": "Panadol is used for pain relief.",
        "source": "panadol.pdf",
    }
    mock_embed.assert_called_once_with("What is Panadol used for?")
    mock_search.assert_called_once_with([0.1, 0.2])
    mock_generate.assert_called_once_with(
        "What is Panadol used for?",
        "Panadol is for pain.",
    )


def test_ask_rag_pipeline_order():
    call_order = []

    def embed(_question):
        call_order.append("embed")
        return [0.1]

    def search(_embedding):
        call_order.append("search")
        return [{"text": "context text", "source": "doc.pdf"}]

    def generate(_question, _context):
        call_order.append("generate")
        return "generated answer"

    with (
        patch("rag.embed_question", side_effect=embed),
        patch("rag.search_opensearch", side_effect=search),
        patch("rag.generate_answer", side_effect=generate),
    ):
        rag.ask_rag("question")

    assert call_order == ["embed", "search", "generate"]


def test_ask_rag_empty_retrieval_returns_controlled_response():
    with (
        patch("rag.embed_question", return_value=[0.1]),
        patch("rag.search_opensearch", return_value=[]),
        patch("rag.generate_answer") as mock_generate,
    ):
        result = rag.ask_rag("Unknown product?")

    assert set(result.keys()) == {"answer", "source"}
    assert isinstance(result["answer"], str)
    assert result["answer"]
    assert result["source"] == ""
    mock_generate.assert_not_called()
