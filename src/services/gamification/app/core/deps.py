"""Dependências do serviço gamification: sessão, JWT e visitas validadas (D-13)."""

from __future__ import annotations

import os
from collections.abc import Callable, Generator

import httpx
import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from shared.errors import ApiError
from shared.security import decode_token


def get_db() -> Generator[Session, None, None]:
    from shared.db import create_service_engine, make_session_factory

    engine = create_service_engine()
    factory = make_session_factory(engine)
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


def require_role(role: str) -> Callable:
    def dependency(claims: dict = Depends(get_current_user)) -> dict:
        if claims.get("role") != role:
            raise ApiError(code="forbidden", message="Acesso negado para o seu perfil.", status_code=403)
        return claims

    return dependency


def get_auth_header(request: Request) -> str:
    """Cabeçalho Authorization bruto (repasse ao validation, D-02)."""
    return request.headers.get("Authorization", "")


def get_validated_visits() -> Callable[[str], list[str]]:
    """Fetcher das visitas validadas do usuário no validation (D-13).

    Recebe o cabeçalho Authorization do turista (mesmo usuário; o serviço
    validation confia no JWT, D-02) e devolve os tourist_spot_id validados.
    Em indisponibilidade o progresso deriva vazio (não trava).
    """
    base_url = os.environ.get("VALIDATION_SERVICE_URL", "http://localhost:8003")

    def fetch(auth_header: str) -> list[str]:
        try:
            resp = httpx.get(
                f"{base_url}/api/v1/visits",
                headers={"Authorization": auth_header},
                timeout=5.0,
            )
            resp.raise_for_status()
            return [item["tourist_spot_id"] for item in resp.json().get("items", [])]
        except (httpx.HTTPError, ValueError, KeyError):
            return []

    return fetch
