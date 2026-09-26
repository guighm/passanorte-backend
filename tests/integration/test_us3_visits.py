"""T038 [US3] Integração: fluxo de visitação (quickstart S3).

Turista marca visitação dentro/fora do raio, idempotência e propagação
tolerante a falhas (D-05) com catalog simulado.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from services.validation.app.core import deps as validation_deps  # noqa: E402
from services.validation.app.core import propagator as propagator_mod  # noqa: E402
from services.validation.app.main import create_test_app as validation_factory  # noqa: E402
from shared.security import create_access_token  # noqa: E402

SPOT = {
    "id": "spot-1",
    "name": "Teatro Amazonas",
    "latitude": -3.4704,
    "longitude": -60.0238,
    "tolerance_radius_m": 100,
    "status": "open",
    "category_ids": [],
}


@pytest.fixture
def app_and_db(db_session):
    app = validation_factory()
    app.dependency_overrides[validation_deps.get_db] = lambda: db_session
    app.dependency_overrides[validation_deps.get_catalog_snapshot] = lambda: (lambda spot_id: dict(SPOT, id=spot_id))
    return app


def test_us3_visit_flow_inside_and_outside_radius(app_and_db):
    app = app_and_db
    propagated: list[dict] = []

    def spy_propagator():
        return lambda fact: propagated.append(fact) or {"insights": True, "gamification": True}

    app.dependency_overrides[propagator_mod.get_propagator] = spy_propagator
    client = TestClient(app)
    token, _ = create_access_token("tourist-9", "tourist")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. visita fora do raio → rejected 422, não conta nem propaga (RF33)
    resp = client.post(
        "/api/v1/visits",
        headers=headers,
        json={"tourist_spot_id": "spot-1", "latitude": -3.4704, "longitude": -60.0100},
    )
    assert resp.status_code == 422
    assert resp.json()["status"] == "rejected"
    assert propagated == []

    # 2. visita dentro do raio → validada e propagada (RF31/RF34)
    resp = client.post(
        "/api/v1/visits",
        headers=headers,
        json={"tourist_spot_id": "spot-1", "latitude": -3.4704, "longitude": -60.0238},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "validated"
    assert len(propagated) == 1
    assert propagated[0]["user_id"] == "tourist-9"

    # 3. repetição do par (user, spot) → idempotente (FR-019), não repropaga
    resp = client.post(
        "/api/v1/visits",
        headers=headers,
        json={"tourist_spot_id": "spot-1", "latitude": -3.4704, "longitude": -60.0238},
    )
    assert resp.status_code == 200
    assert len(propagated) == 1

    # 4. listagem contém exatamente a visita validada
    resp = client.get("/api/v1/visits", headers=headers)
    assert resp.json()["total"] == 1
