from unittest.mock import patch

import services.agent_tools as agent_tools
from services.agent_tools import (
    search_internal_documents,
    search_internal_documents_tool,
)
from services.rag import _CITATION_METADATA_FIELDS


def test_search_internal_documents_returns_ok_with_clean_metadata():
    hits = [
        {
            "text": "Panadol is for pain.",
            "source": "panadol.pdf",
            "score": 0.85,
            "product_name": "Panadol",
            "document_type": "leaflet",
            "source_filename": "panadol.pdf",
            "s3_key": "docs/panadol.pdf",
            "page_number": 1,
            "section_name": "Indications",
            "document_version": "1.0",
            "effective_date": "2024-01-01",
        },
        {
            "text": "Low relevance chunk.",
            "source": "other.pdf",
            "score": 0.50,
            "product_name": "Other",
            "document_type": "leaflet",
            "source_filename": "other.pdf",
            "s3_key": "docs/other.pdf",
            "page_number": 2,
            "section_name": "Other",
            "document_version": "1.0",
            "effective_date": "2024-01-01",
        },
    ]

    with (
        patch(
            "services.agent_tools.embed_question",
            return_value=[0.1, 0.2],
        ) as mock_embed,
        patch(
            "services.agent_tools.search_opensearch",
            return_value=hits,
        ) as mock_search,
    ):
        result = search_internal_documents("What is Panadol used for?")

    mock_embed.assert_called_once_with("What is Panadol used for?")
    mock_search.assert_called_once_with([0.1, 0.2], top_k=None)
    assert result["status"] == "ok"
    assert result["source"] == "internal_documents"
    assert result["query"] == "What is Panadol used for?"
    assert result["error"] is None
    assert len(result["results"]) == 1

    item = result["results"][0]
    assert item["text"] == "Panadol is for pain."
    assert item["score"] == 0.85
    assert set(item["metadata"].keys()) == set(_CITATION_METADATA_FIELDS)
    assert "score" not in item["metadata"]
    assert item["metadata"] == {
        "product_name": "Panadol",
        "document_type": "leaflet",
        "source_filename": "panadol.pdf",
        "s3_key": "docs/panadol.pdf",
        "page_number": 1,
        "section_name": "Indications",
        "document_version": "1.0",
        "effective_date": "2024-01-01",
    }


def test_search_internal_documents_empty_hits_returns_no_results():
    with (
        patch(
            "services.agent_tools.embed_question",
            return_value=[0.1],
        ),
        patch(
            "services.agent_tools.search_opensearch",
            return_value=[],
        ) as mock_search,
    ):
        result = search_internal_documents("Unknown product?")

    mock_search.assert_called_once_with([0.1], top_k=None)
    assert result == {
        "status": "no_results",
        "source": "internal_documents",
        "query": "Unknown product?",
        "results": [],
        "error": None,
    }


def test_search_internal_documents_low_scores_returns_no_results():
    hits = [
        {
            "text": "Below threshold.",
            "source": "doc.pdf",
            "score": 0.50,
            "product_name": "X",
            "document_type": "leaflet",
            "source_filename": "doc.pdf",
            "s3_key": "docs/doc.pdf",
            "page_number": 1,
            "section_name": "A",
            "document_version": "1.0",
            "effective_date": "2024-01-01",
        },
        {
            "text": "At threshold boundary still excluded.",
            "source": "doc2.pdf",
            "score": 0.70,
            "product_name": "Y",
            "document_type": "leaflet",
            "source_filename": "doc2.pdf",
            "s3_key": "docs/doc2.pdf",
            "page_number": 1,
            "section_name": "B",
            "document_version": "1.0",
            "effective_date": "2024-01-01",
        },
    ]

    with (
        patch(
            "services.agent_tools.embed_question",
            return_value=[0.1],
        ),
        patch(
            "services.agent_tools.search_opensearch",
            return_value=hits,
        ),
    ):
        result = search_internal_documents("low score query")

    assert result["status"] == "no_results"
    assert result["source"] == "internal_documents"
    assert result["query"] == "low score query"
    assert result["results"] == []
    assert result["error"] is None


def test_search_internal_documents_embedding_exception_returns_error():
    with patch(
        "services.agent_tools.embed_question",
        side_effect=RuntimeError("AWS AccessDenied secret-key-abc"),
    ):
        result = search_internal_documents("What is Panadol?")

    assert result["status"] == "error"
    assert result["source"] == "internal_documents"
    assert result["query"] == "What is Panadol?"
    assert result["results"] == []
    assert result["error"] == "Internal document search failed."
    assert "AccessDenied" not in result["error"]
    assert "secret-key" not in str(result)


def test_search_internal_documents_search_exception_returns_error():
    with (
        patch(
            "services.agent_tools.embed_question",
            return_value=[0.1],
        ),
        patch(
            "services.agent_tools.search_opensearch",
            side_effect=ConnectionError("OpenSearch timeout host=prod-secret"),
        ),
    ):
        result = search_internal_documents("What is Panadol?")

    assert result["status"] == "error"
    assert result["results"] == []
    assert result["error"] == "Internal document search failed."
    assert "OpenSearch" not in result["error"]
    assert "prod-secret" not in str(result)


def test_search_internal_documents_tool_passes_through_result():
    mocked_return = {
        "status": "ok",
        "source": "internal_documents",
        "query": "What is Ozempic used for?",
        "results": [
            {
                "text": "Example trusted evidence",
                "score": 0.91,
                "metadata": {},
            }
        ],
        "error": None,
    }

    with patch(
        "services.agent_tools.search_internal_documents",
        return_value=mocked_return,
    ) as mock_search:
        result = search_internal_documents_tool.invoke(
            {"query": "What is Ozempic used for?"}
        )

    assert result == mocked_return
    mock_search.assert_called_once_with("What is Ozempic used for?")


def test_search_internal_documents_tool_schema_metadata():
    assert search_internal_documents_tool.name == "search_internal_documents"
    assert "Search trusted internal product documents" in (
        search_internal_documents_tool.description
    )
    assert "dailymed" not in search_internal_documents_tool.description.lower()
    assert list(search_internal_documents_tool.args.keys()) == ["query"]
    assert "top_k" not in search_internal_documents_tool.args
    assert not hasattr(agent_tools, "search_dailymed_evidence_tool")
    assert not hasattr(agent_tools, "search_dailymed_evidence")
