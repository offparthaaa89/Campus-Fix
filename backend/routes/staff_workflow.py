"""Staff queue/status changes, admin assignments and assignment audit records."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, func, insert, select, update

from backend.models.assignment import Assignment
from backend.models.notification import Notification
from backend.models.category import Category
from backend.models.complaint import Complaint
from backend.models.status_history import StatusHistory
from backend.models.user import User
from backend.routes.auth import PublicUser
from backend.routes.complaint import ComplaintDetail, ComplaintSummary, StatusEvent


class StaffOption(BaseModel):
    id: int
    name: str
    email: str


class AdminComplaint(ComplaintSummary):
    reported_by: int
    assigned_to: int | None


class AssignInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    staff_id: Annotated[int, Field(strict=True, ge=1)]


class AssignResult(BaseModel):
    complaint_id: int
    staff_id: int
    assigned_by: int
    assigned_at: datetime | None


class StatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_status: Literal["In Progress", "Resolved"]


class StatusResult(BaseModel):
    complaint_id: int
    old_status: str
    new_status: str
    changed_at: datetime


# One-step forward transitions; Reopened only through a future accepted request.
NEXT_STATUS = {
    "Open": "In Progress",
    "In Progress": "Resolved",
    "Resolved": None,
    "Reopened": "In Progress",
}


def create_staff_workflow_router(
    engine: Engine, current_user: Callable[..., PublicUser]
) -> APIRouter:
    router = APIRouter()

    def require_admin(user: Annotated[PublicUser, Depends(current_user)]) -> PublicUser:
        if user.role != "Admin":
            raise HTTPException(status_code=403, detail="Admin access required.")
        return user

    def require_staff(user: Annotated[PublicUser, Depends(current_user)]) -> PublicUser:
        if user.role != "Staff":
            raise HTTPException(status_code=403, detail="Staff access required.")
        return user

    @router.get("/api/admin/staff", response_model=list[StaffOption], tags=["Admin"])
    def staff_options(admin: Annotated[PublicUser, Depends(require_admin)]):
        with engine.connect() as connection:
            rows = connection.execute(
                select(User.id, User.name, User.email)
                .where(User.role == "Staff")
                .order_by(User.name, User.id)
            ).mappings().all()
        return [StaffOption.model_validate(row) for row in rows]

    @router.get("/api/admin/complaints", response_model=list[AdminComplaint], tags=["Admin"])
    def all_complaints(
        admin: Annotated[PublicUser, Depends(require_admin)],
        page: Annotated[int, Query(ge=1, le=100000)] = 1,
    ):
        statement = (
            select(
                Complaint.id, Complaint.title, Complaint.category_id, Complaint.status,
                Complaint.created_at, Complaint.reported_by, Complaint.assigned_to,
                Category.name.label("category_name"),
            )
            .join(Category, Category.id == Complaint.category_id)
            .order_by(Complaint.created_at.desc(), Complaint.id.desc())
            .limit(20).offset((page - 1) * 20)
        )
        with engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [AdminComplaint.model_validate(row) for row in rows]

    @router.put(
        "/api/admin/complaints/{complaint_id}/assignment",
        response_model=AssignResult,
        tags=["Admin"],
    )
    def assign_complaint(
        complaint_id: Annotated[int, Path(ge=1)],
        body: AssignInput,
        admin: Annotated[PublicUser, Depends(require_admin)],
    ):
        with engine.begin() as connection:
            previous = connection.execute(
                select(Complaint.id, Complaint.assigned_to)
                .where(Complaint.id == complaint_id).with_for_update()
            ).mappings().one_or_none()
            if previous is None:
                raise HTTPException(status_code=404, detail="Complaint not found.")
            staff_exists = connection.scalar(
                select(User.id).where(User.id == body.staff_id, User.role == "Staff")
            )
            if staff_exists is None:
                raise HTTPException(status_code=422, detail="Select an existing staff account.")
            if previous["assigned_to"] == body.staff_id:
                raise HTTPException(status_code=409, detail="Already assigned to this staff member.")

            connection.execute(
                update(Complaint)
                .where(Complaint.id == complaint_id)
                .values(assigned_to=body.staff_id, updated_at=func.now())
            )
            entry = connection.execute(
                insert(Assignment)
                .values(complaint_id=complaint_id, staff_id=body.staff_id, assigned_by=admin.id)
                .returning(Assignment.assigned_at)
            ).scalar_one()
        return AssignResult(
            complaint_id=complaint_id, staff_id=body.staff_id,
            assigned_by=admin.id, assigned_at=entry,
        )

    @router.get("/api/staff/complaints", response_model=list[ComplaintSummary], tags=["Staff"])
    def assigned_queue(
        staff: Annotated[PublicUser, Depends(require_staff)],
        unresolved: bool = True,
    ):
        statement = (
            select(
                Complaint.id, Complaint.title, Complaint.category_id, Complaint.status,
                Complaint.created_at, Category.name.label("category_name"),
            )
            .join(Category, Category.id == Complaint.category_id)
            .where(Complaint.assigned_to == staff.id)
        )
        if unresolved:
            statement = statement.where(Complaint.status != "Resolved")
        statement = statement.order_by(Complaint.created_at.desc(), Complaint.id.desc())
        with engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [ComplaintSummary.model_validate(row) for row in rows]

    @router.get(
        "/api/staff/complaints/{complaint_id}", response_model=ComplaintDetail, tags=["Staff"]
    )
    def staff_detail(
        complaint_id: Annotated[int, Path(ge=1)],
        staff: Annotated[PublicUser, Depends(require_staff)],
    ):
        stmt = (
            select(
                Complaint.id, Complaint.title, Complaint.category_id, Complaint.status,
                Complaint.created_at, Complaint.location, Complaint.description,
                Complaint.reported_by, Complaint.updated_at,
                Category.name.label("category_name"),
            )
            .join(Category, Category.id == Complaint.category_id)
            .where(Complaint.id == complaint_id, Complaint.assigned_to == staff.id)
        )
        with engine.connect() as connection:
            row = connection.execute(stmt).mappings().one_or_none()
            if row is None:
                raise HTTPException(status_code=404, detail="Assigned complaint not found.")
            history = connection.execute(
                select(
                    StatusHistory.old_status, StatusHistory.new_status,
                    StatusHistory.changed_at, User.name.label("changed_by_name"),
                )
                .join(User, User.id == StatusHistory.changed_by)
                .where(StatusHistory.complaint_id == complaint_id)
                .order_by(StatusHistory.changed_at, StatusHistory.id)
            ).mappings().all()
        return ComplaintDetail.model_validate({
            **row,
            "status_history": [StatusEvent.model_validate(event) for event in history],
        })

    @router.put(
        "/api/staff/complaints/{complaint_id}/status",
        response_model=StatusResult,
        tags=["Staff"],
    )
    def update_status(
        complaint_id: Annotated[int, Path(ge=1)],
        body: StatusInput,
        staff: Annotated[PublicUser, Depends(require_staff)],
    ):
        with engine.begin() as connection:
            complaint = connection.execute(
                select(Complaint.id, Complaint.status, Complaint.assigned_to, Complaint.reported_by)
                .where(Complaint.id == complaint_id).with_for_update()
            ).mappings().one_or_none()
            if complaint is None or complaint["assigned_to"] != staff.id:
                raise HTTPException(status_code=404, detail="Assigned complaint not found.")
            previous = complaint["status"]
            if NEXT_STATUS.get(previous) != body.new_status:
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot change {previous} to {body.new_status}.",
                )
            timestamp = connection.scalar(select(func.now()))
            connection.execute(
                update(Complaint)
                .where(Complaint.id == complaint_id)
                .values(status=body.new_status, updated_at=timestamp)
            )
            connection.execute(
                insert(StatusHistory).values(
                    complaint_id=complaint_id, changed_by=staff.id,
                    old_status=previous, new_status=body.new_status,
                    changed_at=timestamp,
                )
            )
            # Save the notification in the same transaction as the status change.
            # If any insert fails, the status and history are rolled back too.
            connection.execute(
                insert(Notification).values(
                    user_id=complaint["reported_by"],
                    complaint_id=complaint_id,
                    message=(
                        f"Complaint #{complaint_id}: status changed "
                        f"from {previous} to {body.new_status}."
                    ),
                )
            )
        return StatusResult(
            complaint_id=complaint_id, old_status=previous,
            new_status=body.new_status, changed_at=timestamp,
        )

    return router
