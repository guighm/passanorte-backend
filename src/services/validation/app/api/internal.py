"""Endpoints internos do serviço validation (outros microsserviços) — T037."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends

from services.validation.app.core.propagator import get_propagator

router = APIRouter(tags=["internal"])


@router.post("/internal/visits/propagate", status_code=202)
def propagate_visit(
    fact: dict,
    propagate: Callable = Depends(get_propagator),
) -> dict:
    """Repropaga um fato de visita (idempotente no alvo por user+spot+data, D-05)."""
    result = propagate(
        {
            "user_id": fact["user_id"],
            "tourist_spot_id": fact["tourist_spot_id"],
            "occurred_at": fact.get("occurred_at"),
        }
    )
    return {"propagated": result}
