from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from app.core.config import settings

# 创建数据库引擎
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


# 创建 Session 工厂
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[
    Session,
    None,
    None,
]:
    """
    为一次请求提供一个数据库 Session。

    请求结束后，无论成功还是失败，
    都会关闭 Session。
    """

    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()
