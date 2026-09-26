"""Modelos NotificationSubscription e Notification (RF37, D-06) — T054."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class NotificationSubscription(Base):
    """Inscrição por interesse — único par (user, categoria) (RF37)."""

    __tablename__ = "notification_subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "category_id", name="uq_subscription_user_category"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    category_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[object] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class Notification(Base):
    """Caixa de entrada in-app (D-06). Idempotência de retry: (user, kind, source_id)."""

    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "kind", "source_id", name="uq_notification_dispatch"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    category_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(16))  # new_event | new_spot | new_route
    source_id: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(String(2000))
    payload_json: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[object] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    read_at: Mapped[object] = mapped_column(DateTime, nullable=True)
