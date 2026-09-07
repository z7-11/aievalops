import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.mark.api
def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "mock-customer-service",
    }


@pytest.mark.api
def test_chat_refund_question() -> None:
    response = client.post(
        "/api/chat",
        json={
            "question": "商品签收后多久可以申请退款？",
        },
    )

    assert response.status_code == 200

    response_body = response.json()

    assert "7天" in response_body["answer"]
    assert "订单详情页" in response_body["answer"]
    assert response_body["model"] == "mock-customer-service-v1"
    assert response_body["latency_ms"] >= 0


@pytest.mark.api
def test_chat_response_contains_usage_information() -> None:
    response = client.post(
        "/api/chat",
        json={
            "question": "订单满多少钱可以包邮？",
        },
    )

    assert response.status_code == 200

    usage = response.json()["usage"]

    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0


@pytest.mark.api
def test_blank_question_should_return_validation_error() -> None:
    response = client.post(
        "/api/chat",
        json={
            "question": "   ",
        },
    )

    assert response.status_code == 422


@pytest.mark.api
def test_missing_question_should_return_validation_error() -> None:
    response = client.post(
        "/api/chat",
        json={},
    )

    assert response.status_code == 422
