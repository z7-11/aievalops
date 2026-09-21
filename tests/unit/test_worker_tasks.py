import pytest

from app.worker.celery_app import celery_app
from app.worker.tasks import ping


@pytest.fixture(autouse=True)
def celery_eager_mode():
    """
    测试期间让 Celery 立即执行任务。
    """
    old_always_eager = celery_app.conf.task_always_eager
    old_eager_propagates = celery_app.conf.task_eager_propagates

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    yield

    celery_app.conf.task_always_eager = old_always_eager
    celery_app.conf.task_eager_propagates = old_eager_propagates


def test_ping_task_returns_pong():
    result = ping.delay()

    assert result.successful()
    assert result.get(timeout=10) == "pong"