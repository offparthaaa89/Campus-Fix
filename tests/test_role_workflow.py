"""CampusFix Phase 3: isolated authentication and role-workflow tests.

Run from the project root:
    python -m pytest tests/test_role_workflow.py -v

All writes take place in a new, in-memory SQLite database per test.
Your existing PostgreSQL database, user accounts, and complaints are untouched.
SQLite is a test double; PostgreSQL-specific behaviour needs separate tests.
"""

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
from backend.models.assignment import Assignment
from backend.models.status_history import StatusHistory
from backend.models.notification import Notification
from backend.routes.auth import AuthRoutes
from backend.routes.complaint import create_complaints_router
from backend.routes.staff_workflow import create_staff_workflow_router

# Only local dummy accounts. No live credentials or production data.
_TEST_PASSWORD = "DemoOnly_123!"
_TEST_SECRET = "test-only-secret-value-never-use-for-real-logins-123456"
_TABLES = [
    User.__table__, Category.__table__, Complaint.__table__,
    Assignment.__table__, StatusHistory.__table__, Notification.__table__,
]


@pytest.fixture
def sandbox(monkeypatch):
    """Fresh isolated database and API for each test; no backend.main import."""
    monkeypatch.setenv("CAMPUSFIX_AUTH_SECRET", _TEST_SECRET)
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=_TABLES)
    pw_hash = PasswordHash.recommended().hash(_TEST_PASSWORD)

    with engine.begin() as con:
        con.execute(insert(User), [
            {"id": 101, "name": "Student One", "email": "student1@example.com", "password_hash": pw_hash, "role": "Student"},
            {"id": 102, "name": "Student Two", "email": "student2@example.com", "password_hash": pw_hash, "role": "Student"},
            {"id": 201, "name": "Staff One", "email": "staff1@example.com", "password_hash": pw_hash, "role": "Staff"},
            {"id": 202, "name": "Staff Two", "email": "staff2@example.com", "password_hash": pw_hash, "role": "Staff"},
            {"id": 301, "name": "Campus Admin", "email": "admin@example.com", "password_hash": pw_hash, "role": "Admin"},
        ])
        con.execute(insert(Category), {"id": 1, "name": "Wi-Fi/IT"})
        con.execute(insert(Complaint), [
            {"id": 501, "title": "No Wi-Fi", "description": "Network is down", "location": "Hostel B", "category_id": 1, "reported_by": 101, "assigned_to": None, "status": "Open"},
            {"id": 502, "title": "Slow Wi-Fi", "description": "Network is slow", "location": "Hostel A", "category_id": 1, "reported_by": 102, "assigned_to": 202, "status": "Open"},
            {"id": 503, "title": "Broken router", "description": "Router failed", "location": "Library", "category_id": 1, "reported_by": 101, "assigned_to": 201, "status": "Open"},
        ])

    auth = AuthRoutes(engine)
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(create_complaints_router(engine, auth.current_user))
    app.include_router(create_staff_workflow_router(engine, auth.current_user))

    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def sign_in(client, email, role):
    response = client.post("/api/auth/login", json={
        "email": email,
        "password": _TEST_PASSWORD,
        "role": role,
    })
    return response


def bearer(client, email, role):
    response = sign_in(client, email, role)
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.mark.parametrize("email,role", [
    ("student1@example.com", "Student"),
    ("staff1@example.com", "Staff"),
    ("admin@example.com", "Admin"),
])
def test_correct_role_login_and_me(sandbox, email, role):
    client, _ = sandbox
    token = bearer(client, email, role)
    result = client.get("/api/auth/me", headers=token)
    assert result.status_code == 200
    assert result.json()["role"] == role
    assert result.json()["email"] == email


@pytest.mark.parametrize("email,wrong_role", [
    ("student1@example.com", "Staff"),
    ("student1@example.com", "Admin"),
    ("staff1@example.com", "Student"),
    ("staff1@example.com", "Admin"),
    ("admin@example.com", "Student"),
    ("admin@example.com", "Staff"),
])
def test_wrong_role_login_rejected(sandbox, email, wrong_role):
    client, _ = sandbox
    response = sign_in(client, email, wrong_role)
    assert response.status_code == 401
    assert "access_token" not in response.text


def test_invalid_token_rejected(sandbox):
    client, _ = sandbox
    result = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert result.status_code == 401


def test_student_sees_only_own_complaints(sandbox):
    client, _ = sandbox
    first = client.get("/api/complaints/mine", headers=bearer(client, "student1@example.com", "Student"))
    second = client.get("/api/complaints/mine", headers=bearer(client, "student2@example.com", "Student"))
    assert first.status_code == second.status_code == 200
    assert {item["id"] for item in first.json()} == {501, 503}
    assert {item["id"] for item in second.json()} == {502}


def test_student_cannot_read_other_students_complaint(sandbox):
    client, _ = sandbox
    response = client.get("/api/complaints/502", headers=bearer(client, "student1@example.com", "Student"))
    assert response.status_code in (403, 404)  # Hidden or explicitly forbidden.


@pytest.mark.parametrize("target", [
    "/api/admin/staff", "/api/admin/complaints", "/api/staff/complaints"
])
def test_student_cannot_access_staff_or_admin_endpoints(sandbox, target):
    client, _ = sandbox
    result = client.get(target, headers=bearer(client, "student1@example.com", "Student"))
    assert result.status_code == 403


def test_staff_cannot_access_admin_endpoint(sandbox):
    client, _ = sandbox
    result = client.get("/api/admin/staff", headers=bearer(client, "staff1@example.com", "Staff"))
    assert result.status_code == 403


def test_admin_cannot_access_staff_queue(sandbox):
    client, _ = sandbox
    result = client.get("/api/staff/complaints", headers=bearer(client, "admin@example.com", "Admin"))
    assert result.status_code == 403


def test_staff_queue_is_scoped_to_assigned_staff(sandbox):
    client, _ = sandbox
    response = client.get("/api/staff/complaints", headers=bearer(client, "staff1@example.com", "Staff"))
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {503}


def test_staff_cannot_update_another_staff_ticket(sandbox):
    client, _ = sandbox
    response = client.put(
        "/api/staff/complaints/502/status",
        json={"new_status": "In Progress"},
        headers=bearer(client, "staff1@example.com", "Staff"),
    )
    assert response.status_code == 404


def test_illegal_status_jump_is_rejected(sandbox):
    client, engine = sandbox
    response = client.put(
        "/api/staff/complaints/503/status",
        json={"new_status": "Resolved"},
        headers=bearer(client, "staff1@example.com", "Staff"),
    )
    assert response.status_code == 409
    with engine.connect() as con:
        assert con.scalar(select(Complaint.status).where(Complaint.id == 503)) == "Open"


def test_status_update_creates_history_and_notification(sandbox):
    client, engine = sandbox
    response = client.put(
        "/api/staff/complaints/503/status",
        json={"new_status": "In Progress"},
        headers=bearer(client, "staff1@example.com", "Staff"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["new_status"] == "In Progress"
    with engine.connect() as con:
        assert con.scalar(select(Complaint.status).where(Complaint.id == 503)) == "In Progress"
        assert con.scalar(select(StatusHistory.new_status).where(StatusHistory.complaint_id == 503)) == "In Progress"
        note = con.execute(select(Notification.user_id, Notification.complaint_id).where(Notification.complaint_id == 503)).one()
        assert note == (101, 503)


def test_admin_can_assign_ticket_and_duplicate_is_rejected(sandbox):
    client, engine = sandbox
    headers = bearer(client, "admin@example.com", "Admin")
    request = {"staff_id": 201}
    response = client.put("/api/admin/complaints/501/assignment", json=request, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["staff_id"] == 201
    with engine.connect() as con:
        assert con.scalar(select(Complaint.assigned_to).where(Complaint.id == 501)) == 201
        assert con.scalar(select(Assignment.assigned_by).where(Assignment.complaint_id == 501)) == 301
    again = client.put("/api/admin/complaints/501/assignment", json=request, headers=headers)
    assert again.status_code == 409
