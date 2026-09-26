"""Dependências do serviço chatbot: sessão, JWT (RF03), embedder e provider (D-08)."""

from __future__ import annotations

from collections.abc import Callable, Generator

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from services.chatbot.app.core.embeddings import Embedder
from services.chatbot.app.core.embeddings import get_embedder as _get_embedder
from services.chatbot.app.core.provider import LLMProvider
from services.chatbot.app.core.provider import get_provider as _get_provider
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


require_tourist = require_role("tourist")


def get_embedder() -> Embedder:
    """Embedder ativo (D-08); sobrescrito nos testes pelo stub determinístico."""
    return _get_embedder()


def get_provider() -> LLMProvider:
    """Provider de LLM ativo (D-08); injetável para testes."""
    return _get_provider()
