"""Endpoints administrativos de rotas e brindes (RF18–RF20) — T043."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.gamification.app.core.deps import get_db, require_role
from services.gamification.app.models.audit import AuditLog
from services.gamification.app.models.enrollment import Badge, CodeStatus, RedeemCode
from services.gamification.app.models.route import Prize
from shared.audit import record_audit
from shared.errors import ApiError

router = APIRouter(tags=["legacy benefits"])

require_admin = require_role("admin")


class PrizeIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class StockUpdate(BaseModel):
    stock_quantity: int = Field(ge=0)


@router.get("/prizes")
def list_prizes(claims: dict = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    prizes = db.query(Prize).all()
    return {
        "items": [
            {"id": p.id, "name": p.name, "description": p.description, "stock_quantity": p.stock_quantity}
            for p in prizes
        ],
        "total": len(prizes),
    }


@router.post("/prizes", status_code=status.HTTP_201_CREATED)
def create_prize(
    payload: PrizeIn, claims: dict = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    prize = Prize(name=payload.name, description=payload.description, stock_quantity=0)
    db.add(prize)
    db.flush()
    record_audit(db, AuditLog, actor_id=claims["sub"], action="create_prize",
                 entity="prize", entity_id=prize.id, payload={"name": payload.name})
    db.commit()
    return {"id": prize.id, "name": prize.name, "stock_quantity": prize.stock_quantity}


@router.patch("/prizes/{prize_id}/stock")
def update_stock(
    prize_id: str, payload: StockUpdate,
    claims: dict = Depends(require_admin), db: Session = Depends(get_db),
) -> dict:
    prize = db.query(Prize).filter(Prize.id == prize_id).first()
    if prize is None:
        raise ApiError(code="not_found", message="Brinde não encontrado.", status_code=404)
    prize.stock_quantity = payload.stock_quantity  # Pydantic já garante ≥ 0 (RF20)
    record_audit(db, AuditLog, actor_id=claims["sub"], action="update_stock",
                 entity="prize", entity_id=prize_id, payload={"stock_quantity": payload.stock_quantity})
    db.commit()
    return {"id": prize.id, "name": prize.name, "stock_quantity": prize.stock_quantity}


@router.get("/badges")
def list_badges(claims: dict = Depends(require_role("tourist")), db: Session = Depends(get_db)) -> dict:
    """Insígnias do turista autenticado (RF35)."""
    badges = db.query(Badge).filter(Badge.user_id == claims["sub"]).all()
    return {
        "items": [
            {"id": b.id, "route_id": b.route_id, "awarded_at": str(b.awarded_at)}
            for b in badges
        ]
    }


@router.get("/redeem-codes")
def list_redeem_codes(claims: dict = Depends(require_role("tourist")), db: Session = Depends(get_db)) -> dict:
    codes = db.query(RedeemCode).filter(RedeemCode.user_id == claims["sub"]).all()
    return {
        "items": [
            {"code": c.code, "route_id": c.route_id, "status": _status_value(c.status), "issued_at": str(c.issued_at)}
            for c in codes
        ]
    }


def _status_value(status_: object) -> str:
    return status_.value if isinstance(status_, CodeStatus) else str(status_)


@router.post("/internal/prizes", status_code=201, include_in_schema=False)
def create_route_prize(payload: PrizeIn, db: Session = Depends(get_db)) -> dict:
    prize = Prize(name=payload.name, description=payload.description, stock_quantity=0)
    db.add(prize)
    db.commit()
    return {"id": prize.id, "name": prize.name, "stock_quantity": prize.stock_quantity}


@router.post("/internal/prizes/lookup", include_in_schema=False)
def lookup_route_prizes(ids: list[str], db: Session = Depends(get_db)) -> dict:
    prizes = db.query(Prize).filter(Prize.id.in_(ids)).all()
    return {prize.id: {"id": prize.id, "name": prize.name, "stock_quantity": prize.stock_quantity} for prize in prizes}
