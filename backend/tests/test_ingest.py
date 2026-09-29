from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from services import ingest


# --- chunk_text boundaries (chunk_size min=1; overlap in [0, chunk_size)) ---


def test_chunk_text_chunk_size_minimum_is_valid():
    assert ingest.chunk_text("ab", chunk_size=1, chunk_overlap=0) == ["a", "b"]


def test_chunk_text_chunk_size_one_below_minimum_raises():
    with pytest.raises(ValueError, match="chunk_size"):
        ingest.chunk_text("ab", chunk_size=0, chunk_overlap=0)


def test_chunk_text_overlap_minimum_is_valid():
    chunks = ingest.chunk_text("abcdef", chunk_size=3, chunk_overlap=0)
    assert chunks == ["abc", "def"]


def test_chunk_text_overlap_one_below_minimum_raises():
    with pytest.raises(ValueError, match="chunk_overlap"):
        ingest.chunk_text("abcdef", chunk_size=3, chunk_overlap=-1)


def test_chunk_text_overlap_maximum_is_valid():
    # max overlap = chunk_size - 1
    chunks = ingest.chunk_text("abcdef", chunk_size=3, chunk_overlap=2)
    assert chunks == ["abc", "bcd", "cde", "def"]


def test_chunk_text_overlap_one_above_maximum_raises():
    with pytest.raises(ValueError, match="chunk_overlap"):
        ingest.chunk_text("abcdef", chunk_size=3, chunk_overlap=3)


def test_chunk_text_empty_returns_no_chunks():
    assert ingest.chunk_text("", chunk_size=500, chunk_overlap=50) == []


def test_chunk_text_shorter_than_size_returns_single_chunk():
    assert ingest.chunk_text("short", chunk_size=500, chunk_overlap=50) == ["short"]


def test_chunk_text_exact_size_returns_single_chunk():
    text = "x" * 500
    assert ingest.chunk_text(text, chunk_size=500, chunk_overlap=50) == [text]


def test_chunk_text_one_above_size_returns_overlapping_chunks():
    text = "x" * 501
    chunks = ingest.chunk_text(text, chunk_size=500, chunk_overlap=50)
    assert len(chunks) == 2
    assert chunks[0] == "x" * 500
    assert chunks[1] == "x" * 51  # overlap 50 + 1 new char
    assert chunks[0][-50:] == chunks[1][:50]


def test_chunk_text_uses_documented_defaults():
    assert ingest.DEFAULT_CHUNK_SIZE == 500
    assert ingest.DEFAULT_CHUNK_OVERLAP == 50


# --- extract / download / index pipeline (mocked) ---


def test_extract_text_from_pdf_concatenates_pages():
    pdf_bytes = b"%PDF-fake"
    page1 = MagicMock()
    page1.extract_text.return_value = "Page one."
    page2 = MagicMock()
    page2.extract_text.return_value = "Page two."
    reader = MagicMock()
    reader.pages = [page1, page2]

    with patch("services.ingest.PdfReader", return_value=reader) as mock_reader:
        text = ingest.extract_text_from_pdf(pdf_bytes)

    mock_reader.assert_called_once()
    call_arg = mock_reader.call_args[0][0]
    assert isinstance(call_arg, BytesIO)
    assert call_arg.getvalue() == pdf_bytes
    assert text == "Page one.\nPage two."


def test_download_pdf_from_s3_reads_object_body():
    body = MagicMock()
    body.read.return_value = b"pdf-bytes"
    s3 = MagicMock()
    s3.get_object.return_value = {"Body": body}

    with patch("services.ingest.boto3.client", return_value=s3) as mock_client:
        result = ingest.download_pdf_from_s3("my-bucket", "Demo-pain-relief.pdf")

    mock_client.assert_called_once_with("s3")
    s3.get_object.assert_called_once_with(
        Bucket="my-bucket",
        Key="Demo-pain-relief.pdf",
    )
    assert result == b"pdf-bytes"


def _ready_opensearch_mock(*, indexed_count: int = 2, source: str = "Demo-pain-relief.pdf"):
    """OpenSearch mock that passes mapping validation and post-index verification."""
    opensearch = MagicMock()
    opensearch.indices.exists.return_value = True
    opensearch.indices.get_mapping.return_value = {
        "medrep-index": {
            "mappings": {
                "properties": {
                    "embedding": {"type": "knn_vector", "dimension": 1024},
                    "source": {"type": "keyword"},
                    "text": {"type": "text"},
                }
            }
        }
    }
    opensearch.count.return_value = {"count": indexed_count}
    opensearch.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "text": "chunk",
                        "source": source,
                        "embedding": [0.1],
                    }
                }
            ]
        }
    }
    return opensearch


def test_ensure_index_ready_accepts_knn_vector_mapping():
    client = MagicMock()
    client.indices.exists.return_value = True
    client.indices.get_mapping.return_value = {
        "medrep-index": {
            "mappings": {
                "properties": {
                    "embedding": {"type": "knn_vector", "dimension": 1024},
                    "source": {"type": "keyword"},
                    "text": {"type": "text"},
                }
            }
        }
    }
    ingest.ensure_index_ready(client, "medrep-index")


def test_ensure_index_ready_raises_when_index_missing():
    client = MagicMock()
    client.indices.exists.return_value = False
    with pytest.raises(RuntimeError, match="does not exist"):
        ingest.ensure_index_ready(client, "medrep-index")


def test_ensure_index_ready_raises_when_embedding_not_knn_vector():
    client = MagicMock()
    client.indices.exists.return_value = True
    client.indices.get_mapping.return_value = {
        "medrep-index": {
            "mappings": {
                "properties": {
                    "embedding": {"type": "float"},
                    "source": {"type": "keyword"},
                    "text": {"type": "text"},
                }
            }
        }
    }
    with pytest.raises(RuntimeError, match="knn_vector"):
        ingest.ensure_index_ready(client, "medrep-index")


def test_ensure_index_ready_raises_when_embedding_field_missing():
    client = MagicMock()
    client.indices.exists.return_value = True
    client.indices.get_mapping.return_value = {
        "medrep-index": {
            "mappings": {
                "properties": {
                    "source": {"type": "keyword"},
                    "text": {"type": "text"},
                }
            }
        }
    }
    with pytest.raises(RuntimeError, match="embedding"):
        ingest.ensure_index_ready(client, "medrep-index")


def test_ensure_index_ready_raises_when_source_missing():
    client = MagicMock()
    client.indices.exists.return_value = True
    client.indices.get_mapping.return_value = {
        "medrep-index": {
            "mappings": {
                "properties": {
                    "embedding": {"type": "knn_vector", "dimension": 1024},
                    "text": {"type": "text"},
                }
            }
        }
    }
    with pytest.raises(RuntimeError, match="source"):
        ingest.ensure_index_ready(client, "medrep-index")


def test_ensure_index_ready_raises_when_source_is_text_without_keyword():
    """Exact filename term queries need a keyword field; plain text mapping is invalid."""
    client = MagicMock()
    client.indices.exists.return_value = True
    client.indices.get_mapping.return_value = {
        "medrep-index": {
            "mappings": {
                "properties": {
                    "embedding": {"type": "knn_vector", "dimension": 1024},
                    "source": {"type": "text"},
                    "text": {"type": "text"},
                }
            }
        }
    }
    with pytest.raises(RuntimeError, match="keyword"):
        ingest.ensure_index_ready(client, "medrep-index")


def test_ensure_index_ready_accepts_source_text_with_keyword_subfield():
    """Dynamic text+.keyword mappings are usable via source.keyword."""
    client = MagicMock()
    client.indices.exists.return_value = True
    client.indices.get_mapping.return_value = {
        "medrep-index": {
            "mappings": {
                "properties": {
                    "embedding": {"type": "knn_vector", "dimension": 1024},
                    "source": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "text": {"type": "text"},
                }
            }
        }
    }
    ingest.ensure_index_ready(client, "medrep-index")


def test_source_keyword_field_prefers_top_level_keyword():
    assert (
        ingest.source_keyword_field(
            {"source": {"type": "keyword"}, "text": {"type": "text"}}
        )
        == "source"
    )


def test_source_keyword_field_uses_keyword_subfield_for_text_mapping():
    assert (
        ingest.source_keyword_field(
            {
                "source": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword"}},
                }
            }
        )
        == "source.keyword"
    )


def test_verify_indexed_documents_returns_count_when_present_and_retrievable():
    client = MagicMock()
    client.indices.exists.return_value = True
    client.indices.get_mapping.return_value = {
        "medrep-index": {
            "mappings": {
                "properties": {
                    "embedding": {"type": "knn_vector", "dimension": 1024},
                    "source": {"type": "keyword"},
                    "text": {"type": "text"},
                }
            }
        }
    }
    client.count.return_value = {"count": 3}
    client.search.return_value = {
        "hits": {
            "hits": [
                {"_source": {"text": "a", "source": "Demo-pain-relief.pdf"}},
            ]
        }
    }
    assert (
        ingest.verify_indexed_documents(
            client,
            "medrep-index",
            source="Demo-pain-relief.pdf",
            min_count=1,
        )
        == 3
    )
    count_body = client.count.call_args.kwargs.get("body") or client.count.call_args[1]["body"]
    assert count_body["query"] == {"term": {"source": "Demo-pain-relief.pdf"}}
    client.search.assert_called()


def test_verify_indexed_documents_queries_source_keyword_subfield():
    client = MagicMock()
    client.indices.exists.return_value = True
    client.indices.get_mapping.return_value = {
        "medrep-index": {
            "mappings": {
                "properties": {
                    "embedding": {"type": "knn_vector", "dimension": 1024},
                    "source": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "text": {"type": "text"},
                }
            }
        }
    }
    client.count.return_value = {"count": 1}
    client.search.return_value = {
        "hits": {
            "hits": [
                {"_source": {"text": "a", "source": "Demo-pain-relief.pdf"}},
            ]
        }
    }
    assert (
        ingest.verify_indexed_documents(
            client,
            "medrep-index",
            source="Demo-pain-relief.pdf",
            min_count=1,
        )
        == 1
    )
    count_body = client.count.call_args.kwargs.get("body") or client.count.call_args[1]["body"]
    assert count_body["query"] == {
        "term": {"source.keyword": "Demo-pain-relief.pdf"}
    }


def _keyword_source_mapping(index: str = "medrep-index") -> dict:
    return {
        index: {
            "mappings": {
                "properties": {
                    "embedding": {"type": "knn_vector", "dimension": 1024},
                    "source": {"type": "keyword"},
                    "text": {"type": "text"},
                }
            }
        }
    }


def test_verify_indexed_documents_raises_when_count_zero():
    client = MagicMock()
    client.indices.get_mapping.return_value = _keyword_source_mapping()
    client.count.return_value = {"count": 0}
    with pytest.raises(RuntimeError, match="count"):
        ingest.verify_indexed_documents(
            client,
            "medrep-index",
            source="Demo-pain-relief.pdf",
            min_count=1,
            retries=1,
            delay_seconds=0,
        )


def test_verify_indexed_documents_raises_when_not_retrievable():
    client = MagicMock()
    client.indices.get_mapping.return_value = _keyword_source_mapping()
    client.count.return_value = {"count": 2}
    client.search.return_value = {"hits": {"hits": []}}
    with pytest.raises(RuntimeError, match="retriev"):
        ingest.verify_indexed_documents(
            client,
            "medrep-index",
            source="Demo-pain-relief.pdf",
            min_count=1,
            retries=1,
            delay_seconds=0,
        )


def test_ingest_pdf_indexes_chunks_with_text_source_and_embedding():
    pdf_bytes = b"%PDF"
    extracted = "A" * 501
    embedding = [0.1, 0.2, 0.3]
    indexed_bodies = []

    opensearch = _ready_opensearch_mock(indexed_count=2)

    def capture_index(**kwargs):
        indexed_bodies.append(kwargs)
        return {"result": "created"}

    opensearch.index.side_effect = capture_index

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=pdf_bytes) as mock_download,
        patch("services.ingest.extract_text_from_pdf", return_value=extracted) as mock_extract,
        patch("services.ingest.embed_text", return_value=embedding) as mock_embed,
        patch("services.ingest.opensearch_client", return_value=opensearch),
        patch.dict(
            "os.environ",
            {"OPENSEARCH_INDEX": "medrep-index"},
            clear=False,
        ),
    ):
        count = ingest.ingest_pdf("bucket", "Demo-pain-relief.pdf")

    mock_download.assert_called_once_with("bucket", "Demo-pain-relief.pdf")
    mock_extract.assert_called_once_with(pdf_bytes)
    assert count == 2
    assert mock_embed.call_count == 2
    assert opensearch.index.call_count == 2
    opensearch.indices.exists.assert_called()
    # Post-index verify must require the number of chunks written.
    count_body = opensearch.count.call_args.kwargs.get("body") or opensearch.count.call_args[1].get("body")
    assert count_body is not None or opensearch.count.called
    opensearch.count.assert_called()
    for kwargs in indexed_bodies:
        assert kwargs["index"] == "medrep-index"
        body = kwargs["body"]
        assert set(body.keys()) == {"text", "source", "embedding"}
        assert body["source"] == "Demo-pain-relief.pdf"
        assert body["embedding"] == embedding
        assert isinstance(body["text"], str)
        assert body["text"]
        assert "id" in kwargs


def test_ingest_pdf_verifies_min_count_equals_chunk_count():
    opensearch = _ready_opensearch_mock(indexed_count=2)
    opensearch.index.return_value = {"result": "created"}

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch("services.ingest.extract_text_from_pdf", return_value="A" * 501),
        patch("services.ingest.embed_text", return_value=[0.1]),
        patch("services.ingest.opensearch_client", return_value=opensearch),
        patch("services.ingest.verify_indexed_documents", return_value=2) as mock_verify,
    ):
        count = ingest.ingest_pdf("bucket", "Demo-pain-relief.pdf")

    assert count == 2
    assert mock_verify.call_args.kwargs["min_count"] == 2
    assert mock_verify.call_args.kwargs["source"] == "Demo-pain-relief.pdf"


def test_ingest_pdf_defaults_index_to_medrep_index():
    opensearch = _ready_opensearch_mock(indexed_count=1, source="file.pdf")
    opensearch.index.return_value = {"result": "created"}
    # mapping key must match default index name used when env cleared
    opensearch.indices.get_mapping.return_value = {
        "medrep-index": {
            "mappings": {
                "properties": {
                    "embedding": {"type": "knn_vector", "dimension": 1024},
                    "source": {"type": "keyword"},
                    "text": {"type": "text"},
                }
            }
        }
    }

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch("services.ingest.extract_text_from_pdf", return_value="short text"),
        patch("services.ingest.embed_text", return_value=[0.5]),
        patch("services.ingest.opensearch_client", return_value=opensearch),
        patch.dict("os.environ", {}, clear=True),
    ):
        count = ingest.ingest_pdf("b", "file.pdf")

    assert count == 1
    assert opensearch.index.call_args.kwargs["index"] == "medrep-index"
    assert opensearch.index.call_args.kwargs["body"]["source"] == "file.pdf"


def test_ingest_pdf_empty_extraction_indexes_nothing():
    opensearch = MagicMock()

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch("services.ingest.extract_text_from_pdf", return_value=""),
        patch("services.ingest.embed_text") as mock_embed,
        patch("services.ingest.opensearch_client", return_value=opensearch),
    ):
        count = ingest.ingest_pdf("bucket", "empty.pdf")

    assert count == 0
    mock_embed.assert_not_called()
    opensearch.index.assert_not_called()
    opensearch.indices.exists.assert_not_called()


def test_ingest_pdf_aborts_when_index_not_ready():
    opensearch = MagicMock()
    opensearch.indices.exists.return_value = False

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch("services.ingest.extract_text_from_pdf", return_value="text"),
        patch("services.ingest.embed_text") as mock_embed,
        patch("services.ingest.opensearch_client", return_value=opensearch),
    ):
        with pytest.raises(RuntimeError, match="does not exist"):
            ingest.ingest_pdf("bucket", "Demo-pain-relief.pdf")

    mock_embed.assert_not_called()
    opensearch.index.assert_not_called()


def test_ingest_pdf_raises_when_verification_fails():
    opensearch = _ready_opensearch_mock(indexed_count=0)
    opensearch.index.return_value = {"result": "created"}
    opensearch.count.return_value = {"count": 0}

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch("services.ingest.extract_text_from_pdf", return_value="chunk text"),
        patch("services.ingest.embed_text", return_value=[0.1]),
        patch("services.ingest.opensearch_client", return_value=opensearch),
        patch("services.ingest.verify_indexed_documents", side_effect=RuntimeError("count is 0")),
    ):
        with pytest.raises(RuntimeError, match="count"):
            ingest.ingest_pdf("bucket", "Demo-pain-relief.pdf")
