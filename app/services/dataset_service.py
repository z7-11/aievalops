from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from app.schemas.test_case import TestCaseRecord

REQUIRED_COLUMNS = {
    "case_id",
    "module",
    "priority",
    "question",
    "expected_keywords",
    "forbidden_keywords",
    "max_latency_ms",
    "security_category",
}

SUPPORTED_SUFFIXES = {
    ".csv",
    ".xlsx",
}


def split_keywords(value: Any) -> list[str]:
    """
    将关键词字符串转换为列表。

    例如：
    "7天|订单详情页"
    转换为：
    ["7天", "订单详情页"]
    """

    if value is None:
        return []

    if isinstance(value, float) and pd.isna(value):
        return []

    text = str(value).strip()

    if not text:
        return []

    return [
        item.strip()
        for item in text.split("|")
        if item.strip()
    ]


def read_dataset_file(file_path: Path) -> pd.DataFrame:
    """
    根据文件后缀读取 CSV 或 Excel 文件。
    """

    suffix = file_path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(
            file_path,
            dtype=str,
            keep_default_na=False,
        )

    if suffix == ".xlsx":
        return pd.read_excel(
            file_path,
            dtype=str,
        ).fillna("")

    raise ValueError(
        f"不支持的文件类型：{suffix}，"
        "目前只支持 .csv 和 .xlsx"
    )


def format_validation_errors(
    validation_error: ValidationError,
) -> str:
    """
    将 Pydantic 错误转换成容易阅读的文本。
    """

    messages: list[str] = []

    for error in validation_error.errors():
        location = ".".join(
            str(item)
            for item in error["loc"]
        )

        messages.append(
            f"{location}: {error['msg']}"
        )

    return "; ".join(messages)


def load_dataset(
    file_path: Path,
) -> list[TestCaseRecord]:
    """
    读取并校验 CSV/Excel 测试数据。

    参数：
        file_path: CSV 或 Excel 文件路径

    返回：
        TestCaseRecord 对象列表

    异常：
        文件不存在、格式错误、字段缺失、
        case_id 重复或数据校验失败时抛出异常
    """

    file_path = Path(file_path)

    # 1. 检查文件是否存在。
    if not file_path.exists():
        raise FileNotFoundError(
            f"数据文件不存在：{file_path}"
        )

    # 2. 检查路径是否是文件。
    if not file_path.is_file():
        raise ValueError(
            f"指定路径不是文件：{file_path}"
        )

    # 3. 检查文件后缀。
    suffix = file_path.suffix.lower()

    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"不支持的文件类型：{suffix}，"
            "目前只支持 .csv 和 .xlsx"
        )

    # 4. 读取 CSV 或 Excel。
    dataframe = read_dataset_file(file_path)

    # 5. 清理列名两侧的空格。
    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]

    # 6. 检查必填列。
    actual_columns = set(dataframe.columns)
    missing_columns = REQUIRED_COLUMNS - actual_columns

    if missing_columns:
        missing_text = "、".join(
            sorted(missing_columns)
        )

        raise ValueError(
            f"数据文件缺少必填列：{missing_text}"
        )

    # 7. 检查数据文件是否为空。
    if dataframe.empty:
        raise ValueError(
            "数据文件没有任何测试用例"
        )

    records: list[TestCaseRecord] = []
    errors: list[str] = []
    seen_case_ids: set[str] = set()

    # 8. 逐行处理数据。
    for dataframe_index, row in dataframe.iterrows():
        # CSV 第 1 行是表头，因此数据从第 2 行开始。
        row_number = dataframe_index + 2

        case_id = str(
            row["case_id"]
        ).strip()

        # 9. 检查 case_id 是否为空。
        if not case_id:
            errors.append(
                f"第 {row_number} 行："
                "case_id 不能为空"
            )
            continue

        # 10. 检查 case_id 是否重复。
        if case_id in seen_case_ids:
            errors.append(
                f"第 {row_number} 行："
                f"case_id 重复：{case_id}"
            )
            continue

        seen_case_ids.add(case_id)

        # 11. 拆分期望关键词和禁止关键词。
        expected_keywords = split_keywords(
            row["expected_keywords"]
        )

        forbidden_keywords = split_keywords(
            row["forbidden_keywords"]
        )

        # 12. 期望关键词不能为空。
        if not expected_keywords:
            errors.append(
                f"第 {row_number} 行："
                "expected_keywords 不能为空"
            )
            continue

        # 13. 组装一行原始数据。
        raw_record = {
            "case_id": case_id,
            "module": str(
                row["module"]
            ).strip(),
            "priority": str(
                row["priority"]
            ).strip(),
            "question": str(
                row["question"]
            ).strip(),
            "expected_keywords": expected_keywords,
            "forbidden_keywords": forbidden_keywords,
            "max_latency_ms": row[
                "max_latency_ms"
            ],
            "security_category": str(
                row["security_category"]
            ).strip(),
        }

        # 14. 使用 Pydantic 校验这一行。
        try:
            record = TestCaseRecord(
                **raw_record
            )

        except ValidationError as validation_error:
            error_text = format_validation_errors(
                validation_error
            )

            errors.append(
                f"第 {row_number} 行："
                f"{error_text}"
            )
            continue

        records.append(record)

    # 15. 只要有一行错误，整个文件就失败。
    if errors:
        error_text = "\n".join(
            f"- {error}"
            for error in errors
        )

        raise ValueError(
            f"数据校验失败，共发现 "
            f"{len(errors)} 个问题：\n"
            f"{error_text}"
        )

    # 16. 所有数据正确后，返回测试用例列表。
    return records