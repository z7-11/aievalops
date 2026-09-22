import argparse
import json
import sys

from app.services.result_parser import ReportError, parse_report


class BaselineError(ValueError):
    """基线或当前结果无法进行可靠比较。"""


def index_cases(cases: list[dict], label: str) -> dict[str, dict]:
    if not isinstance(cases, list) or not cases:
        raise BaselineError(f"{label}必须包含至少一条用例")

    indexed = {}

    for case in cases:
        if not isinstance(case, dict):
            raise BaselineError(f"{label}包含非对象类型的用例")

        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise BaselineError(f"{label}包含无效case_id")

        case_id = case_id.strip()

        if case_id in indexed:
            raise BaselineError(f"{label}存在重复case_id：{case_id}")

        if type(case.get("passed")) is not bool:
            raise BaselineError(f"{label}中{case_id}的passed必须是布尔值")

        indexed[case_id] = case

    return indexed


def compare_cases(
    baseline_cases: list[dict],
    current_cases: list[dict],
) -> dict:
    baseline = index_cases(baseline_cases, "基线")
    current = index_cases(current_cases, "当前结果")

    baseline_ids = set(baseline)
    current_ids = set(current)

    common_ids = baseline_ids & current_ids
    added_ids = current_ids - baseline_ids
    removed_ids = baseline_ids - current_ids

    groups = {
        "new_regressions": [],
        "fixed": [],
        "historical_failures": [],
        "stable": [],
        "added": [],
        "removed": [],
    }

    for case_id in sorted(common_ids):
        before = baseline[case_id]["passed"]
        after = current[case_id]["passed"]

        item = {
            "case_id": case_id,
            "baseline_passed": before,
            "current_passed": after,
            "reason": current[case_id].get("reason"),
        }

        if before and not after:
            groups["new_regressions"].append(item)
        elif not before and after:
            groups["fixed"].append(item)
        elif not before and not after:
            groups["historical_failures"].append(item)
        else:
            groups["stable"].append(item)

    for case_id in sorted(added_ids):
        groups["added"].append(
            {
                "case_id": case_id,
                "current_passed": current[case_id]["passed"],
            }
        )

    for case_id in sorted(removed_ids):
        groups["removed"].append(
            {
                "case_id": case_id,
                "baseline_passed": baseline[case_id]["passed"],
            }
        )

    return {
        "baseline_total": len(baseline),
        "current_total": len(current),
        "common_total": len(common_ids),
        "new_regressions_count": len(groups["new_regressions"]),
        "fixed_count": len(groups["fixed"]),
        "historical_failures_count": len(groups["historical_failures"]),
        "stable_count": len(groups["stable"]),
        "added_count": len(groups["added"]),
        "removed_count": len(groups["removed"]),
        **groups,
    }


def compare_reports(baseline_path: str, current_path: str) -> dict:
    baseline = parse_report(baseline_path)
    current = parse_report(current_path)

    return compare_cases(
        baseline_cases=baseline["cases"],
        current_cases=current["cases"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="比较两份Promptfoo评测报告")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--current", required=True)
    args = parser.parse_args()

    try:
        comparison = compare_reports(args.baseline, args.current)
    except (BaselineError, ReportError) as exc:
        print(f"基线比较失败：{exc}", file=sys.stderr)
        return 2

    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())