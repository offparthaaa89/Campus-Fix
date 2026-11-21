"""Student requests to reopen a resolved CampusFix complaint.

Each complaint can have at most one pending request at a time.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class ReopenRequest(Base):
    __tablename__ = "reopen_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Pending', 'Accepted', 'Declined')",
            name="ck_reopen_requests_status",
        ),
        Index("ix_reopen_requests_complaint_created", "complaint_id", "created_at"),
        Index(
            "uq_reopen_requests_one_pending_per_complaint",
            "complaint_id",
            unique=True,
            postgresql_where=text("status = 'Pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    complaint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("complaints.id"), nullable=False
    )
    requested_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default="Pending", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    decided_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
