"""POST /tourists — cadastro único do turista (RF22, FR-006, T016)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from services.auth.app.core.deps import get_db
from services.auth.app.models.user import TouristProfile, User, UserRole
from services.auth.app.schemas.auth_schemas import MeResponse, TouristCreate
from shared.errors import ApiError
from shared.logging import log_event
from shared.security import encrypt_pii, hash_password, pii_uniqueness_hash

router = APIRouter(tags=["tourists"])


def _masked(document_encrypted: str | None) -> str | None:
    """Marca de presença do documento sem expor PII (RNF08)."""
    return "***" if document_encrypted else None


@router.post("/tourists", response_model=MeResponse, status_code=status.HTTP_201_CREATED)
def register_tourist(payload: TouristCreate, db: Session = Depends(get_db)) -> User:
    if payload.cpf is None and payload.passport is None:
        raise ApiError(
            code="document_required",
            message="Informe CPF ou número de passaporte.",
            status_code=422,
        )

    if db.query(User).filter(User.email == payload.email).first() is not None:
        raise ApiError(code="duplicate_identity", message="Email já cadastrado.", status_code=409)

    document = (payload.cpf or payload.passport).strip()
    document_hash = pii_uniqueness_hash(document)
    if db.query(User).filter((User.cpf_hash == document_hash) | (User.passport_hash == document_hash)).first():
        raise ApiError(
            code="duplicate_identity",
            message="Documento já cadastrado.",
            status_code=409,
            details={"field": "cpf" if payload.cpf else "passport"},
        )

    user = User(
        role=UserRole.tourist,
        name=payload.name,
        surname=payload.surname,
        email=payload.email,
        password_hash=hash_password(payload.password),
        phone_encrypted=encrypt_pii(payload.phone),
        cpf_encrypted=encrypt_pii(payload.cpf) if payload.cpf else None,
        cpf_hash=pii_uniqueness_hash(payload.cpf) if payload.cpf else None,
        passport_encrypted=encrypt_pii(payload.passport) if payload.passport else None,
        passport_hash=pii_uniqueness_hash(payload.passport) if payload.passport else None,
        country_of_origin=payload.country_of_origin,
    )
    db.add(user)
    db.flush()
    db.add(TouristProfile(user_id=user.id))
    db.commit()
    log_event(__import__("logging").getLogger("auth"), "tourist_registered", user_id=user.id)
    return user


@router.get("/internal/users/{user_id}", tags=["internal"])
def get_public_user(user_id: str, db: Session = Depends(get_db)) -> dict:
    """Dados públicos mínimos para outros serviços (sem PII, RNF08)."""
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(code="not_found", message="Usuário não encontrado.", status_code=404)
    return {"id": user.id, "country_of_origin": user.country_of_origin, "role": user.role.value}
