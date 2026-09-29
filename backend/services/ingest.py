"""Ingest product PDFs from S3 into OpenSearch for RAG.

Flow: S3 PDF → extract text (PyPDF) → chunk → Titan embed → OpenSearch.
"""

from __future__ import annotations

import argparse
import logging
import os
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

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_INDEX = "medrep-index"
DEFAULT_DEMO_KEY = "Demo-pain-relief.pdf"
REQUIRED_EMBEDDING_TYPE = "knn_vector"


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size")

    if not text:
        return []

    chunks: list[str] = []
    step = chunk_size - chunk_overlap
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(text[start:end])
        if end == length:
            break
        start += step
    return chunks


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


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


def ensure_index_ready(client, index: str) -> None:
    """Validate that the target index exists with knn embedding and keyword source.

    Does not create infrastructure; fails clearly if mapping assumptions are unmet.
    """
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


def verify_indexed_documents(
    client,
    index: str,
    *,
    source: str,
    min_count: int = 1,
    retries: int = 15,
    delay_seconds: float = 2.0,
) -> int:
    """Confirm documents for source are present and retrievable in OpenSearch."""
    properties = _mapping_properties(client.indices.get_mapping(index=index), index)
    term_field = source_keyword_field(properties)
    query = {"term": {term_field: source}}
    last_count = 0

    for attempt in range(retries):
        count_resp = client.count(index=index, body={"query": query})
        last_count = int(count_resp.get("count", 0))
        if last_count >= min_count:
            search_resp = client.search(
                index=index,
                body={"size": min(min_count, 10), "query": query},
            )
            hits = search_resp.get("hits", {}).get("hits", [])
            if hits:
                return last_count
        if attempt + 1 < retries and delay_seconds > 0:
            time.sleep(delay_seconds)

    if last_count >= min_count:
        raise RuntimeError(
            f"OpenSearch index {index!r} reports count={last_count} for "
            f"source={source!r}, but documents are not retrievable via search."
        )
    raise RuntimeError(
        f"Verification failed: OpenSearch document count for source={source!r} "
        f"in index {index!r} is {last_count} (expected >= {min_count})."
    )


def ingest_pdf(
    bucket: str,
    key: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    index: str | None = None,
) -> int:
    logger.info("ingest_pdf start bucket=%s key=%s", bucket, key)
    try:
        pdf_bytes = download_pdf_from_s3(bucket, key)
        text = extract_text_from_pdf(pdf_bytes)
        chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        if not chunks:
            logger.info(
                "ingest_pdf success bucket=%s key=%s chunk_count=0 (empty PDF)",
                bucket,
                key,
            )
            return 0

        source = Path(key).name
        target_index = index or os.environ.get("OPENSEARCH_INDEX", DEFAULT_INDEX)
        client = opensearch_client()
        ensure_index_ready(client, target_index)

        for i, chunk in enumerate(chunks):
            embedding = embed_text(chunk)
            client.index(
                index=target_index,
                id=f"{source}::{i}",
                body={
                    "text": chunk,
                    "source": source,
                    "embedding": embedding,
                },
            )

        verified = verify_indexed_documents(
            client,
            target_index,
            source=source,
            min_count=len(chunks),
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
    args = parser.parse_args(argv)

    if not args.bucket:
        print("error: --bucket is required (or set S3_BUCKET)", file=sys.stderr)
        return 2

    count = ingest_pdf(args.bucket, args.key, index=args.index)
    print(f"Indexed {count} chunk(s) from {args.key} into OpenSearch.")
    return 0 if count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
