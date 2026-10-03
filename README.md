# MedRep AI — GenAI / RAG

Grounded answers from product PDFs using **S3 → Lambda → Bedrock → OpenSearch**, plus an optional **LangChain** agent for multi-step questions.

## Architecture

```
Ingest (async)
  S3 PDF ──ObjectCreated──► Lambda
                              │
                              ▼
                         chunk + clean
                              │
                              ▼
                    Bedrock Titan embed
                              │
                              ▼
                    OpenSearch (medrep-index)

Query (sync)
  question ──► FastAPI (Lambda)
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
   RAG /chat           Agent /agent-chat
   embed → search      LangChain + tools
   → Bedrock answer    → search (1..N)
                       → Bedrock answer
                  │
                  ▼
           answer + citations
```

## Stack

| Layer | Service |
| --- | --- |
| Document store | S3 |
| Ingest | Lambda (`s3_ingest` → `ingest_pdf`) |
| Vector index | OpenSearch Serverless (`medrep-index`) |
| Embeddings | Bedrock Titan Text Embeddings v2 |
| Generation | Bedrock Converse (Nova Lite) + guardrails |
| Agent | LangChain `ChatBedrockConverse` + `search_internal_documents` |

## Paths

| Path | Use when | Flow |
| --- | --- | --- |
| **RAG** `POST /chat` | Single product Q&A | embed → OpenSearch → generate once |
| **Agent** `POST /agent-chat` | Compare / multi-step | model may call search several times, then answer |

Both use the same OpenSearch index and Bedrock embeddings. Agent answers product questions only from tool evidence.

## Code map

```
backend/
  handlers/s3_ingest.py       S3 → Lambda entry
  services/ingest.py          PDF → chunks → embed → index
  services/rag.py             ask_rag (embed, search, generate)
  services/agent.py           ask_agent loop
  services/agent_bedrock.py   Bedrock model + bind_tools
  services/agent_tools.py     search_internal_documents tool
  repositories/opensearch.py  OpenSearch client
infra/                        SAM: ingest stack + API stack
```

## Design choices

- **Grounded answers only** — no invented medical claims presented as document-backed.
- **RAG for simple, agent for multi-step** — same retrieval backend, different orchestration.
