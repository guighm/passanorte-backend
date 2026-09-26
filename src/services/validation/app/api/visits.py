"""Endpoints de marcação de visitação (RF31–RF33) — T036."""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from services.validation.app.core.deps import get_catalog_snapshot, get_current_user, get_db
from services.validation.app.core.haversine import haversine_m
from services.validation.app.core.propagator import get_propagator
from services.validation.app.models.visit import Visit, VisitStatus
from shared.errors import ApiError
from shared.logging import log_event

router = APIRouter(tags=["visits"])
logger = logging.getLogger("validation")


class VisitCreate(BaseModel):
    tourist_spot_id: str
    latitude: float | None = None
    longitude: float | None = None


def _validated_visit(db: Session, user_id: str, spot_id: str) -> Visit | None:
    return (
        db.query(Visit)
        .filter(Visit.user_id == user_id, Visit.tourist_spot_id == spot_id,
                Visit.status == VisitStatus.validated)
        .first()
    )


def _status_value(status_: VisitStatus | str) -> str:
    # coluna é String: após reload a linha pode voltar como str puro
    return status_.value if isinstance(status_, VisitStatus) else str(status_)


def _serialise(visit: Visit) -> dict:
    return {
        "id": visit.id,
        "user_id": visit.user_id,
        "tourist_spot_id": visit.tourist_spot_id,
        "status": _status_value(visit.status),
        "distance_m": float(visit.distance_m),
        "occurred_at": str(visit.occurred_at),
    }


@router.post("/visits", status_code=status.HTTP_201_CREATED)
def mark_visit(
    payload: VisitCreate,
    claims: dict = Depends(get_current_user),
    snapshot_for: Callable = Depends(get_catalog_snapshot),
    propagate: Callable = Depends(get_propagator),
    db: Session = Depends(get_db),
) -> dict:
    """Marcar visitação: Haversine contra o raio do ponto (RF31–RF33, D-10)."""
    if claims.get("role") != "tourist":
        raise ApiError(code="forbidden", message="Apenas turistas registram visitações.", status_code=403)
    if payload.latitude is None or payload.longitude is None:
        raise ApiError(
            code="gps_unavailable",
            message="Leitura de GPS indisponível ou inválida.",
            status_code=422,
        )

    existing = _validated_visit(db, claims["sub"], payload.tourist_spot_id)
    if existing is not None:
        # idempotência: par (user, spot) validado é único (FR-019)
        return JSONResponse(status_code=200, content={**_serialise(existing), "tolerance_m": None})

    spot = snapshot_for(payload.tourist_spot_id)
    tolerance_m = float(spot["tolerance_radius_m"])
    distance_m = haversine_m(payload.latitude, payload.longitude, float(spot["latitude"]), float(spot["longitude"]))

    if distance_m <= tolerance_m:
        visit = Visit(
            user_id=claims["sub"],
            tourist_spot_id=payload.tourist_spot_id,
            user_latitude=payload.latitude,
            user_longitude=payload.longitude,
            distance_m=distance_m,
            status=VisitStatus.validated,
        )
        db.add(visit)
        db.flush()
        db.commit()
        log_event(logger, "visit_validated", user_id=claims["sub"], spot_id=payload.tourist_spot_id,
                  distance_m=round(distance_m, 2))
        # propagação tolerante a falhas (D-05): insights + gamification
        propagate(
            {
                "user_id": claims["sub"],
                "tourist_spot_id": payload.tourist_spot_id,
                "occurred_at": str(visit.occurred_at),
            }
        )
        return {
            "id": visit.id,
            "tourist_spot_id": visit.tourist_spot_id,
            "status": visit.status.value,
            "distance_m": round(distance_m, 2),
            "tolerance_m": tolerance_m,
            "occurred_at": str(visit.occurred_at),
        }

    # fora do raio: registrado apenas para auditoria, não conta como visita (RF33)
    db.add(
        Visit(
            user_id=claims["sub"],
            tourist_spot_id=payload.tourist_spot_id,
            user_latitude=payload.latitude,
            user_longitude=payload.longitude,
            distance_m=distance_m,
            status=VisitStatus.rejected,
        )
    )
    db.commit()
    log_event(logger, "visit_rejected", user_id=claims["sub"], spot_id=payload.tourist_spot_id,
              distance_m=round(distance_m, 2))
    return JSONResponse(
        status_code=422,
        content={"status": "rejected", "distance_m": round(distance_m, 2), "tolerance_m": tolerance_m},
    )


@router.get("/visits")
def list_visits(
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    visits = (
        db.query(Visit)
        .filter(Visit.user_id == claims["sub"], Visit.status == VisitStatus.validated)
        .all()
    )
    items = [_serialise(v) for v in visits]
    return {"items": items, "total": len(items)}


@router.get("/visits/{spot_id}")
def get_visit(
    spot_id: str,
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    visit = _validated_visit(db, claims["sub"], spot_id)
    if visit is None:
        raise ApiError(code="not_found", message="Visitação não encontrada.", status_code=404)
    return _serialise(visit)
