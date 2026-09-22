import pytest
import yaml

from scripts import check_quality_gate as gate


@pytest.fixture
def config():
    return {
        "minimum_pass_rate": 0.95,
        "minimum_p0_pass_rate": 1.0,
        "maximum_p95_latency_ms": 2000,
        "maximum_average_cost_usd": None,
        "maximum_security_failures": 0,
        "maximum_new_regressions": None,
    }


@pytest.fixture
def summary():
    return {
        "total": 100,
        "passed": 97,
        "failed": 3,
        "pass_rate": 0.97,
        "p95_latency_ms": 1450,
        "p0_pass_rate": 1.0,
        "security_failures": 0,
        "average_cost_usd": None,
    }


def test_all_rules_pass(summary, config):
    checks = gate.check_quality(summary, config)

    assert len(checks) == 4
    assert all(check["passed"] for check in checks)


@pytest.mark.parametrize(
    ("metric", "value"),
    [
        ("pass_rate", 0.94),
        ("p0_pass_rate", 0.9),
        ("p95_latency_ms", 2001),
        ("security_failures", 1),
    ],
)
def test_bad_metric_fails(summary, config, metric, value):
    summary[metric] = value

    checks = gate.check_quality(summary, config)

    assert any(not check["passed"] for check in checks)


def test_threshold_equality_passes(summary, config):
    summary["pass_rate"] = 0.95
    summary["p95_latency_ms"] = 2000

    assert all(check["passed"] for check in gate.check_quality(summary, config))


@pytest.mark.parametrize(
    "metric",
    ["pass_rate", "p0_pass_rate", "p95_latency_ms", "security_failures"],
)
def test_missing_required_metric_is_error(summary, config, metric):
    summary[metric] = None

    with pytest.raises(gate.GateError, match="缺少有效指标"):
        gate.check_quality(summary, config)


def test_enabled_cost_requires_data(summary, config):
    config["maximum_average_cost_usd"] = 0.01

    with pytest.raises(gate.GateError, match="average_cost_usd"):
        gate.check_quality(summary, config)


def test_high_cost_fails(summary, config):
    config["maximum_average_cost_usd"] = 0.01
    summary["average_cost_usd"] = 0.02

    checks = gate.check_quality(summary, config)

    assert checks[-1]["passed"] is False



@pytest.mark.parametrize("bad_value", [95, True, -0.1, "0.95"])
def test_invalid_config_is_rejected(tmp_path, config, bad_value):
    config["minimum_pass_rate"] = bad_value
    path = tmp_path / "quality-gate.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")

    with pytest.raises(gate.GateError):
        gate.load_config(path)


@pytest.mark.parametrize(
    ("pass_rate", "expected_code"),
    [(0.97, 0), (0.94, 1)],
)
def test_main_exit_codes(
    tmp_path,
    monkeypatch,
    config,
    summary,
    pass_rate,
    expected_code,
):
    config_path = tmp_path / "quality-gate.yaml"
    config_path.write_text(
        yaml.safe_dump(config),
        encoding="utf-8",
    )

    summary["pass_rate"] = pass_rate
    summary["passed"] = round(pass_rate * summary["total"])
    summary["failed"] = summary["total"] - summary["passed"]

    monkeypatch.setattr(gate, "parse_report", lambda _: summary)

    exit_code = gate.main(
        [
            "--result",
            "unused.json",
            "--config",
            str(config_path),
        ]
    )

    assert exit_code == expected_code


def test_missing_report_returns_two(tmp_path, config):
    config_path = tmp_path / "quality-gate.yaml"
    config_path.write_text(
        yaml.safe_dump(config),
        encoding="utf-8",
    )

    exit_code = gate.main(
        [
            "--result",
            str(tmp_path / "missing.json"),
            "--config",
            str(config_path),
        ]
    )

    assert exit_code == 2

def test_baseline_rule_requires_comparison_data(summary, config):
    config["maximum_new_regressions"] = 0

    with pytest.raises(gate.GateError, match="缺少有效指标"):
        gate.check_quality(summary, config)


def test_new_regression_fails_gate(summary, config):
    config["maximum_new_regressions"] = 0
    summary.update(
        {
            "removed_count": 0,
            "common_total": 100,
            "new_regressions_count": 1,
        }
    )

    checks = gate.check_quality(summary, config)

    assert checks[-1]["label"] == "新增回归数量"
    assert checks[-1]["passed"] is False


def test_no_regression_passes_gate(summary, config):
    config["maximum_new_regressions"] = 0
    summary.update(
        {
            "removed_count": 0,
            "common_total": 100,
            "new_regressions_count": 0,
        }
    )

    checks = gate.check_quality(summary, config)

    assert all(check["passed"] for check in checks)


def test_missing_baseline_case_is_error(summary, config):
    config["maximum_new_regressions"] = 0
    summary.update(
        {
            "removed_count": 1,
            "common_total": 99,
            "new_regressions_count": 0,
        }
    )

    with pytest.raises(gate.GateError, match="缺少基线"):
        gate.check_quality(summary, config)