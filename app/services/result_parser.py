import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


class ReportError(ValueError):
    """评测报告不存在、格式错误或缺少必要数据。"""


def require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"{name} 必须是JSON对象")
    return value


def require_number(value: Any, name: str) -> float:
    if type(value) not in (int, float):
        raise ReportError(f"{name} 必须是数字")

    if not math.isfinite(value) or value < 0:
        raise ReportError(f"{name} 必须是非负有限数字")

    return float(value)


def percentile(values: list[float], percent: int) -> float:
    """使用最近秩法计算百分位数。"""
    if not values:
        raise ReportError("没有可用于计算百分位数的数据")

    ordered = sorted(values)
    index = math.ceil(len(ordered) * percent / 100) - 1
    return ordered[index]


def parse_report(report_path: str | Path) -> dict[str, Any]:
    path = Path(report_path)

    try:
        raw_text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ReportError(f"无法读取报告：{path}，原因：{exc}") from exc

    try:
        document = json.loads(raw_text)
    except ValueError as exc:
        raise ReportError(f"报告不是有效JSON：{path}") from exc

    document = require_object(document, "报告根节点")
    container = require_object(document.get("results"), "results")
    rows = container.get("results")

    if not isinstance(rows, list) or not rows:
        raise ReportError("results.results 必须是非空列表")

    cases = []
    seen_ids = set()
    latencies = []
    known_costs = []

    for index, raw_row in enumerate(rows, start=1):
        prefix = f"第{index}条结果"
        row = require_object(raw_row, prefix)

        success = row.get("success")
        if type(success) is not bool:
            raise ReportError(f"{prefix}.success 必须是布尔值")

        test_case = require_object(row.get("testCase"), f"{prefix}.testCase")
        metadata = require_object(
            test_case.get("metadata"),
            f"{prefix}.testCase.metadata",
        )

        case_id = metadata.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ReportError(f"{prefix}缺少有效的metadata.case_id")

        case_id = case_id.strip()
        if case_id in seen_ids:
            raise ReportError(
                f"重复case_id：{case_id}。本版解析器只支持单模型、单Prompt、每条用例执行一次的报告"
            )
        seen_ids.add(case_id)

        priority = metadata.get("priority")
        if priority not in ("P0", "P1", "P2"):
            raise ReportError(f"{case_id}的priority必须为P0、P1或P2")

        is_security = metadata.get("is_security")
        if type(is_security) is not bool:
            raise ReportError(f"{case_id}的is_security必须为true或false")

        latency = require_number(
            row.get("latencyMs"),
            f"{case_id}.latencyMs",
        )

        response = require_object(
            row.get("response", {}),
            f"{case_id}.response",
        )

        if response.get("cached") is True:
            raise ReportError(
                f"{case_id}使用了缓存，无法用于本次延迟统计；请使用--no-cache重新评测"
            )

        error = row.get("error")
        if success and error:
            raise ReportError(f"{case_id}同时标记成功和错误，报告不一致")

        # 成功的结果必须有实际输出；调用失败时允许没有output。
        if success and ("output" not in response or response["output"] is None):
            raise ReportError(f"{case_id}标记成功，但缺少response.output")

        grading = require_object(
            row.get("gradingResult", {}),
            f"{case_id}.gradingResult",
        )

        if "pass" in grading:
            if type(grading["pass"]) is not bool:
                raise ReportError(f"{case_id}.gradingResult.pass类型错误")
            if grading["pass"] != success:
                raise ReportError(f"{case_id}的success与gradingResult.pass不一致")

        reason = None
        if not success:
            raw_reason = error or grading.get("reason")
            reason = str(raw_reason) if raw_reason else "报告未提供失败原因"

        # 只读取Provider明确返回的response.cost。
        # 不使用结果顶层的cost默认值推断真实费用。
        cost = None
        if response.get("cost") is not None:
            cost = require_number(
                response["cost"],
                f"{case_id}.response.cost",
            )
            known_costs.append(cost)

        latencies.append(latency)

        cases.append(
            {
                "case_id": case_id,
                "priority": priority,
                "is_security": is_security,
                "passed": success,
                "output": response.get("output"),
                "reason": reason,
                "latency_ms": latency,
                "cost_usd": cost,
            }
        )

    total = len(cases)
    passed = sum(case["passed"] for case in cases)
    failed = total - passed

    p0_cases = [case for case in cases if case["priority"] == "P0"]
    p0_passed = sum(case["passed"] for case in p0_cases)

    security_cases = [case for case in cases if case["is_security"]]
    security_failures = sum(not case["passed"] for case in security_cases)

    # 如果报告带有汇总计数，再检查其是否与明细一致。
    stats = container.get("stats")
    if stats is not None:
        stats = require_object(stats, "results.stats")
        for key in ("successes", "failures", "errors"):
            if type(stats.get(key)) is not int or stats[key] < 0:
                raise ReportError(f"results.stats.{key}必须是非负整数")

        if stats["successes"] != passed:
            raise ReportError("报告汇总成功数与明细成功数不一致")

        if stats["failures"] + stats["errors"] != failed:
            raise ReportError("报告汇总失败/错误数与明细不一致")

    costs_complete = len(known_costs) == total

    return {
        "schema_version": 1,
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / total,
        "p0_total": len(p0_cases),
        "p0_passed": p0_passed,
        "p0_failed": len(p0_cases) - p0_passed,
        "p0_pass_rate": (p0_passed / len(p0_cases) if p0_cases else None),
        "security_total": len(security_cases),
        "security_failures": (security_failures if security_cases else None),
        "p50_latency_ms": percentile(latencies, 50),
        "p95_latency_ms": percentile(latencies, 95),
        "p99_latency_ms": percentile(latencies, 99),
        "cost_known_count": len(known_costs),
        "cost_missing_count": total - len(known_costs),
        "average_cost_usd": (sum(known_costs) / total if costs_complete else None),
        "failures": [case for case in cases if not case["passed"]],
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="解析Promptfoo单模型评测报告")
    parser.add_argument("--input", required=True, help="原始JSON报告路径")
    arguments = parser.parse_args()

    try:
        summary = parse_report(arguments.input)
    except ReportError as exc:
        print(f"报告解析失败：{exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
