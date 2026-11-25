"""Endpoints administrativos de pontos turísticos (RF11–RF15) — T028."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, HttpUrl, model_validator
from sqlalchemy.orm import Session

from services.catalog.app.api.spots import _spot_query, spot_detail
from services.catalog.app.core.deps import get_db, require_role
from services.catalog.app.models.audit import AuditLog
from services.catalog.app.models.route import RoutePoint
from services.catalog.app.models.spot import (
    Category,
    Event,
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


def _index_spot(db: Session, spot: TouristSpot, *, operation: str = "upsert") -> None:
    """Rebuild do embedding do ponto no chatbot — fire-and-forget (D-08)."""
    status_ = spot.status.value if hasattr(spot.status, "value") else spot.status
    db.flush()
    windows = db.query(OpeningSchedule).filter(OpeningSchedule.spot_id == spot.id).order_by(
        OpeningSchedule.day_of_week, OpeningSchedule.opens_at,
    )
    schedule = "; ".join(f"{row.day_of_week}: {row.opens_at}-{row.closes_at}" for row in windows)
    items = [
        {
            "source_type": "tourist_spot",
            "source_id": spot.id,
            "spot_id": spot.id,
            "title": spot.name,
            "description": spot.description,
            "status": status_,
            "latitude": float(spot.latitude),
            "longitude": float(spot.longitude),
            "operation": operation,
            "schedule_text": schedule[:500],
        }
    ]
    if operation == "delete":
        items.extend({
            "source_type": "event", "source_id": event.id, "spot_id": spot.id,
            "title": event.title, "operation": "delete",
        } for event in db.query(Event).filter(Event.tourist_spot_id == spot.id))
    refresh_index(items, db=db)


def _hide_spot_from_routes(db: Session, spot_id: str) -> None:
    db.query(RoutePoint).filter(RoutePoint.tourist_spot_id == spot_id).update({"is_active": False})


class TouristSpotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=2000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str = Field(min_length=1, max_length=500)
    image_url: HttpUrl | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    category_ids: list[str] = Field(min_length=1, max_length=100)
    tolerance_radius_m: int = Field(default=100, ge=1)


class TouristSpotUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    image_url: HttpUrl | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    category_ids: list[str] | None = Field(default=None, min_length=1, max_length=100)
    tolerance_radius_m: int | None = Field(default=None, ge=1)


class StatusUpdate(BaseModel):
    status: SpotStatus


class ScheduleWindow(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    opens_at: str | None = Field(default=None, pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    closes_at: str | None = Field(default=None, pattern=r"^(?:(?:[01][0-9]|2[0-3]):[0-5][0-9]|24:00)$")
    all_day: bool = False

    @model_validator(mode="after")
    def validate_window(self) -> ScheduleWindow:
        if self.all_day:
            if self.opens_at not in (None, "00:00") or self.closes_at not in (None, "24:00"):
                raise ValueError("Uma janela de 24h ocupa o dia inteiro.")
            self.opens_at, self.closes_at = "00:00", "24:00"
        elif not self.opens_at or not self.closes_at or self.closes_at <= self.opens_at:
            raise ValueError("Informe um intervalo crescente no mesmo dia.")
        return self


class ScheduleUpdate(BaseModel):
    schedule: list[ScheduleWindow] = Field(max_length=168)


def _validate_schedule(rows: list[tuple[int, str, str]]) -> None:
    by_day: dict[int, list[tuple[str, str]]] = {}
    for day, opens, closes in rows:
        by_day.setdefault(day, []).append((opens, closes))
    for windows in by_day.values():
        windows = sorted(windows)
        for (_, end_a), (start_b, _) in zip(windows, windows[1:], strict=False):
            if end_a > start_b:
                raise ApiError(
                    code="schedule_overlap",
                    message="Janelas de funcionamento se sobrepõem no mesmo dia.",
                    status_code=422,
                )


def valid_categories(db: Session, category_ids: list[str]) -> list[str]:
    ids = list(dict.fromkeys(category_ids))
    active = db.query(Category).filter(Category.id.in_(ids), Category.is_active.is_(True)).count()
    if not ids or len(ids) != active:
        raise ApiError("invalid_categories", "Selecione ao menos uma categoria ativa.", 422)
    return ids


@router.post("/tourist-spots", status_code=status.HTTP_201_CREATED)
def create_spot(
    payload: TouristSpotCreate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    categories = valid_categories(db, payload.category_ids)
    spot = TouristSpot(
        name=payload.name,
        description=payload.description,
        latitude=payload.latitude,
        longitude=payload.longitude,
        tolerance_radius_m=payload.tolerance_radius_m,
        status=SpotStatus.open,
        address=payload.address,
        image_url=str(payload.image_url) if payload.image_url else None,
        duration_minutes=payload.duration_minutes,
    )
    db.add(spot)
    db.flush()
    for category_id in categories:
        db.add(SpotCategory(spot_id=spot.id, category_id=category_id))
    record_audit(db, AuditLog, actor_id=claims["sub"], action="create_spot",
                 entity="tourist_spot", entity_id=spot.id, payload={"name": payload.name})
    log_event(logging.getLogger("catalog"), "spot_created", spot_id=spot.id, actor_id=claims["sub"])
    # RF37: inscritos nas categorias do ponto recebem notificação (fire-and-forget)
    if payload.category_ids:
        dispatch(db=db, kind="new_spot", source_id=spot.id, title=spot.name, body=spot.description,
                 category_ids=categories, payload={"tourist_spot_id": spot.id})
    _index_spot(db, spot)
    db.commit()
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
    for field in ("name", "description", "latitude", "longitude", "tolerance_radius_m", "address"):
        value = getattr(payload, field, None)
        if value is not None:
            setattr(spot, field, value)
    for field in ("image_url", "duration_minutes"):
        if field in payload.model_fields_set:
            value = getattr(payload, field)
            setattr(spot, field, str(value) if field == "image_url" and value else value)
    if payload.category_ids is not None:
        categories = valid_categories(db, payload.category_ids)
        db.query(SpotCategory).filter(SpotCategory.spot_id == spot_id).delete()
        for category_id in categories:
            db.add(SpotCategory(spot_id=spot_id, category_id=category_id))
    record_audit(db, AuditLog, actor_id=claims["sub"], action="update_spot",
                 entity="tourist_spot", entity_id=spot_id)
    _index_spot(db, spot)
    db.commit()
    return {"id": spot.id, "name": spot.name, "status": spot.status.value}


@router.delete("/tourist-spots/{spot_id}", status_code=204)
def remove_spot(spot_id: str, claims: dict = Depends(require_admin), db: Session = Depends(get_db)) -> None:
    """Remoção lógica (RF12): rotas ativas não quebram (edge case da spec)."""
    spot = _spot_query(db).filter(TouristSpot.id == spot_id).first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    spot.is_removed = True
    _hide_spot_from_routes(db, spot.id)
    record_audit(db, AuditLog, actor_id=claims["sub"], action="remove_spot",
                 entity="tourist_spot", entity_id=spot_id)
    _index_spot(db, spot, operation="delete")
    db.commit()


@router.put("/tourist-spots/{spot_id}/schedule")
def set_schedule(
    spot_id: str,
    payload: ScheduleUpdate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    spot = _spot_query(db).filter(TouristSpot.id == spot_id).with_for_update().first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    existing = sorted(
        (row.day_of_week, row.opens_at, row.closes_at)
        for row in db.query(OpeningSchedule).filter(OpeningSchedule.spot_id == spot_id).all()
    )
    rows = sorted((row.day_of_week, row.opens_at or "", row.closes_at or "") for row in payload.schedule)
    _validate_schedule(rows)
    response = {"id": spot_id, "schedule": payload.model_dump()["schedule"]}
    if rows == existing:
        return response
    db.query(OpeningSchedule).filter(OpeningSchedule.spot_id == spot_id).delete()
    for day, opens, closes in rows:
        db.add(
            OpeningSchedule(
                spot_id=spot_id,
                day_of_week=day, opens_at=opens, closes_at=closes,
            )
        )
    record_audit(db, AuditLog, actor_id=claims["sub"], action="set_schedule",
                 entity="tourist_spot", entity_id=spot_id)
    _index_spot(db, spot)
    db.commit()
    return response


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
    if spot.status == SpotStatus.permanently_closed:
        _hide_spot_from_routes(db, spot.id)
    record_audit(db, AuditLog, actor_id=claims["sub"], action="set_status",
                 entity="tourist_spot", entity_id=spot_id, payload={"status": payload.status.value})
    _index_spot(db, spot, operation="delete" if spot.status == SpotStatus.permanently_closed else "upsert")
    db.commit()
    return {"id": spot.id, "status": spot.status.value}


@router.get("/admin/tourist-spots/{spot_id}", dependencies=[Depends(require_admin)])
def get_spot_admin(spot_id: str, db: Session = Depends(get_db)) -> dict:
    spot = _spot_query(db).filter(TouristSpot.id == spot_id).first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    return spot_detail(db, spot, public=False).model_dump()


@router.get("/admin/tourist-spots", dependencies=[Depends(require_admin)])
def list_spots_admin(db: Session = Depends(get_db)) -> dict:
    return {"items": [spot_detail(db, spot, public=False).model_dump()
                      for spot in _spot_query(db).order_by(TouristSpot.name)]}
