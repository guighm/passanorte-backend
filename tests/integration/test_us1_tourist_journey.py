"""T022 [US1] Integração: jornada completa do turista (quickstart S1).

Cadastro → duplicidade recusada → login → interesses → catálogo.
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
def auth_and_catalog() -> tuple[TestClient, TestClient]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    auth_app = auth_app_factory()
    auth_app.dependency_overrides[auth_deps.get_db] = lambda: make_session_factory(engine)()
    catalog_app = catalog_app_factory()
    catalog_app.dependency_overrides[catalog_deps.get_db] = lambda: make_session_factory(engine)()
    return TestClient(auth_app), TestClient(catalog_app)


def test_us1_full_tourist_journey(auth_and_catalog):
    auth, catalog = auth_and_catalog

    # 1. cadastro único com CPF (RF22)
    resp = auth.post(
        "/api/v1/tourists",
        json={
            "name": "Ana",
            "surname": "Silva",
            "email": "ana@example.com",
            "password": "s3cr3t!x",
            "phone": "+55 92 99999-0000",
            "country_of_origin": "Brasil",
            "cpf": "123.456.789-00",
        },
    )
    assert resp.status_code == 201, resp.text

    # 2. duplicidade de documento recusada (FR-006)
    resp = auth.post(
        "/api/v1/tourists",
        json={
            "name": "Outra",
            "surname": "Pessoa",
            "email": "outra@example.com",
            "password": "s3cr3t!x",
            "phone": "+55 92 99999-1111",
            "country_of_origin": "Brasil",
            "cpf": "123.456.789-00",
        },
    )
    assert resp.status_code == 409

    # 3. login com email + senha (D-01)
    resp = auth.post("/api/v1/session", json={"email": "ana@example.com", "password": "s3cr3t!x"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 4. interesses persistidos (RF25)
    resp = auth.put("/api/v1/me/interests", json={"category_ids": ["cat-cultura"]}, headers=headers)
    assert resp.status_code == 200
    assert auth.get("/api/v1/me/interests", headers=headers).json()["category_ids"] == ["cat-cultura"]

    # 5. catálogo vivo: seed e listagem (RF26/RF27)
    resp = catalog.post(
        "/api/v1/internal/tourist-spots",
        json={
            "name": "Teatro Amazonas",
            "description": "Teatro histórico",
            "latitude": -3.4704,
            "longitude": -60.0238,
            "category_ids": ["cat-cultura"],
        },
    )
    assert resp.status_code == 201
    spot_id = resp.json()["id"]

    resp = catalog.get("/api/v1/tourist-spots", params={"category": "cat-cultura"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Teatro Amazonas"

    resp = catalog.get(f"/api/v1/tourist-spots/{spot_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "open"

    # 6. links externos (RF28)
    resp = catalog.get(f"/api/v1/tourist-spots/{spot_id}/external-links")
    assert "google.com/maps" in resp.json()["links"]["google_maps"]
