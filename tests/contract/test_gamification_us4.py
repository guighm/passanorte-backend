"""T040 [US4] Testes de contrato da gamificação (contracts/gamification.md).

Rotas/brindes (RF18–RF20), inscrição e progresso derivado (RF29/RF30, D-13),
insígnia e código (RF35/RF36), resgate pelo funcionário (RF21).
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from services.gamification.app.core import deps as gam_deps  # noqa: E402
from services.gamification.app.main import create_test_app as gam_factory  # noqa: E402
from shared.security import create_access_token  # noqa: E402

SPOTS = ["spot-a", "spot-b", "spot-c"]


@pytest.fixture
def client(db_session):
    app = gam_factory()
    app.dependency_overrides[gam_deps.get_db] = lambda: db_session
    # validation simulado: user-1 visitou spot-a e spot-b (D-13)
    app.dependency_overrides[gam_deps.get_validated_visits] = lambda: (lambda headers: ["spot-a", "spot-b"])
    return TestClient(app)


def headers_for(role: str, user_id: str) -> dict:
    token, _ = create_access_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


def admin_headers() -> dict:
    return headers_for("admin", "admin-1")


def tourist_headers() -> dict:
    return headers_for("tourist", "user-1")


def employee_headers() -> dict:
    return headers_for("employee", "emp-1")


def create_route(client, points=SPOTS, stock=5) -> dict:
    resp = client.post(
        "/api/v1/routes",
        headers=admin_headers(),
        json={"name": "Centro Histórico", "description": "Rota clássica",
              "points": points, "prize": {"name": "Camisa", "description": "Camisa do projeto"}},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    if stock != 0:
        resp = client.patch(
            f"/api/v1/prizes/{body['prize']['id']}/stock", headers=admin_headers(), json={"stock_quantity": stock}
        )
        assert resp.status_code == 200
    return body


# --- Rotas e brindes (RF18–RF20) ----------------------------------------------

def test_admin_creates_route_and_public_listing(client):
    body = create_route(client)
    assert body["points"] == SPOTS

    resp = client.get("/api/v1/routes")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["name"] == "Centro Histórico"


def test_route_creation_requires_admin(client):
    resp = client.post("/api/v1/routes", headers=tourist_headers(),
                       json={"name": "X", "description": "y", "points": [], "prize": {"name": "p"}})
    assert resp.status_code == 403


def test_admin_lists_and_updates_prize_stock(client):
    create_route(client)
    resp = client.get("/api/v1/prizes", headers=admin_headers())
    prizes = resp.json()["items"]
    assert len(prizes) == 1
    prize_id = prizes[0]["id"]

    resp = client.patch(f"/api/v1/prizes/{prize_id}/stock", headers=admin_headers(), json={"stock_quantity": 3})
    assert resp.status_code == 200
    assert resp.json()["stock_quantity"] == 3


def test_prize_stock_cannot_go_negative(client):
    create_route(client, stock=0)
    prize_id = client.get("/api/v1/prizes", headers=admin_headers()).json()["items"][0]["id"]
    resp = client.patch(f"/api/v1/prizes/{prize_id}/stock", headers=admin_headers(), json={"stock_quantity": -1})
    assert resp.status_code == 422


def test_admin_can_remove_route(client):
    body = create_route(client)
    resp = client.delete(f"/api/v1/routes/{body['id']}", headers=admin_headers())
    assert resp.status_code == 204
    assert client.get("/api/v1/routes").json()["total"] == 0


# --- Inscrição e progresso derivado (RF29/RF30, D-13) --------------------------

def test_enrollment_derives_retroactive_progress(client):
    route = create_route(client)
    resp = client.post(f"/api/v1/routes/{route['id']}/enrollments", headers=tourist_headers())
    assert resp.status_code == 201, resp.text
    # D-13: visitas anteriores à inscrição contam retroativamente (2 de 3)
    assert resp.json()["visited"] == ["spot-a", "spot-b"]
    assert resp.json()["pending"] == ["spot-c"]
    assert resp.json()["percent"] == 66.67


def test_enrollment_completes_when_all_points_visited(client):
    # validation simulado com rota completa
    client.app.dependency_overrides[gam_deps.get_validated_visits] = lambda: (lambda headers: list(SPOTS))
    route = create_route(client)
    resp = client.post(f"/api/v1/routes/{route['id']}/enrollments", headers=tourist_headers())
    assert resp.status_code == 201
    assert resp.json()["status"] == "completed"
    assert resp.json()["percent"] == 100.0
    # badge + código emitidos automaticamente (RF35/RF36)
    badges = client.get("/api/v1/badges", headers=tourist_headers()).json()["items"]
    assert len(badges) == 1
    codes = client.get("/api/v1/redeem-codes", headers=tourist_headers()).json()["items"]
    assert len(codes) == 1
    assert codes[0]["status"] == "issued"


def test_double_enrollment_is_refused(client):
    route = create_route(client)
    first = client.post(f"/api/v1/routes/{route['id']}/enrollments", headers=tourist_headers())
    assert first.status_code == 201
    second = client.post(f"/api/v1/routes/{route['id']}/enrollments", headers=tourist_headers())
    assert second.status_code == 409


def test_get_single_enrollment_progress(client):
    route = create_route(client)
    client.post(f"/api/v1/routes/{route['id']}/enrollments", headers=tourist_headers())
    resp = client.get(f"/api/v1/enrollments/{route['id']}", headers=tourist_headers())
    assert resp.status_code == 200
    assert resp.json()["percent"] == 66.67


# --- Resgate pelo funcionário (RF21) -------------------------------------------

def test_redemption_flow(client, db_session):
    from services.gamification.app.models.enrollment import RedeemCode
    from services.gamification.app.models.route import Prize

    route = create_route(client, points=["spot-a"], stock=2)
    prize_id = db_session.query(Prize).first().id
    code = "BEM-VINDO-123"
    db_session.add(RedeemCode(code=code, user_id="user-1", route_id=route["id"], prize_id=prize_id))
    db_session.commit()

    ok = client.post("/api/v1/redemptions", headers=employee_headers(), json={"code": code})
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "redeemed"

    reused = client.post("/api/v1/redemptions", headers=employee_headers(), json={"code": code})
    assert reused.status_code == 409

    unknown = client.post("/api/v1/redemptions", headers=employee_headers(), json={"code": "INEXISTENTE"})
    assert unknown.status_code == 404

    # estoque não pode ficar negativo: restava 1, foi baixado para 0
    db_session.expire_all()
    assert db_session.query(Prize).first().stock_quantity == 1


def test_redemption_requires_employee_role(client):
    resp = client.post("/api/v1/redemptions", headers=tourist_headers(), json={"code": "X"})
    assert resp.status_code == 403
