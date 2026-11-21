"""CampusFix Phase 3: safe smoke tests.

Run from the campus_fix project root:
    python -m pytest tests/test_smoke.py -v

All API requests in this file are read-only. The Pydantic validation tests
never submit registration forms to the database.
"""

from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from pydantic import ValidationError

# Match the environment supplied by `uvicorn --env-file .env`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

from backend.main import app  # noqa: E402
from backend.routes.auth import LoginInput, RegisterInput  # noqa: E402

client = TestClient(app)


def test_backend_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_database_connection_is_healthy():
    response = client.get("/api/health/db")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"
    assert response.json()["result"] == 1


def test_six_fixed_categories_exist():
    response = client.get("/api/categories")
    assert response.status_code == 200
    categories = response.json()
    assert isinstance(categories, list)
    assert {item["name"] for item in categories} == {
        "Wi-Fi/IT", "Hostel", "Electrical", "Cleanliness", "Classroom", "Other"
    }
    assert all(isinstance(item["id"], int) for item in categories)


@pytest.mark.parametrize(
    "path",
    [
        "/api/auth/me",
        "/api/complaints/mine",
        "/api/notifications",
        "/api/admin/staff",
        "/api/staff/complaints",
    ],
)
def test_protected_endpoint_requires_login(path):
    response = client.get(path)
    assert response.status_code == 401, (
        f"{path} should reject unauthenticated requests, "
        f"but returned {response.status_code}: {response.text[:300]}"
    )


def test_public_registration_cannot_request_admin_role():
    # Validation only: this test does NOT register any account.
    with pytest.raises(ValidationError):
        RegisterInput.model_validate(
            {
                "name": "Test Student",
                "email": "test-student@example.com",
                "password": "TestPassword123!",
                "role": "Admin",
            }
        )


def test_login_role_must_be_one_of_three_known_roles():
    # Validation only: this test does NOT attempt to sign in.
    with pytest.raises(ValidationError):
        LoginInput.model_validate(
            {
                "email": "test-student@example.com",
                "password": "TestPassword123!",
                "role": "SuperAdmin",
            }
        )
