from pathlib import Path

import yaml

from app.schemas.test_case import TestCaseRecord as CaseRecord
from app.services.promptfoo_config_service import (
    build_promptfoo_config,
    write_promptfoo_config,
)


def create_test_case() -> CaseRecord:
    return CaseRecord(
        case_id="refund_001",
        module="refund",
        priority="P0",
        question="商品签收后多久可以退款",
        expected_keywords=[
            "7天",
            "订单详情页",
        ],
        forbidden_keywords=[
            "3天",
        ],
        max_latency_ms=1000,
        security_category="functional",
    )


def test_build_promptfoo_config() -> None:
    test_case = create_test_case()

    config = build_promptfoo_config(
        test_cases=[test_case],
        target_url="http://127.0.0.1:3001/api/chat",
    )

    assert config["description"] == (
        "AIEvalOps Python 客服接口自动评测"
    )

    assert config["prompts"] == [
        "{{question}}",
    ]

    provider = config["providers"][0]

    assert provider["id"] == "http"

    provider_config = provider["config"]

    assert provider_config["url"] == (
        "http://127.0.0.1:3001/api/chat"
    )

    assert provider_config["method"] == "POST"

    promptfoo_test = config["tests"][0]

    assert promptfoo_test["description"] == (
        "refund_001 | refund | P0"
    )

    assert promptfoo_test["vars"] == {
        "question": "商品签收后多久可以退款",
    }

    assertions = promptfoo_test["assert"]

    assert assertions == [
        {
            "type": "contains",
            "value": "7天",
            "metric": "answer_accuracy",
        },
        {
            "type": "contains",
            "value": "订单详情页",
            "metric": "answer_accuracy",
        },
        {
            "type": "not-contains",
            "value": "3天",
            "metric": "safety",
        },
        {
            "type": "latency",
            "threshold": 1000,
            "metric": "response_latency",
        },
    ]


def test_write_promptfoo_config(
    tmp_path: Path,
) -> None:
    test_case = create_test_case()

    config = build_promptfoo_config(
        test_cases=[test_case],
        target_url="http://127.0.0.1:3001/api/chat",
    )

    output_path = (
        tmp_path
        / "generated_promptfooconfig.yaml"
    )

    result_path = write_promptfoo_config(
        config=config,
        output_path=output_path,
    )

    assert result_path == output_path
    assert output_path.exists()

    saved_config = yaml.safe_load(
        output_path.read_text(
            encoding="utf-8",
        )
    )

    assert saved_config["tests"][0]["vars"][
        "question"
    ] == "商品签收后多久可以退款"
