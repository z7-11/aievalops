"""检查 RAG 专项指标；0=通过，1=未达阈值，2=输入缺失或无效。"""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RATIO_RULES = {
    "minimum_retrieval_recall_at_3",
    "minimum_mrr",
    "minimum_answer_relevance",
    "minimum_citation_correctness",
    "minimum_refusal_accuracy",
}
COUNT_RULES = {"maximum_security_failures", "maximum_new_regressions"}
RULES = RATIO_RULES | COUNT_RULES | {"maximum_p95_latency_ms"}
CHECKS = (
    ("检索召回率@3", "retrieval_recall_at_3", "minimum_retrieval_recall_at_3", ">="),
    ("MRR", "mrr", "minimum_mrr", ">="),
    ("答案相关性", "answer_relevance", "minimum_answer_relevance", ">="),
    ("引用正确性", "citation_correctness", "minimum_citation_correctness", ">="),
    ("拒答准确率", "refusal_accuracy", "minimum_refusal_accuracy", ">="),
    ("P95 延迟（毫秒）", "p95_latency_ms", "maximum_p95_latency_ms", "<="),
    ("安全失败数", "security_failures", "maximum_security_failures", "<="),
    ("新增回归数", "new_regressions", "maximum_new_regressions", "<="),
)


class RAGGateError(ValueError):
    """门禁缺少可信指标，或输入格式错误。"""


def resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RAGGateError(f"缺少或无效的对象：{name}")
    return value


def require_number(value: Any, name: str, *, ratio: bool = False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise RAGGateError(f"缺少或无效的数值：{name}")
    if ratio and value > 1:
        raise RAGGateError(f"比例指标必须在 0～1 之间：{name}")
    return float(value)


def require_count(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise RAGGateError(f"缺少或无效的非负整数：{name}")
    return value


def read_json(path: str | Path) -> dict[str, Any]:
    resolved = resolve_path(path)
    try:
        document = json.loads(resolved.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RAGGateError(f"无法读取 JSON 报告 {resolved}：{error}") from error
    return require_object(document, str(resolved))


def load_config(path: str | Path) -> dict[str, float | int]:
    resolved = resolve_path(path)
    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise RAGGateError(f"无法读取门禁配置 {resolved}：{error}") from error
    config = require_object(raw, "rag-quality-gate.yaml")
    missing = RULES - config.keys()
    unknown = config.keys() - RULES
    if missing or unknown:
        raise RAGGateError(
            f"配置项不完整：缺少 {sorted(missing)}；未知 {sorted(str(key) for key in unknown)}"
        )
    for name, value in config.items():
        if name in COUNT_RULES:
            require_count(value, name)
        else:
            require_number(value, name, ratio=name in RATIO_RULES)
    if config["maximum_p95_latency_ms"] <= 0:
        raise RAGGateError("maximum_p95_latency_ms 必须大于 0")
    return config


def retrieval_metrics(report: dict[str, Any]) -> dict[str, float]:
    top_k = report.get("top_k")
    if type(top_k) is not int or top_k != 3:
        raise RAGGateError("检索报告的 top_k 必须明确为 3，不能混用其他 K")
    metrics = require_object(report.get("metrics"), "检索报告.metrics")

    # 与 scripts/evaluate_retrieval.py 的真实输出字段保持一致。
    recall = require_number(
        metrics.get("source_recall_after_threshold_at_k"),
        "metrics.source_recall_after_threshold_at_k",
        ratio=True,
    )
    # 旧版报告没有 MRR；必须由检索评测明确提供，不能拿召回率代替。
    mrr = require_number(metrics.get("mrr"), "metrics.mrr", ratio=True)
    return {"retrieval_recall_at_3": recall, "mrr": mrr}


def promptfoo_metrics(report: dict[str, Any]) -> dict[str, float | int]:
    container = require_object(report.get("results"), "Promptfoo results")
    rows = container.get("results")
    if not isinstance(rows, list) or not rows:
        raise RAGGateError("Promptfoo results.results 必须是非空列表")

    scores: dict[str, list[float]] = {
        "answer_relevance": [],
        "citation_correctness": [],
        "refusal_accuracy": [],
    }
    latencies: list[float] = []
    security_total = 0
    security_failures = 0
    providers: set[str] = set()

    for index, raw_row in enumerate(rows, start=1):
        name = f"Promptfoo 第 {index} 条结果"
        row = require_object(raw_row, name)
        provider = require_object(row.get("provider"), f"{name}.provider")
        label = provider.get("label")
        if not isinstance(label, str) or not label:
            raise RAGGateError(f"{name}缺少 provider.label")
        providers.add(label)

        response = require_object(row.get("response"), f"{name}.response")
        if response.get("cached") is True:
            raise RAGGateError(f"{name}使用了缓存，不能用于延迟门禁")
        latencies.append(require_number(row.get("latencyMs"), f"{name}.latencyMs"))

        grading = require_object(row.get("gradingResult"), f"{name}.gradingResult")
        named_scores = require_object(grading.get("namedScores"), f"{name}.namedScores")
        for metric_name, observations in scores.items():
            if metric_name in named_scores:
                observations.append(
                    require_number(named_scores[metric_name], f"{name}.{metric_name}", ratio=True)
                )

        test_case = require_object(row.get("testCase"), f"{name}.testCase")
        metadata = require_object(test_case.get("metadata"), f"{name}.metadata")
        if "is_security" in metadata and type(metadata["is_security"]) is not bool:
            raise RAGGateError(f"{name}.metadata.is_security 必须是布尔值")
        if metadata.get("is_security") is True:
            security_total += 1
            if type(row.get("success")) is not bool:
                raise RAGGateError(f"{name}.success 必须是布尔值")
            security_failures += not row["success"]

    if len(providers) != 1:
        raise RAGGateError("Promptfoo 报告包含多个 Provider，请先导出单版本报告")
    if security_total == 0:
        raise RAGGateError("缺少安全用例标记 metadata.is_security，不能认定安全失败数为 0")

    for metric_name, observations in scores.items():
        if not observations:
            raise RAGGateError(f"缺少 Promptfoo 指标：{metric_name}")

    comparison = report.get("baseline_comparison", container.get("baseline_comparison"))
    comparison = require_object(comparison, "baseline_comparison")
    common_total = require_count(comparison.get("common_total"), "common_total")
    removed_count = require_count(comparison.get("removed_count"), "removed_count")
    new_regressions = require_count(
        comparison.get("new_regressions_count"), "new_regressions_count"
    )
    if common_total == 0 or removed_count != 0:
        raise RAGGateError("基线没有共同用例或有缺失用例，不能可靠判断新增回归")

    latencies.sort()
    p95_index = math.ceil(len(latencies) * 0.95) - 1
    return {
        **{name: sum(values) / len(values) for name, values in scores.items()},
        "p95_latency_ms": latencies[p95_index],
        "security_failures": security_failures,
        "new_regressions": new_regressions,
    }


def check_metrics(
    metrics: dict[str, float | int], config: dict[str, float | int]
) -> list[tuple[str, float | int, str, float | int, bool]]:
    checks = []
    for label, metric_name, rule_name, operator in CHECKS:
        actual = metrics[metric_name]
        threshold = config[rule_name]
        passed = actual >= threshold if operator == ">=" else actual <= threshold
        checks.append((label, actual, operator, threshold, passed))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAG 专项质量门禁：0 通过，1 不达标，2 缺指标")
    parser.add_argument("--retrieval-result", default="results/experiments/retrieval-metrics.json")
    parser.add_argument("--promptfoo-result", default="results/vector-rag-eval.json")
    parser.add_argument("--config", default="rag-quality-gate.yaml")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        retrieval = retrieval_metrics(read_json(args.retrieval_result))
        promptfoo = promptfoo_metrics(read_json(args.promptfoo_result))
        checks = check_metrics({**retrieval, **promptfoo}, config)
    except RAGGateError as error:
        print(f"RAG 质量门禁无法判断：{error}", file=sys.stderr)
        return 2

    for label, actual, operator, threshold, passed in checks:
        status = "通过" if passed else "失败"
        print(f"[{status}] {label}：{actual:g} {operator} {threshold:g}")

    if all(check[-1] for check in checks):
        print("RAG 质量门禁：通过")
        return 0
    print("RAG 质量门禁：失败，至少一项指标未达标")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
