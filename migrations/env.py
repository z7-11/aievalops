from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from app.core.config import settings
from app.db.base import Base
from app.models import (
    baseline,
    eval_result,
    eval_run,
    project,
    test_case,
)


# Alembic 配置对象
config = context.config


# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# 从 .env 中读取真实数据库地址
#
# settings.database_url 对应：
# DATABASE_URL=...
#
# 这样就不用把密码写进 alembic.ini
config.set_main_option(
    "sqlalchemy.url",
    settings.database_url,
)


# 告诉 Alembic 去哪里查找数据库模型
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    离线模式生成 SQL，不直接连接数据库。
    """

    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    在线模式，直接连接 PostgreSQL 执行迁移。
    """

    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section,
            {},
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()