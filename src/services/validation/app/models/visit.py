"""Modelo Visit (visitação validada por geolocalização) — T034, data-model.md."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class VisitStatus(str, enum.Enum):
    validated = "validated"
    rejected = "rejected"


class Visit(Base):
    __tablename__ = "visits"
    # único par (user, spot) VALIDADO (FR-019); rejected fica só para auditoria
    __table_args__ = (
        Index(
            "uq_visit_validated",
            "user_id",
            "tourist_spot_id",
            unique=True,
            sqlite_where=text("status = 'validated'"),
            postgresql_where=text("status = 'validated'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    tourist_spot_id: Mapped[str] = mapped_column(String(36), index=True)
    user_latitude: Mapped[float] = mapped_column(Numeric(10, 7))
    user_longitude: Mapped[float] = mapped_column(Numeric(10, 7))
    distance_m: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[VisitStatus] = mapped_column(String(16), default=VisitStatus.validated)
    occurred_at: Mapped[object] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    notes: Mapped[str | None] = mapped_column(Text)
