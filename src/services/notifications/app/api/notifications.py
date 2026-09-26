"""Inscrições por interesse e inbox (RF37, D-06) — T055."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from services.notifications.app.core.deps import get_db, require_role
from services.notifications.app.models.notification import Notification, NotificationSubscription
from shared.errors import ApiError

router = APIRouter(tags=["subscriptions"])

require_tourist = require_role("tourist")


class SubscriptionsUpdate(BaseModel):
    category_ids: list[str]


@router.put("/subscriptions")
def replace_subscriptions(
    payload: SubscriptionsUpdate,
    claims: dict = Depends(require_tourist),
    db: Session = Depends(get_db),
) -> dict:
    """Substitui inscrições por interesse (RF37)."""
    db.query(NotificationSubscription).filter(NotificationSubscription.user_id == claims["sub"]).delete()
    for category_id in dict.fromkeys(payload.category_ids):  # sem duplicatas
        db.add(NotificationSubscription(user_id=claims["sub"], category_id=category_id))
    db.commit()
    return {"category_ids": payload.category_ids}


@router.get("/subscriptions")
def list_subscriptions(claims: dict = Depends(require_tourist), db: Session = Depends(get_db)) -> dict:
    rows = db.query(NotificationSubscription).filter(NotificationSubscription.user_id == claims["sub"]).all()
    return {"category_ids": [row.category_id for row in rows]}


@router.get("/notifications")
def list_notifications(claims: dict = Depends(require_tourist), db: Session = Depends(get_db)) -> dict:
    """Caixa de entrada in-app ordenada por created_at (D-06)."""
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == claims["sub"])
        .order_by(Notification.created_at.desc())
        .all()
    )
    items = [_serialise(n) for n in rows]
    return {"items": items, "total": len(items)}


@router.patch("/notifications/{notification_id}/read")
def mark_read(
    notification_id: str,
    claims: dict = Depends(require_tourist),
    db: Session = Depends(get_db),
) -> dict:
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == claims["sub"])
        .first()
    )
    if notification is None:
        raise ApiError(code="not_found", message="Notificação não encontrada.", status_code=404)
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        db.commit()
    return _serialise(notification)


def _serialise(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "kind": notification.kind,
        "source_id": notification.source_id,
        "title": notification.title,
        "body": notification.body,
        "payload": notification.payload_json,
        "created_at": str(notification.created_at),
        "read_at": str(notification.read_at) if notification.read_at else None,
    }
