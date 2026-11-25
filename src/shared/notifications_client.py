"""Disparo de notificações — evento no RabbitMQ, entrega tolerante a falhas (D-05, RF37).

Mantém a assinatura do antigo HTTP fire-and-forget: os call sites (gamification
e catalog) não mudam; as falhas de publicação são logadas, nunca levantadas.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

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
    db: Session | None = None,
) -> None:
    """Publica um evento `notification.dispatch` por alvo (idempotente no consumer)."""
    targets: list[str | None] = list(category_ids) if category_ids else [None]
    for category_id in targets:
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
        messaging.enqueue(db, "notification.dispatch", message)
