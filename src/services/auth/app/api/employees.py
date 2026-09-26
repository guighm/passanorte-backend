"""Gestão de funcionários pelo admin (RF04/RF05) — T027."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.auth.app.core.deps import get_db, require_role
from services.auth.app.models.audit import AuditLog
from services.auth.app.models.user import User, UserRole
from shared.audit import record_audit
from shared.errors import ApiError
from shared.logging import log_event
from shared.security import hash_password

router = APIRouter(tags=["employees"])
logger = logging.getLogger("auth")

require_admin = require_role(UserRole.admin)


class EmployeeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    surname: str = Field(min_length=1, max_length=120)
    email: str
    password: str = Field(min_length=8)


class EmployeeUpdate(BaseModel):
    name: str | None = None
    surname: str | None = None
    email: str | None = None


class EmployeeOut(BaseModel):
    id: str
    name: str
    surname: str
    email: str
    role: str
    is_active: bool


@router.get("/employees", dependencies=[Depends(require_admin)])
def list_employees(db: Session = Depends(get_db)) -> dict:
    employees = db.query(User).filter(User.role == UserRole.employee).all()
    return {
        "items": [
            {"id": e.id, "name": e.name, "surname": e.surname, "email": e.email,
             "role": e.role.value, "is_active": e.is_active}
            for e in employees
        ]
    }


@router.post("/employees", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
def create_employee(
    payload: EmployeeCreate, claims: dict = Depends(require_admin), db: Session = Depends(get_db)
) -> EmployeeOut:
    if db.query(User).filter(User.email == payload.email).first() is not None:
        raise ApiError(code="duplicate_email", message="Email já cadastrado.", status_code=409)
    employee = User(
        role=UserRole.employee,
        name=payload.name,
        surname=payload.surname,
        email=payload.email,
        password_hash=hash_password(payload.password),
        country_of_origin="Brasil",  # funcionários são internos; país não se aplica
    )
    db.add(employee)
    db.flush()  # garante o id gerado para o registro de auditoria
    record_audit(db, AuditLog, actor_id=claims["sub"], action="create_employee",
                 entity="employee", entity_id=employee.id, payload={"employee_id": employee.id})
    db.commit()
    log_event(logger, "employee_created", actor_id=claims["sub"], employee_id=employee.id)
    return EmployeeOut(
        id=employee.id, name=employee.name, surname=employee.surname,
        email=employee.email, role=employee.role.value, is_active=employee.is_active,
    )


@router.patch("/employees/{employee_id}", response_model=EmployeeOut, dependencies=[Depends(require_admin)])
def update_employee(
    employee_id: str,
    payload: EmployeeUpdate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> EmployeeOut:
    employee = db.query(User).filter(User.id == employee_id, User.role == UserRole.employee).first()
    if employee is None:
        raise ApiError(code="not_found", message="Funcionário não encontrado.", status_code=404)
    for field in ("name", "surname", "email"):
        value = getattr(payload, field)
        if value is not None:
            setattr(employee, field, value)
    record_audit(db, AuditLog, actor_id=claims["sub"], action="update_employee",
                 entity="employee", entity_id=employee.id, payload=payload.model_dump(exclude_none=True))
    db.commit()
    return EmployeeOut(
        id=employee.id, name=employee.name, surname=employee.surname,
        email=employee.email, role=employee.role.value, is_active=employee.is_active,
    )


@router.delete("/employees/{employee_id}", status_code=204, dependencies=[Depends(require_admin)])
def revoke_employee(employee_id: str, claims: dict = Depends(require_admin), db: Session = Depends(get_db)) -> None:
    employee = db.query(User).filter(User.id == employee_id, User.role == UserRole.employee).first()
    if employee is None:
        raise ApiError(code="not_found", message="Funcionário não encontrado.", status_code=404)
    # revogação lógica: preserva auditoria, bloqueia novos logins (RF05)
    employee.is_active = False
    record_audit(db, AuditLog, actor_id=claims["sub"], action="revoke_employee",
                 entity="employee", entity_id=employee.id)
    db.commit()
