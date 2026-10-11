"""Disparo de notificações — evento no RabbitMQ, entrega tolerante a falhas (D-05, RF37).

Mantém a assinatura do antigo HTTP fire-and-forget: os call sites (gamification
e catalog) não mudam; as falhas de publicação são logadas, nunca levantadas.
"""

from __future__ import annotations

import logging

from shared import messaging

logger = logging.getLogger("notifications_client")


def dispatch(
    *,
    kind: str,
    source_id: str,
    title: str,
    body: str | None = None,
    category_ids: list[str] | None = None,
    user_ids: list[str] | None = None,
    payload: dict | None = None,
) -> None:
    """Publica um evento `notification.dispatch` por alvo (idempotente no consumer)."""
    for category_id in category_ids or [None]:
        message: dict = {
            "kind": kind,
            "source_id": source_id,
            "title": title,
            "body": body,
            "payload": payload,
        }
        if category_id is not None:
            message["category_id"] = category_id
        if user_ids:
            message["user_ids"] = user_ids
        messaging.publish("notification.dispatch", message)
