"""CampusFix Step 43: comments, notifications, reopen edge-case tests.

This file intentionally creates its own in-memory SQLite database and FastAPI app.
It does NOT import backend.main, connect to PostgreSQL, modify production records,
or use any real CampusFix accounts/passwords.

Run: python -m pytest tests/test_engagement_workflow.py -v
"""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlalchemy import create_engine, insert, select
from sqlalchemy.pool import StaticPool

from backend.models.base import Base
from backend.models.user import User
from backend.models.category import Category
from backend.models.complaint import Complaint
from backend.models.comment import Comment
from backend.models.assignment import Assignment
from backend.models.status_history import StatusHistory
from backend.models.notification import Notification
from backend.models.reopen_request import ReopenRequest
from backend.routes.auth import AuthRoutes
from backend.routes.comments import create_comments_router
from backend.routes.notifications import create_notifications_router
from backend.routes.reopen_requests import create_reopen_router

PASSWORD = "OnlyForIsolatedTests_123!"
SECRET = "isolated-test-only-secret-00000000000000000000"
TABLES = [
    User.__table__, Category.__table__, Complaint.__table__,
    Comment.__table__, Assignment.__table__, StatusHistory.__table__,
    Notification.__table__, ReopenRequest.__table__,
]


@pytest.fixture
def sandbox(monkeypatch):
    """Fresh test DB per test; no live database connection or backend.main import."""
    monkeypatch.setenv("CAMPUSFIX_AUTH_SECRET", SECRET)
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TABLES)
    fake_hash = PasswordHash.recommended().hash(PASSWORD)
    with engine.begin() as con:
        con.execute(insert(User), [
            {"id": 101, "name": "Student One", "email": "student1@example.com", "password_hash": fake_hash, "role": "Student"},
            {"id": 102, "name": "Student Two", "email": "student2@example.com", "password_hash": fake_hash, "role": "Student"},
            {"id": 201, "name": "Staff One", "email": "staff1@example.com", "password_hash": fake_hash, "role": "Staff"},
            {"id": 202, "name": "Staff Two", "email": "staff2@example.com", "password_hash": fake_hash, "role": "Staff"},
            {"id": 301, "name": "Test Admin", "email": "admin@example.com", "password_hash": fake_hash, "role": "Admin"},
        ])
        con.execute(insert(Category), {"id": 1, "name": "Wi-Fi/IT"})
        con.execute(insert(Complaint), [
            {"id": 501, "title": "Open issue", "description": "Test", "location": "Library", "category_id": 1, "reported_by": 101, "assigned_to": 201, "status": "Open"},
            {"id": 502, "title": "Resolved issue", "description": "Test", "location": "Hostel", "category_id": 1, "reported_by": 101, "assigned_to": 201, "status": "Resolved"},
            {"id": 503, "title": "Other student's issue", "description": "Test", "location": "Block A", "category_id": 1, "reported_by": 102, "assigned_to": 202, "status": "Resolved"},
            {"id": 504, "title": "Unassigned issue", "description": "Test", "location": "Canteen", "category_id": 1, "reported_by": 101, "assigned_to": None, "status": "Resolved"},
            {"id": 505, "title": "Working issue", "description": "Test", "location": "Lab", "category_id": 1, "reported_by": 101, "assigned_to": 202, "status": "In Progress"},
            {"id": 506, "title": "Decline example", "description": "Test", "location": "Hall", "category_id": 1, "reported_by": 101, "assigned_to": 201, "status": "Resolved"},
        ])
        con.execute(insert(Notification), [
            {"id": 1001, "user_id": 101, "complaint_id": 502, "message": "Resolved", "read_at": None},
            {"id": 1002, "user_id": 102, "complaint_id": 503, "message": "Other student notification", "read_at": None},
            {"id": 1003, "user_id": 101, "complaint_id": 501, "message": "Already read", "read_at": datetime(2026, 1, 1, tzinfo=timezone.utc)},
        ])

    auth = AuthRoutes(engine)
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(create_comments_router(engine, auth.current_user))
    app.include_router(create_notifications_router(engine, auth.current_user))
    app.include_router(create_reopen_router(engine, auth.current_user))
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def headers(client, email, role):
    response = client.post("/api/auth/login", json={
        "email": email, "password": PASSWORD, "role": role,
    })
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def as_student1(client):
    return headers(client, "student1@example.com", "Student")


def as_student2(client):
    return headers(client, "student2@example.com", "Student")


def as_staff1(client):
    return headers(client, "staff1@example.com", "Staff")


def as_staff2(client):
    return headers(client, "staff2@example.com", "Staff")


def as_admin(client):
    return headers(client, "admin@example.com", "Admin")


# --- Comments: privacy, validation, authorship, removal ---

def test_student_posts_comment_and_author_is_from_token(sandbox):
    client, engine = sandbox
    r = client.post("/api/complaints/501/comments", json={"body": "  Please check Wi-Fi  "}, headers=as_student1(client))
    assert r.status_code == 201, r.text
    assert r.json()["author_id"] == 101
    assert r.json()["author_role"] == "Student"
    assert r.json()["body"] == "Please check Wi-Fi"
    with engine.connect() as con:
        assert con.scalar(select(Comment.author_id).where(Comment.id == r.json()["id"])) == 101


@pytest.mark.parametrize("body", ["   ", "x" * 2001])
def test_comments_reject_blank_and_too_long(sandbox, body):
    client, _ = sandbox
    r = client.post("/api/complaints/501/comments", json={"body": body}, headers=as_student1(client))
    assert r.status_code == 422


def test_comment_cannot_spoof_author_id(sandbox):
    client, _ = sandbox
    r = client.post("/api/complaints/501/comments", json={"body": "Hello", "author_id": 301}, headers=as_student1(client))
    assert r.status_code == 422


def test_other_student_cannot_read_or_write_comments(sandbox):
    client, _ = sandbox
    h = as_student2(client)
    assert client.get("/api/complaints/501/comments", headers=h).status_code == 403
    assert client.post("/api/complaints/501/comments", json={"body": "No"}, headers=h).status_code == 403


def test_unassigned_staff_cannot_read_or_write_comments(sandbox):
    client, _ = sandbox
    h = as_staff2(client)
    assert client.get("/api/complaints/501/comments", headers=h).status_code == 403
    assert client.post("/api/complaints/501/comments", json={"body": "No"}, headers=h).status_code == 403


def test_assigned_staff_can_reply_and_admin_can_read(sandbox):
    client, _ = sandbox
    r = client.post("/api/complaints/501/comments", json={"body": "Working on it"}, headers=as_staff1(client))
    assert r.status_code == 201, r.text
    listing = client.get("/api/complaints/501/comments", headers=as_admin(client))
    assert listing.status_code == 200
    assert any(row["body"] == "Working on it" and row["author_role"] == "Staff" for row in listing.json())


def test_staff_cannot_delete_student_comment_but_admin_can(sandbox):
    client, engine = sandbox
    posted = client.post("/api/complaints/501/comments", json={"body": "Student request"}, headers=as_student1(client))
    comment_id = posted.json()["id"]
    assert client.delete(f"/api/comments/{comment_id}", headers=as_staff1(client)).status_code == 403
    assert client.delete(f"/api/comments/{comment_id}", headers=as_admin(client)).status_code == 204
    with engine.connect() as con:
        assert con.scalar(select(Comment.id).where(Comment.id == comment_id)) is None


def test_comment_author_can_delete_own_comment(sandbox):
    client, _ = sandbox
    posted = client.post("/api/complaints/501/comments", json={"body": "To remove"}, headers=as_student1(client))
    assert posted.status_code == 201
    assert client.delete(f"/api/comments/{posted.json()['id']}", headers=as_student1(client)).status_code == 204


def test_missing_complaint_comments_return_404(sandbox):
    client, _ = sandbox
    assert client.get("/api/complaints/999999/comments", headers=as_admin(client)).status_code == 404


# --- Notifications: identity scoping, unread count, idempotent read ---

def test_students_see_only_their_notifications(sandbox):
    client, _ = sandbox
    first = client.get("/api/notifications", headers=as_student1(client))
    second = client.get("/api/notifications", headers=as_student2(client))
    assert first.status_code == second.status_code == 200
    assert {row["id"] for row in first.json()} == {1001, 1003}
    assert {row["id"] for row in second.json()} == {1002}


def test_unread_count_and_mark_read_are_consistent(sandbox):
    client, _ = sandbox
    h = as_student1(client)
    count_url = "/api/notifications/unread-count"
    assert client.get(count_url, headers=h).json()["unread_count"] == 1
    first = client.put("/api/notifications/1001/read", headers=h)
    assert first.status_code == 200, first.text
    assert first.json()["read_at"] is not None
    second = client.put("/api/notifications/1001/read", headers=h)
    assert second.status_code == 200
    assert second.json()["read_at"] == first.json()["read_at"]
    assert client.get(count_url, headers=h).json()["unread_count"] == 0
    assert client.get("/api/notifications?unread_only=true", headers=h).json() == []


def test_student_cannot_mark_another_students_notification(sandbox):
    client, engine = sandbox
    r = client.put("/api/notifications/1002/read", headers=as_student1(client))
    assert r.status_code == 404
    with engine.connect() as con:
        assert con.scalar(select(Notification.read_at).where(Notification.id == 1002)) is None


@pytest.mark.parametrize("role,email", [
    ("Staff", "staff1@example.com"), ("Admin", "admin@example.com"),
])
def test_staff_and_admin_cannot_use_student_notifications(sandbox, role, email):
    client, _ = sandbox
    h = headers(client, email, role)
    assert client.get("/api/notifications", headers=h).status_code == 403
    assert client.put("/api/notifications/1001/read", headers=h).status_code == 403


# --- Reopen: resolved-only, ownership, review scope, audit trail ---

@pytest.mark.parametrize("complaint_id", [501, 505])
def test_only_resolved_complaints_can_be_reopened(sandbox, complaint_id):
    client, _ = sandbox
    r = client.post(f"/api/complaints/{complaint_id}/reopen", json={"reason": "Still broken"}, headers=as_student1(client))
    assert r.status_code == 409


def test_student_cannot_reopen_other_student_complaint(sandbox):
    client, _ = sandbox
    r = client.post("/api/complaints/503/reopen", json={"reason": "Not mine"}, headers=as_student1(client))
    assert r.status_code == 403


def test_staff_cannot_submit_reopen_request(sandbox):
    client, _ = sandbox
    r = client.post("/api/complaints/502/reopen", json={"reason": "Staff cannot"}, headers=as_staff1(client))
    assert r.status_code == 403


@pytest.mark.parametrize("reason", ["  ", "x" * 2001])
def test_reopen_reason_requires_meaningful_short_text(sandbox, reason):
    client, _ = sandbox
    r = client.post("/api/complaints/502/reopen", json={"reason": reason}, headers=as_student1(client))
    assert r.status_code == 422


def test_duplicate_pending_reopen_request_rejected(sandbox):
    client, engine = sandbox
    h = as_student1(client)
    first = client.post("/api/complaints/502/reopen", json={"reason": "Issue remains"}, headers=h)
    assert first.status_code == 201, first.text
    second = client.post("/api/complaints/502/reopen", json={"reason": "Duplicate"}, headers=h)
    assert second.status_code == 409
    with engine.connect() as con:
        rows = con.scalars(select(ReopenRequest.id).where(ReopenRequest.complaint_id == 502)).all()
        assert len(rows) == 1


def test_reopen_history_is_private_to_complaint_owner(sandbox):
    client, _ = sandbox
    assert client.get("/api/complaints/502/reopen-requests", headers=as_student2(client)).status_code == 403
    assert client.get("/api/complaints/502/reopen-requests", headers=as_student1(client)).status_code == 200


def test_pending_queue_is_limited_to_assigned_staff(sandbox):
    client, _ = sandbox
    a = client.post("/api/complaints/502/reopen", json={"reason": "Test 1"}, headers=as_student1(client))
    b = client.post("/api/complaints/503/reopen", json={"reason": "Test 2"}, headers=as_student2(client))
    assert a.status_code == b.status_code == 201
    first = client.get("/api/reopen/pending", headers=as_staff1(client))
    second = client.get("/api/reopen/pending", headers=as_staff2(client))
    admin = client.get("/api/reopen/pending", headers=as_admin(client))
    assert {r["complaint_id"] for r in first.json()} == {502}
    assert {r["complaint_id"] for r in second.json()} == {503}
    assert {r["complaint_id"] for r in admin.json()} == {502, 503}


def test_other_staff_cannot_decide_pending_request(sandbox):
    client, engine = sandbox
    request = client.post("/api/complaints/502/reopen", json={"reason": "Issue remains"}, headers=as_student1(client))
    assert request.status_code == 201
    r = client.put(f"/api/reopen/{request.json()['id']}", json={"decision": "Accepted"}, headers=as_staff2(client))
    assert r.status_code == 403
    with engine.connect() as con:
        assert con.scalar(select(Complaint.status).where(Complaint.id == 502)) == "Resolved"


def test_student_cannot_decide_reopen_request(sandbox):
    client, _ = sandbox
    request = client.post("/api/complaints/502/reopen", json={"reason": "Still failing"}, headers=as_student1(client))
    assert request.status_code == 201
    r = client.put(f"/api/reopen/{request.json()['id']}", json={"decision": "Accepted"}, headers=as_student1(client))
    assert r.status_code == 403


def test_accept_reopen_changes_status_history_and_notifies_owner(sandbox):
    client, engine = sandbox
    request = client.post("/api/complaints/502/reopen", json={"reason": "Not fixed"}, headers=as_student1(client))
    assert request.status_code == 201, request.text
    request_id = request.json()["id"]
    decided = client.put(f"/api/reopen/{request_id}", json={"decision": "Accepted"}, headers=as_staff1(client))
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "Accepted"
    assert decided.json()["decided_by"] == 201
    with engine.connect() as con:
        assert con.scalar(select(Complaint.status).where(Complaint.id == 502)) == "Reopened"
        assert con.scalar(select(StatusHistory.new_status).where(StatusHistory.complaint_id == 502)) == "Reopened"
        alert = con.execute(select(Notification.user_id, Notification.message).where(Notification.complaint_id == 502, Notification.message.like("%accepted%"))).one()
        assert alert[0] == 101
    again = client.put(f"/api/reopen/{request_id}", json={"decision": "Accepted"}, headers=as_staff1(client))
    assert again.status_code == 409


def test_decline_reopen_preserves_resolved_status_and_notifies_owner(sandbox):
    client, engine = sandbox
    request = client.post("/api/complaints/506/reopen", json={"reason": "Still not fixed"}, headers=as_student1(client))
    assert request.status_code == 201
    decided = client.put(f"/api/reopen/{request.json()['id']}", json={"decision": "Declined"}, headers=as_admin(client))
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "Declined"
    with engine.connect() as con:
        assert con.scalar(select(Complaint.status).where(Complaint.id == 506)) == "Resolved"
        assert con.scalar(select(StatusHistory.id).where(StatusHistory.complaint_id == 506)) is None
        alert = con.execute(select(Notification.user_id, Notification.message).where(Notification.complaint_id == 506)).one()
        assert alert[0] == 101 and "declined" in alert[1]


def test_reopen_decision_rejects_unsupported_value(sandbox):
    client, _ = sandbox
    request = client.post("/api/complaints/502/reopen", json={"reason": "Still broken"}, headers=as_student1(client))
    assert request.status_code == 201
    r = client.put(f"/api/reopen/{request.json()['id']}", json={"decision": "Maybe"}, headers=as_admin(client))
    assert r.status_code == 422


def test_unauthenticated_cannot_access_engagement_endpoints(sandbox):
    client, _ = sandbox
    assert client.get("/api/complaints/501/comments").status_code == 401
    assert client.get("/api/notifications").status_code == 401
    assert client.get("/api/reopen/pending").status_code == 401
