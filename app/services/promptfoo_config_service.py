from pathlib import Path

import yaml

from app.schemas.test_case import TestCaseRecord


def build_assertions(
    test_case: TestCaseRecord,
) -> list[dict]:
    """
    把一条测试用例转换成 Promptfoo 的断言列表。
    """

    assertions: list[dict] = []

    # 期望关键词：回答中必须包含
    for keyword in test_case.expected_keywords:
        assertions.append(
            {
                "type": "contains",
                "value": keyword,
                "metric": "answer_accuracy",
            }
        )

    # 禁止关键词：回答中不能包含
    for keyword in test_case.forbidden_keywords:
        assertions.append(
            {
                "type": "not-contains",
                "value": keyword,
                "metric": "safety",
            }
        )

    # 响应时间：不能超过指定阈值
    assertions.append(
        {
            "type": "latency",
            "threshold": test_case.max_latency_ms,
            "metric": "response_latency",
        }
    )

    return assertions


def build_promptfoo_config(
    test_cases: list[TestCaseRecord],
    target_url: str,
) -> dict:
    """
    将测试用例列表转换为 Promptfoo 配置字典。

    参数：
        test_cases:
            数据加载器返回的 TestCaseRecord 列表。

        target_url:
            被测试的 Python API 地址，
            例如：http://127.0.0.1:3001/api/chat

    返回：
        可以保存为 YAML 的 Promptfoo 配置字典。
    """

    target_url = target_url.strip()

    if not target_url:
        raise ValueError("target_url 不能为空")

    if not test_cases:
        raise ValueError("test_cases 不能为空")

    promptfoo_tests: list[dict] = []

    # 一条 TestCaseRecord 转换成 Promptfoo 中的一条 tests
    for test_case in test_cases:
        promptfoo_test = {
            "description": (
                f"{test_case.case_id} "
                f"| {test_case.module} "
                f"| {test_case.priority}"
            ),
            "vars": {
                "question": test_case.question,
            },
            "assert": build_assertions(test_case),
        }

        promptfoo_tests.append(promptfoo_test)

    config = {
        "description": "AIEvalOps Python 客服接口自动评测",
        "prompts": [
            "{{question}}",
        ],
        "providers": [
            {
                "id": "http",
                "label": "python-customer-service-api",
                "config": {
                    "url": target_url,
                    "method": "POST",
                    "headers": {
                        "Content-Type": "application/json",
                    },
                    "body": {
                        "question": "{{prompt}}",
                    },
                    "transformResponse": "json.answer",
                },
            },
        ],
        "tests": promptfoo_tests,
    }

    return config


def write_promptfoo_config(
    config: dict,
    output_path: Path,
) -> Path:
    """
    将 Promptfoo 配置字典保存成 YAML 文件。
    """

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    yaml_text = yaml.safe_dump(
        config,
        allow_unicode=True,
        sort_keys=False,
    )

    output_path.write_text(
        yaml_text,
        encoding="utf-8",
    )

    return output_path