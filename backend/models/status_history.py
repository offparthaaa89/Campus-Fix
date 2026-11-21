"""Audit records for status transitions on a CampusFix complaint."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class StatusHistory(Base):
    __tablename__ = "status_history"
    __table_args__ = (
        CheckConstraint(
            "old_status IS NULL OR old_status IN ('Open', 'In Progress', 'Resolved', 'Reopened')",
            name="ck_status_history_old_status",
        ),
        CheckConstraint(
            "new_status IN ('Open', 'In Progress', 'Resolved', 'Reopened')",
            name="ck_status_history_new_status",
        ),
        Index("ix_status_history_complaint_time", "complaint_id", "changed_at", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), nullable=False)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
