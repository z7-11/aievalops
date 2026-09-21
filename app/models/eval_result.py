from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
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
    from app.models.eval_run import EvalRun
    from app.models.test_case import TestCase


class EvalResult(Base):
    """
    单条测试用例的评测结果。
    """

    __tablename__ = "eval_results"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    run_id: Mapped[int] = mapped_column(
        ForeignKey(
            "eval_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    test_case_id: Mapped[int] = mapped_column(
        ForeignKey(
            "test_cases.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    output: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    run: Mapped[EvalRun] = relationship(
        "EvalRun",
        back_populates="results",
    )

    test_case: Mapped[TestCase] = relationship(
        "TestCase",
        back_populates="eval_results",
    )
