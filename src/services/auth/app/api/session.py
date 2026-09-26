"""Sessão: login, refresh e logout (RF02/RF23, RNF09, D-01) — T017."""

from __future__ import annotations

import logging

import jwt
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from services.auth.app.core.deps import get_db
from services.auth.app.models.user import User
from services.auth.app.schemas.auth_schemas import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from shared.errors import ApiError
from shared.insights_client import notify_access
from shared.logging import log_event
from shared.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)

router = APIRouter(tags=["session"])
logger = logging.getLogger("auth")

GENERIC_LOGIN_ERROR = ApiError(
    code="invalid_credentials",
    message="Credenciais inválidas.",
    status_code=401,
)


def _authenticate(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise GENERIC_LOGIN_ERROR
    return user


@router.post("/session", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = _authenticate(db, payload.email, payload.password)
    access, expires_in = create_access_token(user.id, user.role.value)
    log_event(logger, "user_logged_in", user_id=user.id, role=user.role.value)
    notify_access(user.id)  # RF07: acesso registrado no insights (fire-and-forget, D-05)
    return TokenResponse(
        access_token=access,
        refresh_token=create_refresh_token(user.id, user.role.value),
        expires_in=expires_in,
    )


@router.post("/session/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
    except jwt.PyJWTError:
        raise ApiError(code="invalid_refresh_token", message="Refresh token inválido.", status_code=401) from None
    user = db.get(User, claims["sub"])
    if user is None or not user.is_active:
        raise ApiError(code="invalid_refresh_token", message="Refresh token inválido.", status_code=401)
    access, expires_in = create_access_token(user.id, user.role.value)
    return TokenResponse(
        access_token=access,
        refresh_token=payload.refresh_token,
        expires_in=expires_in,
    )


@router.delete("/session", status_code=204)
def logout() -> None:
    """Logout stateless: o cliente descarta os tokens; expiração e renovação
    controladas pelo decode dos JWTs (RNF09)."""
    return None
