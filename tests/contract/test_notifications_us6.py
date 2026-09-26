"""T053 [US6] Testes de contrato das notificações (contracts/notifications.md, RF37, D-06)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from services.notifications.app.core import deps as notif_deps  # noqa: E402
from services.notifications.app.main import create_test_app as notifications_factory  # noqa: E402
from shared.security import create_access_token  # noqa: E402


def headers_for(user_id: str) -> dict:
    token, _ = create_access_token(user_id, "tourist")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(db_session):
    app = notifications_factory()
    app.dependency_overrides[notif_deps.get_db] = lambda: db_session
    return TestClient(app)


def test_subscription_replaces_and_lists(client):
    headers = headers_for("user-1")

    resp = client.put("/api/v1/subscriptions", json={"category_ids": ["cat-cultura", "cat-natureza"]}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert client.get("/api/v1/subscriptions", headers=headers).json()["category_ids"] == [
        "cat-cultura",
        "cat-natureza",
    ]

    # substitui inscrições (PUT, RF37)
    client.put("/api/v1/subscriptions", json={"category_ids": ["cat-gastronomia"]}, headers=headers)
    assert client.get("/api/v1/subscriptions", headers=headers).json()["category_ids"] == ["cat-gastronomia"]


def test_dispatch_notifies_only_subscribers(client):
    client.put("/api/v1/subscriptions", json={"category_ids": ["cat-cultura"]}, headers=headers_for("user-1"))
    client.put("/api/v1/subscriptions", json={"category_ids": ["cat-natureza"]}, headers=headers_for("user-2"))

    dispatch = {
        "kind": "new_event",
        "source_id": "evt-1",
        "category_id": "cat-cultura",
        "title": "Festival de Verão",
        "body": "Novo evento no Teatro Amazonas",
        "payload": {"event_id": "evt-1"},
    }
    resp = client.post("/api/v1/internal/dispatch", json=dispatch)
    assert resp.status_code == 202, resp.text
    assert resp.json()["notified"] == 1  # SC-008: só o inscrito recebe

    inbox = client.get("/api/v1/notifications", headers=headers_for("user-1")).json()["items"]
    assert len(inbox) == 1
    assert inbox[0]["title"] == "Festival de Verão"
    assert inbox[0]["kind"] == "new_event"
    assert client.get("/api/v1/notifications", headers=headers_for("user-2")).json()["items"] == []


def test_dispatch_without_subscribers_is_noop(client):
    resp = client.post(
        "/api/v1/internal/dispatch",
        json={"kind": "new_spot", "source_id": "s1", "category_id": "cat-x", "title": "T", "body": "B"},
    )
    assert resp.status_code == 202
    assert resp.json()["notified"] == 0


def test_dispatch_retry_is_idempotent(client):
    client.put("/api/v1/subscriptions", json={"category_ids": ["cat-cultura"]}, headers=headers_for("user-1"))

    dispatch = {"kind": "new_event", "source_id": "evt-9", "category_id": "cat-cultura", "title": "T", "body": "B"}
    first = client.post("/api/v1/internal/dispatch", json=dispatch)
    second = client.post("/api/v1/internal/dispatch", json=dispatch)
    assert first.json()["notified"] == 1
    assert second.json()["notified"] == 0  # idempotente por (kind, source_id) (D-05)


def test_dispatch_direct_user_notification(client):
    """user_ids diretos: conclusão de rota no gamification (RF35) sem categoria."""
    resp = client.post(
        "/api/v1/internal/dispatch",
        json={"kind": "new_route", "source_id": "r-1", "user_ids": ["user-9"],
              "title": "Rota concluída", "body": "Seu código: PN-XYZ"},
    )
    assert resp.status_code == 202
    assert resp.json()["notified"] == 1
    inbox = client.get("/api/v1/notifications", headers=headers_for("user-9")).json()["items"]
    assert len(inbox) == 1


def test_mark_notification_read(client):
    client.put("/api/v1/subscriptions", json={"category_ids": ["cat-cultura"]}, headers=headers_for("user-1"))
    client.post(
        "/api/v1/internal/dispatch",
        json={"kind": "new_route", "source_id": "r-1", "category_id": "cat-cultura",
              "title": "Nova rota", "body": "B"},
    )
    notif_id = client.get("/api/v1/notifications", headers=headers_for("user-1")).json()["items"][0]["id"]

    resp = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers_for("user-1"))
    assert resp.status_code == 200
    assert resp.json()["read_at"] is not None

    # outro usuário não pode marcar a notificação alheia (D-06)
    resp = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers_for("intruder"))
    assert resp.status_code == 404
