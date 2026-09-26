"""Modelo AuditLog compartilhado (RNF19, D-09): mesma forma em todos os serviços.

Cada serviço tem seu próprio banco, mas o metadado `Base` é compartilhado
(monorepo), então a tabela é declarada uma única vez aqui e reexportada por
`services/<svc>/app/models/audit.py`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    payload_json: Mapped[str | None] = mapped_column(String(2000))
    occurred_at: Mapped[object] = mapped_column(DateTime, nullable=False)
