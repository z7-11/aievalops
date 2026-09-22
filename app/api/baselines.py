from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.baseline import Baseline
from app.models.eval_run import EvalRun
from app.models.project import Project
from app.services.baseline_service import BaselineError, compare_cases, index_cases

router = APIRouter(prefix="/api/runs", tags=["Baselines"])

DatabaseSession = Annotated[Session, Depends(get_db)]


def get_completed_run(database: Session, run_id: int) -> EvalRun:
    run = database.get(EvalRun, run_id)

    if run is None:
        raise HTTPException(status_code=404, detail="评测任务不存在")

    if run.status.upper() != "SUCCEEDED":
        raise HTTPException(
            status_code=409,
            detail="只能使用已完成的评测任务",
        )

    return run


def get_run_cases(run: EvalRun) -> list[dict]:
    results = list(run.results)

    if not results or len(results) != run.total:
        raise HTTPException(
            status_code=409,
            detail="任务没有完整的评测明细，请先完成Worker的执行和结果入库",
        )

    cases = []

    for result in results:
        test_case = result.test_case

        if test_case is None or test_case.project_id != run.project_id:
            raise HTTPException(
                status_code=409,
                detail="评测结果关联的测试用例无效",
            )

        cases.append(
            {
                "case_id": test_case.case_id,
                "passed": result.passed,
                "reason": result.reason,
            }
        )

    try:
        index_cases(cases, "数据库评测结果")
    except BaselineError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    passed = sum(case["passed"] for case in cases)
    failed = len(cases) - passed

    if run.passed != passed or run.failed != failed:
        raise HTTPException(
            status_code=409,
            detail="任务汇总数量与评测明细不一致",
        )

    return cases


@router.post("/{run_id}/set-baseline")
def set_baseline(run_id: int, database: DatabaseSession) -> dict:
    run = get_completed_run(database, run_id)

    # PostgreSQL下锁住项目行，使同一项目的基线设置串行执行。
    project = database.scalar(
        select(Project)
        .where(Project.id == run.project_id)
        .with_for_update()
    )

    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    get_run_cases(run)

    latest = database.scalar(
        select(Baseline)
        .where(Baseline.project_id == run.project_id)
        .order_by(Baseline.id.desc())
        .limit(1)
    )

    # 连续设置同一个基线，不重复创建记录。
    if latest is not None and latest.run_id == run.id:
        return {
            "baseline_id": latest.id,
            "project_id": run.project_id,
            "run_id": run.id,
        }

    baseline = Baseline(
        project_id=run.project_id,
        run_id=run.id,
    )
    database.add(baseline)
    database.commit()
    database.refresh(baseline)

    return {
        "baseline_id": baseline.id,
        "project_id": run.project_id,
        "run_id": run.id,
    }


@router.get("/{run_id}/regressions")
def get_regressions(
    run_id: int,
    database: DatabaseSession,
    baseline_run_id: int | None = None,
) -> dict:
    current = get_completed_run(database, run_id)

    if baseline_run_id is None:
        baseline_record = database.scalar(
            select(Baseline)
            .where(Baseline.project_id == current.project_id)
            .order_by(Baseline.id.desc())
            .limit(1)
        )

        if baseline_record is None:
            raise HTTPException(
                status_code=409,
                detail="当前项目尚未设置基线",
            )

        baseline_run_id = baseline_record.run_id

    baseline = get_completed_run(database, baseline_run_id)

    if baseline.project_id != current.project_id:
        raise HTTPException(
            status_code=409,
            detail="不能比较不同项目的评测结果",
        )

    baseline_cases = get_run_cases(baseline)
    current_cases = get_run_cases(current)

    try:
        comparison = compare_cases(baseline_cases, current_cases)
    except BaselineError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "project_id": current.project_id,
        "baseline_run_id": baseline.id,
        "current_run_id": current.id,
        **comparison,
    }