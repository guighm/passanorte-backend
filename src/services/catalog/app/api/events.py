"""Endpoints administrativos de eventos e categorias (RF15/RF29) — T029."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.catalog.app.api.spots import _spot_query
from services.catalog.app.core.deps import get_db, require_role
from services.catalog.app.models.audit import AuditLog
from services.catalog.app.models.spot import Category, Event, SpotCategory, TouristSpot
from shared.audit import record_audit
from shared.chatbot_client import refresh_index
from shared.errors import ApiError
from shared.notifications_client import dispatch

router = APIRouter(tags=["events (admin)"])

require_admin = require_role("admin")


class EventCreate(BaseModel):
    tourist_spot_id: str
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=2000)
    occurs_at: datetime
    ticket_price: float = Field(ge=0, description="preço não pode ser negativo (RF15)")


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    occurs_at: datetime | None = None
    ticket_price: float | None = Field(default=None, ge=0)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class NotifySubscribersPayload(BaseModel):
    event_id: str


@router.get("/events")
def list_events(
    tourist_spot_id: str | None = None,
    from_date: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Lista pública de eventos com filtros por ponto e data (RF16)."""
    query = db.query(Event).order_by(Event.occurs_at)
    if tourist_spot_id:
        query = query.filter(Event.tourist_spot_id == tourist_spot_id)
    if from_date:
        try:
            bound = datetime.fromisoformat(from_date)
        except ValueError:
            raise ApiError(code="invalid_filter", message="Data inválida (ISO 8601).", status_code=422) from None
        query = query.filter(Event.occurs_at >= bound)
    return {
        "items": [
            {
                "id": e.id,
                "tourist_spot_id": e.tourist_spot_id,
                "title": e.title,
                "description": e.description,
                "occurs_at": str(e.occurs_at),
                "ticket_price": float(e.ticket_price),
            }
            for e in query.all()
        ]
    }


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
    event = Event(
        tourist_spot_id=payload.tourist_spot_id,
        title=payload.title,
        description=payload.description,
        occurs_at=payload.occurs_at,
        ticket_price=payload.ticket_price,
    )
    db.add(event)
    db.flush()
    record_audit(db, AuditLog, actor_id=claims["sub"], action="create_event",
                 entity="event", entity_id=event.id, payload={"title": payload.title})
    db.commit()
    # RF37: inscritos nas categorias do ponto recebem notificação (fire-and-forget)
    spot_categories = [
        row.category_id for row in db.query(SpotCategory).filter(SpotCategory.spot_id == payload.tourist_spot_id).all()
    ]
    dispatch(kind="new_event", source_id=event.id, title=payload.title,
             body=payload.description, category_ids=spot_categories,
             payload={"event_id": event.id, "tourist_spot_id": payload.tourist_spot_id})
    # D-08: rebuild do embedding do evento no chatbot (fire-and-forget)
    refresh_index([
        {
            "source_type": "event",
            "source_id": event.id,
            "spot_id": event.tourist_spot_id,
            "title": event.title,
            "description": payload.description,
            "status": "open",
            "ticket_price": float(event.ticket_price),
            "occurs_at": str(event.occurs_at),
        }
    ])
    return {
        "id": event.id,
        "tourist_spot_id": event.tourist_spot_id,
        "title": event.title,
        "occurs_at": str(event.occurs_at),
        "ticket_price": float(event.ticket_price),
    }


@router.patch("/events/{event_id}")
def update_event(
    event_id: str,
    payload: EventUpdate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise ApiError(code="not_found", message="Evento não encontrado.", status_code=404)
    for field in ("title", "description", "occurs_at", "ticket_price"):
        value = getattr(payload, field)
        if value is not None:
            setattr(event, field, value)
    record_audit(db, AuditLog, actor_id=claims["sub"], action="update_event",
                 entity="event", entity_id=event.id)
    db.commit()
    return {
        "id": event.id,
        "title": event.title,
        "occurs_at": str(event.occurs_at),
        "ticket_price": float(event.ticket_price),
    }


@router.delete("/events/{event_id}", status_code=204)
def remove_event(event_id: str, claims: dict = Depends(require_admin), db: Session = Depends(get_db)) -> None:
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise ApiError(code="not_found", message="Evento não encontrado.", status_code=404)
    db.delete(event)
    record_audit(db, AuditLog, actor_id=claims["sub"], action="remove_event",
                 entity="event", entity_id=event_id)
    db.commit()


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if db.query(Category).filter(Category.name == payload.name).first() is not None:
        raise ApiError(code="duplicate_category", message="Categoria já existe.", status_code=409)
    category = Category(name=payload.name)
    db.add(category)
    db.flush()
    record_audit(db, AuditLog, actor_id=claims["sub"], action="create_category",
                 entity="category", entity_id=category.id, payload={"name": payload.name})
    db.commit()
    return {"id": category.id, "name": category.name}


@router.post("/internal/events/notify-subscribers", tags=["internal"], status_code=202)
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
        kind="new_event",
        source_id=event.id,
        title=event.title,
        body=event.description,
        category_ids=spot_categories,
        payload={"event_id": event.id, "tourist_spot_id": event.tourist_spot_id},
    )
    return {"event_id": event.id, "categories": len(spot_categories)}
