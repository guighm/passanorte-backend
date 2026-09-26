"""Ingest interno de fatos (validation/auth → insights, D-05) — T050."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from services.insights.app.core.deps import get_db
from services.insights.app.models.facts import AccessLog, VisitFact
from shared.logging import log_event

router = APIRouter(tags=["internal"])
logger = logging.getLogger("insights")


def _parse_ts(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@router.post("/internal/visit-facts", status_code=status.HTTP_201_CREATED)
def ingest_visit_fact(payload: dict, db: Session = Depends(get_db)) -> dict:
    """Ingest idempotente de fato de visita (D-05): dedup por (user, spot, momento)."""
    occurred_at = _parse_ts(payload.get("occurred_at"))
    existing = (
        db.query(VisitFact)
        .filter(
            VisitFact.user_id == payload["user_id"],
            VisitFact.tourist_spot_id == payload["tourist_spot_id"],
            VisitFact.occurred_at == occurred_at,
        )
        .first()
    )
    if existing is not None:
        return {"id": existing.id, "status": "already_ingested"}

    fact = VisitFact(
        user_id=payload["user_id"],
        tourist_spot_id=payload["tourist_spot_id"],
        spot_name=payload.get("spot_name"),
        spot_latitude=payload.get("latitude"),
        spot_longitude=payload.get("longitude"),
        region_hint=payload.get("region_hint"),
        country_of_origin=payload.get("country_of_origin"),
        interests=",".join(payload["interests"]) if payload.get("interests") else None,
        occurred_at=occurred_at,
    )
    db.add(fact)
    db.commit()
    log_event(logger, "visit_fact_ingested", user_id=payload["user_id"], spot_id=payload["tourist_spot_id"])
    return {"id": fact.id, "status": "ingested"}


@router.post("/internal/accesses", status_code=status.HTTP_201_CREATED)
def ingest_access(payload: dict, db: Session = Depends(get_db)) -> dict:
    """Registro de acesso à aplicação (RF07)."""
    access = AccessLog(user_id=payload["user_id"], client=payload.get("client"))
    db.add(access)
    db.commit()
    log_event(logger, "access_ingested", user_id=payload["user_id"])
    return {"id": access.id, "status": "ingested"}
