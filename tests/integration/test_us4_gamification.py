"""T047 [US4] Integração: ciclo completo de gamificação (quickstart S4).

Inscrição → visitas validadas (validation) → progresso derivado (D-13) →
conclusão com insígnia + código → resgate transacional pelo funcionário.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from services.gamification.app.core import deps as gam_deps  # noqa: E402
from services.gamification.app.main import create_test_app as gam_factory  # noqa: E402
from services.validation.app.core import deps as val_deps  # noqa: E402
from services.validation.app.main import create_test_app as val_factory  # noqa: E402
from shared.security import create_access_token, decode_token  # noqa: E402

SPOTS = ["spot-1", "spot-2"]


@pytest.fixture
def services(db_session):
    """validation e gamification compartilham o mesmo banco em memória."""
    val_app = val_factory()
    val_app.dependency_overrides[val_deps.get_db] = lambda: db_session
    val_app.dependency_overrides[val_deps.get_catalog_snapshot] = lambda: (
        lambda spot_id: {"id": spot_id, "name": "X", "latitude": -3.4704, "longitude": -60.0238,
                         "tolerance_radius_m": 100, "status": "open", "category_ids": []}
    )
    gam_app = gam_factory()
    gam_app.dependency_overrides[gam_deps.get_db] = lambda: db_session

    def fetch_validated(auth_header: str) -> list[str]:
        # simula a chamada REST ao validation lendo o banco compartilhado (D-13)
        from services.validation.app.models.visit import Visit

        claims = decode_token(auth_header.removeprefix("Bearer "), expected_type="access")
        rows = db_session.query(Visit).filter(Visit.user_id == claims["sub"], Visit.status == "validated").all()
        return [row.tourist_spot_id for row in rows]

    gam_app.dependency_overrides[gam_deps.get_validated_visits] = lambda: fetch_validated
    return TestClient(val_app), TestClient(gam_app)


def _headers(role: str, user_id: str) -> dict:
    token, _ = create_access_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


def test_us4_full_gamification_cycle(services):
    validation, gamification = services
    admin = _headers("admin", "admin-1")
    tourist = _headers("tourist", "user-7")
    employee = _headers("employee", "emp-2")

    # 1. admin cadastra rota com brinde e estoque (RF18)
    resp = gamification.post(
        "/api/v1/routes",
        headers=admin,
        json={"name": "Rota Histórica", "description": "d", "points": SPOTS,
              "prize": {"name": "Camisa", "description": "camisa"}},
    )
    assert resp.status_code == 201, resp.text
    route_id = resp.json()["id"]
    prize_id = resp.json()["prize"]["id"]
    resp = gamification.patch(f"/api/v1/prizes/{prize_id}/stock", headers=admin, json={"stock_quantity": 1})
    assert resp.status_code == 200

    # 2. turista se inscreve sem visitas → 0% (RF29)
    resp = gamification.post(f"/api/v1/routes/{route_id}/enrollments", headers=tourist)
    assert resp.status_code == 201, resp.text
    assert resp.json()["percent"] == 0.0
    assert resp.json()["status"] == "in_progress"

    # 3. primeira visitação validada → 50% (RF30)
    resp = validation.post(
        "/api/v1/visits", headers=tourist,
        json={"tourist_spot_id": "spot-1", "latitude": -3.4704, "longitude": -60.0238},
    )
    assert resp.status_code == 201, resp.text
    resp = gamification.get(f"/api/v1/enrollments/{route_id}", headers=tourist)
    assert resp.json()["percent"] == 50.0
    assert resp.json()["pending"] == ["spot-2"]

    # 4. segunda visitação → 100% na próxima consulta → conclusão automática
    resp = validation.post(
        "/api/v1/visits", headers=tourist,
        json={"tourist_spot_id": "spot-2", "latitude": -3.4704, "longitude": -60.0238},
    )
    assert resp.status_code == 201
    resp = gamification.get(f"/api/v1/enrollments/{route_id}", headers=tourist)
    body = resp.json()
    assert body["percent"] == 100.0
    assert body["status"] == "completed"
    redeem_code = body["redeem_code"]
    assert redeem_code

    # insígnia e código visíveis ao turista (RF35/RF36)
    assert len(gamification.get("/api/v1/badges", headers=tourist).json()["items"]) == 1
    assert len(gamification.get("/api/v1/redeem-codes", headers=tourist).json()["items"]) == 1

    # 5. funcionário resgata o código → estoque baixa para 0 (RF21)
    resp = gamification.post("/api/v1/redemptions", headers=employee, json={"code": redeem_code})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "redeemed"

    # reuso do mesmo código → 409 (FR-027)
    resp = gamification.post("/api/v1/redemptions", headers=employee, json={"code": redeem_code})
    assert resp.status_code == 409
