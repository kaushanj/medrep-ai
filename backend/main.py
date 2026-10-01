import logging
import os
from contextlib import asynccontextmanager
from mangum import Mangum

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from api.auth import require_google_user
from api.errors import register_exception_handlers
from api.middleware import RequestIdMiddleware
from api.rate_limit import enforce_chat_rate_limit
from api.schema import ChatRequest, ChatResponse
from repositories.opensearch import opensearch_client
from services.rag import _bedrock_runtime, ask_rag

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)


def _cors_allowed_origins() -> list[str]:
    """Parse CORS_ALLOWED_ORIGINS (comma-separated). Empty/missing → []."""
    raw = os.environ.get("CORS_ALLOWED_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def add_cors_middleware(app: FastAPI) -> None:
    """Register CORSMiddleware with fail-closed origins (no wildcard)."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )


def add_request_id_middleware(app: FastAPI) -> None:
    """Register request-ID middleware outermost (after CORS so it wraps CORS)."""
    app.add_middleware(RequestIdMiddleware)


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
add_cors_middleware(app)
add_request_id_middleware(app)
register_exception_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    """Lightweight liveness check; does not call Bedrock or OpenSearch."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    _user: dict = Depends(require_google_user),
    _rate_limit: None = Depends(enforce_chat_rate_limit),
) -> ChatResponse:
    try:
        result = ask_rag(request.question)
    except Exception:
        logger.error("RAG request failed.", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable.",
        )

    return ChatResponse(
        answer=result["answer"],
        source=result["source"],
        citations=result.get("citations", []),
    )

handler = Mangum(app, lifespan="off")
