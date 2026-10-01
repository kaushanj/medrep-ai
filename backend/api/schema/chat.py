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


class Citation(BaseModel):
    product_name: str | None = None
    document_type: str | None = None
    source_filename: str | None = None
    s3_key: str | None = None
    page_number: int | None = None
    section_name: str | None = None
    document_version: str | None = None
    effective_date: str | None = None


class ChatResponse(BaseModel):
    answer: str
    source: str | None
    citations: list[Citation] = []
