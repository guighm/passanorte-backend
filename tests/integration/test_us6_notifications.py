"""T057 [US6] Integração: gatilhos de dispatch (quickstart S6).

Catalog cria ponto/evento → inscritos na categoria recebem notificação;
gamification conclui rota → turista recebe código por notificação.
"""

from __future__ import annotations

import os

import httpx
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from services.auth.app.core import deps as auth_deps  # noqa: E402
from services.auth.app.main import create_test_app as auth_factory  # noqa: E402
from services.catalog.app.core import deps as catalog_deps  # noqa: E402
from services.catalog.app.main import create_test_app as catalog_factory  # noqa: E402
from services.notifications.app.core import deps as notif_deps  # noqa: E402
from services.notifications.app.main import create_test_app as notif_factory  # noqa: E402
from shared.security import create_access_token  # noqa: E402


@pytest.fixture
def services(db_session, monkeypatch):
    apps = {}
    for name, factory, deps_mod in [
        ("auth", auth_factory, auth_deps),
        ("catalog", catalog_factory, catalog_deps),
        ("notifications", notif_factory, notif_deps),
    ]:
        app = factory()
        app.dependency_overrides[deps_mod.get_db] = lambda: db_session
        apps[name] = TestClient(app)

    # roteia chamadas httpx de dispatch ao TestClient do notifications (D-05)
    notif_client = apps["notifications"]

    def fake_post(url, json=None, timeout=None, **kwargs):
        path = "/" + url.split("://", 1)[1].split("/", 1)[1]
        return notif_client.post(path, json=json)

    monkeypatch.setattr(httpx, "post", fake_post)

    def auth_headers(user_id, role="tourist"):
        token, _ = create_access_token(user_id, role)
        return {"Authorization": f"Bearer {token}"}

    return apps, auth_headers


def test_us6_notification_flow(services):
    apps, auth_headers = services
    catalog, notif = apps["catalog"], apps["notifications"]
    admin = auth_headers("admin-1", "admin")

    # 1. turistas se inscrevem em interesses (RF37)
    notif.put("/api/v1/subscriptions", json={"category_ids": ["cat-cultura"]},
              headers=auth_headers("user-1"))
    notif.put("/api/v1/subscriptions", json={"category_ids": ["cat-natureza"]},
              headers=auth_headers("user-2"))

    # 2. catalog cadastra ponto na categoria → inscrito recebe, não-inscrito não (SC-008)
    resp = catalog.post(
        "/api/v1/tourist-spots",
        headers=admin,
        json={"name": "Teatro Amazonas", "description": "Teatro histórico", "latitude": -3.4704,
              "longitude": -60.0238, "category_ids": ["cat-cultura"]},
    )
    assert resp.status_code == 201, resp.text
    spot_id = resp.json()["id"]

    inbox_1 = notif.get("/api/v1/notifications", headers=auth_headers("user-1")).json()["items"]
    assert len(inbox_1) == 1
    assert inbox_1[0]["kind"] == "new_spot"
    assert notif.get("/api/v1/notifications", headers=auth_headers("user-2")).json()["items"] == []

    # 3. catalog cadastra evento no ponto → nova notificação (RF37)
    resp = catalog.post(
        "/api/v1/events",
        headers=admin,
        json={"tourist_spot_id": spot_id, "title": "Festival", "description": "d",
              "occurs_at": "2026-10-01T20:00:00", "ticket_price": 25.0},
    )
    assert resp.status_code == 201, resp.text
    inbox_1 = notif.get("/api/v1/notifications", headers=auth_headers("user-1")).json()["items"]
    assert len(inbox_1) == 2
    assert inbox_1[0]["kind"] == "new_event"  # ordenado por created_at desc

    # 4. marca como lida (D-06)
    resp = notif.patch(f"/api/v1/notifications/{inbox_1[0]['id']}/read", headers=auth_headers("user-1"))
    assert resp.status_code == 200
    assert resp.json()["read_at"] is not None


def test_gamification_completion_notifies_tourist(db_session, monkeypatch):
    from services.gamification.app.core import completion as completion_mod
    from services.notifications.app.core import deps as notif_deps

    notif_app = notif_factory()
    notif_app.dependency_overrides[notif_deps.get_db] = lambda: db_session
    notif = TestClient(notif_app)

    def fake_post(url, json=None, timeout=None, **kwargs):
        path = "/" + url.split("://", 1)[1].split("/", 1)[1]
        return notif.post(path, json=json)

    monkeypatch.setattr(httpx, "post", fake_post)

    from services.gamification.app.models.route import Prize

    prize = Prize(name="Camisa", description="d", stock_quantity=1)
    db_session.add(prize)
    db_session.flush()

    completion_mod.complete_route(db_session, user_id="user-1", route_id="r-1", prize_id=prize.id)

    token, _ = create_access_token("user-1", "tourist")
    inbox = notif.get(
        "/api/v1/notifications", headers={"Authorization": f"Bearer {token}"}
    ).json()["items"]
    assert len(inbox) == 1
    assert inbox[0]["kind"] == "new_route"
    assert "redeem_code" in inbox[0]["payload"]
