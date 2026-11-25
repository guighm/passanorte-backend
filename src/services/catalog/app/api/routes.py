"""Endpoints administrativos de rotas e brindes (RF18–RF20) — T043."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.catalog.app.core.deps import get_db, require_role
from services.catalog.app.models.audit import AuditLog
from services.catalog.app.models.route import Route, RoutePoint
from shared.audit import record_audit
from shared.errors import ApiError
from shared.internal_client import RouteSnapshot, call_internal

router = APIRouter(tags=["routes (admin)"])

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


def get_prize_service():
    url = os.environ.get("GAMIFICATION_SERVICE_URL", "http://gamification:8004")
    return lambda method, path, **kwargs: call_internal(url, method, path, **kwargs)


def _route_body(route: Route, prize: dict) -> dict:
    return {
        "id": route.id,
        "name": route.name,
        "description": route.description,
        "points": [p.tourist_spot_id for p in route.points if p.is_active],
        "prize": prize,
        "is_active": route.is_active,
    }


@router.get("/routes")
def list_routes(db: Session = Depends(get_db), prizes=Depends(get_prize_service)) -> dict:
    """Rotas ativas com pontos e brinde — leitura pública (RF18)."""
    routes = db.query(Route).filter(Route.is_active.is_(True)).all()
    if not routes:
        return {"items": [], "total": 0}
    results = prizes("POST", "/internal/prizes/lookup", json=[route.prize_id for route in routes])
    items = [_route_body(route, results[route.prize_id]) for route in routes]
    return {"items": items, "total": len(items)}


@router.post("/routes", status_code=status.HTTP_201_CREATED)
def create_route(
    payload: RouteCreate, claims: dict = Depends(require_admin),
    db: Session = Depends(get_db), prizes=Depends(get_prize_service),
) -> dict:
    prize = prizes("POST", "/internal/prizes", json=payload.prize.model_dump())
    route = Route(name=payload.name, description=payload.description, prize_id=prize["id"])
    db.add(route)
    db.flush()
    for position, spot_id in enumerate(payload.points):
        db.add(RoutePoint(route_id=route.id, tourist_spot_id=spot_id, position=position))
    record_audit(db, AuditLog, actor_id=claims["sub"], action="create_route",
                 entity="route", entity_id=route.id, payload={"name": payload.name})
    db.commit()
    return _route_body(route, prize)


@router.patch("/routes/{route_id}")
def update_route(
    route_id: str, payload: RouteUpdate,
    claims: dict = Depends(require_admin), db: Session = Depends(get_db), prizes=Depends(get_prize_service),
) -> dict:
    route = db.query(Route).filter(Route.id == route_id).first()
    if route is None:
        raise ApiError(code="not_found", message="Rota não encontrada.", status_code=404)
    prize = prizes("POST", "/internal/prizes/lookup", json=[route.prize_id])[route.prize_id]
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
    return _route_body(route, prize)


@router.delete("/routes/{route_id}", status_code=204)
def remove_route(route_id: str, claims: dict = Depends(require_admin), db: Session = Depends(get_db)) -> None:
    route = db.query(Route).filter(Route.id == route_id).first()
    if route is None:
        raise ApiError(code="not_found", message="Rota não encontrada.", status_code=404)
    route.is_active = False  # remoção lógica: progresso em andamento não quebra
    record_audit(db, AuditLog, actor_id=claims["sub"], action="remove_route",
                 entity="route", entity_id=route_id)
    db.commit()


@router.get("/internal/routes/{route_id}", include_in_schema=False)
def internal_route(route_id: str, db: Session = Depends(get_db)) -> RouteSnapshot:
    route = db.get(Route, route_id)
    if route is None:
        raise ApiError(code="not_found", message="Rota não encontrada.", status_code=404)
    return RouteSnapshot(
        id=route.id,
        name=route.name,
        is_active=route.is_active,
        prize_id=route.prize_id,
        points=[point.tourist_spot_id for point in route.points if point.is_active],
    )
