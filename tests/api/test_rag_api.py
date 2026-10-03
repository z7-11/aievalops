from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import rag as rag_api
from app.main import app
from app.rag.llm_client import MockLLMClient
from app.rag.vector_store import VectorSearchResult


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    monkeypatch.setattr(
        rag_api.settings,
        "rag_retriever_type",
        "tfidf",
    )
    monkeypatch.setattr(
        rag_api.settings,
        "rag_min_relevance_score",
        0.08,
    )
    monkeypatch.setattr(
        rag_api.settings,
        "llm_mock_mode",
        True,
    )
    monkeypatch.setattr(
        rag_api,
        "create_llm_client",
        MockLLMClient,
    )
    rag_api.get_rag_service.cache_clear()

    with TestClient(app) as test_client:
        yield test_client

    rag_api.get_rag_service.cache_clear()


@pytest.mark.api
def test_refund_answer_has_correct_source_and_evidence(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/rag/query",
        json={
            "question": "商品签收后多久可以退款？",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    data = response.json()
    normalized_answer = data["answer"].replace(" ", "")

    assert "7天" in normalized_answer
    assert data["sources"][0]["file"] == "refund.md"
    assert data["sources"][0]["page"] is None
    assert data["sources"][0]["chunk_id"]
    assert "7天" in data["sources"][0]["excerpt"].replace(" ", "")
    assert data["model"] == "mock"
    assert data["usage"]["estimated_cost_usd"] == 0.0

    project_root = Path(__file__).resolve().parents[2]
    source_text = (project_root / "knowledge" / "refund.md").read_text(encoding="utf-8")

    assert "7天" in source_text.replace(" ", "")


@pytest.mark.api
def test_shipping_answer_retrieves_shipping_source(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/rag/query",
        json={
            "question": "订单发货后在哪里查看物流？",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["sources"][0]["file"] == "shipping.md"
    assert "我的订单" in data["answer"]


@pytest.mark.api
def test_unrelated_question_refuses_without_sources(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/rag/query",
        json={
            "question": "今天天气怎么样？",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["answer"] == "暂时无法确认，请联系人工客服"
    assert data["sources"] == []


@pytest.mark.api
def test_blank_rag_question_returns_validation_error(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/rag/query",
        json={"question": "   "},
    )

    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.parametrize("top_k", [0, 11, "invalid"])
def test_invalid_top_k_returns_validation_error(client: TestClient, top_k: object) -> None:
    response = client.post("/api/rag/query", json={"question": "多久可以退款？", "top_k": top_k})
    assert response.status_code == 422


@pytest.mark.api
def test_rag_api_returns_excerpt(client: TestClient) -> None:
    response = client.post("/api/rag/query", json={"question": "商品签收后多久可以退款？"})

    assert response.status_code == 200
    source = response.json()["sources"][0]
    assert source["file"] == "refund.md"
    assert "7 天" in source["excerpt"]


@pytest.mark.api
def test_prompt_versions_use_same_retrieval_with_different_templates(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []

    class RecordingClient(MockLLMClient):
        def generate(self, prompt: str) -> str:
            prompts.append(prompt)
            return super().generate(prompt)

    monkeypatch.setattr(rag_api, "create_llm_client", RecordingClient)

    base_request = {"question": "商品签收后多久可以退款？", "top_k": 3}
    default_response = client.post("/api/rag/query", json=base_request)
    v2_response = client.post("/api/rag/query", json={**base_request, "prompt_version": "v2"})

    assert default_response.status_code == 200
    assert v2_response.status_code == 200
    assert default_response.json()["sources"] == v2_response.json()["sources"]
    assert len(prompts) == 2
    assert "[来源：refund.md]" not in prompts[0]
    assert "[来源：refund.md]" in prompts[1]


@pytest.mark.api
def test_unknown_prompt_version_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/rag/query",
        json={"question": "多久可以退款？", "prompt_version": "v3"},
    )
    assert response.status_code == 422


@pytest.mark.api
def test_rag_api_returns_pdf_page(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeEmbeddingModel:
        def encode_query(self, question: str) -> list[float]:
            assert question == "个人信息用于什么？"
            return [1.0, 0.0]

    class FakeVectorStore:
        def query(
            self,
            query_embedding: list[float],
            top_k: int,
        ) -> list[VectorSearchResult]:
            assert query_embedding == [1.0, 0.0]
            assert top_k == 2
            return [
                VectorSearchResult(
                    source="raw/privacy.pdf",
                    content="用户个人信息仅用于订单处理。",
                    score=0.91,
                    chunk_index=0,
                    page=1,
                    chunk_id="privacy-page-1-chunk-0",
                )
            ]

    monkeypatch.setattr(rag_api.settings, "rag_retriever_type", "chroma")
    monkeypatch.setattr(rag_api.settings, "rag_vector_min_similarity_score", 0.45)
    monkeypatch.setattr(
        rag_api,
        "get_vector_components",
        lambda: (FakeEmbeddingModel(), FakeVectorStore()),
    )

    response = client.post(
        "/api/rag/query",
        json={"question": "个人信息用于什么？", "top_k": 2},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "用户个人信息仅用于订单处理。"
    assert data["sources"] == [
        {
            "file": "raw/privacy.pdf",
            "page": 1,
            "chunk_index": 0,
            "chunk_id": "privacy-page-1-chunk-0",
            "score": 0.91,
            "excerpt": "用户个人信息仅用于订单处理。",
        }
    ]


@pytest.mark.api
def test_unrelated_question_has_no_valid_source(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeEmbeddingModel:
        def encode_query(self, question: str) -> list[float]:
            assert question == "平台是否提供机票预订？"
            return [1.0, 0.0]

    class FakeVectorStore:
        def query(self, query_embedding: list[float], top_k: int) -> list[VectorSearchResult]:
            return [
                VectorSearchResult(
                    source="refund.md",
                    content="普通商品签收后 7 天内可退款。",
                    score=0.20,
                    chunk_index=0,
                    page=None,
                    chunk_id="low-score",
                )
            ]

    monkeypatch.setattr(rag_api.settings, "rag_retriever_type", "chroma")
    monkeypatch.setattr(rag_api.settings, "rag_vector_min_similarity_score", 0.45)
    monkeypatch.setattr(
        rag_api, "get_vector_components", lambda: (FakeEmbeddingModel(), FakeVectorStore())
    )

    response = client.post("/api/rag/query", json={"question": "平台是否提供机票预订？"})

    assert response.status_code == 200
    assert response.json()["sources"] == []
    assert response.json()["answer"] == "暂时无法确认，请联系人工客服"
