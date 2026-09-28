# Architecture

The backend uses Python and FastAPI.

The RAG module (`ask_rag` in `backend/rag.py`) embeds questions with Amazon Bedrock, retrieves from Amazon OpenSearch, and generates answers with Amazon Bedrock. It is not yet connected to `POST /chat`.

The frontend remains planned.

```mermaid
flowchart TD
    rep[Medical representative]
    frontend["Frontend (planned)"]
    api[FastAPI]
    rag["RAG ask_rag()"]
    opensearch["Amazon OpenSearch (retrieval)"]
    bedrock["Amazon Bedrock (embed + generation)"]
    result[Answer and source]

    rep --> frontend
    frontend --> api
    api -.->|"not wired yet"| rag
    rag --> opensearch
    rag --> bedrock
    rag --> result
```
