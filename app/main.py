import asyncio
from time import perf_counter

from fastapi import FastAPI

from app.api.projects import router as projects_router
from app.api.rag import router as rag_router
from app.api.runs import router as runs_router
from app.api.test_cases import router as test_cases_router
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    TokenUsage,
)
from app.services.chat_service import generate_answer

app = FastAPI(
    title="AIEvalOps Mock Customer Service",
    description="用于演示大模型自动化评测的本地客服接口",
    version="0.1.0",
)

app.include_router(projects_router)
app.include_router(test_cases_router)
app.include_router(runs_router)
app.include_router(rag_router)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="mock-customer-service",
    )


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    tags=["Chat"],
)
async def chat(request: ChatRequest) -> ChatResponse:
    started_at = perf_counter()

    # 模拟真实模型接口的网络和推理耗时。
    await asyncio.sleep(0.08)

    answer = generate_answer(request.question)
    latency_ms = round((perf_counter() - started_at) * 1000, 2)

    return ChatResponse(
        answer=answer,
        model="mock-customer-service-v1",
        latency_ms=latency_ms,
        usage=TokenUsage(
            prompt_tokens=len(request.question),
            completion_tokens=len(answer),
        ),
    )
