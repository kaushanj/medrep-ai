"""Ingest product PDFs from S3 into OpenSearch for RAG.

Flow: S3 PDF → extract pages (PyPDF) → clean → token chunk → Titan embed → OpenSearch.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
import sys
import time
from io import BytesIO
from pathlib import Path

import boto3
from dotenv import load_dotenv
from pypdf import PdfReader

from repositories.opensearch import opensearch_client
from services.rag import embed_question

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 400
DEFAULT_CHUNK_OVERLAP = 40
DEFAULT_INDEX = "medrep-index"
DEFAULT_DEMO_KEY = "Demo-pain-relief.pdf"
REQUIRED_EMBEDDING_TYPE = "knn_vector"

METADATA_FIELD_TYPES: dict[str, str] = {
    "document_id": "keyword",
    "chunk_id": "keyword",
    "product_name": "keyword",
    "document_type": "keyword",
    "source_filename": "keyword",
    "s3_key": "keyword",
    "page_number": "integer",
    "section_name": "keyword",
    "document_version": "keyword",
    "effective_date": "keyword",
}

_SECTION_HEADING_RE = re.compile(
    r"^(?:"
    r"\d+\.\s+\S.+"          # 1. NAME...
    r"|"
    r"\d+(?:\.\d+)+\s+\S.+" # 4.1 Therapeutic...
    r"|"
    r"[A-Z][A-Z0-9\s\-/,&()]{2,100}"
    r")$"
)
_VERSION_RE = re.compile(
    r"(?i)\bversion\s*[:\s]\s*([vV]?\d+(?:\.\d+)*)",
)
_EFFECTIVE_DATE_RE = re.compile(
    r"(?i)(?:effective|revision)\s*date\s*[:\s]\s*"
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
)
_HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")


def token_count(text: str) -> int:
    if not text or not text.strip():
        return 0
    return len(text.split())


def clean_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace("\x00", "").replace("\f", "\n").replace("\r\n", "\n")
    cleaned = cleaned.replace("\r", "\n").replace("\t", " ")
    cleaned = _HYPHEN_BREAK_RE.sub(r"\1\2", cleaned)
    lines = [" ".join(line.split()) for line in cleaned.split("\n")]
    collapsed: list[str] = []
    blank_pending = False
    for line in lines:
        if not line:
            blank_pending = True
            continue
        if collapsed and blank_pending:
            collapsed.append("")
        collapsed.append(line)
        blank_pending = False
    return "\n".join(collapsed).strip()


def _validate_chunk_params(chunk_size: int, chunk_overlap: int) -> None:
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size")


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def _sliding_token_windows(
    tokens: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Split tokens into overlapping windows of at most chunk_size tokens."""
    if not tokens:
        return []
    _validate_chunk_params(chunk_size, chunk_overlap)
    step = chunk_size - chunk_overlap
    chunks: list[str] = []
    start = 0
    length = len(tokens)
    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(" ".join(tokens[start:end]))
        if end == length:
            break
        start += step
    return chunks


def _split_oversized_unit(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Split text that exceeds chunk_size on sentences, then overlapping words."""
    if token_count(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks: list[str] = []
    pending_sentences: list[str] = []

    def flush_sentences() -> None:
        nonlocal pending_sentences
        if pending_sentences:
            chunks.extend(_pack_pieces(pending_sentences, chunk_size, chunk_overlap))
            pending_sentences = []

    for sentence in _split_sentences(text):
        if token_count(sentence) <= chunk_size:
            pending_sentences.append(sentence)
            continue
        flush_sentences()
        chunks.extend(
            _sliding_token_windows(sentence.split(), chunk_size, chunk_overlap)
        )
    flush_sentences()
    return chunks


def _overlap_prefix(text: str, overlap: int) -> str:
    if overlap <= 0 or not text:
        return ""
    tokens = text.split()
    if not tokens:
        return ""
    return " ".join(tokens[-overlap:])


def _pack_pieces(
    pieces: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Greedily pack pieces under the token budget, preferring piece boundaries."""
    if not pieces:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    pending_overlap: str | None = None

    def apply_pending() -> None:
        nonlocal current, current_tokens, pending_overlap
        if pending_overlap and not current:
            current = [pending_overlap]
            current_tokens = token_count(pending_overlap)
            pending_overlap = None

    def emit(*, seed_overlap: bool) -> None:
        nonlocal current, current_tokens, pending_overlap
        if not current:
            return
        chunks.append(" ".join(current))
        current = []
        current_tokens = 0
        if seed_overlap and chunk_overlap > 0:
            pending_overlap = _overlap_prefix(chunks[-1], chunk_overlap) or None
        else:
            pending_overlap = None

    for part in pieces:
        part = part.strip()
        if not part:
            continue
        part_tokens = token_count(part)
        apply_pending()

        if part_tokens > chunk_size:
            if current:
                emit(seed_overlap=False)
            pending_overlap = None
            chunks.extend(
                _sliding_token_windows(part.split(), chunk_size, chunk_overlap)
            )
            pending_overlap = (
                _overlap_prefix(chunks[-1], chunk_overlap) if chunks else None
            ) or None
            continue

        if current and current_tokens + part_tokens > chunk_size:
            emit(seed_overlap=True)
            apply_pending()
            if current and current_tokens + part_tokens > chunk_size:
                pending_overlap = None
                current = []
                current_tokens = 0

        current.append(part)
        current_tokens += part_tokens

    if current:
        emit(seed_overlap=False)
    return chunks


def _pack_token_chunks(
    units: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Pack paragraph units preferring boundaries under the token budget.

    Whole paragraphs stay together when they fit. Oversized paragraphs are split
    on sentences, then words (with token overlap). Never fixed character cuts.
    """
    _validate_chunk_params(chunk_size, chunk_overlap)
    if not units:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    pending_overlap: str | None = None

    def apply_pending() -> None:
        nonlocal current, current_tokens, pending_overlap
        if pending_overlap and not current:
            current = [pending_overlap]
            current_tokens = token_count(pending_overlap)
            pending_overlap = None

    def emit(*, seed_overlap: bool) -> None:
        nonlocal current, current_tokens, pending_overlap
        if not current:
            return
        chunks.append(" ".join(current))
        current = []
        current_tokens = 0
        if seed_overlap and chunk_overlap > 0:
            pending_overlap = _overlap_prefix(chunks[-1], chunk_overlap) or None
        else:
            pending_overlap = None

    for unit in units:
        unit = unit.strip()
        if not unit:
            continue
        unit_tokens = token_count(unit)
        apply_pending()

        if unit_tokens > chunk_size:
            if current:
                emit(seed_overlap=False)
            pending_overlap = None
            oversized_chunks = _split_oversized_unit(
                unit, chunk_size, chunk_overlap
            )
            chunks.extend(oversized_chunks)
            pending_overlap = (
                _overlap_prefix(chunks[-1], chunk_overlap)
                if chunks and chunk_overlap > 0
                else None
            ) or None
            continue

        if current and current_tokens + unit_tokens > chunk_size:
            emit(seed_overlap=True)
            apply_pending()
            if current and current_tokens + unit_tokens > chunk_size:
                pending_overlap = None
                current = []
                current_tokens = 0

        current.append(unit)
        current_tokens += unit_tokens

    if current:
        emit(seed_overlap=False)
    return chunks


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into paragraph-aware, whitespace-token-sized chunks."""
    _validate_chunk_params(chunk_size, chunk_overlap)
    cleaned = clean_text(text) if text else ""
    if not cleaned:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    if not paragraphs:
        return []
    return _pack_token_chunks(paragraphs, chunk_size, chunk_overlap)


def _is_section_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return False
    if token_count(stripped) > 20:
        return False
    return bool(_SECTION_HEADING_RE.match(stripped))


def _units_from_pages(pages: list[dict]) -> list[dict]:
    """Build paragraph units with page_number and optional section_name."""
    units: list[dict] = []
    current_section: str | None = None

    for page in pages:
        page_number = int(page["page_number"])
        cleaned = clean_text(page.get("text") or "")
        if not cleaned:
            continue

        blocks = re.split(r"\n\s*\n", cleaned)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.split("\n")
            if len(lines) == 1 and _is_section_heading(lines[0]):
                current_section = lines[0].strip()
                continue
            # heading as first line of a multi-line block
            if len(lines) > 1 and _is_section_heading(lines[0]):
                current_section = lines[0].strip()
                body = "\n".join(lines[1:]).strip()
                if body:
                    units.append(
                        {
                            "text": body,
                            "page_number": page_number,
                            "section_name": current_section,
                        }
                    )
                continue
            units.append(
                {
                    "text": block,
                    "page_number": page_number,
                    "section_name": current_section,
                }
            )
    return units


def _section_runs(units: list[dict]) -> list[list[dict]]:
    """Group consecutive units that share the same section_name."""
    runs: list[list[dict]] = []
    current: list[dict] = []
    current_section: object | None = object()  # sentinel ≠ any real section
    for unit in units:
        section = unit.get("section_name")
        if current and section != current_section:
            runs.append(current)
            current = []
        current.append(unit)
        current_section = section
    if current:
        runs.append(current)
    return runs


def chunk_pages(
    pages: list[dict],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    """Chunk page records into token-sized chunks with page/section metadata.

    Page boundaries are hard breaks so each chunk's ``page_number`` reflects
    content from that page. Section changes within a page are also hard breaks
    so ``section_name`` stays correct. Token overlap applies within a section.
    """
    _validate_chunk_params(chunk_size, chunk_overlap)
    units = _units_from_pages(pages)
    if not units:
        return []

    chunks: list[dict] = []
    # Group units by page to preserve page_number on every chunk
    by_page: dict[int, list[dict]] = {}
    page_order: list[int] = []
    for unit in units:
        page_number = int(unit["page_number"])
        if page_number not in by_page:
            by_page[page_number] = []
            page_order.append(page_number)
        by_page[page_number].append(unit)

    for page_number in page_order:
        for run in _section_runs(by_page[page_number]):
            texts = [u["text"] for u in run]
            section_name = run[0].get("section_name")
            for text in _pack_token_chunks(texts, chunk_size, chunk_overlap):
                chunk: dict = {"text": text, "page_number": page_number}
                if section_name:
                    chunk["section_name"] = section_name
                chunks.append(chunk)
    return chunks


def extract_pages_from_pdf(pdf_bytes: bytes) -> list[dict]:
    """Return ordered page records with 1-based page_number and raw text."""
    reader = PdfReader(BytesIO(pdf_bytes))
    pages: list[dict] = []
    for i, page in enumerate(reader.pages, start=1):
        pages.append({"page_number": i, "text": page.extract_text() or ""})
    return pages


def make_document_id(s3_key: str) -> str:
    return hashlib.sha256(s3_key.encode("utf-8")).hexdigest()


def make_chunk_id(document_id: str, index: int) -> str:
    return f"{document_id}:{index:04d}"


def product_name_from_key(s3_key: str) -> str:
    parts = Path(s3_key).parts
    if len(parts) > 1:
        return parts[0]
    return Path(s3_key).stem


def extract_document_version(text: str) -> str | None:
    match = _VERSION_RE.search(text or "")
    return match.group(1) if match else None


def extract_effective_date(text: str) -> str | None:
    match = _EFFECTIVE_DATE_RE.search(text or "")
    return match.group(1) if match else None


def download_pdf_from_s3(bucket: str, key: str) -> bytes:
    client = boto3.client("s3")
    response = client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def embed_text(text: str) -> list[float]:
    return embed_question(text)


def _mapping_properties(mapping_response: dict, index: str) -> dict:
    index_mapping = mapping_response.get(index) or next(
        iter(mapping_response.values()),
        {},
    )
    return index_mapping.get("mappings", {}).get("properties", {})


def source_keyword_field(properties: dict) -> str:
    """Return the field path for exact filename term queries on ``source``.

    Prefers a top-level keyword mapping; falls back to ``source.keyword`` when
    dynamic text+.keyword mapping is present.
    """
    source = properties.get("source")
    if source is None:
        raise RuntimeError(
            "missing required field 'source'. "
            "Expected type 'keyword' (or text with a keyword subfield) "
            "for exact filename queries."
        )

    src_type = source.get("type")
    if src_type == "keyword":
        return "source"

    keyword_sub = (source.get("fields") or {}).get("keyword")
    if keyword_sub is not None and keyword_sub.get("type") == "keyword":
        return "source.keyword"

    raise RuntimeError(
        "field 'source' must be type 'keyword' "
        "(or text with a keyword subfield) for exact filename term queries; "
        f"got type {src_type!r}."
    )


def _resolve_chunk_settings(
    chunk_size: int | None,
    chunk_overlap: int | None,
) -> tuple[int, int]:
    size = (
        chunk_size
        if chunk_size is not None
        else int(os.environ.get("INGEST_CHUNK_SIZE") or DEFAULT_CHUNK_SIZE)
    )
    overlap = (
        chunk_overlap
        if chunk_overlap is not None
        else int(os.environ.get("INGEST_CHUNK_OVERLAP") or DEFAULT_CHUNK_OVERLAP)
    )
    _validate_chunk_params(size, overlap)
    return size, overlap


def ensure_index_ready(client, index: str) -> None:
    """Validate knn embedding + keyword source; put_mapping for ingest metadata."""
    if not client.indices.exists(index=index):
        raise RuntimeError(
            f"OpenSearch index {index!r} does not exist. "
            "Create it with a knn_vector embedding mapping before ingesting."
        )

    properties = _mapping_properties(client.indices.get_mapping(index=index), index)
    embedding = properties.get("embedding")
    if embedding is None:
        raise RuntimeError(
            f"OpenSearch index {index!r} is missing required field 'embedding'. "
            f"Expected type {REQUIRED_EMBEDDING_TYPE!r} for RAG retrieval."
        )

    emb_type = embedding.get("type")
    if emb_type != REQUIRED_EMBEDDING_TYPE:
        raise RuntimeError(
            f"OpenSearch index {index!r} field 'embedding' must be "
            f"{REQUIRED_EMBEDDING_TYPE!r} for knn retrieval; got {emb_type!r}."
        )

    try:
        source_keyword_field(properties)
    except RuntimeError as exc:
        raise RuntimeError(f"OpenSearch index {index!r}: {exc}") from exc

    to_add: dict[str, dict[str, str]] = {}
    for field, expected_type in METADATA_FIELD_TYPES.items():
        existing = properties.get(field)
        if existing is None:
            to_add[field] = {"type": expected_type}
            continue
        existing_type = existing.get("type")
        if existing_type != expected_type:
            raise RuntimeError(
                f"OpenSearch index {index!r} field {field!r} has type "
                f"{existing_type!r}; expected {expected_type!r}. "
                "Resolve the mapping conflict before ingesting."
            )

    if to_add:
        try:
            client.indices.put_mapping(index=index, body={"properties": to_add})
        except Exception as exc:
            raise RuntimeError(
                f"OpenSearch index {index!r} put_mapping failed for metadata "
                f"fields {sorted(to_add)}: {exc}"
            ) from exc


def _prior_docs_query(document_id: str, source_filename: str, source_field: str) -> dict:
    """Match current-scheme docs by document_id and legacy docs by source.

    Legacy ingest used ``_id={filename}::{i}`` with a ``source`` field and no
    ``document_id``. Matching source only when ``document_id`` is absent avoids
    deleting newer docs from a different S3 key that share a filename.
    """
    return {
        "bool": {
            "should": [
                {"term": {"document_id": document_id}},
                {
                    "bool": {
                        "must": [{"term": {source_field: source_filename}}],
                        "must_not": [{"exists": {"field": "document_id"}}],
                    }
                },
            ],
            "minimum_should_match": 1,
        }
    }


def delete_documents_for_document_id(
    client,
    index: str,
    document_id: str,
    source_filename: str | None = None,
) -> int:
    """Delete prior chunks for re-index (document_id + legacy source orphans).

    Uses search→delete with refresh between pages so full hit pages do not
    stall or loop on Amazon OpenSearch Serverless. When ``source_filename`` is
    provided, also removes legacy docs for that filename that lack document_id
    (old ``_id={filename}::{i}`` ingest).
    """
    deleted = 0
    seen_ids: set[str] = set()

    if source_filename:
        properties = _mapping_properties(
            client.indices.get_mapping(index=index),
            index,
        )
        source_field = source_keyword_field(properties)
        query = _prior_docs_query(document_id, source_filename, source_field)
    else:
        query = {"term": {"document_id": document_id}}

    while True:
        resp = client.search(
            index=index,
            body={
                "size": 1000,
                "query": query,
                "_source": False,
            },
        )
        hits = resp.get("hits", {}).get("hits", [])
        if not hits:
            break

        new_deletes = 0
        for hit in hits:
            hit_id = hit["_id"]
            if hit_id in seen_ids:
                continue
            seen_ids.add(hit_id)
            client.delete(index=index, id=hit_id)
            deleted += 1
            new_deletes += 1

        try:
            client.indices.refresh(index=index)
        except Exception:
            logger.warning(
                "OpenSearch refresh after delete failed index=%s; continuing",
                index,
                exc_info=True,
            )

        if new_deletes == 0:
            # Hits still visible but already deleted — stop to avoid a loop.
            break

    return deleted


def verify_indexed_documents(
    client,
    index: str,
    *,
    document_id: str,
    expected_count: int,
    retries: int = 15,
    delay_seconds: float = 2.0,
) -> int:
    """Confirm exact document_id count and that docs are searchable."""
    query = {"term": {"document_id": document_id}}
    last_count = 0

    for attempt in range(retries):
        count_resp = client.count(index=index, body={"query": query})
        last_count = int(count_resp.get("count", 0))
        if last_count == expected_count:
            search_resp = client.search(
                index=index,
                body={"size": min(expected_count, 10), "query": query},
            )
            hits = search_resp.get("hits", {}).get("hits", [])
            if hits:
                return last_count
        if attempt + 1 < retries and delay_seconds > 0:
            time.sleep(delay_seconds)

    if last_count == expected_count:
        raise RuntimeError(
            f"OpenSearch index {index!r} reports count={last_count} for "
            f"document_id={document_id!r}, but documents are not retrievable via search."
        )
    raise RuntimeError(
        f"Verification failed: OpenSearch document count for "
        f"document_id={document_id!r} in index {index!r} is {last_count} "
        f"(expected exactly {expected_count})."
    )


def ingest_pdf(
    bucket: str,
    key: str,
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    index: str | None = None,
) -> int:
    logger.info("ingest_pdf start bucket=%s key=%s", bucket, key)
    try:
        size, overlap = _resolve_chunk_settings(chunk_size, chunk_overlap)
        pdf_bytes = download_pdf_from_s3(bucket, key)
        pages = extract_pages_from_pdf(pdf_bytes)
        chunks = chunk_pages(pages, chunk_size=size, chunk_overlap=overlap)

        source_filename = Path(key).name
        document_id = make_document_id(key)
        target_index = index or os.environ.get("OPENSEARCH_INDEX", DEFAULT_INDEX)
        client = opensearch_client()
        ensure_index_ready(client, target_index)
        # Always delete prior/legacy docs before return — including empty extracts
        # so a blank re-upload does not leave stale chunks.
        delete_documents_for_document_id(
            client,
            target_index,
            document_id,
            source_filename=source_filename,
        )

        if not chunks:
            logger.info(
                "ingest_pdf success bucket=%s key=%s chunk_count=0 (empty PDF)",
                bucket,
                key,
            )
            return 0

        product_name = product_name_from_key(key)
        early_text = "\n".join((p.get("text") or "") for p in pages[:3])
        document_version = extract_document_version(early_text)
        effective_date = extract_effective_date(early_text)

        for i, chunk in enumerate(chunks):
            chunk_id = make_chunk_id(document_id, i)
            embedding = embed_text(chunk["text"])
            body: dict = {
                "text": chunk["text"],
                "source": source_filename,
                "embedding": embedding,
                "document_id": document_id,
                "chunk_id": chunk_id,
                "product_name": product_name,
                "document_type": "pdf",
                "source_filename": source_filename,
                "s3_key": key,
                "page_number": chunk["page_number"],
            }
            if chunk.get("section_name"):
                body["section_name"] = chunk["section_name"]
            if document_version:
                body["document_version"] = document_version
            if effective_date:
                body["effective_date"] = effective_date

            client.index(
                index=target_index,
                id=chunk_id,
                body=body,
            )

        verified = verify_indexed_documents(
            client,
            target_index,
            document_id=document_id,
            expected_count=len(chunks),
        )
        logger.info(
            "ingest_pdf success bucket=%s key=%s chunk_count=%s",
            bucket,
            key,
            verified,
        )
        return verified
    except Exception:
        logger.exception("ingest_pdf failure bucket=%s key=%s", bucket, key)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest a product PDF from S3 into OpenSearch.",
    )
    parser.add_argument(
        "--bucket",
        default=os.environ.get("S3_BUCKET"),
        help="S3 bucket containing the PDF (or set S3_BUCKET).",
    )
    parser.add_argument(
        "--key",
        default=os.environ.get("S3_PDF_KEY", DEFAULT_DEMO_KEY),
        help=f"S3 object key (default: {DEFAULT_DEMO_KEY}).",
    )
    parser.add_argument(
        "--index",
        default=None,
        help=f"OpenSearch index (default: OPENSEARCH_INDEX or {DEFAULT_INDEX}).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help=(
            f"Token chunk size (default: INGEST_CHUNK_SIZE or {DEFAULT_CHUNK_SIZE})."
        ),
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=None,
        help=(
            f"Token chunk overlap (default: INGEST_CHUNK_OVERLAP or "
            f"{DEFAULT_CHUNK_OVERLAP})."
        ),
    )
    args = parser.parse_args(argv)

    if not args.bucket:
        print("error: --bucket is required (or set S3_BUCKET)", file=sys.stderr)
        return 2

    count = ingest_pdf(
        args.bucket,
        args.key,
        index=args.index,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print(f"Indexed {count} chunk(s) from {args.key} into OpenSearch.")
    return 0 if count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
