import logging

from langchain_core.tools import tool

from services.chat_result import citation_from_fields
from services.rag import (
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
                    "metadata": citation_from_fields(chunk),
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


@tool("search_internal_documents")
def search_internal_documents_tool(query: str) -> dict:
    """Search trusted internal product documents and return retrieved evidence.

    Use this tool for internal-document questions about products and labels.
    """
    return search_internal_documents(query)
