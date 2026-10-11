"""Propagação do fato de visita pelo barramento (D-05, RF34) — T037.

Publica o evento `visit.validated`; a entrega tolerante a falhas (durable,
requeue/DLQ) é responsabilidade do broker — a visita permanece válida
independentemente do estado dos consumidores.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from shared import messaging
from shared.logging import log_event

logger = logging.getLogger("validation")


def get_propagator() -> Callable[[dict], dict]:
    """Propagador substituível em testes (fire-and-forget via broker, D-05)."""

    def propagate(fact: dict) -> dict:
        messaging.publish("visit.validated", fact)
        log_event(logger, "visit_propagated", user_id=fact.get("user_id"))
        return {"published": True}

    return propagate
