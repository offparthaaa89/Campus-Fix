"""Admin-only campus-wide statistics and server-side complaint filtering.

This is an additive router: it does not replace the working staff/admin routes.
"""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Engine, func, select

from backend.models.category import Category
from backend.models.complaint import Complaint
from backend.routes.auth import PublicUser
from backend.routes.staff_workflow import AdminComplaint


STATUSES = ("Open", "In Progress", "Resolved", "Reopened")
UNRESOLVED = ("Open", "In Progress", "Reopened")


class CategoryCount(BaseModel):
    id: int
    name: str
    count: int


class BasicStats(BaseModel):
    total: int = Field(ge=0)
    unresolved: int = Field(ge=0)
    unresolved_over_7_days: int = Field(ge=0)
    by_status: dict[str, int]
    by_category: list[CategoryCount]


def create_admin_insights_router(
    engine: Engine, current_user: Callable[..., PublicUser]
) -> APIRouter:
    router = APIRouter(tags=["Admin"])

    def require_admin(
        user: Annotated[PublicUser, Depends(current_user)],
    ) -> PublicUser:
        if user.role != "Admin":
            raise HTTPException(status_code=403, detail="Admin access required.")
        return user

    @router.get("/api/stats/basic", response_model=BasicStats)
    def stats_basic(admin: Annotated[PublicUser, Depends(require_admin)]):
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        with engine.connect() as connection:
            statuses = connection.execute(
                select(Complaint.status, func.count(Complaint.id))
                .group_by(Complaint.status)
            ).all()
            status_counts = {status: 0 for status in STATUSES}
            status_counts.update({status: count for status, count in statuses})

            category_rows = connection.execute(
                select(
                    Category.id, Category.name,
                    func.count(Complaint.id).label("count"),
                )
                .select_from(Category)
                .outerjoin(Complaint, Complaint.category_id == Category.id)
                .group_by(Category.id, Category.name)
                .order_by(Category.id)
            ).mappings().all()

            older_unresolved = connection.scalar(
                select(func.count(Complaint.id)).where(
                    Complaint.status.in_(UNRESOLVED),
                    Complaint.created_at < cutoff,
                )
            ) or 0

        return BasicStats(
            total=sum(status_counts.values()),
            unresolved=sum(status_counts.get(status, 0) for status in UNRESOLVED),
            unresolved_over_7_days=older_unresolved,
            by_status=status_counts,
            by_category=[CategoryCount.model_validate(row) for row in category_rows],
        )

    @router.get("/api/admin/complaints/search", response_model=list[AdminComplaint])
    def filtered_complaints(
        admin: Annotated[PublicUser, Depends(require_admin)],
        page: Annotated[int, Query(ge=1, le=100000)] = 1,
        category_id: Annotated[int | None, Query(ge=1)] = None,
        status: Annotated[
            Literal["Open", "In Progress", "Resolved", "Reopened"] | None,
            Query(),
        ] = None,
        older_than_7_days: bool = False,
    ):
        statement = (
            select(
                Complaint.id, Complaint.title, Complaint.category_id, Complaint.status,
                Complaint.created_at, Complaint.reported_by, Complaint.assigned_to,
                Category.name.label("category_name"),
            )
            .join(Category, Category.id == Complaint.category_id)
        )
        if category_id is not None:
            statement = statement.where(Complaint.category_id == category_id)
        if status is not None:
            statement = statement.where(Complaint.status == status)
        if older_than_7_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            statement = statement.where(
                Complaint.status.in_(UNRESOLVED),
                Complaint.created_at < cutoff,
            )

        statement = (
            statement.order_by(Complaint.created_at.desc(), Complaint.id.desc())
            .limit(20)
            .offset((page - 1) * 20)
        )
        with engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [AdminComplaint.model_validate(row) for row in rows]

    return router
