import argparse
import math
import sys
from pathlib import Path

import yaml

# 支持直接运行：python scripts/check_quality_gate.py
# 把项目根目录加入模块搜索路径。
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.baseline_service import BaselineError, compare_cases
from app.services.result_parser import ReportError, parse_report


class GateError(ValueError):
    """质量门禁配置或必要指标无效。"""


RULE_NAMES = {
    "minimum_pass_rate",
    "minimum_p0_pass_rate",
    "maximum_p95_latency_ms",
    "maximum_average_cost_usd",
    "maximum_security_failures",
    "maximum_new_regressions",
}

OPTIONAL_RULES = {
    "maximum_average_cost_usd",
    "maximum_new_regressions",
}

INTEGER_RULES = {
    "maximum_p95_latency_ms",
    "maximum_security_failures",
    "maximum_new_regressions",
}

RATIO_RULES = {
    "minimum_pass_rate",
    "minimum_p0_pass_rate",
}


def load_config(path: str | Path) -> dict:
    """读取并校验六项质量规则。"""
    config_path = Path(path)

    try:
        text = config_path.read_text(encoding="utf-8-sig")
        config = yaml.safe_load(text)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise GateError(f"无法读取质量配置：{exc}") from exc

    if not isinstance(config, dict):
        raise GateError("质量配置必须是YAML键值对象")

    missing = RULE_NAMES - config.keys()
    unknown = config.keys() - RULE_NAMES

    if missing:
        raise GateError(f"缺少配置项：{', '.join(sorted(missing))}")

    if unknown:
        names = ", ".join(sorted(str(key) for key in unknown))
        raise GateError(f"存在未知配置项：{names}")

    for name, value in config.items():
        if value is None:
            if name in OPTIONAL_RULES:
                continue
            raise GateError(f"{name} 不允许为null")

        # bool是int的子类，使用type排除true/false误填。
        if type(value) not in (int, float):
            raise GateError(f"{name} 必须是数字")

        if not math.isfinite(value) or value < 0:
            raise GateError(f"{name} 必须是非负有限数字")

        if name in INTEGER_RULES and type(value) is not int:
            raise GateError(f"{name} 必须是整数")

        if name in RATIO_RULES and value > 1:
            raise GateError(f"{name} 必须在0到1之间")

        if name == "maximum_p95_latency_ms" and value <= 0:
            raise GateError("maximum_p95_latency_ms 必须大于0")

    return config


def require_metric(summary: dict, name: str) -> float:
    """启用的规则缺少有效指标时，明确拒绝判断。"""
    value = summary.get(name)

    if value is None:
        raise GateError(f"报告缺少有效指标：{name}")

    if type(value) not in (int, float):
        raise GateError(f"指标类型错误：{name}")

    if not math.isfinite(value) or value < 0:
        raise GateError(f"指标值无效：{name}")

    return float(value)


def check_quality(summary: dict, config: dict) -> list[dict]:
    """返回各项检查结果，不进行文件读写。"""

    rules = [
        (
            "整体通过率",
            "pass_rate",
            "minimum_pass_rate",
            ">=",
        ),
        (
            "P0通过率",
            "p0_pass_rate",
            "minimum_p0_pass_rate",
            ">=",
        ),
        (
            "P95延迟（毫秒）",
            "p95_latency_ms",
            "maximum_p95_latency_ms",
            "<=",
        ),
        (
            "安全失败数量",
            "security_failures",
            "maximum_security_failures",
            "<=",
        ),
    ]

    if config["maximum_average_cost_usd"] is not None:
        rules.append(
            (
                "平均成本（美元）",
                "average_cost_usd",
                "maximum_average_cost_usd",
                "<=",
            )
        )

    if config["maximum_new_regressions"] is not None:
        removed_count = require_metric(summary, "removed_count")
        common_total = require_metric(summary, "common_total")

        if common_total == 0:
            raise GateError("当前报告与基线没有共同用例，无法判断回归")

        if removed_count > 0:
            raise GateError(
                f"当前报告缺少基线中的{int(removed_count)}条用例；"
                "请恢复测试覆盖，或审核用例变更后建立新基线"
            )

        rules.append(
            (
                "新增回归数量",
                "new_regressions_count",
                "maximum_new_regressions",
                "<=",
            )
        )

    checks = []

    for label, metric_name, rule_name, operator in rules:
        actual = require_metric(summary, metric_name)
        threshold = config[rule_name]

        if operator == ">=":
            passed = actual >= threshold
        else:
            passed = actual <= threshold

        checks.append(
            {
                "label": label,
                "actual": actual,
                "operator": operator,
                "threshold": threshold,
                "passed": passed,
            }
        )

    return checks


def print_summary(summary: dict, config: dict, checks: list[dict]) -> None:
    print(f"总用例数：{summary['total']}")
    print(f"通过：{summary['passed']}")
    print(f"失败：{summary['failed']}")
    print(f"通过率：{summary['pass_rate']:.2%}")
    print(f"P95：{summary['p95_latency_ms']:g} ms")
    print(f"P0通过率：{summary['p0_pass_rate']:.2%}")
    print(f"安全失败：{summary['security_failures']}")

    if config["maximum_average_cost_usd"] is None:
        print("成本检查：未启用")
    else:
        print(f"平均成本：${summary['average_cost_usd']:.6f}")

    if config["maximum_new_regressions"] is None:
        print("基线检查：未启用")
    else:
        print(f"新增回归：{summary['new_regressions_count']}")
        print(f"已修复：{summary['fixed_count']}")
        print(f"新增用例：{summary['added_count']}")
        print(f"缺失用例：{summary['removed_count']}")

        for item in summary["new_regressions"]:
            print(f"  回归用例：{item['case_id']}")
    print()

    for check in checks:
        status = "通过" if check["passed"] else "失败"
        actual = f"{check['actual']:g}"
        threshold = f"{check['threshold']:g}"

        print(f"[{status}] {check['label']}：实际值={actual}，要求 {check['operator']} {threshold}")

    failures = [check for check in checks if not check["passed"]]

    print()
    if failures:
        print(f"质量门禁：失败，共{len(failures)}项规则不达标")
    else:
        print("质量门禁：通过")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="根据质量配置检查Promptfoo评测报告")
    parser.add_argument("--result", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--baseline",
        help="历史基线的原始Promptfoo JSON报告",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        summary = parse_report(args.result)

        if config["maximum_new_regressions"] is not None:
            if not args.baseline:
                raise GateError("已启用新增回归检查，必须通过--baseline指定基线报告")

            baseline = parse_report(args.baseline)
            comparison = compare_cases(
                baseline_cases=baseline["cases"],
                current_cases=summary["cases"],
            )
            summary.update(comparison)

        checks = check_quality(summary, config)

    except (GateError, ReportError, BaselineError) as exc:
        print(f"质量门禁无法执行：{exc}", file=sys.stderr)
        return 2

    print_summary(summary, config, checks)
    return 0 if all(check["passed"] for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
