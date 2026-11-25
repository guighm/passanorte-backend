"""Login, single-use refresh rotation, replay detection and family logout."""
from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from services.auth.app.core.deps import get_db
from services.auth.app.core.partners import get_partner_lookup
from services.auth.app.models.session import RefreshSession
from services.auth.app.models.user import User, UserRole
from services.auth.app.schemas.auth_schemas import LoginRequest, RefreshRequest, TokenResponse
from shared.errors import ApiError
from shared.insights_client import notify_access
from shared.messaging import enqueue
from shared.security import create_access_token, create_refresh_token, decode_token, verify_password

router = APIRouter(tags=["session"])


def _invalid() -> ApiError:
    return ApiError(code="invalid_refresh_token", message="Refresh token inválido.", status_code=401)


def _can_login(user: User, partner_lookup: Callable[[str], dict | None]) -> bool:
    if not user.is_active:
        return False
    if user.role != UserRole.supplier:
        return True
    partner = partner_lookup(user.partner_id) if user.partner_id else None
    return bool(partner and partner["is_active"])


def _digest(jti: str) -> str:
    return hashlib.sha256(jti.encode()).hexdigest()


def _issue(db: Session, user: User, family_id: str | None = None) -> TokenResponse:
    refresh = create_refresh_token(user.id, user.role.value)
    claims = decode_token(refresh, expected_type="refresh")
    db.add(RefreshSession(
        jti_hash=_digest(claims["jti"]), family_id=family_id or uuid.uuid4().hex,
        user_id=user.id, expires_at=claims["exp"], revoked=False,
    ))
    access, expires_in = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=expires_in)


def _session(db: Session, token: str) -> RefreshSession:
    try:
        claims = decode_token(token, expected_type="refresh")
    except jwt.PyJWTError:
        raise _invalid() from None
    session = db.get(RefreshSession, _digest(claims["jti"]))
    if session is None or session.user_id != claims["sub"] or session.expires_at <= int(time.time()):
        raise _invalid()
    return session


@router.post("/session", response_model=TokenResponse, openapi_extra={"security": []})
def login(
    payload: LoginRequest, db: Session = Depends(get_db),
    partner_lookup: Callable[[str], dict | None] = Depends(get_partner_lookup),
) -> TokenResponse:
    user = db.query(User).filter(func.lower(User.email) == payload.email.lower()).first()
    if (
        user is None or not verify_password(payload.password, user.password_hash)
        or not _can_login(user, partner_lookup)
    ):
        raise ApiError(code="invalid_credentials", message="Credenciais inválidas.", status_code=401)
    if payload.panel and user.role == UserRole.tourist:
        raise ApiError("forbidden", "O perfil de turista não pode acessar o painel.", 403)
    response = _issue(db, user)
    if user.role == UserRole.tourist:
        enqueue(db, "tourist.login", {"user_id": user.id, "occurred_at": datetime.now(UTC).isoformat()})
    else:
        notify_access(user.id, db=db)
    db.commit()
    return response


@router.post("/session/refresh", response_model=TokenResponse, openapi_extra={"security": []})
def refresh(
    payload: RefreshRequest, db: Session = Depends(get_db),
    partner_lookup: Callable[[str], dict | None] = Depends(get_partner_lookup),
) -> TokenResponse:
    session = _session(db, payload.refresh_token)
    user = db.scalar(select(User).where(User.id == session.user_id).with_for_update())
    if user is None or not _can_login(user, partner_lookup):
        raise _invalid()
    # Atomic compare-and-set prevents two concurrent renewals of the same token.
    result = db.execute(update(RefreshSession).where(
        RefreshSession.jti_hash == session.jti_hash, RefreshSession.revoked.is_(False)
    ).values(revoked=True))
    assert isinstance(result, CursorResult)
    if result.rowcount != 1:
        db.execute(update(RefreshSession).where(
            RefreshSession.family_id == session.family_id
        ).values(revoked=True))
        db.commit()
        raise _invalid()
    response = _issue(db, user, session.family_id)
    db.commit()
    return response


@router.delete("/session", status_code=204, openapi_extra={"security": []})
def logout(payload: RefreshRequest, db: Session = Depends(get_db)) -> None:
    session = _session(db, payload.refresh_token)
    db.scalar(select(User).where(User.id == session.user_id).with_for_update())
    db.execute(update(RefreshSession).where(
        RefreshSession.family_id == session.family_id
    ).values(revoked=True))
    db.commit()
