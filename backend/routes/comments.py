"""Comments: reporter, assigned staff and admin can read/reply; author/admin delete.

All endpoints use the existing bearer login. The author is taken from the token,
never from client-submitted JSON.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import Engine, delete, insert, select
from sqlalchemy.engine import Connection

from backend.models.comment import Comment
from backend.models.complaint import Complaint
from backend.models.user import User
from backend.routes.auth import PublicUser


class CommentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]


class CommentOutput(BaseModel):
    id: int
    complaint_id: int
    author_id: int
    author_name: str
    author_role: Literal["Student", "Staff", "Admin"]
    body: str
    created_at: datetime


def create_comments_router(
    engine: Engine, current_user: Callable[..., PublicUser]
) -> APIRouter:
    router = APIRouter(tags=["Comments"])

    def ensure_access(connection: Connection, complaint_id: int, user: PublicUser) -> None:
        record = connection.execute(
            select(Complaint.reported_by, Complaint.assigned_to).where(
                Complaint.id == complaint_id
            )
        ).mappings().one_or_none()
        if record is None:
            raise HTTPException(status_code=404, detail="Complaint not found.")

        allowed = (
            user.role == "Admin"
            or (user.role == "Student" and record["reported_by"] == user.id)
            or (user.role == "Staff" and record["assigned_to"] == user.id)
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="You cannot access this complaint.")

    detail_query = (
        select(
            Comment.id,
            Comment.complaint_id,
            Comment.author_id,
            Comment.body,
            Comment.created_at,
            User.name.label("author_name"),
            User.role.label("author_role"),
        )
        .join(User, User.id == Comment.author_id)
    )

    @router.get(
        "/api/complaints/{complaint_id}/comments",
        response_model=list[CommentOutput],
    )
    def list_comments(
        complaint_id: Annotated[int, Path(ge=1)],
        user: Annotated[PublicUser, Depends(current_user)],
    ):
        with engine.connect() as connection:
            ensure_access(connection, complaint_id, user)
            rows = connection.execute(
                detail_query
                .where(Comment.complaint_id == complaint_id)
                .order_by(Comment.created_at, Comment.id)
            ).mappings().all()
        return [CommentOutput.model_validate(row) for row in rows]

    @router.post(
        "/api/complaints/{complaint_id}/comments",
        response_model=CommentOutput,
        status_code=status.HTTP_201_CREATED,
    )
    def add_comment(
        complaint_id: Annotated[int, Path(ge=1)],
        body: CommentInput,
        user: Annotated[PublicUser, Depends(current_user)],
    ):
        with engine.begin() as connection:
            ensure_access(connection, complaint_id, user)
            comment_id = connection.execute(
                insert(Comment)
                .values(complaint_id=complaint_id, author_id=user.id, body=body.body)
                .returning(Comment.id)
            ).scalar_one()
            row = connection.execute(
                detail_query.where(Comment.id == comment_id)
            ).mappings().one()
        return CommentOutput.model_validate(row)

    @router.delete(
        "/api/comments/{comment_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def remove_comment(
        comment_id: Annotated[int, Path(ge=1)],
        user: Annotated[PublicUser, Depends(current_user)],
    ):
        with engine.begin() as connection:
            record = connection.execute(
                select(Comment.complaint_id, Comment.author_id)
                .where(Comment.id == comment_id)
            ).mappings().one_or_none()
            if record is None:
                raise HTTPException(status_code=404, detail="Comment not found.")
            ensure_access(connection, record["complaint_id"], user)
            if user.role != "Admin" and record["author_id"] != user.id:
                raise HTTPException(status_code=403, detail="Only the author or admin may delete this comment.")
            connection.execute(delete(Comment).where(Comment.id == comment_id))
        return None

    return router
