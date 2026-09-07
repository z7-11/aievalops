from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2000,
        description="用户需要咨询的问题",
    )

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized_value = value.strip()

        if not normalized_value:
            raise ValueError("question must not be blank")

        return normalized_value


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int


class ChatResponse(BaseModel):
    answer: str
    model: str
    latency_ms: float
    usage: TokenUsage


class HealthResponse(BaseModel):
    status: str
    service: str
