import json
import os

import boto3

from utils.constants import DEFAULT_GENERATION_MODEL_ID
from repositories.opensearch import opensearch_client

# Re-export for callers/tests that historically imported from rag.
_opensearch_client = opensearch_client


def _bedrock_runtime():
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client("bedrock-runtime", region_name=region)


def embed_question(question: str) -> list[float]:
    model_id = os.environ.get(
        "BEDROCK_EMBEDDING_MODEL_ID",
        "amazon.titan-embed-text-v2:0",
    )
    client = _bedrock_runtime()
    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": question}),
    )
    payload = json.loads(response["body"].read())
    return payload["embedding"]


def search_opensearch(embedding: list[float]) -> list[dict[str, str]]:
    index = os.environ.get("OPENSEARCH_INDEX", "medrep-index")
    top_k = int(os.environ.get("RAG_TOP_K", "3"))
    client = _opensearch_client()
    query = {
        "size": top_k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": embedding,
                    "k": top_k,
                }
            }
        },
    }
    response = client.search(index=index, body=query)
    hits = response.get("hits", {}).get("hits", [])
    results: list[dict[str, str]] = []
    for hit in hits:
        source = hit.get("_source", {})
        results.append(
            {
                "text": source.get("text", ""),
                "source": source.get("source", ""),
            }
        )
    return results


def generate_answer(question: str, context: str) -> str:
    model_id = os.environ.get(
        "BEDROCK_GENERATION_MODEL_ID",
        DEFAULT_GENERATION_MODEL_ID,
    )
    client = _bedrock_runtime()
    prompt = (
        "Answer the question using only the provided context. "
        "If the context is insufficient, say you do not know.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )
    response = client.converse(
        modelId=model_id,
        messages=[
            {
                "role": "user",
                "content": [{"text": prompt}],
            }
        ],
    )
    output = response.get("output", {}).get("message", {}).get("content", [])
    texts = [block.get("text", "") for block in output if "text" in block]
    return "".join(texts).strip()


def _dedupe_chunks(results: list[dict[str, str]]) -> list[dict[str, str]]:
    seen_texts: set[str] = set()
    unique: list[dict[str, str]] = []
    for chunk in results:
        text = chunk.get("text", "")
        if text in seen_texts:
            continue
        seen_texts.add(text)
        unique.append(chunk)
    return unique


def ask_rag(question: str) -> dict[str, str]:
    embedding = embed_question(question)
    results = search_opensearch(embedding)
    if not results:
        return {
            "answer": "No relevant documents found.",
            "source": "",
            "context": "",
        }

    chunks = _dedupe_chunks(results)
    context_parts = [c["text"] for c in chunks if c.get("text")]
    context = "\n\n".join(context_parts)

    sources: list[str] = []
    seen_sources: set[str] = set()
    for chunk in chunks:
        source = chunk.get("source", "")
        if not source or source in seen_sources:
            continue
        seen_sources.add(source)
        sources.append(source)
    source = ", ".join(sources)

    answer = generate_answer(question, context)
    return {
        "answer": answer,
        "source": source,
        "context": context,
    }
