"""Auditoria compartilhada (RNF19, D-09): registro atômico com a ação.

Cada serviço define a sua tabela AuditLog (mesma forma) e usa o helper
`record_audit` na MESMA transação da ação administrativa.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from shared.logging import log_event

logger = logging.getLogger("audit")


def record_audit(
    db: Session,
    model_class: type,
    *,
    actor_id: str,
    action: str,
    entity: str,
    entity_id: str | None,
    payload: dict | None = None,
) -> None:
    """Adiciona um AuditLog à transação corrente (commit junto com a ação)."""
    db.add(
        model_class(
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            payload_json=str(payload) if payload else None,
            occurred_at=datetime.now(UTC),
        )
    )
    log_event(logger, "audit_recorded", actor_id=actor_id, action=action, entity=entity, entity_id=entity_id)
