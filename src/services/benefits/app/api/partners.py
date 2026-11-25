from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import AfterValidator, BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.benefits.app.models import Partner, PartnerAuditLog
from shared.audit import record_audit
from shared.db import service_session_factory
from shared.documents import normalize_tax_id
from shared.errors import ApiError
from shared.rbac import require_role

router = APIRouter(tags=["partners"])
require_admin = require_role("admin")


def get_db() -> Generator[Session, None, None]:
    with service_session_factory()() as session:
        yield session


def normalize_cnpj(value: str) -> str:
    return normalize_tax_id(value, cnpj=True)


class PartnerInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    cnpj: Annotated[str, AfterValidator(normalize_cnpj)]
    contact: str = Field(min_length=1, max_length=255)


class PartnerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    cnpj: Annotated[str, AfterValidator(normalize_cnpj)] | None = None
    contact: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


def partner_body(partner: Partner) -> dict:
    return {
        "id": partner.id, "name": partner.name, "cnpj": partner.cnpj,
        "contact": partner.contact, "is_active": partner.is_active,
    }


def save(db: Session, claims: dict, entity: Partner, action: str) -> None:
    try:
        db.flush()
        record_audit(db, PartnerAuditLog, actor_id=claims["sub"], action=action,
                     entity=entity.__tablename__, entity_id=entity.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError("duplicate_identity", "Identificador já cadastrado.", 409) from None


def lookup_partner(db: Session, partner_id: str) -> Partner:
    partner = db.get(Partner, partner_id, with_for_update=True)
    if partner is None:
        raise ApiError("not_found", "Parceiro não encontrado.", 404)
    return partner


@router.get("/partners", dependencies=[Depends(require_admin)])
def list_partners(db: Session = Depends(get_db)) -> dict:
    return {"items": [partner_body(partner) for partner in db.query(Partner).order_by(Partner.name)]}


@router.get("/partners/{partner_id}", dependencies=[Depends(require_admin)])
def get_partner(partner_id: str, db: Session = Depends(get_db)) -> dict:
    partner = db.get(Partner, partner_id)
    if partner is None:
        raise ApiError("not_found", "Parceiro não encontrado.", 404)
    return partner_body(partner)


@router.post("/partners", status_code=201)
def create_partner(payload: PartnerInput, claims: dict = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    partner = Partner(**payload.model_dump())
    db.add(partner)
    save(db, claims, partner, "create_partner")
    return partner_body(partner)


@router.patch("/partners/{partner_id}")
def update_partner(
    partner_id: str, payload: PartnerUpdate, claims: dict = Depends(require_admin), db: Session = Depends(get_db),
) -> dict:
    partner = lookup_partner(db, partner_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(partner, field, value)
    save(db, claims, partner, "update_partner")
    return partner_body(partner)


@router.delete("/partners/{partner_id}", status_code=204)
def remove_partner(partner_id: str, claims: dict = Depends(require_admin), db: Session = Depends(get_db)) -> None:
    update_partner(partner_id, PartnerUpdate(is_active=False), claims, db)


@router.get("/internal/partners/{partner_id}", include_in_schema=False)
def internal_partner(partner_id: str, db: Session = Depends(get_db)) -> dict:
    partner = db.get(Partner, partner_id)
    if partner is None:
        raise ApiError("not_found", "Parceiro n?o encontrado.", 404)
    return {"id": partner.id, "is_active": partner.is_active}
