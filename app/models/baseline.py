from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
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
    from app.models.project import Project


class Baseline(Base):
    """
    基线评测记录。
    """

    __tablename__ = "baselines"

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

    run_id: Mapped[int] = mapped_column(
        ForeignKey(
            "eval_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship(
        "Project",
        back_populates="baselines",
    )

    run: Mapped[EvalRun] = relationship(
        "EvalRun",
        back_populates="baselines",
    )
