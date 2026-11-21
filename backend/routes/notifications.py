"""Student in-app notifications: own messages only, protected by bearer login."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import Engine, func, select, update

from backend.models.notification import Notification
from backend.routes.auth import PublicUser


class NotificationOutput(BaseModel):
    id: int
    complaint_id: int
    message: str
    created_at: datetime
    read_at: datetime | None


class UnreadCount(BaseModel):
    unread_count: int


def create_notifications_router(
    engine: Engine, current_user: Callable[..., PublicUser]
) -> APIRouter:
    router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

    def require_student(user: Annotated[PublicUser, Depends(current_user)]) -> PublicUser:
        if user.role != "Student":
            raise HTTPException(status_code=403, detail="Student access required.")
        return user

    @router.get("", response_model=list[NotificationOutput])
    def list_notifications(
        student: Annotated[PublicUser, Depends(require_student)],
        unread_only: bool = False,
    ):
        query = select(
            Notification.id, Notification.complaint_id,
            Notification.message, Notification.created_at, Notification.read_at,
        ).where(Notification.user_id == student.id)
        if unread_only:
            query = query.where(Notification.read_at.is_(None))
        query = query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(100)
        with engine.connect() as connection:
            rows = connection.execute(query).mappings().all()
        return [NotificationOutput.model_validate(row) for row in rows]

    @router.get("/unread-count", response_model=UnreadCount)
    def unread_count(student: Annotated[PublicUser, Depends(require_student)]):
        with engine.connect() as connection:
            count = connection.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == student.id,
                    Notification.read_at.is_(None),
                )
            )
        return UnreadCount(unread_count=count or 0)

    @router.put("/{notification_id}/read", response_model=NotificationOutput)
    def mark_notification_read(
        notification_id: Annotated[int, Path(ge=1)],
        student: Annotated[PublicUser, Depends(require_student)],
    ):
        with engine.begin() as connection:
            row = connection.execute(
                update(Notification)
                .where(Notification.id == notification_id, Notification.user_id == student.id)
                .values(read_at=func.coalesce(Notification.read_at, func.now()))
                .returning(
                    Notification.id, Notification.complaint_id,
                    Notification.message, Notification.created_at, Notification.read_at,
                )
            ).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Notification not found.")
        return NotificationOutput.model_validate(row)

    return router
