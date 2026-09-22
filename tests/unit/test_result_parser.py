import json

import pytest

from app.services.result_parser import ReportError, parse_report


def make_report():
    cases = []

    settings = [
        ("refund_001", True, "P0", False, 100),
        ("security_001", False, "P0", True, 300),
        ("service_001", True, "P1", False, 200),
    ]

    for case_id, passed, priority, is_security, latency in settings:
        cases.append(
            {
                "success": passed,
                "latencyMs": latency,
                "testCase": {
                    "metadata": {
                        "case_id": case_id,
                        "priority": priority,
                        "is_security": is_security,
                    }
                },
                "response": {
                    "output": "模拟回答",
                    "cached": False,
                    "cost": 0.003,
                },
                "gradingResult": {
                    "pass": passed,
                    "reason": "通过" if passed else "未满足安全断言",
                },
            }
        )

    return {
        "results": {
            "results": cases,
            "stats": {
                "successes": 2,
                "failures": 1,
                "errors": 0,
            },
        }
    }


def save_report(tmp_path, report):
    path = tmp_path / "eval.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_summary_calculation(tmp_path):
    path = save_report(tmp_path, make_report())

    summary = parse_report(path)

    assert summary["total"] == 3
    assert summary["passed"] == 2
    assert summary["failed"] == 1
    assert summary["pass_rate"] == pytest.approx(2 / 3)
    assert summary["p0_total"] == 2
    assert summary["p0_failed"] == 1
    assert summary["p0_pass_rate"] == 0.5
    assert summary["security_failures"] == 1
    assert summary["p50_latency_ms"] == 200
    assert summary["p95_latency_ms"] == 300
    assert summary["p99_latency_ms"] == 300
    assert summary["average_cost_usd"] == pytest.approx(0.003)
    assert summary["failures"][0]["reason"] == "未满足安全断言"


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(ReportError, match="无法读取报告"):
        parse_report(tmp_path / "missing.json")


def test_invalid_json_is_rejected(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(ReportError, match="不是有效JSON"):
        parse_report(path)


@pytest.mark.parametrize("field", ["success", "latencyMs", "testCase"])
def test_missing_required_field_is_rejected(tmp_path, field):
    report = make_report()
    del report["results"]["results"][0][field]
    path = save_report(tmp_path, report)

    with pytest.raises(ReportError):
        parse_report(path)


def test_missing_classification_is_rejected(tmp_path):
    report = make_report()
    report["results"]["results"][0]["testCase"]["metadata"] = {}
    path = save_report(tmp_path, report)

    with pytest.raises(ReportError, match="case_id"):
        parse_report(path)


def test_unknown_cost_is_not_assumed_to_be_zero(tmp_path):
    report = make_report()
    row = report["results"]["results"][0]
    del row["response"]["cost"]
    row["cost"] = 0
    path = save_report(tmp_path, report)

    summary = parse_report(path)

    assert summary["average_cost_usd"] is None
    assert summary["cost_missing_count"] == 1


def test_no_p0_or_security_cases_is_not_a_pass(tmp_path):
    report = make_report()
    for row in report["results"]["results"]:
        row["testCase"]["metadata"]["priority"] = "P1"
        row["testCase"]["metadata"]["is_security"] = False

    summary = parse_report(save_report(tmp_path, report))

    assert summary["p0_pass_rate"] is None
    assert summary["security_failures"] is None


def test_duplicate_case_id_is_rejected(tmp_path):
    report = make_report()
    report["results"]["results"][1]["testCase"]["metadata"]["case_id"] = (
        "refund_001"
    )

    with pytest.raises(ReportError, match="重复case_id"):
        parse_report(save_report(tmp_path, report))


def test_inconsistent_stats_are_rejected(tmp_path):
    report = make_report()
    report["results"]["stats"]["successes"] = 99

    with pytest.raises(ReportError, match="汇总成功数"):
        parse_report(save_report(tmp_path, report))


def test_cached_latency_is_rejected(tmp_path):
    report = make_report()
    report["results"]["results"][0]["response"]["cached"] = True

    with pytest.raises(ReportError, match="缓存"):
        parse_report(save_report(tmp_path, report))
        