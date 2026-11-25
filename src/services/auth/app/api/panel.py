from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import AfterValidator, BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.auth.app.core.deps import get_db, require_role
from services.auth.app.core.partners import get_partner_lookup
from services.auth.app.models.audit import AuditLog
from services.auth.app.models.session import RefreshSession
from services.auth.app.models.user import User, UserRole
from shared.audit import record_audit
from shared.errors import ApiError
from shared.security import hash_password, validate_password

router = APIRouter(tags=["panel"])
require_admin = require_role(UserRole.admin)


class PanelUserInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    surname: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: Annotated[str, AfterValidator(validate_password)] = Field(min_length=8)
    role: Literal["admin", "supplier"]
    partner_id: str | None = None


class PanelUserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    surname: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    partner_id: str | None = None
    is_active: bool | None = None


def user_body(user: User) -> dict:
    return {
        "id": user.id, "name": user.name, "surname": user.surname, "email": user.email,
        "role": user.role.value, "partner_id": user.partner_id, "is_active": user.is_active,
    }


def save(db: Session, claims: dict, entity: User, action: str) -> None:
    try:
        db.flush()
        record_audit(db, AuditLog, actor_id=claims["sub"], action=action,
                     entity=entity.__tablename__, entity_id=entity.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError("duplicate_identity", "Identificador já cadastrado.", 409) from None


def validate_partner(
    lookup: Callable[[str], dict | None], role: UserRole, partner_id: str | None, *, active: bool = True,
) -> None:
    if role == UserRole.admin and partner_id is None:
        return
    if role == UserRole.supplier and partner_id:
        partner = lookup(partner_id)
        if partner and (partner["is_active"] or not active):
            return
    raise ApiError("invalid_partner", "Vínculo com parceiro inválido para este perfil.", 422)


@router.get("/panel/users", dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)) -> dict:
    users = db.query(User).filter(User.role.in_([UserRole.admin, UserRole.supplier])).order_by(User.email)
    return {"items": [user_body(user) for user in users]}


@router.post("/panel/users", status_code=201)
def create_user(
    payload: PanelUserInput, claims: dict = Depends(require_admin), db: Session = Depends(get_db),
    partner_lookup: Callable[[str], dict | None] = Depends(get_partner_lookup),
) -> dict:
    role = UserRole(payload.role)
    validate_partner(partner_lookup, role, payload.partner_id)
    user = User(name=payload.name, surname=payload.surname, email=payload.email.casefold(),
                role=role, partner_id=payload.partner_id, password_hash=hash_password(payload.password),
                country_of_origin="Brasil")
    db.add(user)
    save(db, claims, user, "create_panel_user")
    return user_body(user)


@router.patch("/panel/users/{user_id}")
def update_user(
    user_id: str, payload: PanelUserUpdate, claims: dict = Depends(require_admin), db: Session = Depends(get_db),
    partner_lookup: Callable[[str], dict | None] = Depends(get_partner_lookup),
) -> dict:
    user = db.get(User, user_id, with_for_update=True)
    if user is None or user.role == UserRole.tourist:
        raise ApiError("not_found", "Usuário do painel não encontrado.", 404)
    if user.id == claims["sub"] and payload.is_active is False:
        raise ApiError("self_deactivation", "Sua conta administrativa precisa permanecer ativa.", 409)
    fields = payload.model_dump(exclude_none=True)
    if "email" in fields:
        fields["email"] = fields["email"].casefold()
    if fields.get("is_active", user.is_active) or "partner_id" in fields:
        validate_partner(partner_lookup, user.role, fields.get("partner_id", user.partner_id),
                         active=fields.get("is_active", user.is_active))
    for field, value in fields.items():
        setattr(user, field, value)
    if payload.is_active is False or "partner_id" in fields:
        db.query(RefreshSession).filter(RefreshSession.user_id == user.id).update({"revoked": True})
    save(db, claims, user, "update_panel_user")
    return user_body(user)


@router.delete("/panel/users/{user_id}", status_code=204)
def disable_user(
    user_id: str, claims: dict = Depends(require_admin), db: Session = Depends(get_db),
    partner_lookup: Callable[[str], dict | None] = Depends(get_partner_lookup),
) -> None:
    update_user(user_id, PanelUserUpdate(is_active=False), claims, db, partner_lookup)
