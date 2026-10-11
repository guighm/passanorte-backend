"""Ingestão de fatos consumidos do barramento (validation/auth → insights, D-05) — T050.

Funções puras com session explícita (testes e consumers chamam direto;
os handlers AMQP em `handle_*` abrem a sessão cacheada por processo).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from services.insights.app.models.facts import AccessLog, VisitFact
from shared.db import service_session_factory
from shared.logging import log_event

logger = logging.getLogger("insights")


def _parse_ts(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def ingest_visit_fact(db: Session, payload: dict) -> dict:
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


def ingest_access(db: Session, payload: dict) -> dict:
    """Registro de acesso à aplicação (RF07)."""
    access = AccessLog(user_id=payload["user_id"], client=payload.get("client"))
    db.add(access)
    db.commit()
    log_event(logger, "access_ingested", user_id=payload["user_id"])
    return {"id": access.id, "status": "ingested"}


def handle_visit_fact(data: dict) -> None:
    _consume(ingest_visit_fact, data)


def handle_access(data: dict) -> None:
    _consume(ingest_access, data)


def _consume(ingest_fn, data: dict) -> None:
    db = service_session_factory()()
    try:
        ingest_fn(db, data)
    finally:
        db.close()
