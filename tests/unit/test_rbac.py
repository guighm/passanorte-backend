"""T023 [US2] Testes unitários de RBAC (RF03).

admin: acesso total; supplier: apenas concessão de benefícios;
tourist: apenas /me*. Falha antes da implementação de T027/T028.
"""


import pytest
from fastapi.testclient import TestClient

from services.auth.app.api import panel, session  # noqa: E402
from services.auth.app.core import deps as auth_deps  # noqa: E402
from shared.app import create_app  # noqa: E402


@pytest.fixture
def client(db_session, connect_partner_services):
    app = create_app("auth", routers=[session.router, panel.router])
    app.dependency_overrides[auth_deps.get_db] = lambda: db_session
    connect_partner_services(app, db_session)
    return TestClient(app)


def seed_user(db, role: str, email: str) -> None:
    from services.auth.app.models.user import User, UserRole
    from services.benefits.app.models import Partner
    from shared.security import hash_password

    partner = None
    if role == "supplier":
        partner = Partner(name="Parceiro", cnpj="04252011000110", contact="contato@example.com")
        db.add(partner)
        db.flush()
    db.add(
        User(
            role=UserRole(role), partner_id=partner.id if partner else None,
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


def test_admin_can_manage_panel(client, db_session):
    seed_user(db_session, "admin", "admin@example.com")
    resp = client.get("/api/v1/panel/users", headers=login(client, "admin@example.com"))
    assert resp.status_code == 200


def test_supplier_cannot_access_admin_endpoints(client, db_session):
    seed_user(db_session, "admin", "admin@example.com")
    seed_user(db_session, "supplier", "emp@example.com")
    resp = client.get(
        "/api/v1/panel/users",
        headers=login(client, "emp@example.com"),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_tourist_cannot_access_admin_endpoints(client, db_session):
    seed_user(db_session, "admin", "admin@example.com")
    seed_user(db_session, "tourist", "tourist@example.com")
    resp = client.get("/api/v1/panel/users", headers=login(client, "tourist@example.com"))
    assert resp.status_code == 403


def test_anonymous_is_401(client):
    assert client.get("/api/v1/panel/users").status_code == 401


def test_legacy_employee_token_is_rejected(client):
    from shared.security import create_access_token

    token, _ = create_access_token("legacy-user", "employee")
    response = client.get("/api/v1/panel/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_revoked_supplier_cannot_authenticate(client, db_session):
    seed_user(db_session, "admin", "admin@example.com")
    seed_user(db_session, "supplier", "emp@example.com")
    admin_headers = login(client, "admin@example.com")
    emp = next(user for user in client.get("/api/v1/panel/users", headers=admin_headers).json()["items"]
               if user["role"] == "supplier")
    resp = client.delete(f"/api/v1/panel/users/{emp['id']}", headers=admin_headers)
    assert resp.status_code == 204
    # revogado não autentica mais (edge case da spec)
    resp = client.post("/api/v1/session", json={"email": "emp@example.com", "password": "s3cr3t!x"})
    assert resp.status_code == 401
