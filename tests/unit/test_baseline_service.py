import pytest

from app.services.baseline_service import BaselineError, compare_cases


def test_four_categories():
    baseline = [
        {"case_id": "a", "passed": True},
        {"case_id": "b", "passed": False},
        {"case_id": "c", "passed": False},
        {"case_id": "d", "passed": True},
    ]

    current = [
        {"case_id": "d", "passed": True},
        {"case_id": "c", "passed": False},
        {"case_id": "b", "passed": True},
        {"case_id": "a", "passed": False, "reason": "退款规则错误"},
    ]

    result = compare_cases(baseline, current)

    assert result["new_regressions_count"] == 1
    assert result["fixed_count"] == 1
    assert result["historical_failures_count"] == 1
    assert result["stable_count"] == 1
    assert result["new_regressions"][0]["case_id"] == "a"
    assert result["new_regressions"][0]["reason"] == "退款规则错误"


def test_added_and_removed_cases():
    baseline = [{"case_id": "old", "passed": True}]
    current = [{"case_id": "new", "passed": True}]

    result = compare_cases(baseline, current)

    assert result["common_total"] == 0
    assert result["added_count"] == 1
    assert result["removed_count"] == 1
    assert result["added"][0]["case_id"] == "new"
    assert result["removed"][0]["case_id"] == "old"


def test_order_does_not_matter():
    baseline = [
        {"case_id": "a", "passed": True},
        {"case_id": "b", "passed": False},
    ]

    result = compare_cases(baseline, list(reversed(baseline)))

    assert result["new_regressions_count"] == 0
    assert result["stable_count"] == 1
    assert result["historical_failures_count"] == 1


def test_duplicate_case_id_is_rejected():
    baseline = [
        {"case_id": "a", "passed": True},
        {"case_id": "a", "passed": False},
    ]

    with pytest.raises(BaselineError, match="重复case_id"):
        compare_cases(baseline, [{"case_id": "a", "passed": True}])


def test_empty_baseline_is_rejected():
    with pytest.raises(BaselineError, match="至少一条"):
        compare_cases([], [{"case_id": "a", "passed": True}])


def test_non_boolean_result_is_rejected():
    with pytest.raises(BaselineError, match="布尔值"):
        compare_cases(
            [{"case_id": "a", "passed": "false"}],
            [{"case_id": "a", "passed": True}],
        )