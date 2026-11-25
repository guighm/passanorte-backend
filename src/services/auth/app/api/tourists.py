"""POST /tourists — cadastro único do turista (RF22, FR-006, T016)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.auth.app.core.categories import get_category_lookup, validate_categories
from services.auth.app.core.deps import get_db
from services.auth.app.models.user import TouristInterest, TouristProfile, User, UserRole
from services.auth.app.schemas.auth_schemas import MeResponse, TouristCreate
from shared.errors import ApiError
from shared.logging import log_event
from shared.security import encrypt_pii, hash_password, pii_uniqueness_hash

router = APIRouter(tags=["tourists"])


@router.post("/tourists", response_model=MeResponse, status_code=status.HTTP_201_CREATED)
def register_tourist(
    payload: TouristCreate, db: Session = Depends(get_db),
    category_lookup: Callable[[list[str]], set[str]] = Depends(get_category_lookup),
) -> User:
    email = payload.email.lower()
    if db.query(User).filter(func.lower(User.email) == email).first() is not None:
        raise ApiError(code="duplicate_identity", message="Email já cadastrado.", status_code=409)
    document = payload.cpf or payload.passport
    assert document is not None
    hashes = [pii_uniqueness_hash(document)]
    if payload.cpf:
        cpf = payload.cpf
        hashes.append(pii_uniqueness_hash(f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"))
    if db.query(User).filter(User.cpf_hash.in_(hashes) | User.passport_hash.in_(hashes)).first():
        raise ApiError("duplicate_identity", "Documento já cadastrado.", 409)

    categories = validate_categories(payload.category_ids, category_lookup)
    user = User(
        role=UserRole.tourist,
        name=payload.name,
        surname=payload.surname,
        email=email,
        password_hash=hash_password(payload.password),
        phone_encrypted=encrypt_pii(payload.phone),
        cpf_encrypted=encrypt_pii(payload.cpf) if payload.cpf else None,
        cpf_hash=hashes[0] if payload.cpf else None,
        passport_encrypted=encrypt_pii(payload.passport) if payload.passport else None,
        passport_hash=hashes[0] if payload.passport else None,
        country_of_origin=payload.country_of_origin,
    )
    try:
        db.add(user)
        db.flush()
        db.add(TouristProfile(user_id=user.id, consent_version=payload.consent_version, consent_at=datetime.now(UTC)))
        db.flush()
        db.add_all(TouristInterest(user_id=user.id, category_id=category) for category in categories)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError("duplicate_identity", "E-mail ou documento já cadastrado.", 409) from None
    log_event(__import__("logging").getLogger("auth"), "tourist_registered", user_id=user.id)
    return user


@router.get("/internal/users/{user_id}", tags=["internal"])
def get_public_user(user_id: str, db: Session = Depends(get_db)) -> dict:
    """Dados públicos mínimos para outros serviços (sem PII, RNF08)."""
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(code="not_found", message="Usuário não encontrado.", status_code=404)
    return {"id": user.id, "country_of_origin": user.country_of_origin, "role": user.role.value}
