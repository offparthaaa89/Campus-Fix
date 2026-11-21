"""Reopen requests for resolved complaints.

Student creates a request on their own resolved complaint. The assigned Staff
or any Admin accepts/declines the pending request; acceptance changes the
complaint status to Reopened and writes status history and a notification.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import Engine, func, insert, select, update

from backend.models.complaint import Complaint
from backend.models.notification import Notification
from backend.models.reopen_request import ReopenRequest
from backend.models.status_history import StatusHistory
from backend.routes.auth import PublicUser


class ReopenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ReopenDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["Accepted", "Declined"]


class ReopenOutput(BaseModel):
    id: int
    complaint_id: int
    requested_by: int
    reason: str
    status: Literal["Pending", "Accepted", "Declined"]
    created_at: datetime
    decided_by: int | None
    decided_at: datetime | None


RETURN_FIELDS = (
    ReopenRequest.id,
    ReopenRequest.complaint_id,
    ReopenRequest.requested_by,
    ReopenRequest.reason,
    ReopenRequest.status,
    ReopenRequest.created_at,
    ReopenRequest.decided_by,
    ReopenRequest.decided_at,
)


def create_reopen_router(engine: Engine, current_user: Callable[..., PublicUser]) -> APIRouter:
    router = APIRouter(tags=["Reopen Requests"])

    def require_student(user: Annotated[PublicUser, Depends(current_user)]) -> PublicUser:
        if user.role != "Student":
            raise HTTPException(status_code=403, detail="Student access required.")
        return user

    def require_reviewer(user: Annotated[PublicUser, Depends(current_user)]) -> PublicUser:
        if user.role not in ("Staff", "Admin"):
            raise HTTPException(status_code=403, detail="Staff or Admin access required.")
        return user

    @router.post(
        "/api/complaints/{complaint_id}/reopen",
        response_model=ReopenOutput,
        status_code=status.HTTP_201_CREATED,
    )
    def request_reopen(
        complaint_id: Annotated[int, Path(ge=1)],
        body: ReopenInput,
        student: Annotated[PublicUser, Depends(require_student)],
    ):
        with engine.begin() as connection:
            # Lock complaint first so parallel student requests cannot create duplicates.
            complaint = connection.execute(
                select(Complaint.id, Complaint.reported_by, Complaint.status)
                .where(Complaint.id == complaint_id)
                .with_for_update()
            ).mappings().one_or_none()
            if complaint is None:
                raise HTTPException(status_code=404, detail="Complaint not found.")
            if complaint["reported_by"] != student.id:
                raise HTTPException(status_code=403, detail="This complaint belongs to another account.")
            if complaint["status"] != "Resolved":
                raise HTTPException(status_code=409, detail="Only resolved complaints can be reopened.")
            pending = connection.scalar(
                select(ReopenRequest.id).where(
                    ReopenRequest.complaint_id == complaint_id,
                    ReopenRequest.status == "Pending",
                )
            )
            if pending is not None:
                raise HTTPException(status_code=409, detail="A reopen request is already pending.")
            row = connection.execute(
                insert(ReopenRequest)
                .values(complaint_id=complaint_id, requested_by=student.id, reason=body.reason)
                .returning(*RETURN_FIELDS)
            ).mappings().one()
        return ReopenOutput.model_validate(row)

    @router.get(
        "/api/complaints/{complaint_id}/reopen-requests",
        response_model=list[ReopenOutput],
    )
    def student_reopen_history(
        complaint_id: Annotated[int, Path(ge=1)],
        student: Annotated[PublicUser, Depends(require_student)],
    ):
        with engine.connect() as connection:
            complaint = connection.execute(
                select(Complaint.reported_by).where(Complaint.id == complaint_id)
            ).scalar_one_or_none()
            if complaint is None:
                raise HTTPException(status_code=404, detail="Complaint not found.")
            if complaint != student.id:
                raise HTTPException(status_code=403, detail="This complaint belongs to another account.")
            rows = connection.execute(
                select(*RETURN_FIELDS)
                .where(ReopenRequest.complaint_id == complaint_id)
                .order_by(ReopenRequest.created_at.desc(), ReopenRequest.id.desc())
            ).mappings().all()
        return [ReopenOutput.model_validate(row) for row in rows]

    @router.get("/api/reopen/pending", response_model=list[ReopenOutput])
    def pending_requests(reviewer: Annotated[PublicUser, Depends(require_reviewer)]):
        query = (
            select(*RETURN_FIELDS)
            .join(Complaint, Complaint.id == ReopenRequest.complaint_id)
            .where(ReopenRequest.status == "Pending")
            .order_by(ReopenRequest.created_at, ReopenRequest.id)
        )
        if reviewer.role == "Staff":
            query = query.where(Complaint.assigned_to == reviewer.id)
        with engine.connect() as connection:
            rows = connection.execute(query).mappings().all()
        return [ReopenOutput.model_validate(row) for row in rows]

    @router.put("/api/reopen/{request_id}", response_model=ReopenOutput)
    def decide_reopen(
        request_id: Annotated[int, Path(ge=1)],
        body: ReopenDecision,
        reviewer: Annotated[PublicUser, Depends(require_reviewer)],
    ):
        with engine.begin() as connection:
            # Consistent lock order: complaint, then reopen request.
            complaint_id = connection.scalar(
                select(ReopenRequest.complaint_id).where(ReopenRequest.id == request_id)
            )
            if complaint_id is None:
                raise HTTPException(status_code=404, detail="Reopen request not found.")
            complaint = connection.execute(
                select(Complaint.id, Complaint.status, Complaint.assigned_to, Complaint.reported_by)
                .where(Complaint.id == complaint_id)
                .with_for_update()
            ).mappings().one_or_none()
            if complaint is None:
                raise HTTPException(status_code=404, detail="Complaint not found.")
            if reviewer.role == "Staff" and complaint["assigned_to"] != reviewer.id:
                raise HTTPException(status_code=403, detail="Only assigned Staff may decide this request.")
            request_row = connection.execute(
                select(ReopenRequest.id, ReopenRequest.status)
                .where(ReopenRequest.id == request_id).with_for_update()
            ).mappings().one_or_none()
            if request_row is None:
                raise HTTPException(status_code=404, detail="Reopen request not found.")
            if request_row["status"] != "Pending":
                raise HTTPException(status_code=409, detail="This request has already been decided.")
            if complaint["status"] != "Resolved":
                raise HTTPException(status_code=409, detail="Complaint must still be Resolved.")

            timestamp = connection.scalar(select(func.now()))
            row = connection.execute(
                update(ReopenRequest)
                .where(ReopenRequest.id == request_id)
                .values(status=body.decision, decided_by=reviewer.id, decided_at=timestamp)
                .returning(*RETURN_FIELDS)
            ).mappings().one()

            if body.decision == "Accepted":
                connection.execute(
                    update(Complaint)
                    .where(Complaint.id == complaint_id)
                    .values(status="Reopened", updated_at=timestamp)
                )
                connection.execute(
                    insert(StatusHistory).values(
                        complaint_id=complaint_id,
                        changed_by=reviewer.id,
                        old_status="Resolved",
                        new_status="Reopened",
                        changed_at=timestamp,
                    )
                )

            connection.execute(
                insert(Notification).values(
                    user_id=complaint["reported_by"],
                    complaint_id=complaint_id,
                    message=(
                        f"Complaint #{complaint_id}: reopen request {body.decision.lower()}."
                    ),
                )
            )
        return ReopenOutput.model_validate(row)

    return router
