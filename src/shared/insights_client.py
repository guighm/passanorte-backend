"""Registro de acesso no insights — evento no RabbitMQ (D-05, RF07).

Mantém a assinatura do antigo HTTP fire-and-forget; falha de publicação é
logada, nunca levantada.
"""

from __future__ import annotations

import logging

from shared import messaging

logger = logging.getLogger("insights_client")


def notify_access(user_id: str, client: str | None = None) -> None:
    messaging.publish("access.registered", {"user_id": user_id, "client": client})
