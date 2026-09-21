from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import rag as rag_api
from app.main import app
from app.rag.llm_client import MockLLMClient


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
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
