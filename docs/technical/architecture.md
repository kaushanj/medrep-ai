# Architecture

The backend uses Python and FastAPI.

The frontend, RAG, Amazon OpenSearch, and Amazon Bedrock are planned.

Amazon OpenSearch is planned for retrieval. Amazon Bedrock is planned for LLM generation.

```mermaid
flowchart TD
    rep[Medical representative]
    frontend["Frontend (planned)"]
    api[FastAPI]
    rag["RAG (planned)"]
    opensearch["Amazon OpenSearch (planned retrieval)"]
    bedrock["Amazon Bedrock (planned generation)"]
    result[Answer and source documents]

    rep --> frontend
    frontend --> api
    api --> rag
    rag --> opensearch
    rag --> bedrock
    rag --> result
```
