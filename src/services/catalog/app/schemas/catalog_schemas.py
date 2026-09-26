"""Schemas Pydantic do serviço catalog (Princípio II)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CategoryOut(BaseModel):
    id: str
    name: str


class TouristSpotOut(BaseModel):
    id: str
    name: str
    description: str
    latitude: float
    longitude: float
    status: str
    categories: list[CategoryOut] = Field(default_factory=list)


class TouristSpotDetail(TouristSpotOut):
    tolerance_radius_m: int
    schedule: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)


class TouristSpotList(BaseModel):
    items: list[TouristSpotOut]
    total: int


class ExternalLinksOut(BaseModel):
    links: dict[str, str]
