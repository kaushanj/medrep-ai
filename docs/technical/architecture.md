# Architecture

The backend uses Python and FastAPI with a layered package layout under `backend/` (`api/schema`, `services`, `repositories`, `handlers`).

Product PDFs in S3 are ingested into OpenSearch (`medrep-index`) with RAG fields `{text, source, embedding}` plus ingest metadata (`document_id`, `chunk_id`, `product_name`, `document_type`, `source_filename`, `s3_key`, `page_number`, and optional `section_name` / `document_version` / `effective_date`):

1. **S3 ObjectCreated** (suffix `.pdf`) invokes Lambda `handlers.s3_ingest.handler` (thin function package built from the repo-root Makefile; handler source under `backend/handlers/`).
2. Shared ingest code and deps ship as a Lambda Layer (`python/services` + `python/repositories` copied from `backend/` at `sam build`, plus ingest deps). The handler calls `services.ingest.ingest_pdf` (download → page-aware PyPDF extract → clean → paragraph/section token chunk → Titan embed via Bedrock → delete prior `document_id` and legacy same-filename orphans → index with deterministic `chunk_id`).
3. The same ingest service is available via CLI: `python ingest.py --bucket … --key …` or `python -m services.ingest` (optional `--chunk-size` / `--chunk-overlap`, or env `INGEST_CHUNK_SIZE` / `INGEST_CHUNK_OVERLAP`; defaults 400 / 40 whitespace tokens).

Objects uploaded before the S3 notification existed are not auto-ingested; re-upload or run the CLI for backfill. Live deploy and one-PDF verification are operator steps (see `docs/technical/backend.md`).

The RAG module (`ask_rag` in `backend/services/rag.py`) embeds questions with Amazon Bedrock, retrieves from Amazon OpenSearch, and generates answers with Amazon Bedrock. `POST /chat` is wired to `ask_rag`.

The frontend is a Next.js App Router app under `frontend/`. It calls `POST /chat` using `NEXT_PUBLIC_API_BASE_URL`.

```mermaid
flowchart TD
    s3["S3 product PDFs"]
    lambda["Lambda s3_ingest"]
    ingest["services.ingest.ingest_pdf"]
    cli["CLI ingest.py / -m services.ingest"]
    rep[Medical representative]
    frontend["Next.js frontend/"]
    api[FastAPI]
    rag["RAG ask_rag()"]
    opensearch["Amazon OpenSearch (medrep-index)"]
    bedrock["Amazon Bedrock (embed + generation)"]
    result[Answer and source]

    s3 -->|"ObjectCreated .pdf"| lambda
    lambda --> ingest
    cli --> ingest
    ingest --> opensearch
    ingest --> bedrock
    rep --> frontend
    frontend --> api
    api --> rag
    rag --> opensearch
    rag --> bedrock
    rag --> result
```
