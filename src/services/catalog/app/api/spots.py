"""Endpoints de leitura do catálogo (RF26/RF27/RF28) — T020."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from services.catalog.app.core.deps import get_db, get_optional_user
from services.catalog.app.core.links import build_external_links
from services.catalog.app.models.spot import (
    Category,
    Event,
    OpeningSchedule,
    SpotCategory,
    SpotStatus,
    TouristSpot,
)
from services.catalog.app.schemas.catalog_schemas import (
    CategoryOut,
    ExternalLinksOut,
    TouristSpotDetail,
    TouristSpotList,
    TouristSpotOut,
)
from shared.errors import ApiError
from shared.insights_client import notify_access

router = APIRouter(tags=["tourist-spots"])


def _categories_for(db: Session, spot_id: str) -> list[CategoryOut]:
    rows = db.query(SpotCategory).filter(SpotCategory.spot_id == spot_id).all()
    ids = [row.category_id for row in rows]
    cats = {c.id: c for c in db.query(Category).filter(Category.id.in_(ids)).all()} if ids else {}
    return [CategoryOut(id=row.category_id, name=cats[row.category_id].name) for row in rows if row.category_id in cats]


def _spot_query(db: Session):
    return db.query(TouristSpot).filter(TouristSpot.is_removed.is_(False))


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine em km para ordenação por proximidade (RF26)."""
    import math

    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)) -> dict:
    cats = db.query(Category).filter(Category.is_active.is_(True)).all()
    return {"items": [{"id": c.id, "name": c.name} for c in cats]}


@router.get("/tourist-spots", response_model=TouristSpotList)
def list_spots(
    category: str | None = None,
    status: str | None = None,
    lat: str | None = None,
    lng: str | None = None,
    interests: str | None = Query(default=None, description="ids de interesses do usuário (RF26)"),
    claims_user: dict | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> TouristSpotList:
    query = _spot_query(db)
    if claims_user:
        notify_access(claims_user.get("sub"))  # RF07: acesso registrado no insights (D-05)
    if status:
        query = query.filter(TouristSpot.status == SpotStatus(status))
    if category:
        query = query.join(SpotCategory).filter(SpotCategory.category_id == category)
    spots = query.all()

    if lat is not None and lng is not None:
        spots.sort(key=lambda s: haversine_km(float(lat), float(lng), float(s.latitude), float(s.longitude)))

    items = [
        TouristSpotOut(
            id=s.id,
            name=s.name,
            description=s.description,
            latitude=float(s.latitude),
            longitude=float(s.longitude),
            status=s.status.value,
            categories=_categories_for(db, s.id),
        )
        for s in spots
    ]
    return TouristSpotList(items=items, total=len(items))


@router.get("/tourist-spots/{spot_id}", response_model=TouristSpotDetail)
def get_spot(spot_id: str, db: Session = Depends(get_db)) -> TouristSpotDetail:
    spot = _spot_query(db).filter(TouristSpot.id == spot_id).first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    schedule = [
        {"day_of_week": row.day_of_week, "opens_at": row.opens_at, "closes_at": row.closes_at}
        for row in db.query(OpeningSchedule).filter(OpeningSchedule.spot_id == spot_id).all()
    ]
    events = [
        {
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "occurs_at": str(e.occurs_at),
            "ticket_price": float(e.ticket_price),
        }
        for e in db.query(Event).filter(Event.tourist_spot_id == spot_id).all()
    ]
    return TouristSpotDetail(
        id=spot.id,
        name=spot.name,
        description=spot.description,
        latitude=float(spot.latitude),
        longitude=float(spot.longitude),
        status=spot.status.value,
        tolerance_radius_m=spot.tolerance_radius_m,
        categories=_categories_for(db, spot.id),
        schedule=schedule,
        events=events,
    )


@router.get("/tourist-spots/{spot_id}/external-links", response_model=ExternalLinksOut)
def get_external_links(spot_id: str, db: Session = Depends(get_db)) -> ExternalLinksOut:
    spot = _spot_query(db).filter(TouristSpot.id == spot_id).first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    links = build_external_links(float(spot.latitude), float(spot.longitude), spot.name)
    return ExternalLinksOut(links=links)


# --- interno (outros serviços) — T030 ----------------------------------------

@router.post("/internal/tourist-spots", tags=["internal"], status_code=201)
def internal_create_spot(payload: dict, db: Session = Depends(get_db)) -> dict:
    """Seed interno de ponto turístico (usado por seed admin e testes)."""

    spot = TouristSpot(
        name=payload["name"],
        description=payload.get("description", ""),
        latitude=payload["latitude"],
        longitude=payload["longitude"],
        status=SpotStatus(payload.get("status", "open")),
        tolerance_radius_m=payload.get("tolerance_radius_m", 100),
    )
    db.add(spot)
    db.flush()
    for category_id in payload.get("category_ids", []):
        db.add(SpotCategory(spot_id=spot.id, category_id=category_id))
    db.commit()
    return {
        "id": spot.id,
        "name": spot.name,
        "status": spot.status.value,
        "latitude": float(spot.latitude),
        "longitude": float(spot.longitude),
    }


@router.get("/internal/tourist-spots", tags=["internal"])
def internal_list_spots(ids: str | None = None, db: Session = Depends(get_db)) -> dict:
    """Lista de pontos para feed/recomendação (RF26); filtro opcional por ids (CSV)."""
    query = _spot_query(db)
    if ids:
        wanted = [i for i in ids.split(",") if i]
        if not wanted:
            return {"items": []}
        query = query.filter(TouristSpot.id.in_(wanted))
    return {
        "items": [
            {
                "id": spot.id,
                "name": spot.name,
                "description": spot.description,
                "latitude": float(spot.latitude),
                "longitude": float(spot.longitude),
                "status": spot.status.value,
                "category_ids": [
                    row.category_id
                    for row in db.query(SpotCategory).filter(SpotCategory.spot_id == spot.id).all()
                ],
            }
            for spot in query.all()
        ]
    }


@router.get("/internal/tourist-spots/{spot_id}", tags=["internal"])
def internal_spot_snapshot(spot_id: str, db: Session = Depends(get_db)) -> dict:
    spot = _spot_query(db).filter(TouristSpot.id == spot_id).first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    category_ids = [
        row.category_id
        for row in db.query(SpotCategory).filter(SpotCategory.spot_id == spot_id).all()
    ]
    return {
        "id": spot.id,
        "name": spot.name,
        "latitude": float(spot.latitude),
        "longitude": float(spot.longitude),
        "tolerance_radius_m": spot.tolerance_radius_m,
        "status": spot.status.value,
        "category_ids": category_ids,
    }
