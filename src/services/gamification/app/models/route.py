"""Modelos Route/Prize (RF18–RF20) — T041, data-model.md."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base


class Prize(Base):
    __tablename__ = "prizes"
    # estoque nunca negativo (FR-027)
    __table_args__ = (CheckConstraint("stock_quantity >= 0", name="ck_prize_stock_non_negative"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    stock_quantity: Mapped[int] = mapped_column(default=0)


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    prize_id: Mapped[str] = mapped_column(ForeignKey("prizes.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    prize: Mapped[Prize] = relationship()
    points: Mapped[list[RoutePoint]] = relationship(
        back_populates="route", order_by="RoutePoint.position", cascade="all, delete-orphan"
    )


class RoutePoint(Base):
    """Associação N:M ordenável e inativável (edge case: ponto removido no catalog)."""

    __tablename__ = "route_points"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id"), index=True)
    tourist_spot_id: Mapped[str] = mapped_column(String(36))
    position: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    route: Mapped[Route] = relationship(back_populates="points")
