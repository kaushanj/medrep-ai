from io import BytesIO
from unittest.mock import MagicMock, call, patch

import pytest

from services import ingest


# --- clean_text ---


def test_clean_text_collapses_noisy_whitespace_and_nulls():
    raw = "Hello\x00  world\f\n\n\nNext\tline"
    assert ingest.clean_text(raw) == "Hello world\n\nNext line"


def test_clean_text_fixes_hyphenation_at_line_break():
    assert ingest.clean_text("medi-\ncine is used") == "medicine is used"


def test_clean_text_preserves_paragraph_breaks():
    cleaned = ingest.clean_text("Para one.\n\nPara two.")
    assert "\n\n" in cleaned
    assert cleaned == "Para one.\n\nPara two."


# --- token chunk boundaries (chunk_size min=1; overlap in [0, chunk_size)) ---


def test_chunk_text_chunk_size_minimum_is_valid():
    assert ingest.chunk_text("a b", chunk_size=1, chunk_overlap=0) == ["a", "b"]


def test_chunk_text_chunk_size_one_below_minimum_raises():
    with pytest.raises(ValueError, match="chunk_size"):
        ingest.chunk_text("a b", chunk_size=0, chunk_overlap=0)


def test_chunk_text_overlap_minimum_is_valid():
    chunks = ingest.chunk_text("one two three four", chunk_size=2, chunk_overlap=0)
    assert chunks == ["one two", "three four"]


def test_chunk_text_overlap_one_below_minimum_raises():
    with pytest.raises(ValueError, match="chunk_overlap"):
        ingest.chunk_text("one two three", chunk_size=2, chunk_overlap=-1)


def test_chunk_text_overlap_maximum_is_valid():
    # max overlap = chunk_size - 1
    chunks = ingest.chunk_text(
        "one two three four five",
        chunk_size=3,
        chunk_overlap=2,
    )
    assert chunks[0] == "one two three"
    assert chunks[1].split()[:2] == ["two", "three"]
    assert all(len(c.split()) <= 3 for c in chunks)


def test_chunk_text_overlap_one_above_maximum_raises():
    with pytest.raises(ValueError, match="chunk_overlap"):
        ingest.chunk_text("one two three", chunk_size=3, chunk_overlap=3)


def test_chunk_text_empty_returns_no_chunks():
    assert ingest.chunk_text("", chunk_size=400, chunk_overlap=40) == []


def test_chunk_text_shorter_than_size_returns_single_chunk():
    assert ingest.chunk_text("short text here", chunk_size=400, chunk_overlap=40) == [
        "short text here"
    ]


def test_chunk_text_exact_token_size_returns_single_chunk():
    tokens = [f"w{i}" for i in range(400)]
    text = " ".join(tokens)
    assert ingest.chunk_text(text, chunk_size=400, chunk_overlap=40) == [text]


def test_chunk_text_one_above_token_size_returns_overlapping_chunks():
    tokens = [f"w{i}" for i in range(401)]
    text = " ".join(tokens)
    chunks = ingest.chunk_text(text, chunk_size=400, chunk_overlap=40)
    assert len(chunks) == 2
    assert len(chunks[0].split()) == 400
    # overlap 40 + 1 new token
    assert len(chunks[1].split()) == 41
    assert chunks[0].split()[-40:] == chunks[1].split()[:40]


def test_chunk_text_uses_documented_token_defaults():
    assert ingest.DEFAULT_CHUNK_SIZE == 400
    assert ingest.DEFAULT_CHUNK_OVERLAP == 40


def test_chunk_text_old_character_defaults_are_not_token_defaults():
    """Old provisional 500/50 character defaults must not remain as token defaults."""
    assert ingest.DEFAULT_CHUNK_SIZE != 500
    assert ingest.DEFAULT_CHUNK_OVERLAP != 50


# --- paragraph / section packing ---


def test_chunk_text_merges_short_paragraphs_under_token_budget():
    text = "Alpha beta.\n\nGamma delta.\n\nEpsilon zeta."
    chunks = ingest.chunk_text(text, chunk_size=20, chunk_overlap=0)
    assert len(chunks) == 1
    assert "Alpha beta." in chunks[0]
    assert "Epsilon zeta." in chunks[0]


def test_chunk_text_prefers_paragraph_boundaries_under_budget():
    # 8 + 8 tokens; budget 10 → two chunks at paragraph boundary (not mid-paragraph slide)
    para_a = " ".join(f"a{i}" for i in range(8))
    para_b = " ".join(f"b{i}" for i in range(8))
    chunks = ingest.chunk_text(
        f"{para_a}\n\n{para_b}",
        chunk_size=10,
        chunk_overlap=0,
    )
    assert len(chunks) == 2
    assert chunks[0] == para_a
    assert chunks[1] == para_b


def test_chunk_text_splits_oversized_paragraph_on_words_not_fixed_chars():
    words = " ".join(f"word{i}" for i in range(50))
    chunks = ingest.chunk_text(words, chunk_size=10, chunk_overlap=0)
    assert len(chunks) > 1
    assert all(len(c.split()) <= 10 for c in chunks)
    # reassembled tokens match input (no character-window slicing artifacts)
    assert " ".join(chunks).split() == words.split()


def test_numbered_section_heading():
    assert ingest._is_section_heading("1. NAME OF THE MEDICINAL PRODUCT") is True
    assert ingest._is_section_heading("4.1 Therapeutic indications") is True


def test_packaging_text_is_not_section_heading():
    assert ingest._is_section_heading("1 x 1.5 ml") is False


def test_chunk_pages_attaches_section_heading_to_following_chunk():
    pages = [
        {
            "page_number": 1,
            "text": (
                "1. NAME OF THE MEDICINAL PRODUCT\n\n"
                "Ozempic is indicated for treatment.\n\n"
                "More detail about dosing and administration follows here."
            ),
        }
    ]
    chunks = ingest.chunk_pages(pages, chunk_size=400, chunk_overlap=0)
    assert len(chunks) >= 1
    assert chunks[0]["section_name"] == "1. NAME OF THE MEDICINAL PRODUCT"
    assert "Ozempic is indicated" in chunks[0]["text"]
    assert chunks[0]["page_number"] == 1


def test_chunk_pages_preserves_per_section_name_on_multi_section_page():
    pages = [
        {
            "page_number": 1,
            "text": (
                "1. NAME OF THE MEDICINAL PRODUCT\n\n"
                "Ozempic is a medicine for diabetes treatment and care.\n\n"
                "2. QUALITATIVE AND QUANTITATIVE COMPOSITION\n\n"
                "Each pen contains semaglutide solution for injection use."
            ),
        }
    ]
    chunks = ingest.chunk_pages(pages, chunk_size=400, chunk_overlap=0)
    name_chunks = [
        c for c in chunks if c.get("section_name") == "1. NAME OF THE MEDICINAL PRODUCT"
    ]
    comp_chunks = [
        c
        for c in chunks
        if c.get("section_name") == "2. QUALITATIVE AND QUANTITATIVE COMPOSITION"
    ]
    assert name_chunks
    assert comp_chunks
    assert any("Ozempic is a medicine" in c["text"] for c in name_chunks)
    assert any("semaglutide" in c["text"] for c in comp_chunks)
    # No chunk from section 2 incorrectly labeled as section 1
    assert all("semaglutide" not in c["text"] for c in name_chunks)


def test_chunk_pages_preserves_page_number_across_pages():
    pages = [
        {"page_number": 1, "text": "First page content with several words here."},
        {"page_number": 2, "text": "Second page content with several words here."},
    ]
    chunks = ingest.chunk_pages(pages, chunk_size=400, chunk_overlap=0)
    assert any(c["page_number"] == 1 for c in chunks)
    assert any(c["page_number"] == 2 for c in chunks)


# --- page extraction ---


def test_extract_pages_from_pdf_returns_numbered_pages():
    pdf_bytes = b"%PDF-fake"
    page1 = MagicMock()
    page1.extract_text.return_value = "Page one."
    page2 = MagicMock()
    page2.extract_text.return_value = "Page two."
    page3 = MagicMock()
    page3.extract_text.return_value = None  # empty page keeps alignment
    reader = MagicMock()
    reader.pages = [page1, page2, page3]

    with patch("services.ingest.PdfReader", return_value=reader) as mock_reader:
        pages = ingest.extract_pages_from_pdf(pdf_bytes)

    mock_reader.assert_called_once()
    call_arg = mock_reader.call_args[0][0]
    assert isinstance(call_arg, BytesIO)
    assert call_arg.getvalue() == pdf_bytes
    assert pages == [
        {"page_number": 1, "text": "Page one."},
        {"page_number": 2, "text": "Page two."},
        {"page_number": 3, "text": ""},
    ]


# --- ID generation ---


def test_make_document_id_is_deterministic_for_same_key():
    a = ingest.make_document_id("ozempic/Ozempic-SmPC.pdf")
    b = ingest.make_document_id("ozempic/Ozempic-SmPC.pdf")
    assert a == b
    assert isinstance(a, str)
    assert len(a) >= 16


def test_make_document_id_differs_for_different_keys():
    assert ingest.make_document_id("ozempic/a.pdf") != ingest.make_document_id(
        "ozempic/b.pdf"
    )


def test_make_chunk_id_is_stable_for_index():
    doc_id = ingest.make_document_id("ozempic/Ozempic.pdf")
    assert ingest.make_chunk_id(doc_id, 0) == f"{doc_id}:0000"
    assert ingest.make_chunk_id(doc_id, 12) == f"{doc_id}:0012"


# --- metadata helpers ---


def test_product_name_from_first_path_segment():
    assert ingest.product_name_from_key("ozempic/Ozempic-SmPC.pdf") == "ozempic"


def test_product_name_falls_back_to_filename_stem_for_flat_key():
    assert ingest.product_name_from_key("Demo-pain-relief.pdf") == "Demo-pain-relief"


def test_extract_document_version_and_effective_date_best_effort():
    text = "Version: 2.1\nEffective date: 2024-03-15\nBody text."
    assert ingest.extract_document_version(text) == "2.1"
    assert ingest.extract_effective_date(text) == "2024-03-15"


def test_extract_document_version_returns_none_when_unknown():
    assert ingest.extract_document_version("No version here.") is None
    assert ingest.extract_effective_date("No date here.") is None


# --- download ---


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


# --- OpenSearch helpers ---


def _full_mapping(index: str = "medrep-index") -> dict:
    return {
        index: {
            "mappings": {
                "properties": {
                    "embedding": {"type": "knn_vector", "dimension": 1024},
                    "source": {"type": "keyword"},
                    "text": {"type": "text"},
                    "document_id": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "product_name": {"type": "keyword"},
                    "document_type": {"type": "keyword"},
                    "source_filename": {"type": "keyword"},
                    "s3_key": {"type": "keyword"},
                    "page_number": {"type": "integer"},
                    "section_name": {"type": "keyword"},
                    "document_version": {"type": "keyword"},
                    "effective_date": {"type": "keyword"},
                }
            }
        }
    }


def _ready_opensearch_mock(*, indexed_count: int = 2, document_id: str = "doc123"):
    """OpenSearch mock that passes mapping validation and post-index verification."""
    opensearch = MagicMock()
    opensearch.indices.exists.return_value = True
    opensearch.indices.get_mapping.return_value = _full_mapping()
    opensearch.indices.put_mapping.return_value = {"acknowledged": True}
    opensearch.indices.refresh.return_value = {"_shards": {"successful": 1}}
    opensearch.search.return_value = {"hits": {"hits": []}}
    opensearch.delete.return_value = {"result": "deleted"}
    opensearch.count.return_value = {"count": indexed_count}
    # verification search after index (delete lookup returns empty)
    opensearch.search.side_effect = [
        {"hits": {"hits": []}},  # delete lookup
        {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "text": "chunk",
                            "source": "Demo-pain-relief.pdf",
                            "document_id": document_id,
                            "embedding": [0.1],
                        }
                    }
                ]
            }
        },
    ]
    return opensearch


def test_ensure_index_ready_accepts_knn_vector_mapping():
    client = MagicMock()
    client.indices.exists.return_value = True
    client.indices.get_mapping.return_value = _full_mapping()
    client.indices.put_mapping.return_value = {"acknowledged": True}
    ingest.ensure_index_ready(client, "medrep-index")


def test_ensure_index_ready_puts_missing_metadata_fields():
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
    client.indices.put_mapping.return_value = {"acknowledged": True}
    ingest.ensure_index_ready(client, "medrep-index")
    client.indices.put_mapping.assert_called()
    body = (
        client.indices.put_mapping.call_args.kwargs.get("body")
        or client.indices.put_mapping.call_args[1].get("body")
        or client.indices.put_mapping.call_args.kwargs
    )
    props = body.get("properties") if isinstance(body, dict) else None
    if props is None:
        # opensearch-py may pass properties as keyword arg
        props = client.indices.put_mapping.call_args.kwargs.get("properties")
    assert props is not None
    assert props["document_id"]["type"] == "keyword"
    assert props["page_number"]["type"] == "integer"


def test_ensure_index_ready_raises_on_metadata_type_conflict():
    client = MagicMock()
    client.indices.exists.return_value = True
    client.indices.get_mapping.return_value = {
        "medrep-index": {
            "mappings": {
                "properties": {
                    "embedding": {"type": "knn_vector", "dimension": 1024},
                    "source": {"type": "keyword"},
                    "text": {"type": "text"},
                    "document_id": {"type": "text"},
                }
            }
        }
    }
    with pytest.raises(RuntimeError, match="document_id"):
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
    client = MagicMock()
    client.indices.exists.return_value = True
    mapping = _full_mapping()
    mapping["medrep-index"]["mappings"]["properties"]["source"] = {
        "type": "text",
        "fields": {"keyword": {"type": "keyword"}},
    }
    client.indices.get_mapping.return_value = mapping
    client.indices.put_mapping.return_value = {"acknowledged": True}
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


def test_verify_indexed_documents_returns_count_for_document_id():
    client = MagicMock()
    client.indices.get_mapping.return_value = _full_mapping()
    client.count.return_value = {"count": 3}
    client.search.return_value = {
        "hits": {
            "hits": [
                {"_source": {"text": "a", "document_id": "abc"}},
            ]
        }
    }
    assert (
        ingest.verify_indexed_documents(
            client,
            "medrep-index",
            document_id="abc",
            expected_count=3,
        )
        == 3
    )
    count_body = client.count.call_args.kwargs.get("body") or client.count.call_args[1]["body"]
    assert count_body["query"] == {"term": {"document_id": "abc"}}


def test_verify_indexed_documents_raises_when_count_not_exact():
    client = MagicMock()
    client.indices.get_mapping.return_value = _full_mapping()
    client.count.return_value = {"count": 5}
    with pytest.raises(RuntimeError, match="expected exactly"):
        ingest.verify_indexed_documents(
            client,
            "medrep-index",
            document_id="abc",
            expected_count=3,
            retries=1,
            delay_seconds=0,
        )


def test_verify_indexed_documents_raises_when_count_zero():
    client = MagicMock()
    client.indices.get_mapping.return_value = _full_mapping()
    client.count.return_value = {"count": 0}
    with pytest.raises(RuntimeError, match="count"):
        ingest.verify_indexed_documents(
            client,
            "medrep-index",
            document_id="abc",
            expected_count=1,
            retries=1,
            delay_seconds=0,
        )


def test_verify_indexed_documents_raises_when_not_retrievable():
    client = MagicMock()
    client.indices.get_mapping.return_value = _full_mapping()
    client.count.return_value = {"count": 2}
    client.search.return_value = {"hits": {"hits": []}}
    with pytest.raises(RuntimeError, match="retriev"):
        ingest.verify_indexed_documents(
            client,
            "medrep-index",
            document_id="abc",
            expected_count=2,
            retries=1,
            delay_seconds=0,
        )


def test_delete_documents_for_document_id_deletes_by_id():
    client = MagicMock()
    client.search.side_effect = [
        {
            "hits": {
                "hits": [
                    {"_id": "id-a"},
                    {"_id": "id-b"},
                ]
            }
        },
        {"hits": {"hits": []}},
    ]
    deleted = ingest.delete_documents_for_document_id(client, "medrep-index", "doc123")
    assert deleted == 2
    client.delete.assert_has_calls(
        [
            call(index="medrep-index", id="id-a"),
            call(index="medrep-index", id="id-b"),
        ],
        any_order=False,
    )
    client.indices.refresh.assert_called_with(index="medrep-index")


def test_delete_documents_refreshes_between_full_pages():
    client = MagicMock()
    page = [{"_id": f"id-{i}"} for i in range(1000)]
    client.search.side_effect = [
        {"hits": {"hits": page}},
        {"hits": {"hits": [{"_id": "id-last"}]}},
        {"hits": {"hits": []}},
    ]
    deleted = ingest.delete_documents_for_document_id(client, "medrep-index", "doc123")
    assert deleted == 1001
    assert client.indices.refresh.call_count >= 2


def test_delete_documents_also_removes_legacy_source_docs():
    client = MagicMock()
    client.indices.get_mapping.return_value = _full_mapping()
    client.search.side_effect = [
        {
            "hits": {
                "hits": [
                    {"_id": "Demo-pain-relief.pdf::0"},
                    {"_id": "Demo-pain-relief.pdf::1"},
                ]
            }
        },
        {"hits": {"hits": []}},
    ]
    deleted = ingest.delete_documents_for_document_id(
        client,
        "medrep-index",
        "doc123",
        source_filename="Demo-pain-relief.pdf",
    )
    assert deleted == 2
    search_body = client.search.call_args_list[0].kwargs.get("body") or client.search.call_args_list[0][1]["body"]
    should = search_body["query"]["bool"]["should"]
    assert {"term": {"document_id": "doc123"}} in should
    legacy = next(c for c in should if "bool" in c)
    assert legacy["bool"]["must"] == [{"term": {"source": "Demo-pain-relief.pdf"}}]
    assert {"exists": {"field": "document_id"}} in legacy["bool"]["must_not"]


# --- ingest_pdf pipeline ---


def test_ingest_pdf_indexes_chunks_with_metadata():
    pdf_bytes = b"%PDF"
    pages = [
        {
            "page_number": 1,
            "text": " ".join(f"word{i}" for i in range(401)),
        }
    ]
    embedding = [0.1, 0.2, 0.3]
    indexed_bodies = []
    doc_id = ingest.make_document_id("Demo-pain-relief.pdf")

    opensearch = _ready_opensearch_mock(indexed_count=2, document_id=doc_id)

    def capture_index(**kwargs):
        indexed_bodies.append(kwargs)
        return {"result": "created"}

    opensearch.index.side_effect = capture_index

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=pdf_bytes) as mock_download,
        patch("services.ingest.extract_pages_from_pdf", return_value=pages) as mock_extract,
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
    for i, kwargs in enumerate(indexed_bodies):
        assert kwargs["index"] == "medrep-index"
        body = kwargs["body"]
        assert body["source"] == "Demo-pain-relief.pdf"
        assert body["source_filename"] == "Demo-pain-relief.pdf"
        assert body["s3_key"] == "Demo-pain-relief.pdf"
        assert body["document_id"] == doc_id
        assert body["chunk_id"] == ingest.make_chunk_id(doc_id, i)
        assert kwargs["id"] == body["chunk_id"]
        assert body["document_type"] == "pdf"
        assert body["product_name"] == "Demo-pain-relief"
        assert body["page_number"] == 1
        assert body["embedding"] == embedding
        assert isinstance(body["text"], str) and body["text"]
        assert "text" in body


def test_ingest_pdf_deletes_prior_docs_before_reindex():
    pages = [{"page_number": 1, "text": "short content for one chunk"}]
    doc_id = ingest.make_document_id("ozempic/Ozempic.pdf")
    opensearch = _ready_opensearch_mock(indexed_count=1, document_id=doc_id)
    opensearch.index.return_value = {"result": "created"}
    opensearch.search.side_effect = [
        {"hits": {"hits": [{"_id": "old-chunk"}]}},
        {"hits": {"hits": []}},  # delete loop done after refresh
        {
            "hits": {
                "hits": [
                    {"_source": {"text": "x", "document_id": doc_id}},
                ]
            }
        },
    ]

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch("services.ingest.extract_pages_from_pdf", return_value=pages),
        patch("services.ingest.embed_text", return_value=[0.1]),
        patch("services.ingest.opensearch_client", return_value=opensearch),
    ):
        count = ingest.ingest_pdf("bucket", "ozempic/Ozempic.pdf")

    assert count == 1
    opensearch.delete.assert_called_with(index="medrep-index", id="old-chunk")
    # delete happens before index
    assert opensearch.delete.call_count >= 1
    assert opensearch.index.call_count == 1
    # re-index delete includes source_filename for legacy cleanup
    delete_search = opensearch.search.call_args_list[0]
    body = delete_search.kwargs.get("body") or delete_search[1]["body"]
    assert "bool" in body["query"]


def test_ingest_pdf_reindex_fewer_chunks_deletes_orphan_higher_ids():
    pages = [{"page_number": 1, "text": "short content for one chunk"}]
    doc_id = ingest.make_document_id("file.pdf")
    orphan_ids = [
        ingest.make_chunk_id(doc_id, 0),
        ingest.make_chunk_id(doc_id, 1),
        ingest.make_chunk_id(doc_id, 2),
    ]
    opensearch = _ready_opensearch_mock(indexed_count=1, document_id=doc_id)
    opensearch.index.return_value = {"result": "created"}
    opensearch.search.side_effect = [
        {"hits": {"hits": [{"_id": oid} for oid in orphan_ids]}},
        {"hits": {"hits": []}},
        {"hits": {"hits": [{"_source": {"text": "x", "document_id": doc_id}}]}},
    ]

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch("services.ingest.extract_pages_from_pdf", return_value=pages),
        patch("services.ingest.embed_text", return_value=[0.1]),
        patch("services.ingest.opensearch_client", return_value=opensearch),
    ):
        count = ingest.ingest_pdf("bucket", "file.pdf")

    assert count == 1
    deleted_ids = [c.kwargs.get("id") or c[1]["id"] for c in opensearch.delete.call_args_list]
    assert set(deleted_ids) == set(orphan_ids)
    assert opensearch.index.call_count == 1


def test_ingest_pdf_cleans_legacy_filename_double_colon_ids():
    pages = [{"page_number": 1, "text": "short content for one chunk"}]
    key = "Demo-pain-relief.pdf"
    doc_id = ingest.make_document_id(key)
    legacy_ids = [f"{key}::0", f"{key}::1"]
    opensearch = _ready_opensearch_mock(indexed_count=1, document_id=doc_id)
    opensearch.index.return_value = {"result": "created"}
    opensearch.search.side_effect = [
        {"hits": {"hits": [{"_id": lid} for lid in legacy_ids]}},
        {"hits": {"hits": []}},
        {"hits": {"hits": [{"_source": {"text": "x", "document_id": doc_id}}]}},
    ]

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch("services.ingest.extract_pages_from_pdf", return_value=pages),
        patch("services.ingest.embed_text", return_value=[0.1]),
        patch("services.ingest.opensearch_client", return_value=opensearch),
    ):
        count = ingest.ingest_pdf("bucket", key)

    assert count == 1
    deleted_ids = [c.kwargs.get("id") or c[1]["id"] for c in opensearch.delete.call_args_list]
    assert set(deleted_ids) == set(legacy_ids)


def test_ingest_pdf_verifies_exact_count_by_document_id():
    pages = [
        {"page_number": 1, "text": " ".join(f"word{i}" for i in range(401))},
    ]
    doc_id = ingest.make_document_id("Demo-pain-relief.pdf")
    opensearch = _ready_opensearch_mock(indexed_count=2, document_id=doc_id)
    opensearch.index.return_value = {"result": "created"}

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch("services.ingest.extract_pages_from_pdf", return_value=pages),
        patch("services.ingest.embed_text", return_value=[0.1]),
        patch("services.ingest.opensearch_client", return_value=opensearch),
        patch("services.ingest.verify_indexed_documents", return_value=2) as mock_verify,
        patch("services.ingest.delete_documents_for_document_id", return_value=0),
    ):
        count = ingest.ingest_pdf("bucket", "Demo-pain-relief.pdf")

    assert count == 2
    assert mock_verify.call_args.kwargs["expected_count"] == 2
    assert mock_verify.call_args.kwargs["document_id"] == doc_id


def test_ingest_pdf_defaults_index_to_medrep_index():
    pages = [{"page_number": 1, "text": "short text"}]
    doc_id = ingest.make_document_id("file.pdf")
    opensearch = _ready_opensearch_mock(indexed_count=1, document_id=doc_id)
    opensearch.index.return_value = {"result": "created"}
    opensearch.indices.get_mapping.return_value = _full_mapping()

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch("services.ingest.extract_pages_from_pdf", return_value=pages),
        patch("services.ingest.embed_text", return_value=[0.5]),
        patch("services.ingest.opensearch_client", return_value=opensearch),
        patch("services.ingest.delete_documents_for_document_id", return_value=0),
        patch.dict("os.environ", {}, clear=True),
    ):
        count = ingest.ingest_pdf("b", "file.pdf")

    assert count == 1
    assert opensearch.index.call_args.kwargs["index"] == "medrep-index"
    assert opensearch.index.call_args.kwargs["body"]["source"] == "file.pdf"


def test_ingest_pdf_empty_extraction_deletes_prior_docs():
    doc_id = ingest.make_document_id("empty.pdf")
    opensearch = _ready_opensearch_mock(indexed_count=0, document_id=doc_id)
    opensearch.search.side_effect = [
        {"hits": {"hits": [{"_id": f"{doc_id}:0000"}, {"_id": "empty.pdf::0"}]}},
        {"hits": {"hits": []}},
    ]

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch("services.ingest.extract_pages_from_pdf", return_value=[]),
        patch("services.ingest.embed_text") as mock_embed,
        patch("services.ingest.opensearch_client", return_value=opensearch),
    ):
        count = ingest.ingest_pdf("bucket", "empty.pdf")

    assert count == 0
    mock_embed.assert_not_called()
    opensearch.index.assert_not_called()
    assert opensearch.delete.call_count == 2
    opensearch.indices.exists.assert_called()


def test_ingest_pdf_empty_pages_with_no_text_deletes_prior_docs():
    doc_id = ingest.make_document_id("empty.pdf")
    opensearch = _ready_opensearch_mock(indexed_count=0, document_id=doc_id)
    opensearch.search.side_effect = [
        {"hits": {"hits": [{"_id": "stale"}]}},
        {"hits": {"hits": []}},
    ]

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch(
            "services.ingest.extract_pages_from_pdf",
            return_value=[{"page_number": 1, "text": ""}],
        ),
        patch("services.ingest.embed_text") as mock_embed,
        patch("services.ingest.opensearch_client", return_value=opensearch),
    ):
        count = ingest.ingest_pdf("bucket", "empty.pdf")

    assert count == 0
    mock_embed.assert_not_called()
    opensearch.index.assert_not_called()
    opensearch.delete.assert_called_with(index="medrep-index", id="stale")


def test_ingest_pdf_aborts_when_index_not_ready():
    opensearch = MagicMock()
    opensearch.indices.exists.return_value = False

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch(
            "services.ingest.extract_pages_from_pdf",
            return_value=[{"page_number": 1, "text": "text"}],
        ),
        patch("services.ingest.embed_text") as mock_embed,
        patch("services.ingest.opensearch_client", return_value=opensearch),
    ):
        with pytest.raises(RuntimeError, match="does not exist"):
            ingest.ingest_pdf("bucket", "Demo-pain-relief.pdf")

    mock_embed.assert_not_called()
    opensearch.index.assert_not_called()


def test_ingest_pdf_raises_when_verification_fails():
    pages = [{"page_number": 1, "text": "chunk text"}]
    opensearch = _ready_opensearch_mock(indexed_count=0)
    opensearch.index.return_value = {"result": "created"}
    opensearch.count.return_value = {"count": 0}

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch("services.ingest.extract_pages_from_pdf", return_value=pages),
        patch("services.ingest.embed_text", return_value=[0.1]),
        patch("services.ingest.opensearch_client", return_value=opensearch),
        patch(
            "services.ingest.verify_indexed_documents",
            side_effect=RuntimeError("count is 0"),
        ),
    ):
        with pytest.raises(RuntimeError, match="count"):
            ingest.ingest_pdf("bucket", "Demo-pain-relief.pdf")


def test_ingest_pdf_respects_env_chunk_size():
    # 10 tokens total; with size=5 overlap=0 → 2 chunks
    pages = [{"page_number": 1, "text": " ".join(f"t{i}" for i in range(10))}]
    doc_id = ingest.make_document_id("file.pdf")
    opensearch = _ready_opensearch_mock(indexed_count=2, document_id=doc_id)
    opensearch.index.return_value = {"result": "created"}

    with (
        patch("services.ingest.download_pdf_from_s3", return_value=b"%PDF"),
        patch("services.ingest.extract_pages_from_pdf", return_value=pages),
        patch("services.ingest.embed_text", return_value=[0.1]),
        patch("services.ingest.opensearch_client", return_value=opensearch),
        patch("services.ingest.verify_indexed_documents", return_value=2),
        patch.dict(
            "os.environ",
            {"INGEST_CHUNK_SIZE": "5", "INGEST_CHUNK_OVERLAP": "0"},
            clear=False,
        ),
    ):
        count = ingest.ingest_pdf("b", "file.pdf")

    assert count == 2
    assert opensearch.index.call_count == 2
