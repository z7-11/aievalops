from functools import lru_cache
from pathlib import Path
from time import perf_counter

from fastapi import (
    APIRouter,
    HTTPException,
)

from app.core.config import settings
from app.rag.llm_client import (
    build_rag_prompt,
    create_llm_client,
)
from app.rag.service import RAGService
from app.schemas.rag import (
    RAGRequest,
    RAGResponse,
    RAGSource,
    RAGUsage,
)

router = APIRouter(
    prefix="/api/rag",
    tags=["RAG"],
)


@lru_cache(maxsize=1)
def get_rag_service() -> RAGService:
    """
    创建并缓存 RAG 服务。

    只在第一次请求时读取知识库，
    后续请求复用已经创建好的检索器。
    """

    project_root = Path(__file__).resolve().parents[2]

    knowledge_dir = project_root / "knowledge"

    return RAGService(
        knowledge_dir=knowledge_dir,
    )


@router.post(
    "/query",
    response_model=RAGResponse,
)
def query_rag(
    request: RAGRequest,
) -> RAGResponse:
    """
    执行一次 RAG 查询。
    """

    started_at = perf_counter()

    try:
        rag_service = get_rag_service()

        retrieval_results = rag_service.retriever.search(
            query=request.question,
            top_k=request.top_k,
        )

        relevant_results = [
            result
            for result in retrieval_results
            if result.score >= settings.rag_min_relevance_score
        ]

        prompt = build_rag_prompt(
            question=request.question,
            results=relevant_results,
        )

        client = create_llm_client()

        answer = client.generate(prompt)

    except (
        FileNotFoundError,
        NotADirectoryError,
        ValueError,
        RuntimeError,
    ) as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    latency_ms = round(
        (perf_counter() - started_at) * 1000,
        2,
    )

    raw_usage = getattr(
        client,
        "last_usage",
        {},
    )

    usage = RAGUsage(
        prompt_tokens=int(
            raw_usage.get(
                "prompt_tokens",
                0,
            )
        ),
        completion_tokens=int(
            raw_usage.get(
                "completion_tokens",
                0,
            )
        ),
        estimated_cost_usd=float(
            raw_usage.get(
                "estimated_cost_usd",
                0.0,
            )
        ),
    )

    sources = [
        RAGSource(
            file=result.source,
            score=result.score,
        )
        for result in relevant_results
    ]

    model_name = "mock" if settings.llm_mock_mode else settings.llm_model

    return RAGResponse(
        answer=answer,
        sources=sources,
        model=model_name,
        latency_ms=latency_ms,
        usage=usage,
    )
