from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.baseline import Baseline
    from app.models.eval_run import EvalRun
    from app.models.test_case import TestCase


class Project(Base):
    """
    测试项目表。
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    target_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    test_cases: Mapped[list[TestCase]] = relationship(
        "TestCase",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    eval_runs: Mapped[list[EvalRun]] = relationship(
        "EvalRun",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    baselines: Mapped[list[Baseline]] = relationship(
        "Baseline",
        back_populates="project",
        cascade="all, delete-orphan",
    )
