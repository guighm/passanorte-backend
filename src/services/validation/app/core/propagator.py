"""Propagação tolerante a falhas do fato de visita (D-05, RF34) — T037.

Publica o VisitFact no insights e avisa o gamification; falhas são
toleradas com retry idempotente — a visita permanece válida.
"""

from __future__ import annotations

import os
from collections.abc import Callable

import httpx

from shared.logging import log_event

logger_name = "validation"

MAX_ATTEMPTS = 2


def _post_with_retry(url: str, payload: dict) -> bool:
    for _ in range(MAX_ATTEMPTS):
        try:
            resp = httpx.post(url, json=payload, timeout=5.0)
            if resp.status_code < 500:
                return resp.status_code < 400
        except httpx.HTTPError:
            pass  # retry idempotente: o alvo deduplica por (user, spot, occurred_at)
    return False


def get_propagator() -> Callable[[dict], dict]:
    """Propagador substituível em testes (fire-and-forget, D-05)."""
    insights_url = os.environ.get("INSIGHTS_SERVICE_URL", "http://localhost:8005")
    gamification_url = os.environ.get("GAMIFICATION_SERVICE_URL", "http://localhost:8004")

    def propagate(fact: dict) -> dict:
        result = {
            "insights": _post_with_retry(f"{insights_url}/api/v1/internal/visit-facts", fact),
            "gamification": _post_with_retry(f"{gamification_url}/api/v1/internal/visit-notification", fact),
        }
        log_event(
            __import__("logging").getLogger(logger_name),
            "visit_propagated",
            user_id=fact.get("user_id"),
            insights=result["insights"],
            gamification=result["gamification"],
        )
        return result

    return propagate
