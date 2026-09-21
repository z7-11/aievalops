import logging

import httpx
import pytest

from app.rag.llm_client import (
    MockLLMClient,
    OllamaClient,
    build_rag_prompt,
)
from app.rag.retriever import RetrievalResult


def make_ollama_client(api_key: str = "test-key") -> OllamaClient:
    return OllamaClient(
        base_url="http://127.0.0.1:11434/v1/",
        model="test-model",
        api_key=api_key,
    )


@pytest.mark.unit
def test_mock_client_uses_evidence_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("Mock 模式不应该请求外网")

    monkeypatch.setattr(httpx, "post", fail_if_called)

    prompt = build_rag_prompt(
        question="多久可以退款？",
        results=[
            RetrievalResult(
                source="refund.md",
                content="商品签收后 7 天内可以退款。",
                score=0.9,
                chunk_index=0,
            )
        ],
    )
    client = MockLLMClient()

    answer = client.generate(prompt)

    assert "7 天" in answer
    assert client.last_usage["estimated_cost_usd"] == 0.0


@pytest.mark.unit
def test_mock_client_refuses_when_there_is_no_evidence() -> None:
    prompt = build_rag_prompt(
        question="今天天气怎么样？",
        results=[],
    )

    answer = MockLLMClient().generate(prompt)

    assert answer == "暂时无法确认，请联系人工客服"


@pytest.mark.unit
def test_ollama_timeout_returns_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_ollama_client()
    request = httpx.Request("POST", client.api_url)

    def raise_timeout(*args: object, **kwargs: object) -> None:
        raise httpx.ReadTimeout(
            "timed out",
            request=request,
        )

    monkeypatch.setattr(httpx, "post", raise_timeout)

    with pytest.raises(
        RuntimeError,
        match="Ollama 请求超时",
    ):
        client.generate("test prompt")


@pytest.mark.unit
def test_ollama_empty_answer_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_ollama_client()
    request = httpx.Request("POST", client.api_url)

    def return_empty(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "message": {"content": "   "},
                "prompt_eval_count": 10,
                "eval_count": 0,
            },
            request=request,
        )

    monkeypatch.setattr(httpx, "post", return_empty)

    with pytest.raises(
        RuntimeError,
        match="Ollama 返回了空内容",
    ):
        client.generate("test prompt")


@pytest.mark.unit
def test_api_key_is_not_exposed_in_logs_or_errors(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "super-secret-api-key"
    client = make_ollama_client(api_key=secret)
    request = httpx.Request("POST", client.api_url)

    def raise_timeout(*args: object, **kwargs: object) -> None:
        raise httpx.ReadTimeout(
            "timed out",
            request=request,
        )

    monkeypatch.setattr(httpx, "post", raise_timeout)

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(RuntimeError) as error:
            client.generate("test prompt")

    assert secret not in caplog.text
    assert secret not in str(error.value)
