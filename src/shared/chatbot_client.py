"""Gatilho de rebuild do índice RAG do chatbot — evento no RabbitMQ (D-05).

Mantém a assinatura do antigo HTTP fire-and-forget: os call sites (catalog)
não mudam; o consumer no chatbot re-embeda de forma idempotente.
"""

from __future__ import annotations

import logging

from shared import messaging

logger = logging.getLogger("chatbot_client")


def refresh_index(items: list[dict]) -> None:
    """Publica um evento `catalog.index.refresh` (idempotente no consumer)."""
    messaging.publish("catalog.index.refresh", {"items": items})
