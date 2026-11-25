"""Modelos Route/Prize (RF18–RF20) — T041, data-model.md."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from services.gamification.app.db import Base


class Prize(Base):
    __tablename__ = "prizes"
    # estoque nunca negativo (FR-027)
    __table_args__ = (CheckConstraint("stock_quantity >= 0", name="ck_prize_stock_non_negative"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    stock_quantity: Mapped[int] = mapped_column(default=0)
