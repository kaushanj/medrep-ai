from dotenv import load_dotenv
from fastapi import FastAPI

from api.schema import ChatRequest, ChatResponse
from services.rag import ask_rag

load_dotenv()

app = FastAPI()


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    result = ask_rag(request.question)
    return ChatResponse(answer=result["answer"], source=result["source"])
