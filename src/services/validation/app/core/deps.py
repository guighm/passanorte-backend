"""Dependências do serviço validation: sessão, JWT e snapshot do catalog (D-05)."""

from __future__ import annotations

from collections.abc import Callable, Generator

import httpx
import jwt
from fastapi import Request
from sqlalchemy.orm import Session

from shared.errors import ApiError
from shared.security import decode_token
from shared.settings import Settings, secret


def get_db() -> Generator[Session, None, None]:
    from shared.db import service_session_factory

    factory = service_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise ApiError(code="unauthorized", message="Autenticação necessária.", status_code=401)
    try:
        return decode_token(auth.removeprefix("Bearer ").strip(), expected_type="access")
    except jwt.PyJWTError:
        raise ApiError(code="unauthorized", message="Autenticação necessária.", status_code=401) from None


def get_catalog_snapshot() -> Callable[[str], dict]:
    """Fetcher do snapshot do ponto no catalog (substituível em testes)."""
    base_url = str(Settings.load().catalog_service_url).rstrip("/")

    def fetch(spot_id: str) -> dict:
        try:
            resp = httpx.get(
                f"{base_url}/api/v1/internal/tourist-spots/{spot_id}",
                headers={"X-Internal-Token": secret("INTERNAL_API_TOKEN", required=False)}, timeout=5.0,
            )
        except httpx.HTTPError:
            raise ApiError(
                code="catalog_unavailable",
                message="Catálogo indisponível no momento.",
                status_code=503,
            ) from None
        if resp.status_code == 404:
            raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
        resp.raise_for_status()
        return resp.json()

    return fetch
