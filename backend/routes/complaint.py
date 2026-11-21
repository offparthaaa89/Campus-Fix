"""Student complaint endpoints. The verified account supplies the reporter ID."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import Engine, insert, select

from backend.models.category import Category
from backend.models.complaint import Complaint
from backend.models.status_history import StatusHistory
from backend.models.user import User
from backend.routes.auth import PublicUser


class ComplaintInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    category_id: Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
    location: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ComplaintSummary(BaseModel):
    id: int
    title: str
    category_id: int
    category_name: str
    status: Literal["Open", "In Progress", "Resolved", "Reopened"]
    created_at: datetime


class ComplaintCreated(ComplaintSummary):
    location: str
    description: str
    reported_by: int


class StatusEvent(BaseModel):
    old_status: Literal["Open", "In Progress", "Resolved", "Reopened"] | None
    new_status: Literal["Open", "In Progress", "Resolved", "Reopened"]
    changed_by_name: str
    changed_at: datetime


class ComplaintDetail(ComplaintCreated):
    updated_at: datetime
    status_history: list[StatusEvent]


SUMMARY_COLUMNS = (
    Complaint.id,
    Complaint.title,
    Complaint.category_id,
    Complaint.status,
    Complaint.created_at,
)


def create_complaints_router(
    engine: Engine, current_user: Callable[..., PublicUser]
) -> APIRouter:
    router = APIRouter(prefix="/api/complaints", tags=["Complaints"])

    def require_student(user: Annotated[PublicUser, Depends(current_user)]) -> PublicUser:
        if user.role != "Student":
            raise HTTPException(status_code=403, detail="This action is for students only.")
        return user

    @router.post("", status_code=status.HTTP_201_CREATED, response_model=ComplaintCreated)
    def create_complaint(
        body: ComplaintInput, student: Annotated[PublicUser, Depends(require_student)]
    ) -> ComplaintCreated:
        with engine.begin() as connection:
            category_name = connection.scalar(
                select(Category.name)
                .where(Category.id == body.category_id)
                .with_for_update(read=True, key_share=True)
            )
            if category_name is None:
                raise HTTPException(status_code=422, detail="Select an available category.")

            query = (
                insert(Complaint)
                .values(**body.model_dump(), reported_by=student.id)
                .returning(
                    *SUMMARY_COLUMNS, Complaint.location, Complaint.description, Complaint.reported_by
                )
            )
            row = connection.execute(query).mappings().one()
            # Complaint and its first timeline event succeed or fail together.
            connection.execute(
                insert(StatusHistory).values(
                    complaint_id=row["id"], changed_by=student.id,
                    old_status=None, new_status="Open", changed_at=row["created_at"],
                )
            )

        return ComplaintCreated.model_validate({**row, "category_name": category_name})

    @router.get("/mine", response_model=list[ComplaintSummary])
    def my_complaints(
        student: Annotated[PublicUser, Depends(require_student)]
    ) -> list[ComplaintSummary]:
        query = (
            select(*SUMMARY_COLUMNS, Category.name.label("category_name"))
            .select_from(Complaint)
            .join(Category, Category.id == Complaint.category_id)
            .where(Complaint.reported_by == student.id)
            .order_by(Complaint.created_at.desc(), Complaint.id.desc())
        )
        with engine.connect() as connection:
            rows = connection.execute(query).mappings().all()

        return [ComplaintSummary.model_validate(row) for row in rows]

    @router.get("/{complaint_id}", response_model=ComplaintDetail)
    def complaint_detail(
        complaint_id: Annotated[int, Path(ge=1, le=2_147_483_647)],
        student: Annotated[PublicUser, Depends(require_student)],
    ) -> ComplaintDetail:
        query = (
            select(
                *SUMMARY_COLUMNS, Complaint.location, Complaint.description,
                Complaint.reported_by, Complaint.updated_at, Category.name.label("category_name"),
            )
            .select_from(Complaint)
            .join(Category, Category.id == Complaint.category_id)
            .where(Complaint.id == complaint_id, Complaint.reported_by == student.id)
        )
        with engine.connect() as connection:
            row = connection.execute(query).mappings().one_or_none()
            if row is None:
                exists = connection.scalar(select(Complaint.id).where(Complaint.id == complaint_id))
                if exists is not None:
                    raise HTTPException(status_code=403, detail="This complaint belongs to another account.")
                raise HTTPException(status_code=404, detail="Complaint not found.")

            # Ownership is checked above BEFORE any timeline records are fetched.
            history = connection.execute(
                select(
                    StatusHistory.old_status,
                    StatusHistory.new_status,
                    StatusHistory.changed_at,
                    User.name.label("changed_by_name"),
                )
                .join(User, User.id == StatusHistory.changed_by)
                .where(StatusHistory.complaint_id == complaint_id)
                .order_by(StatusHistory.changed_at, StatusHistory.id)
            ).mappings().all()

        return ComplaintDetail.model_validate({
            **row,
            "status_history": [StatusEvent.model_validate(event) for event in history],
        })

    return router
