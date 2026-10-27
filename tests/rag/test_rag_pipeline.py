"""不依赖外网的 RAG 检索到回答专项回归。"""

import pytest

from app.rag.llm_client import MockLLMClient, build_rag_prompt_v2
from app.rag.vector_retriever import VectorRetriever
from app.rag.vector_store import VectorSearchResult


@pytest.mark.unit
def test_fake_vector_pipeline_preserves_source_and_evidence() -> None:
    class FakeEmbedder:
        def encode_query(self, query: str) -> list[float]:
            assert query == "多久可以退款？"
            return [1.0, 0.0]

    class FakeStore:
        def query(self, query_embedding: list[float], top_k: int) -> list[VectorSearchResult]:
            assert query_embedding == [1.0, 0.0]
            assert top_k == 3
            return [
                VectorSearchResult(
                    source="refund.md",
                    content="普通商品签收后 7 天内可以申请无理由退款。",
                    score=0.95,
                    chunk_index=0,
                    page=None,
                    chunk_id="refund-0",
                )
            ]

    results = VectorRetriever(FakeEmbedder(), FakeStore()).search("多久可以退款？")
    prompt = build_rag_prompt_v2("多久可以退款？", results)
    answer = MockLLMClient().generate(prompt)

    assert results[0].source == "refund.md"
    assert "来源：refund.md" in prompt
    assert "7 天" in answer
