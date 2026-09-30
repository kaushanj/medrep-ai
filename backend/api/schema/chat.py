from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Question cannot be empty")

        return value


class ChatResponse(BaseModel):
    answer: str
    source: str | None
