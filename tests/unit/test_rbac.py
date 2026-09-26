"""T023 [US2] Testes unitários de RBAC (RF03).

admin: acesso total; employee: apenas concessão de benefícios;
tourist: apenas /me*. Falha antes da implementação de T027/T028.
"""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from services.auth.app.api import employees, session  # noqa: E402
from services.auth.app.core import deps as auth_deps  # noqa: E402
from shared.app import create_app  # noqa: E402


@pytest.fixture
def client(db_session):
    app = create_app("auth", routers=[session.router, employees.router])
    app.dependency_overrides[auth_deps.get_db] = lambda: db_session
    return TestClient(app)


def seed_user(db, role: str, email: str) -> None:
    from services.auth.app.models.user import User, UserRole
    from shared.security import hash_password

    db.add(
        User(
            role=UserRole(role),
            name="X",
            surname="Y",
            email=email,
            password_hash=hash_password("s3cr3t!x"),
            country_of_origin="Brasil",
        )
    )
    db.commit()


def login(client: TestClient, email: str) -> dict:
    resp = client.post("/api/v1/session", json={"email": email, "password": "s3cr3t!x"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_admin_can_manage_employees(client, db_session):
    seed_user(db_session, "admin", "admin@example.com")
    resp = client.get("/api/v1/employees", headers=login(client, "admin@example.com"))
    assert resp.status_code == 200


def test_employee_cannot_access_admin_endpoints(client, db_session):
    seed_user(db_session, "admin", "admin@example.com")
    seed_user(db_session, "employee", "emp@example.com")
    resp = client.get(
        "/api/v1/employees",
        headers=login(client, "emp@example.com"),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_tourist_cannot_access_admin_endpoints(client, db_session):
    seed_user(db_session, "admin", "admin@example.com")
    seed_user(db_session, "tourist", "tourist@example.com")
    resp = client.get("/api/v1/employees", headers=login(client, "tourist@example.com"))
    assert resp.status_code == 403


def test_anonymous_is_401(client):
    assert client.get("/api/v1/employees").status_code == 401


def test_revoked_employee_cannot_authenticate(client, db_session):
    seed_user(db_session, "admin", "admin@example.com")
    seed_user(db_session, "employee", "emp@example.com")
    admin_headers = login(client, "admin@example.com")
    emp = client.get("/api/v1/employees", headers=admin_headers).json()["items"][0]
    resp = client.delete(f"/api/v1/employees/{emp['id']}", headers=admin_headers)
    assert resp.status_code == 204
    # revogado não autentica mais (edge case da spec)
    resp = client.post("/api/v1/session", json={"email": "emp@example.com", "password": "s3cr3t!x"})
    assert resp.status_code == 401
