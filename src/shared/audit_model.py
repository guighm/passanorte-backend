from __future__ import annotations

import uuid

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


class AuditFields:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    payload_json: Mapped[str | None] = mapped_column(String(2000))
    occurred_at: Mapped[object] = mapped_column(DateTime, nullable=False)
