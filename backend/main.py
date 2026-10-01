import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from api.schema import ChatRequest, ChatResponse
from repositories.opensearch import opensearch_client
from services.rag import _bedrock_runtime, ask_rag

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        opensearch_client()
    except Exception:
        logger.warning("OpenSearch client warmup failed.", exc_info=True)

    try:
        _bedrock_runtime()
    except Exception:
        logger.warning("Bedrock runtime client warmup failed.", exc_info=True)

    yield


app = FastAPI(lifespan=lifespan)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = ask_rag(request.question)
    except Exception:
        logger.error("RAG request failed.", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable.",
        )

    return ChatResponse(answer=result["answer"], source=result["source"])


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)

    return JSONResponse(status_code=500, content={"detail": "Internal Server Error."})
