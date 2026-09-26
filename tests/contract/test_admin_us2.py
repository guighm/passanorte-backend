"""T024 [US2] Testes de contrato dos endpoints administrativos (contracts/*.md).

Pontos/eventos/categorias/cronograma/status no catalog (RF11–RF17) e
funcionários no auth (RF04/RF05), com auditoria (RNF19).
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from services.auth.app.core import deps as auth_deps  # noqa: E402
from services.auth.app.main import create_test_app as auth_factory  # noqa: E402
from services.auth.app.models.user import User, UserRole  # noqa: E402
from services.catalog.app.core import deps as catalog_deps  # noqa: E402
from services.catalog.app.main import create_test_app as catalog_factory  # noqa: E402
from shared.security import hash_password  # noqa: E402


@pytest.fixture
def admin_headers(auth_client) -> dict:
    """Cabeçalhos de um admin autenticado (RBAC real, RF03)."""
    return admin_login(auth_client)


@pytest.fixture
def auth_client(db_session):
    def seed(email: str, role: str):
        db_session.add(
            User(role=UserRole(role), name="A", surname="B", email=email,
                 password_hash=hash_password("s3cr3t!x"), country_of_origin="Brasil")
        )
        db_session.commit()

    app = auth_factory()
    app.dependency_overrides[auth_deps.get_db] = lambda: db_session
    client = TestClient(app)
    client.seed = seed  # type: ignore[attr-defined]
    return client


@pytest.fixture
def catalog_client(db_session):
    app = catalog_factory()
    app.dependency_overrides[catalog_deps.get_db] = lambda: db_session
    return TestClient(app)


def admin_login(auth_client) -> dict:
    auth_client.seed("admin@example.com", "admin")
    login = auth_client.post("/api/v1/session", json={"email": "admin@example.com", "password": "s3cr3t!x"}).json()
    return {"Authorization": f"Bearer {login['access_token']}"}


# --- Pontos turísticos (RF11–RF15) ------------------------------------------

def test_admin_creates_spot(catalog_client, admin_headers):
    headers = admin_headers
    resp = catalog_client.post(
        "/api/v1/tourist-spots",
        headers=headers,
        json={
            "name": "Teatro Amazonas",
            "description": "Teatro histórico",
            "latitude": -3.4704,
            "longitude": -60.0238,
            "category_ids": [],
        },
    )
    assert resp.status_code == 201, resp.text


def test_admin_updates_spot_status(catalog_client, admin_headers):
    headers = admin_headers
    spot = catalog_client.post(
        "/api/v1/tourist-spots",
        headers=headers,
        json={"name": "X", "description": "Y", "latitude": -3.0, "longitude": -60.0, "category_ids": []},
    ).json()
    resp = catalog_client.patch(
        f"/api/v1/tourist-spots/{spot['id']}/status", headers=headers, json={"status": "temporarily_closed"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "temporarily_closed"


def test_admin_sets_schedule_no_overlap(catalog_client, admin_headers):
    headers = admin_headers
    spot = catalog_client.post(
        "/api/v1/tourist-spots",
        headers=headers,
        json={"name": "X", "description": "Y", "latitude": -3.0, "longitude": -60.0, "category_ids": []},
    ).json()
    resp = catalog_client.put(
        f"/api/v1/tourist-spots/{spot['id']}/schedule",
        headers=headers,
        json={"schedule": [{"day_of_week": 1, "opens_at": "09:00", "closes_at": "17:00"}]},
    )
    assert resp.status_code == 200
    # janela sobreposta no mesmo dia → 422 (constraint do data-model.md)
    resp = catalog_client.put(
        f"/api/v1/tourist-spots/{spot['id']}/schedule",
        headers=headers,
        json={"schedule": [
            {"day_of_week": 1, "opens_at": "16:00", "closes_at": "18:00"},
            {"day_of_week": 1, "opens_at": "17:00", "closes_at": "20:00"},
        ]},
    )
    assert resp.status_code == 422


def test_admin_removes_spot_logically(catalog_client, admin_headers):
    headers = admin_headers
    spot = catalog_client.post(
        "/api/v1/tourist-spots",
        headers=headers,
        json={"name": "X", "description": "Y", "latitude": -3.0, "longitude": -60.0, "category_ids": []},
    ).json()
    resp = catalog_client.delete(f"/api/v1/tourist-spots/{spot['id']}", headers=headers)
    assert resp.status_code == 204
    assert catalog_client.get(f"/api/v1/tourist-spots/{spot['id']}").status_code == 404


def test_admin_creates_event(catalog_client, admin_headers):
    headers = admin_headers
    spot = catalog_client.post(
        "/api/v1/tourist-spots",
        headers=headers,
        json={"name": "X", "description": "Y", "latitude": -3.0, "longitude": -60.0, "category_ids": []},
    ).json()
    resp = catalog_client.post(
        "/api/v1/events",
        headers=headers,
        json={"tourist_spot_id": spot["id"], "title": "Festival", "description": "d",
              "occurs_at": "2026-10-01T20:00:00", "ticket_price": 25.0},
    )
    assert resp.status_code == 201


def test_negative_ticket_price_rejected(catalog_client, admin_headers):
    headers = admin_headers
    spot = catalog_client.post(
        "/api/v1/tourist-spots",
        headers=headers,
        json={"name": "X", "description": "Y", "latitude": -3.0, "longitude": -60.0, "category_ids": []},
    ).json()
    resp = catalog_client.post(
        "/api/v1/events",
        headers=headers,
        json={"tourist_spot_id": spot["id"], "title": "F", "description": "d",
              "occurs_at": "2026-10-01T20:00:00", "ticket_price": -1.0},
    )
    assert resp.status_code == 422


def test_admin_snapshot_internal_endpoint(catalog_client, admin_headers):
    headers = admin_headers
    spot = catalog_client.post(
        "/api/v1/tourist-spots",
        headers=headers,
        json={"name": "X", "description": "Y", "latitude": -3.0, "longitude": -60.0, "category_ids": ["c1"]},
    ).json()
    resp = catalog_client.get(f"/api/v1/internal/tourist-spots/{spot['id']}")
    body = resp.json()
    assert body["latitude"] == -3.0
    assert body["category_ids"] == ["c1"]


def test_admin_actions_are_audited(catalog_client, db_session, admin_headers):
    headers = admin_headers
    catalog_client.post(
        "/api/v1/tourist-spots",
        headers=headers,
        json={"name": "Audit", "description": "Y", "latitude": -3.0, "longitude": -60.0, "category_ids": []},
    )
    from services.catalog.app.models.audit import AuditLog

    logs = db_session.query(AuditLog).filter(AuditLog.action == "create_spot").all()
    assert len(logs) == 1
    assert logs[0].entity == "tourist_spot"


# --- Funcionários (RF04/RF05) -------------------------------------------------

def test_admin_creates_employee(auth_client, admin_headers):
    headers = admin_headers
    resp = auth_client.post(
        "/api/v1/employees",
        headers=headers,
        json={"name": "Fulano", "surname": "Beltrano", "email": "func@example.com", "password": "s3cr3t!x"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "employee"
