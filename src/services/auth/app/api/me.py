"""Perfil autenticado e interesses do turista (RF24/RF25) — T018."""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from services.auth.app.core.categories import get_category_lookup, validate_categories
from services.auth.app.core.deps import get_current_user, get_db, load_user, require_role
from services.auth.app.models.user import TouristInterest, TouristProfile, UserRole
from services.auth.app.schemas.auth_schemas import (
    InterestsResponse,
    InterestsUpdate,
    MeResponse,
    MeUpdate,
)
from shared.logging import log_event
from shared.security import encrypt_pii

router = APIRouter(tags=["me"])
logger = logging.getLogger("auth")
require_tourist = require_role(UserRole.tourist)


@router.get("/me", response_model=MeResponse)
def get_me(
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    user = load_user(db, claims)
    return MeResponse(
        id=user.id,
        role=user.role.value,
        name=user.name,
        surname=user.surname,
        email=user.email,
        country_of_origin=user.country_of_origin,
        partner_id=user.partner_id,
    )


@router.patch("/me", response_model=MeResponse)
def update_me(
    payload: MeUpdate,
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    user = load_user(db, claims)
    if payload.name is not None:
        user.name = payload.name
    if payload.surname is not None:
        user.surname = payload.surname
    if payload.phone is not None:
        user.phone_encrypted = encrypt_pii(payload.phone)
    db.commit()
    return MeResponse(
        id=user.id,
        role=user.role.value,
        name=user.name,
        surname=user.surname,
        email=user.email,
        country_of_origin=user.country_of_origin,
        partner_id=user.partner_id,
    )


@router.put("/me/interests", response_model=InterestsResponse)
def set_interests(
    payload: InterestsUpdate,
    claims: dict = Depends(require_tourist),
    db: Session = Depends(get_db),
    category_lookup: Callable[[list[str]], set[str]] = Depends(get_category_lookup),
) -> InterestsResponse:
    user = load_user(db, claims)
    categories = validate_categories(payload.category_ids, category_lookup)
    profile = db.get(TouristProfile, user.id)
    if profile is None:
        profile = TouristProfile(user_id=user.id)
        db.add(profile)
        db.flush()
    db.query(TouristInterest).filter(TouristInterest.user_id == user.id).delete()
    for category_id in categories:
        db.add(TouristInterest(user_id=user.id, category_id=category_id))
    db.commit()
    log_event(logger, "interests_updated", user_id=user.id, count=len(payload.category_ids))
    return InterestsResponse(category_ids=categories)


@router.get("/me/interests", response_model=InterestsResponse)
def get_interests(
    claims: dict = Depends(require_tourist),
    db: Session = Depends(get_db),
) -> InterestsResponse:
    user = load_user(db, claims)
    rows = db.query(TouristInterest).filter(TouristInterest.user_id == user.id).all()
    return InterestsResponse(category_ids=[row.category_id for row in rows])


@router.get("/internal/users/{user_id}/interests", include_in_schema=False)
def internal_interests(user_id: str, db: Session = Depends(get_db)) -> InterestsResponse:
    rows = db.query(TouristInterest).filter(TouristInterest.user_id == user_id).all()
    return InterestsResponse(category_ids=[row.category_id for row in rows])
