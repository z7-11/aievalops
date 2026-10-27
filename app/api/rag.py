from functools import lru_cache
from pathlib import Path
from time import perf_counter

from fastapi import (
    APIRouter,
    HTTPException,
)

from app.core.config import settings
from app.rag.document_loader import build_chunk_id
from app.rag.embedding import LocalEmbeddingModel
from app.rag.llm_client import (
    build_rag_prompt_v1,
    build_rag_prompt_v2,
    create_llm_client,
)
from app.rag.service import RAGService
from app.rag.vector_retriever import VectorRetriever
from app.rag.vector_store import ChromaVectorStore
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


@lru_cache(maxsize=1)
def get_vector_components() -> tuple[
    LocalEmbeddingModel,
    ChromaVectorStore,
]:
    """加载向量模型，并连接已有的Chroma索引。"""

    project_root = Path(__file__).resolve().parents[2]

    chroma_path = Path(settings.rag_chroma_path)

    if not chroma_path.is_absolute():
        chroma_path = project_root / chroma_path

    if not chroma_path.is_dir():
        raise FileNotFoundError(f"Chroma目录不存在：{chroma_path}")

    store = ChromaVectorStore(
        persist_dir=chroma_path,
        collection_name=settings.rag_collection_name,
        embedding_model=settings.rag_embedding_model,
    )

    if store.collection.count() == 0:
        raise ValueError(
            f"Chroma集合 {settings.rag_collection_name} 没有索引数据，请先构建索引并检查集合名称"
        )

    embedding_model = LocalEmbeddingModel(model_name=settings.rag_embedding_model)

    return embedding_model, store


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
        if settings.rag_retriever_type == "chroma":
            embedding_model, store = get_vector_components()
            retrieval_results = VectorRetriever(embedding_model, store).search(
                query=request.question, top_k=request.top_k
            )
            minimum_score = settings.rag_vector_min_similarity_score
        elif settings.rag_retriever_type == "tfidf":
            rag_service = get_rag_service()
            retrieval_results = rag_service.retriever.search(
                query=request.question,
                top_k=request.top_k,
            )
            minimum_score = settings.rag_min_relevance_score
        else:
            raise ValueError("RAG_RETRIEVER_TYPE 必须是 chroma 或 tfidf")

        relevant_results = [result for result in retrieval_results if result.score >= minimum_score]

        prompt_builder = (
            build_rag_prompt_v1 if request.prompt_version == "v1" else build_rag_prompt_v2
        )
        prompt = prompt_builder(
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

    sources = []

    for result in relevant_results:
        page = getattr(result, "page", None)

        chunk_id = getattr(result, "chunk_id", "") or build_chunk_id(
            source=result.source,
            page=page,
            chunk_index=result.chunk_index,
            content=result.content,
        )

        sources.append(
            RAGSource(
                file=result.source,
                page=page,
                chunk_index=result.chunk_index,
                chunk_id=chunk_id,
                score=result.score,
                excerpt=result.content,
            )
        )

    model_name = "mock" if settings.llm_mock_mode else settings.llm_model

    return RAGResponse(
        answer=answer,
        sources=sources,
        model=model_name,
        latency_ms=latency_ms,
        usage=usage,
    )
