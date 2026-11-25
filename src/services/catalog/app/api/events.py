"""Endpoints administrativos de eventos e categorias (RF15/RF29) — T029."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import AliasChoices, BaseModel, Field
from sqlalchemy.orm import Session

from services.catalog.app.api.spots import _spot_query
from services.catalog.app.core.deps import get_db, require_role
from services.catalog.app.core.discovery import event_body, event_time, upcoming
from services.catalog.app.models.audit import AuditLog
from services.catalog.app.models.spot import Event, SpotCategory, SpotStatus, TouristSpot
from shared.audit import record_audit
from shared.chatbot_client import refresh_index
from shared.errors import ApiError
from shared.notifications_client import dispatch

router = APIRouter(tags=["events (admin)"])
development_router = APIRouter(tags=["internal"])

require_admin = require_role("admin")


class EventCreate(BaseModel):
    tourist_spot_id: str
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=2000)
    starts_at: datetime = Field(validation_alias=AliasChoices("starts_at", "occurs_at"))
    ends_at: datetime | None = None
    ticket_price: float = Field(ge=0, description="preço não pode ser negativo (RF15)")


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    starts_at: datetime | None = Field(default=None, validation_alias=AliasChoices("starts_at", "occurs_at"))
    ends_at: datetime | None = None
    ticket_price: float | None = Field(default=None, ge=0)


class NotifySubscribersPayload(BaseModel):
    event_id: str


@router.get("/events")
def list_events(
    tourist_spot_id: str | None = None,
    from_date: datetime | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Lista pública de eventos com filtros por ponto e data (RF16)."""
    query = db.query(Event).join(TouristSpot).filter(
        upcoming(), TouristSpot.is_removed.is_(False), TouristSpot.status != SpotStatus.permanently_closed,
    ).order_by(Event.occurs_at, Event.id)
    if tourist_spot_id:
        query = query.filter(Event.tourist_spot_id == tourist_spot_id)
    if from_date:
        query = query.filter(Event.occurs_at >= event_time(from_date))
    return {"items": [event_body(event) for event in query]}


@router.get("/admin/events", dependencies=[Depends(require_admin)])
def list_events_admin(db: Session = Depends(get_db)) -> dict:
    return {"items": [event_body(event) for event in db.query(Event).order_by(Event.occurs_at, Event.id)]}


def _index_event(db: Session, event: Event, *, operation: str = "upsert") -> None:
    spot = db.get(TouristSpot, event.tourist_spot_id)
    if spot is None or spot.is_removed or spot.status == SpotStatus.permanently_closed:
        operation = "delete"
    refresh_index([{
        **event_body(event), "source_type": "event", "source_id": event.id,
        "spot_id": event.tourist_spot_id, "operation": operation,
    }], db=db)


def _validate_period(start: datetime, end: datetime | None) -> None:
    if end is not None and end <= start:
        raise ApiError("invalid_event_period", "O fim precisa ser posterior ao início.", 422)


def _load_spot(db: Session, spot_id: str) -> TouristSpot:
    spot = _spot_query(db).filter(TouristSpot.id == spot_id).first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    return spot


@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    _load_spot(db, payload.tourist_spot_id)
    start = event_time(payload.starts_at)
    end = event_time(payload.ends_at) if payload.ends_at else None
    _validate_period(start, end)
    event = Event(
        tourist_spot_id=payload.tourist_spot_id,
        title=payload.title,
        description=payload.description,
        occurs_at=start,
        ends_at=end,
        ticket_price=payload.ticket_price,
    )
    db.add(event)
    db.flush()
    record_audit(db, AuditLog, actor_id=claims["sub"], action="create_event",
                 entity="event", entity_id=event.id, payload={"title": payload.title})
    # RF37: inscritos nas categorias do ponto recebem notificação (fire-and-forget)
    spot_categories = [
        row.category_id for row in db.query(SpotCategory).filter(SpotCategory.spot_id == payload.tourist_spot_id).all()
    ]
    dispatch(db=db, kind="new_event", source_id=event.id, title=payload.title,
             body=payload.description, category_ids=spot_categories,
             payload={"event_id": event.id, "tourist_spot_id": payload.tourist_spot_id})
    # D-08: rebuild do embedding do evento no chatbot (fire-and-forget)
    _index_event(db, event)
    db.commit()
    return event_body(event)


@router.patch("/events/{event_id}")
def update_event(
    event_id: str,
    payload: EventUpdate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    event = db.query(Event).filter(Event.id == event_id).with_for_update().first()
    if event is None:
        raise ApiError(code="not_found", message="Evento não encontrado.", status_code=404)
    for field in ("title", "description", "ticket_price"):
        value = getattr(payload, field)
        if value is not None:
            setattr(event, field, value)
    if payload.starts_at is not None or "ends_at" in payload.model_fields_set:
        start = event_time(payload.starts_at) if payload.starts_at is not None else event.occurs_at
        end = event.ends_at
        if "ends_at" in payload.model_fields_set:
            end = event_time(payload.ends_at) if payload.ends_at else None
        _validate_period(start, end)
        event.occurs_at, event.ends_at = start, end
    record_audit(db, AuditLog, actor_id=claims["sub"], action="update_event",
                 entity="event", entity_id=event.id)
    _index_event(db, event)
    db.commit()
    return event_body(event)


@router.delete("/events/{event_id}", status_code=204)
def remove_event(event_id: str, claims: dict = Depends(require_admin), db: Session = Depends(get_db)) -> None:
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise ApiError(code="not_found", message="Evento não encontrado.", status_code=404)
    _index_event(db, event, operation="delete")
    db.delete(event)
    record_audit(db, AuditLog, actor_id=claims["sub"], action="remove_event",
                 entity="event", entity_id=event_id)
    db.commit()


@development_router.post("/internal/events/notify-subscribers", status_code=202)
def notify_subscribers(
    payload: NotifySubscribersPayload, db: Session = Depends(get_db)
) -> dict:
    """Gatilho re-executável: notifica inscritos nas categorias do ponto do evento (RF37, D-05).

    O create_event já dispara diretamente; este endpoint permite reenvio
    idempotente (a dedup por (user, kind, source_id) fica no notifications).
    """
    event = db.query(Event).filter(Event.id == payload.event_id).first()
    if event is None:
        raise ApiError(code="not_found", message="Evento não encontrado.", status_code=404)
    spot_categories = [
        row.category_id
        for row in db.query(SpotCategory).filter(SpotCategory.spot_id == event.tourist_spot_id).all()
    ]
    dispatch(
        db=db,
        kind="new_event",
        source_id=event.id,
        title=event.title,
        body=event.description,
        category_ids=spot_categories,
        payload={"event_id": event.id, "tourist_spot_id": event.tourist_spot_id},
    )
    db.commit()
    return {"event_id": event.id, "categories": len(spot_categories)}
