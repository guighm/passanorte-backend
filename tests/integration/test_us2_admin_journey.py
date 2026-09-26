"""T031 [US2] Integração: jornada do admin (quickstart S2).

Login admin → cria ponto → schedule/status → evento → funcionário →
RBAC do funcionário → auditoria de todas as ações.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from services.auth.app.core import deps as auth_deps  # noqa: E402
from services.auth.app.main import create_test_app as auth_app_factory  # noqa: E402
from services.catalog.app.core import deps as catalog_deps  # noqa: E402
from services.catalog.app.main import create_test_app as catalog_app_factory  # noqa: E402
from shared.db import Base, make_session_factory  # noqa: E402


@pytest.fixture
def services() -> tuple[TestClient, TestClient]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    auth_app = auth_app_factory()
    auth_app.dependency_overrides[auth_deps.get_db] = lambda: make_session_factory(engine)()
    catalog_app = catalog_app_factory()
    catalog_app.dependency_overrides[catalog_deps.get_db] = lambda: make_session_factory(engine)()
    return TestClient(auth_app), TestClient(catalog_app)


def test_us2_full_admin_journey(services):
    auth, catalog = services

    # 1. credencial inicial do admin (RF01, scripts/create_admin.py) — seeded aqui
    from services.auth.app.models.user import User, UserRole
    from shared.security import hash_password

    session = auth.app.dependency_overrides[auth_deps.get_db]()
    session.add(
        User(role=UserRole.admin, name="Admin", surname="PassaNorte",
             email="admin@passanorte.com", password_hash=hash_password("admin-s3cr3t-1"),
             country_of_origin="Brasil")
    )
    session.commit()

    resp = auth.post("/api/v1/session", json={"email": "admin@passanorte.com", "password": "admin-s3cr3t-1"})
    assert resp.status_code == 200, resp.text
    admin_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    assert auth.get("/api/v1/me", headers=admin_headers).json()["role"] == "admin"

    # 2. cria ponto turístico (RF11)
    resp = catalog.post(
        "/api/v1/tourist-spots",
        headers=admin_headers,
        json={"name": "Teatro Amazonas", "description": "Teatro histórico",
              "latitude": -3.4704, "longitude": -60.0238, "category_ids": []},
    )
    assert resp.status_code == 201, resp.text
    spot_id = resp.json()["id"]

    # 3. cronograma sem sobreposição + status (RF14/RF15)
    resp = catalog.put(
        f"/api/v1/tourist-spots/{spot_id}/schedule",
        headers=admin_headers,
        json={"schedule": [{"day_of_week": 1, "opens_at": "09:00", "closes_at": "17:00"}]},
    )
    assert resp.status_code == 200
    resp = catalog.put(
        f"/api/v1/tourist-spots/{spot_id}/schedule",
        headers=admin_headers,
        json={"schedule": [{"day_of_week": 1, "opens_at": "16:00", "closes_at": "18:00"}]},
    )
    assert resp.status_code == 422  # sobreposição recusada

    resp = catalog.patch(f"/api/v1/tourist-spots/{spot_id}/status",
                         headers=admin_headers, json={"status": "temporarily_closed"})
    assert resp.status_code == 200

    # 4. evento (RF16)
    resp = catalog.post(
        "/api/v1/events",
        headers=admin_headers,
        json={"tourist_spot_id": spot_id, "title": "Festival", "description": "d",
              "occurs_at": "2026-10-01T20:00:00", "ticket_price": 25.0},
    )
    assert resp.status_code == 201

    # 5. cria funcionário e verifica RBAC (RF03/RF04)
    resp = auth.post(
        "/api/v1/employees",
        headers=admin_headers,
        json={"name": "Fulano", "surname": "Beltrano", "email": "func@passanorte.com", "password": "s3cr3t!x"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "employee"

    resp = auth.post("/api/v1/session", json={"email": "func@passanorte.com", "password": "s3cr3t!x"})
    emp_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    assert auth.get("/api/v1/employees", headers=emp_headers).status_code == 403
    assert catalog.post(
        "/api/v1/tourist-spots",
        headers=emp_headers,
        json={"name": "X", "description": "Y", "latitude": -3.0, "longitude": -60.0, "category_ids": []},
    ).status_code == 403
    # turista: apenas /me (RF03) — catálogo público continua acessível
    assert catalog.get("/api/v1/tourist-spots").status_code == 200

    # 6. auditoria das ações admin (RNF19)
    from shared.audit_model import AuditLog

    actions = {log.action for log in session.query(AuditLog).all()}
    assert {"create_spot", "set_schedule", "set_status", "create_event", "create_employee"} <= actions
