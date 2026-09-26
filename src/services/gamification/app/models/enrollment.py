"""Modelos RouteEnrollment/Badge/RedeemCode (RF29–RF30, RF35–RF36) — T042."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.gamification.app.models.route import Route
from shared.db import Base


class EnrollmentStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"


class CodeStatus(str, enum.Enum):
    issued = "issued"
    redeemed = "redeemed"


class RouteEnrollment(Base):
    __tablename__ = "route_enrollments"
    # mesmo user não se inscreve 2× na mesma rota (data-model.md)
    __table_args__ = (UniqueConstraint("user_id", "route_id", name="uq_enrollment_user_route"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id"), index=True)
    status: Mapped[EnrollmentStatus] = mapped_column(
        String(16), default=EnrollmentStatus.in_progress
    )
    started_at: Mapped[object] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    completed_at: Mapped[object] = mapped_column(DateTime, nullable=True)

    route: Mapped[Route] = relationship()


class Badge(Base):
    __tablename__ = "badges"
    __table_args__ = (UniqueConstraint("user_id", "route_id", name="uq_badge_user_route"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    route_id: Mapped[str] = mapped_column(String(36))
    awarded_at: Mapped[object] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class RedeemCode(Base):
    __tablename__ = "redeem_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    route_id: Mapped[str] = mapped_column(String(36))
    prize_id: Mapped[str] = mapped_column(ForeignKey("prizes.id"))
    status: Mapped[CodeStatus] = mapped_column(String(16), default=CodeStatus.issued)
    issued_at: Mapped[object] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    redeemed_at: Mapped[object] = mapped_column(DateTime, nullable=True)
