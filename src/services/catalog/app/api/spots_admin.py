"""Endpoints administrativos de pontos turísticos (RF11–RF15) — T028."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.catalog.app.api.spots import _categories_for, _spot_query
from services.catalog.app.core.deps import get_db, require_role
from services.catalog.app.models.audit import AuditLog
from services.catalog.app.models.spot import (
    OpeningSchedule,
    SpotCategory,
    SpotStatus,
    TouristSpot,
)
from shared.audit import record_audit
from shared.chatbot_client import refresh_index
from shared.errors import ApiError
from shared.logging import log_event
from shared.notifications_client import dispatch

router = APIRouter(tags=["tourist-spots (admin)"])
logger = logging.getLogger("catalog")

require_admin = require_role("admin")


def _index_spot(spot: TouristSpot) -> None:
    """Rebuild do embedding do ponto no chatbot — fire-and-forget (D-08)."""
    status_ = spot.status.value if hasattr(spot.status, "value") else spot.status
    refresh_index([
        {
            "source_type": "tourist_spot",
            "source_id": spot.id,
            "spot_id": spot.id,
            "title": spot.name,
            "description": spot.description,
            "status": status_,
            "latitude": float(spot.latitude),
            "longitude": float(spot.longitude),
        }
    ])


class TouristSpotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=2000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    category_ids: list[str] = Field(default_factory=list)
    tolerance_radius_m: int = Field(default=100, ge=1)


class TouristSpotUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    category_ids: list[str] | None = None
    tolerance_radius_m: int | None = Field(default=None, ge=1)


class StatusUpdate(BaseModel):
    status: SpotStatus


class ScheduleUpdate(BaseModel):
    schedule: list[dict] = Field(min_length=1)


def _validate_schedule(rows: list[dict], existing: list[tuple[int, str, str]] | None = None) -> None:
    """Janelas do mesmo dia não podem se sobrepor, inclusive com as existentes (RF14)."""
    by_day: dict[int, list[tuple[str, str]]] = {}
    for day, opens, closes in existing or []:
        by_day.setdefault(day, []).append((opens, closes))
    for row in rows:
        day = int(row["day_of_week"])
        if not 0 <= day <= 6:
            raise ApiError(code="invalid_schedule", message="Dia da semana inválido.", status_code=422)
        if row["closes_at"] <= row["opens_at"]:
            raise ApiError(code="invalid_schedule", message="Janela de horário inválida.", status_code=422)
        by_day.setdefault(day, []).append((row["opens_at"], row["closes_at"]))
    for windows in by_day.values():
        windows = sorted(windows)
        for (_, end_a), (start_b, _) in zip(windows, windows[1:], strict=False):
            if end_a > start_b:
                raise ApiError(
                    code="schedule_overlap",
                    message="Janelas de funcionamento se sobrepõem no mesmo dia.",
                    status_code=422,
                )


@router.post("/tourist-spots", status_code=status.HTTP_201_CREATED)
def create_spot(
    payload: TouristSpotCreate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    spot = TouristSpot(
        name=payload.name,
        description=payload.description,
        latitude=payload.latitude,
        longitude=payload.longitude,
        tolerance_radius_m=payload.tolerance_radius_m,
        status=SpotStatus.open,
    )
    db.add(spot)
    db.flush()
    for category_id in payload.category_ids:
        db.add(SpotCategory(spot_id=spot.id, category_id=category_id))
    record_audit(db, AuditLog, actor_id=claims["sub"], action="create_spot",
                 entity="tourist_spot", entity_id=spot.id, payload={"name": payload.name})
    db.commit()
    log_event(logging.getLogger("catalog"), "spot_created", spot_id=spot.id, actor_id=claims["sub"])
    # RF37: inscritos nas categorias do ponto recebem notificação (fire-and-forget)
    if payload.category_ids:
        dispatch(kind="new_spot", source_id=spot.id, title=spot.name, body=spot.description,
                 category_ids=payload.category_ids, payload={"tourist_spot_id": spot.id})
    _index_spot(spot)
    return {"id": spot.id, "name": spot.name, "status": spot.status.value}


@router.patch("/tourist-spots/{spot_id}")
def update_spot(
    spot_id: str,
    payload: TouristSpotUpdate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    spot = _spot_query(db).filter(TouristSpot.id == spot_id).first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    for field in ("name", "description", "latitude", "longitude", "tolerance_radius_m"):
        value = getattr(payload, field, None)
        if value is not None:
            setattr(spot, field, value)
    if getattr(payload, "category_ids", None) is not None:
        db.query(SpotCategory).filter(SpotCategory.spot_id == spot_id).delete()
        for category_id in payload.category_ids:
            db.add(SpotCategory(spot_id=spot_id, category_id=category_id))
    record_audit(db, AuditLog, actor_id=claims["sub"], action="update_spot",
                 entity="tourist_spot", entity_id=spot_id)
    db.commit()
    _index_spot(spot)
    return {"id": spot.id, "name": spot.name, "status": spot.status.value}


@router.delete("/tourist-spots/{spot_id}", status_code=204)
def remove_spot(spot_id: str, claims: dict = Depends(require_admin), db: Session = Depends(get_db)) -> None:
    """Remoção lógica (RF12): rotas ativas não quebram (edge case da spec)."""
    spot = _spot_query(db).filter(TouristSpot.id == spot_id).first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    spot.is_removed = True
    record_audit(db, AuditLog, actor_id=claims["sub"], action="remove_spot",
                 entity="tourist_spot", entity_id=spot_id)
    db.commit()


@router.put("/tourist-spots/{spot_id}/schedule")
def set_schedule(
    spot_id: str,
    payload: ScheduleUpdate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    spot = _spot_query(db).filter(TouristSpot.id == spot_id).first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    existing = [
        (row.day_of_week, row.opens_at, row.closes_at)
        for row in db.query(OpeningSchedule).filter(OpeningSchedule.spot_id == spot_id).all()
    ]
    _validate_schedule(payload.schedule, existing)
    db.query(OpeningSchedule).filter(OpeningSchedule.spot_id == spot_id).delete()
    for row in payload.schedule:
        db.add(
            OpeningSchedule(
                spot_id=spot_id,
                day_of_week=row["day_of_week"],
                opens_at=row["opens_at"],
                closes_at=row["closes_at"],
            )
        )
    record_audit(db, AuditLog, actor_id=claims["sub"], action="set_schedule",
                 entity="tourist_spot", entity_id=spot_id)
    db.commit()
    return {"id": spot_id, "schedule": payload.schedule}


@router.patch("/tourist-spots/{spot_id}/status")
def set_status(
    spot_id: str,
    payload: StatusUpdate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    spot = _spot_query(db).filter(TouristSpot.id == spot_id).first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    if spot.status == SpotStatus.permanently_closed:
        # permanently_closed é estado terminal (data-model.md)
        raise ApiError(
            code="invalid_status_transition",
            message="Ponto fechado permanentemente não pode mudar de status.",
            status_code=409,
        )
    spot.status = payload.status
    record_audit(db, AuditLog, actor_id=claims["sub"], action="set_status",
                 entity="tourist_spot", entity_id=spot_id, payload={"status": payload.status.value})
    db.commit()
    _index_spot(spot)  # status fechado propaga ao índice RAG (RF38)
    return {"id": spot.id, "status": spot.status.value}


@router.get("/admin/tourist-spots/{spot_id}", dependencies=[Depends(require_admin)])
def get_spot_admin(spot_id: str, db: Session = Depends(get_db)) -> dict:
    spot = _spot_query(db).filter(TouristSpot.id == spot_id).first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    return {
        "id": spot.id,
        "name": spot.name,
        "status": spot.status.value,
        "categories": [c.model_dump() for c in _categories_for(db, spot_id)],
    }
