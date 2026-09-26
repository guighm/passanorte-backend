"""Modelos do catálogo turístico (T019, data-model.md).

Status: open | temporarily_closed | permanently_closed (RF15).
Cronograma: dias e horários sem sobreposição no mesmo dia (RF14).
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base


class SpotStatus(str, enum.Enum):
    open = "open"
    temporarily_closed = "temporarily_closed"
    permanently_closed = "permanently_closed"


class Category(Base):
    """Categoria pré-definida de turismo (RF13) — usada também como interesse."""

    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TouristSpot(Base):
    __tablename__ = "tourist_spots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    status: Mapped[SpotStatus] = mapped_column(
        Enum(SpotStatus, name="spot_status"), nullable=False, default=SpotStatus.open
    )
    tolerance_radius_m: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_removed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    categories: Mapped[list[SpotCategory]] = relationship(back_populates="spot")
    schedule: Mapped[list[OpeningSchedule]] = relationship(back_populates="spot")
    events: Mapped[list[Event]] = relationship(back_populates="spot")


class SpotCategory(Base):
    """Associação N:M ponto ↔ categoria (RF13)."""

    __tablename__ = "spot_categories"
    __table_args__ = (UniqueConstraint("spot_id", "category_id", name="uq_spot_category"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    spot_id: Mapped[str] = mapped_column(String(36), ForeignKey("tourist_spots.id"), index=True)
    category_id: Mapped[str] = mapped_column(String(36), index=True)
    spot: Mapped[TouristSpot] = relationship(back_populates="categories")


class OpeningSchedule(Base):
    """Cronograma de funcionamento: dia da semana + janela (RF14)."""

    __tablename__ = "opening_schedules"
    __table_args__ = (UniqueConstraint("spot_id", "day_of_week", "opens_at", name="uq_spot_day_window"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    spot_id: Mapped[str] = mapped_column(String(36), ForeignKey("tourist_spots.id"), index=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=dom … 6=sáb
    opens_at: Mapped[str] = mapped_column(String(5), nullable=False)  # "HH:MM"
    closes_at: Mapped[str] = mapped_column(String(5), nullable=False)
    spot: Mapped[TouristSpot] = relationship(back_populates="schedule")


class Event(Base):
    """Evento associado a um ponto turístico (RF16)."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tourist_spot_id: Mapped[str] = mapped_column(String(36), ForeignKey("tourist_spots.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    occurs_at: Mapped[str] = mapped_column(DateTime, nullable=False)
    ticket_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    spot: Mapped[TouristSpot] = relationship(back_populates="events")
