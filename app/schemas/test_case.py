from pydantic import BaseModel, Field, field_validator


class TestCaseRecord(BaseModel):
    case_id: str = Field(min_length=1, max_length=100)
    module: str = Field(min_length=1, max_length=100)
    priority: str
    question: str = Field(min_length=1, max_length=2000)
    expected_keywords: list[str]
    forbidden_keywords: list[str] = Field(default_factory=list)
    max_latency_ms: int = Field(gt=0, le=300_000)
    security_category: str

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        normalized = value.strip().upper()

        if normalized not in {"P0", "P1", "P2"}:
            raise ValueError("priority must be P0, P1 or P2")

        return normalized


class DatasetValidationResult(BaseModel):
    valid: bool
    total: int
    cases: list[TestCaseRecord]
    errors: list[str]