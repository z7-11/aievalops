from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.eval_result import EvalResult
    from app.models.project import Project


class TestCase(Base):
    """
    测试用例数据库表。
    """

    __tablename__ = "test_cases"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "case_id",
            name="uq_test_cases_project_case_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    case_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    module: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    priority: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
    )

    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    expected_keywords: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    forbidden_keywords: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    max_latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    security_category: Mapped[str] = mapped_column(
        String(50),
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

    project: Mapped[Project] = relationship(
        "Project",
        back_populates="test_cases",
    )

    eval_results: Mapped[list[EvalResult]] = relationship(
        "EvalResult",
        back_populates="test_case",
    )
