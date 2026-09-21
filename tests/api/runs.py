from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun
from app.repositories.project_repository import get_project
from app.worker.tasks import run_evaluation

router = APIRouter(
    prefix="/api",
    tags=["Evaluation Runs"],
)


DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]


class RunCreateResponse(BaseModel):
    run_id: int
    task_id: str
    status: str


class RunResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    project_id: int
    status: str
    total: int
    passed: int
    failed: int
    pass_rate: float | None
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime


class EvalResultResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    run_id: int
    test_case_id: int
    passed: bool
    output: str
    score: float | None
    latency_ms: int | None
    reason: str | None
    created_at: datetime


@router.post(
    "/projects/{project_id}/runs",
    response_model=RunCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_run_api(
    project_id: int,
    database: DatabaseSession,
) -> RunCreateResponse:
    project = get_project(
        database,
        project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    if not project.test_cases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目还没有测试用例",
        )

    run = EvalRun(
        project_id=project_id,
        status="PENDING",
    )

    database.add(run)
    database.commit()
    database.refresh(run)

    task_result = run_evaluation.delay(run.id)

    return RunCreateResponse(
        run_id=run.id,
        task_id=task_result.id,
        status=run.status,
    )


@router.get(
    "/runs/{run_id}",
    response_model=RunResponse,
)
def get_run_api(
    run_id: int,
    database: DatabaseSession,
) -> RunResponse:
    run = database.get(EvalRun, run_id)

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="评估任务不存在",
        )

    return run


@router.get(
    "/runs/{run_id}/results",
    response_model=list[EvalResultResponse],
)
def list_run_results_api(
    run_id: int,
    database: DatabaseSession,
) -> list[EvalResult]:
    run = database.get(EvalRun, run_id)

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="评估任务不存在",
        )

    return list(
        database.query(EvalResult)
        .filter(EvalResult.run_id == run_id)
        .order_by(EvalResult.id)
        .all()
    )


@router.post(
    "/runs/{run_id}/cancel",
    response_model=RunResponse,
)
def cancel_run_api(
    run_id: int,
    database: DatabaseSession,
) -> RunResponse:
    run = database.get(EvalRun, run_id)

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="评估任务不存在",
        )

    if run.status in {
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="任务已经结束，不能取消",
        )

    run.status = "CANCELLED"
    run.finished_at = datetime.utcnow()

    database.commit()
    database.refresh(run)

    return run