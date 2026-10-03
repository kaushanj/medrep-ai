"""Shared chat/agent response and citation helpers."""

CITATION_FIELDS = (
    "product_name",
    "document_type",
    "source_filename",
    "s3_key",
    "page_number",
    "section_name",
    "document_version",
    "effective_date",
)


def citation_from_fields(data: dict) -> dict:
    return {field: data.get(field) for field in CITATION_FIELDS}


def citation_dedupe_key(citation: dict, fallback_source: str = "") -> tuple:
    identity = (
        citation.get("s3_key")
        or citation.get("source_filename")
        or citation.get("product_name")
        or fallback_source
        or ""
    )
    return (
        identity,
        citation.get("page_number"),
        citation.get("section_name"),
    )


def join_unique_labels(values: list[str]) -> str:
    labels: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        labels.append(value)
    return ", ".join(labels)


def build_chat_result(
    answer: str,
    *,
    source: str | None = "",
    citations: list[dict] | None = None,
    context: str | None = None,
) -> dict:
    result = {
        "answer": answer,
        "source": source,
        "citations": list(citations or []),
    }
    if context is not None:
        result["context"] = context
    return result
