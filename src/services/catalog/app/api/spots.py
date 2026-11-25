"""Endpoints de leitura do catálogo (RF26/RF27/RF28) — T020."""

from __future__ import annotations

from collections.abc import Callable
from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from services.catalog.app.core.deps import get_db, get_optional_user
from services.catalog.app.core.discovery import deployment_timezone, event_body, get_interest_lookup, upcoming
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
development_router = APIRouter(tags=["internal"])


def _categories_for(db: Session, spot_id: str) -> list[CategoryOut]:
    return _categories_by_spot(db, [spot_id])[spot_id]


def _categories_by_spot(db: Session, spot_ids: list[str]) -> dict[str, list[CategoryOut]]:
    categories: dict[str, list[CategoryOut]] = {spot_id: [] for spot_id in spot_ids}
    rows = db.query(SpotCategory.spot_id, Category).join(
        Category, SpotCategory.category_id == Category.id,
    ).filter(SpotCategory.spot_id.in_(spot_ids)).order_by(Category.name, Category.id)
    for spot_id, category in rows:
        categories[spot_id].append(CategoryOut(id=category.id, name=category.name))
    return categories


def _spot_query(db: Session):
    return db.query(TouristSpot).filter(TouristSpot.is_removed.is_(False))


def _public_spots(db: Session):
    return _spot_query(db).filter(TouristSpot.status != SpotStatus.permanently_closed)


def _public_fields(spot: TouristSpot) -> dict:
    links = build_external_links(float(spot.latitude), float(spot.longitude), spot.name)
    return {
        "id": spot.id, "name": spot.name, "description": spot.description,
        "latitude": float(spot.latitude), "longitude": float(spot.longitude),
        "status": spot.status.value, "address": spot.address,
        "image_url": spot.image_url, "duration_minutes": spot.duration_minutes,
        "maps_url": links["google_maps"],
    }


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine em km para ordenação por proximidade (RF26)."""
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    )
    return 2 * r * asin(sqrt(min(1.0, a)))


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)) -> dict:
    cats = db.query(Category).filter(Category.is_active.is_(True)).order_by(Category.name).all()
    return {"items": [{"id": c.id, "name": c.name} for c in cats]}


@router.post("/internal/category-ids", include_in_schema=False)
def active_category_ids(ids: list[str], db: Session = Depends(get_db)) -> dict:
    return {"ids": [row.id for row in db.query(Category).filter(
        Category.id.in_(ids), Category.is_active.is_(True),
    )]}


@router.get("/tourist-spots", response_model=TouristSpotList)
def list_spots(
    category: str | None = None,
    status: SpotStatus | None = None,
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    q: str | None = Query(default=None, max_length=255),
    interests: str | None = Query(default=None, description="ids de interesses do usuário (RF26)"),
    claims_user: dict | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
    interest_lookup: Callable[[str], set[str]] = Depends(get_interest_lookup),
) -> TouristSpotList:
    if (lat is None) != (lng is None):
        raise ApiError("invalid_coordinates", "Informe latitude e longitude juntas.", 422)
    query = _public_spots(db)
    preferred = set(interests.split(",")) if interests else set()
    if claims_user:
        if claims_user["role"] == "tourist" and interests is None:
            preferred = interest_lookup(claims_user["sub"])
        notify_access(claims_user["sub"], db=db)
        db.commit()  # RF07: acesso registrado no insights (D-05)
    if status:
        query = query.filter(TouristSpot.status == status)
    if q:
        query = query.filter(TouristSpot.name.icontains(q, autoescape=True))
    if category:
        query = query.join(SpotCategory).filter(SpotCategory.category_id == category)
    spots = query.all()

    categories = _categories_by_spot(db, [spot.id for spot in spots])

    def relevance(spot: TouristSpot) -> tuple[int, float, str, str]:
        matches, distance = 0, 0.0
        if preferred and lat is not None and lng is not None:
            matches = sum(category.id in preferred for category in categories[spot.id])
            distance = haversine_km(lat, lng, float(spot.latitude), float(spot.longitude))
        return -matches, distance, spot.name.casefold(), spot.id

    spots.sort(key=relevance)
    items = [TouristSpotOut(**_public_fields(spot), categories=categories[spot.id]) for spot in spots]
    return TouristSpotList(items=items, total=len(items))


@router.get("/tourist-spots/{spot_id}", response_model=TouristSpotDetail)
def get_spot(spot_id: str, db: Session = Depends(get_db)) -> TouristSpotDetail:
    spot = _public_spots(db).filter(TouristSpot.id == spot_id).first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    return spot_detail(db, spot)


def spot_detail(db: Session, spot: TouristSpot, *, public: bool = True) -> TouristSpotDetail:
    spot_id = spot.id
    schedule = [
        {"day_of_week": row.day_of_week, "opens_at": row.opens_at, "closes_at": row.closes_at,
         "all_day": row.opens_at == "00:00" and row.closes_at == "24:00"}
        for row in db.query(OpeningSchedule).filter(OpeningSchedule.spot_id == spot_id)
        .order_by(OpeningSchedule.day_of_week, OpeningSchedule.opens_at)
    ]
    events = db.query(Event).filter(Event.tourist_spot_id == spot_id)
    if public:
        events = events.filter(upcoming())
    return TouristSpotDetail(
        **_public_fields(spot),
        tolerance_radius_m=spot.tolerance_radius_m,
        categories=_categories_for(db, spot.id),
        schedule=schedule,
        events=[event_body(event) for event in events.order_by(Event.occurs_at)],
        timezone=deployment_timezone(),
    )


@router.get("/tourist-spots/{spot_id}/external-links", response_model=ExternalLinksOut)
def get_external_links(spot_id: str, db: Session = Depends(get_db)) -> ExternalLinksOut:
    spot = _public_spots(db).filter(TouristSpot.id == spot_id).first()
    if spot is None:
        raise ApiError(code="not_found", message="Ponto turístico não encontrado.", status_code=404)
    links = build_external_links(float(spot.latitude), float(spot.longitude), spot.name)
    return ExternalLinksOut(links=links)


# --- interno (outros serviços) — T030 ----------------------------------------

@development_router.post("/internal/tourist-spots", status_code=201)
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
