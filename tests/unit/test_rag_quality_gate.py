"""RAG 专项门禁的通过、失败和缺指标行为。"""

import copy

import pytest

from scripts import check_rag_quality_gate as gate


@pytest.fixture
def config() -> dict:
    return {
        "minimum_retrieval_recall_at_3": 0.90,
        "minimum_mrr": 0.80,
        "minimum_answer_relevance": 0.75,
        "minimum_citation_correctness": 0.95,
        "minimum_refusal_accuracy": 0.95,
        "maximum_p95_latency_ms": 3000,
        "maximum_security_failures": 0,
        "maximum_new_regressions": 0,
    }


@pytest.fixture
def retrieval_report() -> dict:
    return {
        "top_k": 3,
        "metrics": {
            "source_recall_after_threshold_at_k": 0.95,
            "mrr": 0.90,
        },
    }


@pytest.fixture
def promptfoo_report() -> dict:
    return {
        "results": {
            "results": [
                {
                    "provider": {"label": "vector-rag-api"},
                    "response": {"cached": False},
                    "latencyMs": 1000,
                    "success": True,
                    "gradingResult": {
                        "namedScores": {
                            "answer_relevance": 0.80,
                            "citation_correctness": 1.0,
                        }
                    },
                    "testCase": {"metadata": {"is_security": False}},
                },
                {
                    "provider": {"label": "vector-rag-api"},
                    "response": {"cached": False},
                    "latencyMs": 1200,
                    "success": True,
                    "gradingResult": {"namedScores": {"refusal_accuracy": 1.0}},
                    "testCase": {"metadata": {"is_security": True}},
                },
            ]
        },
        "baseline_comparison": {
            "common_total": 2,
            "removed_count": 0,
            "new_regressions_count": 0,
        },
    }


def run_gate(
    monkeypatch: pytest.MonkeyPatch,
    config: dict,
    retrieval_report: dict,
    promptfoo_report: dict,
) -> int:
    monkeypatch.setattr(gate, "load_config", lambda _: config)
    monkeypatch.setattr(
        gate,
        "read_json",
        lambda path: retrieval_report if path == "retrieval.json" else promptfoo_report,
    )
    return gate.main(
        [
            "--retrieval-result",
            "retrieval.json",
            "--promptfoo-result",
            "promptfoo.json",
            "--config",
            "config.yaml",
        ]
    )


@pytest.mark.unit
def test_all_metrics_pass(monkeypatch, config, retrieval_report, promptfoo_report) -> None:
    assert run_gate(monkeypatch, config, retrieval_report, promptfoo_report) == 0


@pytest.mark.unit
def test_checked_in_config_has_all_required_thresholds(config) -> None:
    assert gate.load_config("rag-quality-gate.yaml") == config


@pytest.mark.unit
@pytest.mark.parametrize(
    "metric",
    [
        "retrieval_recall_at_3",
        "mrr",
        "answer_relevance",
        "citation_correctness",
        "refusal_accuracy",
        "p95_latency_ms",
        "security_failures",
        "new_regressions",
    ],
)
def test_each_failed_rule_returns_one(
    monkeypatch, config, retrieval_report, promptfoo_report, metric
) -> None:
    retrieval = copy.deepcopy(retrieval_report)
    promptfoo = copy.deepcopy(promptfoo_report)
    if metric == "retrieval_recall_at_3":
        retrieval["metrics"]["source_recall_after_threshold_at_k"] = 0.89
    elif metric == "mrr":
        retrieval["metrics"]["mrr"] = 0.79
    elif metric in ("answer_relevance", "citation_correctness"):
        promptfoo["results"]["results"][0]["gradingResult"]["namedScores"][metric] = 0.70
    elif metric == "refusal_accuracy":
        promptfoo["results"]["results"][1]["gradingResult"]["namedScores"][metric] = 0.90
    elif metric == "p95_latency_ms":
        promptfoo["results"]["results"][1]["latencyMs"] = 3001
    elif metric == "security_failures":
        promptfoo["results"]["results"][1]["success"] = False
    else:
        promptfoo["baseline_comparison"]["new_regressions_count"] = 1

    assert run_gate(monkeypatch, config, retrieval, promptfoo) == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    "missing",
    [
        "mrr",
        "answer_relevance",
        "citation_correctness",
        "refusal_accuracy",
        "security_case",
        "baseline_comparison",
    ],
)
def test_missing_metric_returns_two(
    monkeypatch, config, retrieval_report, promptfoo_report, missing
) -> None:
    retrieval = copy.deepcopy(retrieval_report)
    promptfoo = copy.deepcopy(promptfoo_report)
    if missing == "mrr":
        del retrieval["metrics"]["mrr"]
    elif missing in ("answer_relevance", "citation_correctness"):
        del promptfoo["results"]["results"][0]["gradingResult"]["namedScores"][missing]
    elif missing == "refusal_accuracy":
        del promptfoo["results"]["results"][1]["gradingResult"]["namedScores"][missing]
    elif missing == "security_case":
        promptfoo["results"]["results"][1]["testCase"]["metadata"]["is_security"] = False
    else:
        del promptfoo["baseline_comparison"]

    assert run_gate(monkeypatch, config, retrieval, promptfoo) == 2


@pytest.mark.unit
@pytest.mark.parametrize("bad_value", [None, True, -0.1, 1.1, "0.9"])
def test_invalid_mrr_returns_two(
    monkeypatch, config, retrieval_report, promptfoo_report, bad_value
) -> None:
    retrieval_report["metrics"]["mrr"] = bad_value
    assert run_gate(monkeypatch, config, retrieval_report, promptfoo_report) == 2


@pytest.mark.unit
def test_wrong_top_k_returns_two(monkeypatch, config, retrieval_report, promptfoo_report) -> None:
    retrieval_report["top_k"] = 5
    assert run_gate(monkeypatch, config, retrieval_report, promptfoo_report) == 2


@pytest.mark.unit
def test_cached_latency_returns_two(
    monkeypatch, config, retrieval_report, promptfoo_report
) -> None:
    promptfoo_report["results"]["results"][0]["response"]["cached"] = True
    assert run_gate(monkeypatch, config, retrieval_report, promptfoo_report) == 2


@pytest.mark.unit
def test_removed_baseline_case_returns_two(
    monkeypatch, config, retrieval_report, promptfoo_report
) -> None:
    promptfoo_report["baseline_comparison"]["removed_count"] = 1
    assert run_gate(monkeypatch, config, retrieval_report, promptfoo_report) == 2


@pytest.mark.unit
def test_missing_report_returns_two(monkeypatch, config) -> None:
    monkeypatch.setattr(gate, "load_config", lambda _: config)

    def missing_report(_: str) -> dict:
        raise gate.RAGGateError("报告不存在")

    monkeypatch.setattr(gate, "read_json", missing_report)
    assert gate.main(["--retrieval-result", "missing.json"]) == 2
