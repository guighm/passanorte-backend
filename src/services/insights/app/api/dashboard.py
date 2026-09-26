"""Dashboard de insights (RF06–RF10) — T051.

Agregações SQL sobre os fatos locais; consulta nunca sai do banco do serviço
(Princípio I) e sem cache distribuído (Princípio VII).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from services.insights.app.core.deps import get_db, require_role
from services.insights.app.models.facts import AccessLog, VisitFact

router = APIRouter(tags=["dashboard"])

require_admin = require_role("admin")


@router.get("/heatmap")
def heatmap(
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Mapa de calor: concentração de visitas por ponto (RF06)."""
    rows = (
        db.query(
            VisitFact.tourist_spot_id,
            func.max(VisitFact.spot_name),
            func.max(VisitFact.spot_latitude),
            func.max(VisitFact.spot_longitude),
            func.count(VisitFact.id),
        )
        .group_by(VisitFact.tourist_spot_id)
        .all()
    )
    total = sum(row[4] for row in rows) or 1
    items = [
        {
            "tourist_spot_id": spot_id,
            "name": name,
            "lat": float(lat) if lat is not None else None,
            "lng": float(lng) if lng is not None else None,
            "visit_count": count,
            "weight": round(count / total, 4),
        }
        for spot_id, name, lat, lng, count in rows
    ]
    return {"items": items, "total": len(items)}


def _period_range(period: str, from_: str | None, to: str | None) -> list[tuple[datetime, datetime]]:
    from shared.errors import ApiError

    now = datetime.now(UTC)
    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return [(start, start + timedelta(days=1))]
    if period == "week":
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return [(start, now + timedelta(days=1))]
    if period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return [(start, now + timedelta(days=1))]
    if period == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return [(start, now + timedelta(days=1))]
    if period == "custom":
        if not from_ or not to:
            raise ApiError(code="invalid_period", message="Período custom exige 'from' e 'to'.", status_code=422)
        return [(datetime.fromisoformat(from_), datetime.fromisoformat(to))]
    raise ApiError(code="invalid_period", message="Período inválido.", status_code=422)


@router.get("/accesses")
def accesses(
    period: str = Query(default="day", pattern="^(day|week|month|year|custom)$"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None, alias="to"),
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Contador de acessos por período (RF07)."""
    from shared.errors import ApiError

    try:
        ranges = _period_range(period, from_, to)
    except ValueError:
        raise ApiError(code="invalid_period", message="Período inválido.", status_code=422) from None

    by_period = []
    total = 0
    for start, end in ranges:
        count = db.query(func.count(AccessLog.id)).filter(
            AccessLog.occurred_at >= start, AccessLog.occurred_at < end
        ).scalar()
        by_period.append({"period": period, "start": start.isoformat(), "count": int(count)})
        total += int(count)
    return {"total": total, "by_period": by_period}


@router.get("/rankings/tourist-spots")
def ranking(
    segment: str = Query(default="month", pattern="^(day|month|year)$"),
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Ranking de pontos mais visitados no segmento (RF08)."""
    now = datetime.now(UTC)
    if segment == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif segment == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(VisitFact.tourist_spot_id, func.count(VisitFact.id))
        .filter(VisitFact.occurred_at >= start)
        .group_by(VisitFact.tourist_spot_id)
        .order_by(func.count(VisitFact.id).desc())
        .all()
    )
    items = [{"tourist_spot_id": spot_id, "visit_count": int(count)} for spot_id, count in rows]
    return {"segment": segment, "items": items}


def _split_interests(interests_csv: str | None) -> list[str]:
    return [i for i in (interests_csv or "").split(",") if i]


@router.get("/distributions/country-of-origin")
def country_distribution(claims: dict = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    """Proporção de visitantes por país (RF09) — snapshot sem PII (RNF08)."""
    rows = (
        db.query(VisitFact.country_of_origin, func.count(VisitFact.id))
        .filter(VisitFact.country_of_origin.isnot(None))
        .group_by(VisitFact.country_of_origin)
        .all()
    )
    total = sum(int(count) for _, count in rows) or 1
    items = [
        {"country_of_origin": country, "count": int(count), "share": round(int(count) / total, 4)}
        for country, count in rows
    ]
    return {"items": items, "total": len(items)}


@router.get("/distributions/interests")
def interests_distribution(claims: dict = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    """Proporção por interesses (RF10) — snapshot agregado (RNF08)."""
    facts = db.query(VisitFact.interests).all()
    counter: dict[str, int] = {}
    for (interests_csv,) in facts:
        for interest in set(_split_interests(interests_csv)):
            counter[interest] = counter.get(interest, 0) + 1
    total = sum(counter.values()) or 1
    items = [
        {"interest": interest, "count": count, "share": round(count / total, 4)}
        for interest, count in sorted(counter.items(), key=lambda kv: -kv[1])
    ]
    return {"items": items, "total": len(items)}
