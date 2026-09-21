from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# 创建 SQLite 内存数据库
TEST_DATABASE_URL = (
    "sqlite+pysqlite:///:memory:"
)

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    expire_on_commit=False,
)


def override_get_db() -> Generator[
    Session,
    None,
    None,
]:
    """
    为测试接口提供测试数据库 Session。
    """

    database = TestingSessionLocal()

    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def client() -> Generator[
    TestClient,
    None,
    None,
]:
    """
    创建一个独立的测试客户端。

    每个测试开始前创建表，
    每个测试结束后删除表。
    """

    Base.metadata.create_all(
        bind=test_engine,
    )

    app.dependency_overrides[
        get_db
    ] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

    Base.metadata.drop_all(
        bind=test_engine,
    )