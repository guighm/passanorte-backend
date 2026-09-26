"""Dependências do serviço auth: sessão de banco e autenticação JWT."""

from __future__ import annotations

from collections.abc import Callable, Generator

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from services.auth.app.models.user import User, UserRole
from shared.errors import ApiError
from shared.security import decode_token


def get_db() -> Generator[Session, None, None]:
    """Sessão do banco do serviço (sobrescrita pelos testes via dependency_overrides)."""
    from shared.db import create_service_engine, make_session_factory

    engine = create_service_engine()
    factory = make_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_current_user(request: Request) -> dict:
    """Decodifica o JWT do header Authorization; 401 se ausente/inválido."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise ApiError(code="unauthorized", message="Autenticação necessária.", status_code=401)
    try:
        return decode_token(auth.removeprefix("Bearer ").strip(), expected_type="access")
    except jwt.PyJWTError:
        raise ApiError(code="unauthorized", message="Autenticação necessária.", status_code=401) from None


def require_role(*roles: UserRole) -> Callable:
    """Fábrica de dependência RBAC: exige um dos papéis informados (RF03)."""

    def dependency(claims: dict = Depends(get_current_user)) -> dict:
        if claims.get("role") not in {r.value for r in roles}:
            raise ApiError(code="forbidden", message="Acesso negado para o seu perfil.", status_code=403)
        return claims

    return dependency


def load_user(db: Session, claims: dict) -> User:
    user = db.get(User, claims["sub"])
    if user is None or not user.is_active:
        raise ApiError(code="unauthorized", message="Autenticação necessária.", status_code=401)
    return user
