"""Modelos de fato do insights: AccessLog e VisitFact (RF06–RF10) — T049."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class AccessLog(Base):
    """Cada acesso à aplicação (RF07)."""

    __tablename__ = "access_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    client: Mapped[str | None] = mapped_column(String(16))  # web | mobile
    occurred_at: Mapped[object] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)


class VisitFact(Base):
    """Fato de visita (réplica lógica, sem PII sensível — RNF08, LGPD)."""

    __tablename__ = "visit_facts"
    # ingest idempotente por par (usuário, ponto, momento) (D-05)
    __table_args__ = (
        UniqueConstraint("user_id", "tourist_spot_id", "occurred_at", name="uq_visitfact_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    tourist_spot_id: Mapped[str] = mapped_column(String(36), index=True)
    # snapshot do ponto no momento do ingest (contrato do heatmap: name/lat/lng)
    spot_name: Mapped[str | None] = mapped_column(String(255))
    spot_latitude: Mapped[object] = mapped_column(Numeric(10, 7), nullable=True)
    spot_longitude: Mapped[object] = mapped_column(Numeric(10, 7), nullable=True)
    region_hint: Mapped[str | None] = mapped_column(String(120))
    country_of_origin: Mapped[str | None] = mapped_column(String(64))
    interests: Mapped[str | None] = mapped_column(String(500))  # snapshot agregado (JSON/csv)
    occurred_at: Mapped[object] = mapped_column(DateTime, index=True)
