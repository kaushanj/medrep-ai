"""Trusted DailyMed evidence retrieval for the agent.

Uses a supported-product registry (stable setid) and semantic section
ranking. Does not blindly take the first name-search hit.
"""

from __future__ import annotations

import logging
import math
import re

from services.dailymed import get_dailymed_label
from services.rag import embed_question

logger = logging.getLogger(__name__)

# Normalized product name -> DailyMed setid.
SUPPORTED_PRODUCT_SETIDS: dict[str, str] = {
    "ozempic": "adec4fd2-6858-4c99-91d4-531f5f2a2d79",
}

# Warm-process cache: setid -> list of section embeddings (aligned to sections).
_SECTION_EMBEDDING_CACHE: dict[str, list[list[float]]] = {}


def normalize_product_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def resolve_supported_setid(product_name: str) -> str | None:
    """Registry lookup only. Never falls back to name-search first hit."""
    key = normalize_product_name(product_name)
    if not key:
        return None
    return SUPPORTED_PRODUCT_SETIDS.get(key)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_cached_section_embeddings(
    setid: str,
    sections: list[dict],
) -> list[list[float]]:
    cached = _SECTION_EMBEDDING_CACHE.get(setid)
    if cached is not None and len(cached) == len(sections):
        return cached

    embeddings = [
        embed_question(f"{section.get('title', '')}\n{section.get('text', '')}")
        for section in sections
    ]
    _SECTION_EMBEDDING_CACHE[setid] = embeddings
    return embeddings


def _evidence_response(
    *,
    status: str,
    query: str,
    results: list[dict],
    error: str | None,
) -> dict:
    return {
        "status": status,
        "source": "dailymed",
        "query": query,
        "results": results,
        "error": error,
    }


def retrieve_dailymed_evidence(
    query: str,
    product_name: str,
    top_k: int = 3,
) -> dict:
    """Return top DailyMed sections for a supported product as bounded evidence."""
    query = (query or "").strip()
    top_k = max(1, min(int(top_k), 3))

    try:
        setid = resolve_supported_setid(product_name)
        if setid is None:
            return _evidence_response(
                status="no_results",
                query=query,
                results=[],
                error=None,
            )

        label = get_dailymed_label(setid)
        if label.get("status") != "ok":
            logger.error(
                "DailyMed label retrieval failed for setid=%s",
                setid,
            )
            return _evidence_response(
                status="error",
                query=query,
                results=[],
                error="DailyMed label retrieval failed.",
            )

        sections = label.get("sections") or []
        if not sections:
            return _evidence_response(
                status="no_results",
                query=query,
                results=[],
                error=None,
            )

        query_embedding = embed_question(query)
        section_embeddings = _get_cached_section_embeddings(setid, sections)

        ranked: list[tuple[float, dict]] = []
        for section, embedding in zip(sections, section_embeddings):
            score = _cosine_similarity(query_embedding, embedding)
            ranked.append((score, section))

        ranked.sort(key=lambda item: item[0], reverse=True)
        top = ranked[:top_k]

        results = [
            {
                "text": section.get("text", ""),
                "score": score,
                "metadata": {
                    "setid": setid,
                    "title": section.get("title", ""),
                    "section_name": section.get("title", ""),
                    "spl_version": None,
                    "published_date": None,
                },
            }
            for score, section in top
        ]

        if not results:
            return _evidence_response(
                status="no_results",
                query=query,
                results=[],
                error=None,
            )

        return _evidence_response(
            status="ok",
            query=query,
            results=results,
            error=None,
        )
    except Exception:
        logger.exception("DailyMed evidence retrieval failed.")
        return _evidence_response(
            status="error",
            query=query,
            results=[],
            error="DailyMed evidence retrieval failed.",
        )
