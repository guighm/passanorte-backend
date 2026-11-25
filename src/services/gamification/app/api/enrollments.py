"""Inscrição e progresso derivado de rotas (RF29/RF30, D-13) — T044."""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from services.gamification.app.core.completion import complete_route
from services.gamification.app.core.deps import (
    get_auth_header,
    get_db,
    get_route_lookup,
    get_validated_visits,
    require_role,
)
from services.gamification.app.models.enrollment import (
    Badge,
    EnrollmentStatus,
    RedeemCode,
    RouteEnrollment,
)
from shared.errors import ApiError
from shared.internal_client import RouteSnapshot
from shared.logging import log_event

router = APIRouter(tags=["enrollments"])

logger = logging.getLogger("gamification")


def _derive_progress(route: RouteSnapshot, visited: set[str]) -> dict:
    active_points = route.points
    visited_points = [spot for spot in active_points if spot in visited]
    pending = [spot for spot in active_points if spot not in visited]
    percent = round(100.0 * len(visited_points) / len(active_points), 2) if active_points else 0.0
    return {"visited": visited_points, "pending": pending, "percent": percent}



def _check_completion(db: Session, enrollment: RouteEnrollment, route: RouteSnapshot, body: dict) -> dict:
    """Conclusão derivada: percent 100% emite insígnia + código idempotentes (RF35/RF36)."""
    if body["percent"] == 100.0 and enrollment.status == EnrollmentStatus.in_progress:
        result = complete_route(db, user_id=enrollment.user_id, route_id=route.id, prize_id=route.prize_id)
        enrollment.status = EnrollmentStatus.completed
        enrollment.completed_at = __import__("datetime").datetime.now(__import__("datetime").UTC)
        db.commit()
        body["status"] = "completed"
        body["redeem_code"] = result["code"]
        body["badge_awarded"] = True
    return body

def _enrollment_body(db: Session, enrollment: RouteEnrollment, validated: set[str], route: RouteSnapshot) -> dict:
    progress = _derive_progress(route, validated)
    badge = db.query(Badge).filter(Badge.user_id == enrollment.user_id, Badge.route_id == route.id).first()
    code = (
        db.query(RedeemCode).filter(RedeemCode.user_id == enrollment.user_id, RedeemCode.route_id == route.id).first()
    )
    return {
        "id": enrollment.id,
        "route_id": route.id,
        "route_name": route.name,
        "status": _status_value(enrollment.status),
        **progress,
        "badge_awarded": badge is not None,
        "redeem_code": code.code if code else None,
    }


def _status_value(status_: object) -> str:
    return status_.value if isinstance(status_, EnrollmentStatus) else str(status_)


@router.post("/routes/{route_id}/enrollments", status_code=201)
def enroll(
    route_id: str,
    claims: dict = Depends(require_role("tourist")),
    auth_header: str = Depends(get_auth_header),
    validated_for: Callable = Depends(get_validated_visits),
    lookup: Callable = Depends(get_route_lookup),
    db: Session = Depends(get_db),
) -> dict:
    route = lookup(route_id)
    if route is None or not route.is_active:
        raise ApiError(code="not_found", message="Rota não encontrada.", status_code=404)
    existing = (
        db.query(RouteEnrollment).filter(RouteEnrollment.user_id == claims["sub"], RouteEnrollment.route_id == route_id)
        .first()
    )
    if existing is not None:
        raise ApiError(code="already_enrolled", message="Você já está inscrito nesta rota.", status_code=409)

    enrollment = RouteEnrollment(user_id=claims["sub"], route_id=route_id)
    db.add(enrollment)
    db.flush()
    db.commit()
    log_event(logger, "route_enrolled", user_id=claims["sub"], route_id=route_id)

    # progresso é DERIVADO (D-13): visitas anteriores à inscrição contam
    validated = set(validated_for(auth_header))
    body = _enrollment_body(db, enrollment, validated, route)

    # conclusão imediata (retroativa, D-13)
    return _check_completion(db, enrollment, route, body)


@router.get("/enrollments")
def list_enrollments(
    claims: dict = Depends(require_role("tourist")),
    auth_header: str = Depends(get_auth_header),
    validated_for: Callable = Depends(get_validated_visits),
    lookup: Callable = Depends(get_route_lookup),
    db: Session = Depends(get_db),
) -> dict:
    enrollments = db.query(RouteEnrollment).filter(RouteEnrollment.user_id == claims["sub"]).all()
    validated = set(validated_for(auth_header))
    items = []
    for enrollment in enrollments:
        route = require_enrolled_route(lookup, enrollment.route_id)
        items.append(_check_completion(db, enrollment, route, _enrollment_body(db, enrollment, validated, route)))
    return {"items": items, "total": len(items)}


@router.get("/enrollments/{route_id}")
def get_enrollment(
    route_id: str,
    claims: dict = Depends(require_role("tourist")),
    auth_header: str = Depends(get_auth_header),
    validated_for: Callable = Depends(get_validated_visits),
    lookup: Callable = Depends(get_route_lookup),
    db: Session = Depends(get_db),
) -> dict:
    enrollment = (
        db.query(RouteEnrollment).filter(RouteEnrollment.user_id == claims["sub"], RouteEnrollment.route_id == route_id)
        .first()
    )
    if enrollment is None:
        raise ApiError(code="not_found", message="Inscrição não encontrada.", status_code=404)
    validated = set(validated_for(auth_header))
    route = require_enrolled_route(lookup, route_id)
    return _check_completion(db, enrollment, route, _enrollment_body(db, enrollment, validated, route))


def require_enrolled_route(lookup: Callable, route_id: str) -> RouteSnapshot:
    route: RouteSnapshot | None = lookup(route_id)
    if route is None:
        raise ApiError(code="route_unavailable", message="Definição de rota indisponível.", status_code=503)
    return route
