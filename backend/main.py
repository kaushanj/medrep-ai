import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from api.schema import ChatRequest, ChatResponse
from services.rag import ask_rag

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI()


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