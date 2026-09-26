"""Registro de acesso no insights — fire-and-forget, falha é tolerada (D-05, RF07)."""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("insights_client")


def notify_access(user_id: str, client: str | None = None) -> None:
    base_url = os.environ.get("INSIGHTS_SERVICE_URL", "http://localhost:8005")
    try:
        httpx.post(f"{base_url}/api/v1/internal/accesses",
                   json={"user_id": user_id, "client": client}, timeout=5.0)
    except httpx.HTTPError:
        pass  # propagação tolerante a falhas (D-05)
