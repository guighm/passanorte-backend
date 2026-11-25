"""Endpoints internos do serviço validation (outros microsserviços) — T037."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from services.validation.app.core.deps import get_db
from services.validation.app.core.propagator import get_propagator

router = APIRouter(tags=["internal"])


@router.post("/internal/visits/propagate", status_code=202)
def propagate_visit(
    fact: dict,
    propagate: Callable = Depends(get_propagator),
    db: Session = Depends(get_db),
) -> dict:
    """Repropaga um fato de visita (idempotente no alvo por user+spot+data, D-05)."""
    payload = {
        "user_id": fact["user_id"],
        "tourist_spot_id": fact["tourist_spot_id"],
        "occurred_at": fact.get("occurred_at"),
    }
    result = propagate(payload, db=db) if propagate is get_propagator() else propagate(payload)
    db.commit()
    return {"propagated": result}
