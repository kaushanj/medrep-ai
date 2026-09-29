import json
from pathlib import Path
from unittest.mock import patch

import pytest

from handlers import s3_ingest

FIXTURES = Path(__file__).parent / "fixtures"


def _sample_event(**overrides):
    with open(FIXTURES / "s3_object_created.json", encoding="utf-8") as f:
        event = json.load(f)
    event.update(overrides)
    return event


def test_handler_calls_ingest_pdf_with_bucket_and_key():
    event = _sample_event()

    with patch("handlers.s3_ingest.ingest_pdf", return_value=2) as mock_ingest:
        s3_ingest.handler(event, None)

    mock_ingest.assert_called_once_with("medrep-product-pdfs", "Demo-pain-relief.pdf")


def test_handler_url_decodes_object_key():
    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "medrep-product-pdfs"},
                    "object": {"key": "folder/Demo+pain%2Frelief.pdf"},
                }
            }
        ]
    }

    with patch("handlers.s3_ingest.ingest_pdf", return_value=1) as mock_ingest:
        s3_ingest.handler(event, None)

    mock_ingest.assert_called_once_with(
        "medrep-product-pdfs",
        "folder/Demo pain/relief.pdf",
    )


def test_handler_skips_non_pdf_without_calling_ingest():
    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "medrep-product-pdfs"},
                    "object": {"key": "notes.txt"},
                }
            }
        ]
    }

    with patch("handlers.s3_ingest.ingest_pdf") as mock_ingest:
        s3_ingest.handler(event, None)

    mock_ingest.assert_not_called()


def test_handler_propagates_ingest_exception():
    event = _sample_event()

    with patch(
        "handlers.s3_ingest.ingest_pdf",
        side_effect=RuntimeError("index missing"),
    ):
        with pytest.raises(RuntimeError, match="index missing"):
            s3_ingest.handler(event, None)


def test_handler_processes_each_pdf_in_multi_record_event():
    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket-a"},
                    "object": {"key": "a.pdf"},
                }
            },
            {
                "s3": {
                    "bucket": {"name": "bucket-a"},
                    "object": {"key": "skip.txt"},
                }
            },
            {
                "s3": {
                    "bucket": {"name": "bucket-b"},
                    "object": {"key": "b.pdf"},
                }
            },
        ]
    }

    with patch("handlers.s3_ingest.ingest_pdf", return_value=1) as mock_ingest:
        s3_ingest.handler(event, None)

    assert mock_ingest.call_count == 2
    mock_ingest.assert_any_call("bucket-a", "a.pdf")
    mock_ingest.assert_any_call("bucket-b", "b.pdf")
