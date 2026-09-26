"""Endpoints administrativos de rotas e brindes (RF18–RF20) — T043."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.gamification.app.core.deps import get_db, require_role
from services.gamification.app.models.enrollment import Badge, RedeemCode
from services.gamification.app.models.route import Prize, Route, RoutePoint
from shared.audit import record_audit
from shared.audit_model import AuditLog
from shared.errors import ApiError

router = APIRouter(tags=["routes (admin)"])
logger = logging.getLogger("gamification")

require_admin = require_role("admin")


class PrizeIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class RouteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    points: list[str] = Field(min_length=1)
    prize: PrizeIn


class RouteUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    points: list[str] | None = None
    is_active: bool | None = None


class StockUpdate(BaseModel):
    stock_quantity: int = Field(ge=0)


def _route_body(route: Route) -> dict:
    return {
        "id": route.id,
        "name": route.name,
        "description": route.description,
        "points": [p.tourist_spot_id for p in route.points if p.is_active],
        "prize": {"id": route.prize.id, "name": route.prize.name, "stock_quantity": route.prize.stock_quantity},
        "is_active": route.is_active,
    }


@router.get("/routes")
def list_routes(db: Session = Depends(get_db)) -> dict:
    """Rotas ativas com pontos e brinde — leitura pública (RF18)."""
    routes = db.query(Route).filter(Route.is_active.is_(True)).all()
    items = [_route_body(r) for r in routes]
    return {"items": items, "total": len(items)}


@router.post("/routes", status_code=status.HTTP_201_CREATED)
def create_route(payload: RouteCreate, claims: dict = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    prize = Prize(name=payload.prize.name, description=payload.prize.description, stock_quantity=0)
    db.add(prize)
    db.flush()
    route = Route(name=payload.name, description=payload.description, prize_id=prize.id)
    db.add(route)
    db.flush()
    for position, spot_id in enumerate(payload.points):
        db.add(RoutePoint(route_id=route.id, tourist_spot_id=spot_id, position=position))
    record_audit(db, AuditLog, actor_id=claims["sub"], action="create_route",
                 entity="route", entity_id=route.id, payload={"name": payload.name})
    db.commit()
    return _route_body(route)


@router.patch("/routes/{route_id}")
def update_route(
    route_id: str, payload: RouteUpdate,
    claims: dict = Depends(require_admin), db: Session = Depends(get_db),
) -> dict:
    route = db.query(Route).filter(Route.id == route_id).first()
    if route is None:
        raise ApiError(code="not_found", message="Rota não encontrada.", status_code=404)
    if payload.name is not None:
        route.name = payload.name
    if payload.description is not None:
        route.description = payload.description
    if payload.is_active is not None:
        route.is_active = payload.is_active
    if payload.points is not None:
        db.query(RoutePoint).filter(RoutePoint.route_id == route_id).delete()
        for position, spot_id in enumerate(payload.points):
            db.add(RoutePoint(route_id=route_id, tourist_spot_id=spot_id, position=position))
    record_audit(db, AuditLog, actor_id=claims["sub"], action="update_route",
                 entity="route", entity_id=route_id)
    db.commit()
    return _route_body(route)


@router.delete("/routes/{route_id}", status_code=204)
def remove_route(route_id: str, claims: dict = Depends(require_admin), db: Session = Depends(get_db)) -> None:
    route = db.query(Route).filter(Route.id == route_id).first()
    if route is None:
        raise ApiError(code="not_found", message="Rota não encontrada.", status_code=404)
    route.is_active = False  # remoção lógica: progresso em andamento não quebra
    record_audit(db, AuditLog, actor_id=claims["sub"], action="remove_route",
                 entity="route", entity_id=route_id)
    db.commit()


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
    from services.gamification.app.models.enrollment import CodeStatus

    return status_.value if isinstance(status_, CodeStatus) else str(status_)
