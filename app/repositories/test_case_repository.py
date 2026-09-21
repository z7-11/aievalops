from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.test_case import TestCase
from app.schemas.test_case import TestCaseRecord


def create_test_cases(
    database: Session,
    *,
    project_id: int,
    records: list[TestCaseRecord],
) -> list[TestCase]:
    """
    向指定项目中导入测试用例。
    """

    existing_case_ids = set(
        database.scalars(
            select(TestCase.case_id).where(
                TestCase.project_id == project_id
            )
        ).all()
    )

    incoming_case_ids: set[str] = set()
    test_cases: list[TestCase] = []

    for record in records:
        if record.case_id in existing_case_ids:
            raise ValueError(
                f"case_id 已存在：{record.case_id}"
            )

        if record.case_id in incoming_case_ids:
            raise ValueError(
                f"本次导入中 case_id 重复："
                f"{record.case_id}"
            )

        incoming_case_ids.add(record.case_id)

        test_case = TestCase(
            project_id=project_id,
            case_id=record.case_id,
            module=record.module,
            priority=record.priority,
            question=record.question,
            expected_keywords=(
                record.expected_keywords
            ),
            forbidden_keywords=(
                record.forbidden_keywords
            ),
            max_latency_ms=record.max_latency_ms,
            security_category=(
                record.security_category
            ),
        )

        database.add(test_case)
        test_cases.append(test_case)

    try:
        database.commit()

    except IntegrityError as error:
        database.rollback()

        raise ValueError(
            "测试用例导入失败，"
            "可能存在重复 case_id"
        ) from error

    for test_case in test_cases:
        database.refresh(test_case)

    return test_cases


def list_test_cases(
    database: Session,
    *,
    project_id: int,
) -> list[TestCase]:
    """
    查询某个项目下的所有测试用例。
    """

    statement = (
        select(TestCase)
        .where(
            TestCase.project_id == project_id
        )
        .order_by(TestCase.id)
    )

    return list(
        database.scalars(statement).all()
    )


def get_test_case(
    database: Session,
    *,
    project_id: int,
    case_id: str,
) -> TestCase | None:
    """
    查询某个项目中的指定测试用例。
    """

    statement = select(TestCase).where(
        TestCase.project_id == project_id,
        TestCase.case_id == case_id,
    )

    return database.scalars(
        statement
    ).first()


def delete_test_case(
    database: Session,
    test_case: TestCase,
) -> None:
    """
    删除一条测试用例。
    """

    database.delete(test_case)
    database.commit()