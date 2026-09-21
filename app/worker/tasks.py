from datetime import UTC, datetime
from pathlib import Path

from app.db.session import SessionLocal
from app.models.eval_run import EvalRun
from app.models.test_case import TestCase
from app.schemas.test_case import TestCaseRecord
from app.services.promptfoo_config_service import (
    build_promptfoo_config,
    write_promptfoo_config,
)
from app.worker.celery_app import celery_app


@celery_app.task(name="app.worker.tasks.ping")
def ping() -> str:
    """用于验证 Celery 基础链路的最小任务。"""

    return "pong"


@celery_app.task(
    name="app.worker.tasks.run_evaluation",
)
def run_evaluation(run_id: int) -> dict:
    database = SessionLocal()
    run = None

    try:
        # 1. 查询评估任务
        run = database.get(EvalRun, run_id)

        if run is None:
            raise ValueError(
                f"评估任务不存在: {run_id}"
            )

        # 2. 防止重复执行
        if run.status in {
            "RUNNING",
            "SUCCEEDED",
        }:
            return {
                "run_id": run_id,
                "status": run.status,
                "message": "任务已经执行过",
            }

        # 3. 如果已经取消，则不再执行
        if run.status == "CANCELLED":
            return {
                "run_id": run_id,
                "status": "CANCELLED",
            }

        # 4. 更新为 RUNNING
        run.status = "RUNNING"
        run.started_at = datetime.now(UTC)
        database.commit()

        # 5. 查询测试用例
        test_cases = (
            database.query(TestCase)
            .filter(
                TestCase.project_id == run.project_id,
            )
            .order_by(TestCase.id)
            .all()
        )

        if not test_cases:
            raise ValueError(
                "项目没有可执行的测试用例"
            )

        # 6. 将数据库模型转换成 Pydantic 模型
        records = [
            TestCaseRecord(
                case_id=item.case_id,
                module=item.module,
                priority=item.priority,
                question=item.question,
                expected_keywords=item.expected_keywords,
                forbidden_keywords=item.forbidden_keywords,
                max_latency_ms=item.max_latency_ms,
                security_category=item.security_category,
            )
            for item in test_cases
        ]

        # 7. 查询项目，获得 target_url
        project = run.project

        # 8. 生成 Promptfoo 配置
        config = build_promptfoo_config(
            test_cases=records,
            target_url=project.target_url,
        )

        config_path = Path(
            f"output/generated/run_{run_id}.yaml"
        )

        write_promptfoo_config(
            config,
            config_path,
        )

        # 9. 这里调用 Promptfoo Runner
        #
        # 后续需要接入：
        #
        # result = run_promptfoo(
        #     config_path=str(config_path),
        #     output_path=f"results/run_{run_id}.json",
        # )
        #
        # 然后解析 result，创建 EvalResult。

        # 当前先记录总数，作为任务框架验证
        run.total = len(test_cases)
        run.passed = 0
        run.failed = 0
        run.pass_rate = 0.0
        run.status = "SUCCEEDED"
        run.finished_at = datetime.now(UTC)

        database.commit()

        return {
            "run_id": run_id,
            "status": "SUCCEEDED",
            "total": run.total,
        }

    except Exception as error:
        database.rollback()

        if run is not None:
            failed_run = database.get(
                EvalRun,
                run_id,
            )

            if failed_run is not None:
                failed_run.status = "FAILED"
                failed_run.error_message = str(error)
                failed_run.finished_at = (
                    datetime.now(UTC)
                )

                database.commit()

        raise

    finally:
        database.close()
