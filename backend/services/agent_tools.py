import logging

from langchain_core.tools import tool

from services.dailymed_evidence import retrieve_dailymed_evidence
from services.rag import (
    _citation_from_chunk,
    _dedupe_chunks,
    embed_question,
    search_opensearch,
)

logger = logging.getLogger(__name__)


def search_internal_documents(query: str, top_k: int | None = None) -> dict:
    try:
        embedding = embed_question(query)
        results = search_opensearch(embedding, top_k=top_k)
        chunks = _dedupe_chunks(results)
        if not chunks:
            return {
                "status": "no_results",
                "source": "internal_documents",
                "query": query,
                "results": [],
                "error": None,
            }
        return {
            "status": "ok",
            "source": "internal_documents",
            "query": query,
            "results": [
                {
                    "text": chunk.get("text", ""),
                    "score": chunk.get("score", 0),
                    "metadata": _citation_from_chunk(chunk),
                }
                for chunk in chunks
            ],
            "error": None,
        }
    except Exception:
        logger.exception("Internal document search failed.")
        return {
            "status": "error",
            "source": "internal_documents",
            "query": query,
            "results": [],
            "error": "Internal document search failed.",
        }


def search_dailymed_evidence(
    query: str,
    product_name: str,
    top_k: int | None = None,
) -> dict:
    return retrieve_dailymed_evidence(
        query,
        product_name,
        top_k=3 if top_k is None else top_k,
    )


@tool("search_internal_documents")
def search_internal_documents_tool(query: str) -> dict:
    """Search trusted internal product documents and return retrieved evidence.

    Prefer this tool for products not in the DailyMed supported registry
    and for general internal-document questions.
    """
    return search_internal_documents(query)


@tool("search_dailymed_evidence")
def search_dailymed_evidence_tool(query: str, product_name: str) -> dict:
    """Search DailyMed label sections for a supported labeled product.

    Use only for products in the DailyMed registry (currently Ozempic).
    For unsupported products, use search_internal_documents instead.
    """
    return search_dailymed_evidence(query, product_name)
