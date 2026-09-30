from unittest.mock import patch

from services import rag


def test_ask_rag_returns_answer_and_source():
    with (
        patch("services.rag.embed_question", return_value=[0.1, 0.2]) as mock_embed,
        patch(
            "services.rag.search_opensearch",
            return_value=[{"text": "Panadol is for pain.", "source": "panadol.pdf"}],
        ) as mock_search,
        patch(
            "services.rag.generate_answer",
            return_value="Panadol is used for pain relief.",
        ) as mock_generate,
    ):
        result = rag.ask_rag("What is Panadol used for?")

    assert result == {
        "answer": "Panadol is used for pain relief.",
        "source": "panadol.pdf",
        "context": "Panadol is for pain.",
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
        patch("services.rag.embed_question", side_effect=embed),
        patch("services.rag.search_opensearch", side_effect=search),
        patch("services.rag.generate_answer", side_effect=generate),
    ):
        rag.ask_rag("question")

    assert call_order == ["embed", "search", "generate"]


def test_ask_rag_empty_retrieval_returns_controlled_response():
    with (
        patch("services.rag.embed_question", return_value=[0.1]),
        patch("services.rag.search_opensearch", return_value=[]),
        patch("services.rag.generate_answer") as mock_generate,
    ):
        result = rag.ask_rag("Unknown product?")

    assert set(result.keys()) == {"answer", "source", "context"}
    assert isinstance(result["answer"], str)
    assert result["answer"]
    assert result["source"] == ""
    assert result["context"] == ""
    mock_generate.assert_not_called()


def test_ask_rag_uses_all_retrieved_chunks_as_context():
    chunks = [
        {"text": "Panadol is for pain.", "source": "panadol.pdf"},
        {"text": "Dose is 500mg every 4-6 hours.", "source": "panadol.pdf"},
        {"text": "Do not exceed 8 tablets in 24 hours.", "source": "safety.pdf"},
    ]
    combined = (
        "Panadol is for pain.\n\n"
        "Dose is 500mg every 4-6 hours.\n\n"
        "Do not exceed 8 tablets in 24 hours."
    )

    with (
        patch("services.rag.embed_question", return_value=[0.1]),
        patch("services.rag.search_opensearch", return_value=chunks),
        patch(
            "services.rag.generate_answer",
            return_value="Panadol relieves pain; max 8 tablets/day.",
        ) as mock_generate,
    ):
        result = rag.ask_rag("What is Panadol dosing?")

    assert result == {
        "answer": "Panadol relieves pain; max 8 tablets/day.",
        "source": "panadol.pdf, safety.pdf",
        "context": combined,
    }
    mock_generate.assert_called_once_with("What is Panadol dosing?", combined)


def test_ask_rag_dedupes_identical_chunk_text():
    chunks = [
        {"text": "Same text.", "source": "a.pdf"},
        {"text": "Same text.", "source": "b.pdf"},
        {"text": "Other text.", "source": "c.pdf"},
        {"text": "", "source": "d.pdf"},
        {"text": "Third text.", "source": ""},
    ]
    combined = "Same text.\n\nOther text.\n\nThird text."

    with (
        patch("services.rag.embed_question", return_value=[0.1]),
        patch("services.rag.search_opensearch", return_value=chunks),
        patch(
            "services.rag.generate_answer",
            return_value="answer",
        ) as mock_generate,
    ):
        result = rag.ask_rag("question")

    assert result["context"] == combined
    assert result["source"] == "a.pdf, c.pdf, d.pdf"
    mock_generate.assert_called_once_with("question", combined)
