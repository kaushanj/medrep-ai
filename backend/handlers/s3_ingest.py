"""Thin S3 ObjectCreated Lambda entry for PDF ingestion."""

from __future__ import annotations

import logging
import urllib.parse

from services.ingest import ingest_pdf

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        raw_key = record["s3"]["object"]["key"]
        key = urllib.parse.unquote_plus(raw_key)

        if not key.lower().endswith(".pdf"):
            logger.info("Skipping non-PDF key bucket=%s key=%s", bucket, key)
            continue

        logger.info("Ingesting PDF bucket=%s key=%s", bucket, key)
        try:
            count = ingest_pdf(bucket, key)
            logger.info(
                "Ingest complete bucket=%s key=%s chunk_count=%s",
                bucket,
                key,
                count,
            )
        except Exception:
            logger.exception("Ingest failed bucket=%s key=%s", bucket, key)
            raise
