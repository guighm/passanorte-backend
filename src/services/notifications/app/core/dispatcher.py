"""Disparo de notificações consumido do barramento (catalog/gamification → notifications) — T056.

Função pura com session explícita (testes e o consumer chamam direto).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from services.notifications.app.models.notification import Notification, NotificationSubscription
from shared.db import service_session_factory
from shared.errors import ApiError
from shared.logging import log_event

logger = logging.getLogger("notifications")

KINDS = ("new_event", "new_spot", "new_route")


def apply_dispatch(db: Session, payload: dict) -> dict:
    """Disparo fire-and-forget (D-05): notifica inscritos da categoria ou usuários
    diretos; idempotente por (user, kind, source_id); sem inscritos → no-op (RF37)."""
    kind = payload["kind"]
    if kind not in KINDS:
        raise ApiError(code="invalid_kind", message="Tipo de notificação inválido.", status_code=422)
    source_id = payload["source_id"]

    if payload.get("user_ids"):
        targets = list(dict.fromkeys(payload["user_ids"]))
        category_id = None
    elif payload.get("category_id"):
        category_id = payload["category_id"]
        targets = [
            row.user_id
            for row in db.query(NotificationSubscription)
            .filter(NotificationSubscription.category_id == category_id)
            .all()
        ]
    else:
        return {"notified": 0}

    notified = 0
    for user_id in targets:
        existing = (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.kind == kind, Notification.source_id == source_id)
            .first()
        )
        if existing is not None:
            continue  # retry idempotente (D-05)
        db.add(
            Notification(
                user_id=user_id,
                category_id=category_id,
                kind=kind,
                source_id=source_id,
                title=payload["title"],
                body=payload.get("body"),
                payload_json=str(payload["payload"]) if payload.get("payload") else None,
            )
        )
        notified += 1
    db.commit()
    log_event(logger, "dispatch_done", kind=kind, source_id=source_id, notified=notified)
    return {"notified": notified}


def handle_dispatch(data: dict) -> None:
    db = service_session_factory()()
    try:
        apply_dispatch(db, data)
    finally:
        db.close()
