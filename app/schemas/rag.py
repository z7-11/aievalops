from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


class RAGRequest(BaseModel):
    """
    RAG 查询请求。
    """

    question: str = Field(
        min_length=1,
        max_length=2000,
        description="用户问题",
    )

    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="最多返回多少条参考资料",
    )

    prompt_version: Literal["v1", "v2"] = Field(
        default="v1",
        description="用于 Prompt 对比实验的模板版本",
    )

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(
        cls,
        value: str,
    ) -> str:
        normalized_value = value.strip()

        if not normalized_value:
            raise ValueError("question 不能为空")

        return normalized_value


class RAGSource(BaseModel):
    """一条能够追溯到原文的引用。"""

    file: str = Field(
        description="相对于 knowledge 目录的文件路径",
    )

    page: int | None = Field(
        default=None,
        ge=1,
        description="PDF 页码；Markdown 为 null",
    )

    chunk_index: int = Field(
        ge=0,
        description="文件内的片段序号",
    )

    chunk_id: str = Field(
        min_length=1,
        description="片段唯一 ID",
    )

    score: float = Field(
        ge=0,
        le=1,
        description="检索相关性分数",
    )

    excerpt: str = Field(
        min_length=1,
        description="实际提供给模型的引用原文",
    )


class RAGUsage(BaseModel):
    """
    模型 Token 使用情况。
    """

    prompt_tokens: int = Field(
        ge=0,
    )

    completion_tokens: int = Field(
        ge=0,
    )

    estimated_cost_usd: float = Field(
        default=0.0,
        ge=0,
    )


class RAGResponse(BaseModel):
    """
    RAG 接口响应。
    """

    answer: str

    sources: list[RAGSource]

    model: str

    latency_ms: float

    usage: RAGUsage
