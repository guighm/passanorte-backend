"""Gatilho de rebuild do índice RAG do chatbot — fire-and-forget (D-05)."""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("chatbot_client")


def refresh_index(items: list[dict]) -> None:
    """Reenvia itens alterados do catálogo ao chatbot (idempotente no alvo)."""
    base_url = os.environ.get("CHATBOT_SERVICE_URL", "http://localhost:8007")
    try:
        httpx.post(f"{base_url}/api/v1/internal/index/refresh", json={"items": items}, timeout=10.0)
    except httpx.HTTPError:
        pass  # tolerante a falhas: o cadastro não bloqueia (D-05)
