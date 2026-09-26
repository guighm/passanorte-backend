"""Disparo de notificações — fire-and-forget, falha é tolerada (D-05, RF37)."""

from __future__ import annotations

import logging
import os

import httpx

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
    """Dispara notificações no serviço notifications (idempotente no alvo)."""
    base_url = os.environ.get("NOTIFICATIONS_SERVICE_URL", "http://localhost:8006")
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
        try:
            httpx.post(f"{base_url}/api/v1/internal/dispatch", json=message, timeout=5.0)
        except httpx.HTTPError:
            pass  # tolerante a falhas: o cadastro não bloqueia (D-05)
