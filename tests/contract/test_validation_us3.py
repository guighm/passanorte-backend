"""T033 [US3] Testes de contrato dos endpoints de visitação (contracts/validation.md).

POST /visits (validated/rejected/422 gps_unavailable), GET /visits,
GET /visits/{spot_id}, idempotência por par (user, spot) — RF31–RF33.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from services.validation.app.core import deps as validation_deps  # noqa: E402
from services.validation.app.main import create_test_app as validation_factory  # noqa: E402
from shared.security import create_access_token  # noqa: E402

SPOT = {
    "id": "11111111-1111-1111-1111-111111111111",
    "name": "Teatro Amazonas",
    "latitude": -3.4704,
    "longitude": -60.0238,
    "tolerance_radius_m": 100,
    "status": "open",
    "category_ids": [],
}


@pytest.fixture
def client(db_session):
    app = validation_factory()
    app.dependency_overrides[validation_deps.get_db] = lambda: db_session
    # snapshot do catalog fixo (serviço externo simulado, D-05)
    app.dependency_overrides[validation_deps.get_catalog_snapshot] = lambda: (lambda spot_id: dict(SPOT, id=spot_id))
    return TestClient(app)


def tourist_headers() -> dict:
    token, _ = create_access_token("user-1", "tourist")
    return {"Authorization": f"Bearer {token}"}


def test_post_visit_within_radius_is_validated(client, db_session):
    resp = client.post(
        "/api/v1/visits",
        headers=tourist_headers(),
        json={"tourist_spot_id": SPOT["id"], "latitude": -3.4704, "longitude": -60.0235},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "validated"
    assert body["distance_m"] <= body["tolerance_m"]


def test_post_visit_outside_radius_is_rejected(client, db_session):
    resp = client.post(
        "/api/v1/visits",
        headers=tourist_headers(),
        json={"tourist_spot_id": SPOT["id"], "latitude": -3.4704, "longitude": -60.0100},
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["distance_m"] > body["tolerance_m"]
    # rejeitada não conta como visita (RF33)
    assert client.get("/api/v1/visits", headers=tourist_headers()).json()["items"] == []


def test_post_visit_missing_gps_is_422_gps_unavailable(client):
    resp = client.post(
        "/api/v1/visits",
        headers=tourist_headers(),
        json={"tourist_spot_id": SPOT["id"]},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "gps_unavailable"


def test_post_visit_unknown_spot_is_404(client):
    from shared.errors import ApiError

    client.app.dependency_overrides[validation_deps.get_catalog_snapshot] = (
        lambda: (lambda spot_id: (_ for _ in ()).throw(ApiError("not_found", "não encontrado", 404)))
    )
    resp = client.post(
        "/api/v1/visits",
        headers=tourist_headers(),
        json={"tourist_spot_id": "999", "latitude": -3.4704, "longitude": -60.0238},
    )
    assert resp.status_code == 404


def test_post_visit_is_idempotent(client, db_session):
    payload = {"tourist_spot_id": SPOT["id"], "latitude": -3.4704, "longitude": -60.0238}
    first = client.post("/api/v1/visits", headers=tourist_headers(), json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/visits", headers=tourist_headers(), json=payload)
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]


def test_get_visits_lists_validated(client):
    client.post(
        "/api/v1/visits",
        headers=tourist_headers(),
        json={"tourist_spot_id": SPOT["id"], "latitude": -3.4704, "longitude": -60.0238},
    )
    resp = client.get("/api/v1/visits", headers=tourist_headers())
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["tourist_spot_id"] == SPOT["id"]
    assert body["items"][0]["status"] == "validated"


def test_get_visit_by_spot(client):
    client.post(
        "/api/v1/visits",
        headers=tourist_headers(),
        json={"tourist_spot_id": SPOT["id"], "latitude": -3.4704, "longitude": -60.0238},
    )
    resp = client.get(f"/api/v1/visits/{SPOT['id']}", headers=tourist_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "validated"
    # ponto sem visita → 404
    resp = client.get("/api/v1/visits/other-spot", headers=tourist_headers())
    assert resp.status_code == 404


def test_visits_require_authentication(client):
    payload = {"tourist_spot_id": SPOT["id"], "latitude": 0, "longitude": 0}
    assert client.post("/api/v1/visits", json=payload).status_code == 401
