"""T064 [US7] Integração: conversa de planejamento com conteúdo só do catálogo (S7).

RF38/RF39: roteiro contém apenas pontos/eventos indexados, com custo e
horários; fechados são sinalizados e fora do roteiro; LLM indisponível →
`assistant_unavailable` (503), nunca roteiro inventado.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")

from services.chatbot.app.core import deps as chatbot_deps  # noqa: E402
from services.chatbot.app.core.embeddings import _stub_embed  # noqa: E402
from services.chatbot.app.core.provider import StubProvider  # noqa: E402
from services.chatbot.app.main import create_test_app  # noqa: E402
from shared.security import create_access_token  # noqa: E402


@pytest.fixture
def client(db_session):
    app = create_test_app()
    app.dependency_overrides[chatbot_deps.get_db] = lambda: db_session
    app.dependency_overrides[chatbot_deps.get_embedder] = lambda: _stub_embed
    app.dependency_overrides[chatbot_deps.get_provider] = lambda: StubProvider()
    return TestClient(app)


def _headers(user_id="user-1"):
    token, _ = create_access_token(user_id, "tourist")
    return {"Authorization": f"Bearer {token}"}


def _index_catalog(client):
    """Índice com o conteúdo do catálogo — exatamente o que o catalog dispara (D-08)."""
    resp = client.post(
        "/api/v1/internal/index/refresh",
        json={"items": [
            {
                "source_type": "tourist_spot",
                "source_id": "s-teatro",
                "title": "Teatro Amazonas",
                "description": "Teatro histórico em Manaus, ingresso pago",
                "status": "open",
                "latitude": -3.47,
                "longitude": -60.02,
                "ticket_price": 50.0,
                "schedule_text": "seg-dom 09:00-17:00",
            },
            {
                "source_type": "tourist_spot",
                "source_id": "s-museu",
                "title": "Museu Amazônico",
                "description": "Museu com história da Amazônia",
                "status": "open",
                "latitude": -3.48,
                "longitude": -60.03,
                "ticket_price": 20.0,
                "schedule_text": "ter-dom 10:00-18:00",
            },
            {
                "source_type": "tourist_spot",
                "source_id": "s-rex",
                "title": "Cine Rex",
                "description": "Cinema antigo fechado para obras",
                "status": "temporarily_closed",
                "latitude": -3.49,
                "longitude": -60.01,
            },
        ]},
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["indexed"] == 3


def test_planning_conversation_uses_only_catalog_content(client):
    conversation_id = client.post("/api/v1/conversations", headers=_headers()).json()["id"]
    _index_catalog(client)

    resp = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=_headers(),
        json={"content": "roteiro com teatro e museu, quero horários e ingressos"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    refs = {r["source_id"] for r in body["references"]}
    assert {"s-teatro", "s-museu"} <= refs  # só conteúdo indexado entra no roteiro (SC-009)
    assert "s-rex" not in refs  # fechado fora do roteiro (RF38)
    assert body["estimated_cost"] == 70.0  # custo total dos ingressos (RF39)
    assert "09:00-17:00" in body["reply"]  # horários relevantes na resposta (RF39)
    assert "ATENÇÃO" not in body["reply"] or "s-rex" not in refs


def test_unavailable_llm_returns_assistant_unavailable(db_session):
    app = create_test_app()
    app.dependency_overrides[chatbot_deps.get_db] = lambda: db_session
    app.dependency_overrides[chatbot_deps.get_embedder] = lambda: _stub_embed

    from services.chatbot.app.core.provider import ProviderUnavailable

    class BrokenProvider(StubProvider):
        name = "broken"

        def generate(self, *, question: str, context: list[dict]) -> str:
            raise ProviderUnavailable("simulado")

    app.dependency_overrides[chatbot_deps.get_provider] = lambda: BrokenProvider()
    client = TestClient(app)

    conversation_id = client.post("/api/v1/conversations", headers=_headers()).json()["id"]
    resp = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=_headers(),
        json={"content": "roteiro"},
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "assistant_unavailable"
