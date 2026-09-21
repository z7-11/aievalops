from pathlib import Path

import pytest

from app.rag.service import RAGService


@pytest.fixture(scope="module")
def rag_service() -> RAGService:
    project_root = Path(__file__).resolve().parents[2]
    return RAGService(project_root / "knowledge")


@pytest.mark.unit
def test_refund_question_retrieves_refund_document(
    rag_service: RAGService,
) -> None:
    results = rag_service.retriever.search(
        "商品签收后多久可以退款？",
        top_k=3,
    )

    assert results[0].source == "refund.md"
    assert results[0].score >= 0.08


@pytest.mark.unit
def test_shipping_question_retrieves_shipping_document(
    rag_service: RAGService,
) -> None:
    results = rag_service.retriever.search(
        "订单发货后在哪里查看物流？",
        top_k=3,
    )

    assert results[0].source == "shipping.md"
    assert results[0].score >= 0.08


@pytest.mark.unit
def test_unrelated_question_has_no_high_relevance_document(
    rag_service: RAGService,
) -> None:
    results = rag_service.retriever.search(
        "今天天气怎么样？",
        top_k=3,
    )

    assert max(result.score for result in results) < 0.08
