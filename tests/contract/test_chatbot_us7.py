"""T059 [US7] Testes de contrato dos endpoints do chatbot (RF38/RF39, D-08)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")

from services.chatbot.app.core import deps as chatbot_deps  # noqa: E402
from services.chatbot.app.core.embeddings import _stub_embed  # noqa: E402
from services.chatbot.app.main import create_test_app  # noqa: E402
from shared.security import create_access_token  # noqa: E402


@pytest.fixture
def client(db_session):
    app = create_test_app()
    app.dependency_overrides[chatbot_deps.get_db] = lambda: db_session
    app.dependency_overrides[chatbot_deps.get_embedder] = lambda: _stub_embed
    return TestClient(app)


def tourist_headers(user_id="user-1"):
    token, _ = create_access_token(user_id, "tourist")
    return {"Authorization": f"Bearer {token}"}


def test_conversations_require_tourist_jwt(client):
    assert client.post("/api/v1/conversations").status_code == 401
    token, _ = create_access_token("admin-1", "admin")
    resp = client.post("/api/v1/conversations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403  # admin não conversa com o assistente


def test_conversation_lifecycle_and_message(client, db_session):
    resp = client.post("/api/v1/conversations", headers=tourist_headers())
    assert resp.status_code == 201, resp.text
    conversation_id = resp.json()["id"]

    # índice com conteúdo do catálogo (como o catalog enviaria via /internal/index/refresh)
    resp = client.post(
        "/api/v1/internal/index/refresh",
        json={"items": [
            {
                "source_type": "tourist_spot",
                "source_id": "s-1",
                "title": "Teatro Amazonas",
                "description": "Teatro histórico, ingresso R$ 50, abre 09h-17h",
                "status": "open",
                "latitude": -3.47,
                "longitude": -60.02,
                "ticket_price": 50.0,
                "schedule_text": "seg-dom 09:00-17:00",
            },
            {
                "source_type": "tourist_spot",
                "source_id": "s-closed",
                "title": "Cine Rex",
                "description": "Cinema antigo fechado",
                "status": "permanently_closed",
                "latitude": -3.48,
                "longitude": -60.01,
            },
        ]},
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["indexed"] == 2

    resp = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=tourist_headers(),
        json={"content": "roteiro com teatro histórico e ingresso barato"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reply"], "resposta do assistente não pode ser vazia"
    refs = {r["source_id"] for r in body["references"]}
    assert "s-1" in refs  # conteúdo recuperado entra no roteiro (SC-009)
    assert "s-closed" not in refs  # fechado não é opção de roteiro (RF38)
    assert body["estimated_cost"] == 50.0

    # histórico persistido (D-06 de auditoria de respostas)
    resp = client.get(f"/api/v1/conversations/{conversation_id}", headers=tourist_headers())
    assert resp.status_code == 200, resp.text
    messages = resp.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]

    # mensagem em conversa de outro usuário não existe para este (404)
    resp = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=tourist_headers("user-2"),
        json={"content": "oi"},
    )
    assert resp.status_code == 404


def test_index_refresh_is_idempotent(client):
    payload = {"items": [{
        "source_type": "event",
        "source_id": "e-1",
        "title": "Festival",
        "description": "evento no Teatro",
        "status": "open",
        "ticket_price": 10.0,
    }]}
    assert client.post("/api/v1/internal/index/refresh", json=payload).json()["indexed"] == 1
    assert client.post("/api/v1/internal/index/refresh", json=payload).json()["indexed"] == 1
