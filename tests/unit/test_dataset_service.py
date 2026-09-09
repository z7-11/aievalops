from pathlib import Path

import pandas as pd
import pytest

from app.services.dataset_service import (
    load_dataset,
    split_keywords,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

NORMAL_CSV_PATH = (
    PROJECT_ROOT
    / "data"
    / "examples"
    / "customer_service_cases.csv"
)

DUPLICATE_CSV_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "duplicate_cases.csv"
)

MISSING_COLUMNS_CSV_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "missing_columns.csv"
)


def test_split_keywords正常拆分关键词() -> None:
    result = split_keywords(
        "7天 | 订单详情页 | "
    )

    assert result == [
        "7天",
        "订单详情页",
    ]


def test_split_keywords空值返回空列表() -> None:
    assert split_keywords("") == []
    assert split_keywords(None) == []


def test_load_dataset正常读取_csv() -> None:
    records = load_dataset(NORMAL_CSV_PATH)

    assert len(records) == 5

    first_record = records[0]

    assert first_record.case_id == "refund_001"
    assert first_record.priority == "P0"
    assert first_record.expected_keywords == [
        "7天",
        "订单详情页",
    ]
    assert first_record.forbidden_keywords == [
        "3天",
    ]
    assert first_record.max_latency_ms == 1000


def test_load_dataset正常读取_xlsx(
    tmp_path: Path,
) -> None:
    data = {
        "case_id": ["xlsx_001"],
        "module": ["refund"],
        "priority": ["P1"],
        "question": ["Excel 测试问题"],
        "expected_keywords": ["7天|订单详情页"],
        "forbidden_keywords": [""],
        "max_latency_ms": ["1500"],
        "security_category": ["functional"],
    }

    dataframe = pd.DataFrame(data)
    xlsx_path = tmp_path / "test_cases.xlsx"

    dataframe.to_excel(
        xlsx_path,
        index=False,
    )

    records = load_dataset(xlsx_path)

    assert len(records) == 1
    assert records[0].case_id == "xlsx_001"
    assert records[0].expected_keywords == [
        "7天",
        "订单详情页",
    ]


def test_load_dataset缺少必填列时失败() -> None:
    with pytest.raises(
        ValueError,
        match="数据文件缺少必填列",
    ):
        load_dataset(MISSING_COLUMNS_CSV_PATH)


def test_load_dataset_case_id重复时失败() -> None:
    with pytest.raises(
        ValueError,
        match="case_id 重复",
    ):
        load_dataset(DUPLICATE_CSV_PATH)


def test_load_dataset非法优先级时失败(
    tmp_path: Path,
) -> None:
    data = {
        "case_id": ["invalid_priority_001"],
        "module": ["refund"],
        "priority": ["P3"],
        "question": ["商品可以退款吗"],
        "expected_keywords": ["7天"],
        "forbidden_keywords": [""],
        "max_latency_ms": ["1000"],
        "security_category": ["functional"],
    }

    dataframe = pd.DataFrame(data)
    csv_path = tmp_path / "invalid_priority.csv"

    dataframe.to_csv(
        csv_path,
        index=False,
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="priority",
    ):
        load_dataset(csv_path)