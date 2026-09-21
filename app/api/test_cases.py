from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.project_repository import (
    get_project,
)
from app.repositories.test_case_repository import (
    create_test_cases,
    delete_test_case,
    get_test_case,
    list_test_cases,
)
from app.schemas.test_case import TestCaseRecord

router = APIRouter(
    prefix="/api/projects/{project_id}/test-cases",
    tags=["Test Cases"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]


class TestCaseImportRequest(BaseModel):
    """
    测试用例导入请求。
    """

    cases: list[TestCaseRecord] = Field(
        min_length=1,
    )


class TestCaseResponse(BaseModel):
    """
    测试用例响应。
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    project_id: int
    case_id: str
    module: str
    priority: str
    question: str
    expected_keywords: list[str]
    forbidden_keywords: list[str]
    max_latency_ms: int
    security_category: str
    created_at: datetime
    updated_at: datetime


@router.post(
    "/import",
    response_model=list[TestCaseResponse],
    status_code=status.HTTP_201_CREATED,
)
def import_test_cases_api(
    project_id: int,
    request: TestCaseImportRequest,
    database: DatabaseSession,
) -> list[TestCaseResponse]:
    project = get_project(
        database,
        project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    try:
        return create_test_cases(
            database,
            project_id=project_id,
            records=request.cases,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=list[TestCaseResponse],
)
def list_test_cases_api(
    project_id: int,
    database: DatabaseSession,
) -> list[TestCaseResponse]:
    project = get_project(
        database,
        project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    return list_test_cases(
        database,
        project_id=project_id,
    )


@router.get(
    "/{case_id}",
    response_model=TestCaseResponse,
)
def get_test_case_api(
    project_id: int,
    case_id: str,
    database: DatabaseSession,
) -> TestCaseResponse:
    test_case = get_test_case(
        database,
        project_id=project_id,
        case_id=case_id,
    )

    if test_case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在",
        )

    return test_case


@router.delete(
    "/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_test_case_api(
    project_id: int,
    case_id: str,
    database: DatabaseSession,
) -> None:
    test_case = get_test_case(
        database,
        project_id=project_id,
        case_id=case_id,
    )

    if test_case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在",
        )

    delete_test_case(
        database,
        test_case,
    )
