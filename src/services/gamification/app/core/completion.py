"""Detecção de conclusão: insígnia + código de resgate idempotentes (RF35/RF36) — T045."""

from __future__ import annotations

import logging
import secrets

from sqlalchemy.orm import Session

from services.gamification.app.models.enrollment import Badge, CodeStatus, RedeemCode
from shared.logging import log_event
from shared.notifications_client import dispatch

logger = logging.getLogger("gamification")


def _notify_completion(user_id: str, code: str) -> None:
    """Notificação ao turista — fire-and-forget, falha é tolerada (D-05)."""
    dispatch(
        kind="new_route",
        source_id=code,
        user_ids=[user_id],
        title="Rota concluída!",
        body="Você concluiu a rota e recebeu um código de resgate.",
        payload={"redeem_code": code},
    )


def complete_route(db: Session, *, user_id: str, route_id: str, prize_id: str) -> dict:
    """Emite Badge + RedeemCode uma única vez (idempotente, FR-027)."""
    badge = db.query(Badge).filter(Badge.user_id == user_id, Badge.route_id == route_id).first()
    existing_code = (
        db.query(RedeemCode).filter(RedeemCode.user_id == user_id, RedeemCode.route_id == route_id).first()
    )
    if existing_code is not None:
        status_ = existing_code.status.value if hasattr(existing_code.status, "value") else existing_code.status
        return {"badge_id": badge.id if badge else None, "code": existing_code.code, "status": status_}

    badge = Badge(user_id=user_id, route_id=route_id)
    code = RedeemCode(
        code=f"PN-{secrets.token_hex(8).upper()}",
        user_id=user_id,
        route_id=route_id,
        prize_id=prize_id,
        status=CodeStatus.issued,
    )
    db.add(badge)
    db.add(code)
    db.flush()
    db.commit()
    log_event(logger, "route_completed", user_id=user_id, route_id=route_id)
    _notify_completion(user_id, code.code)
    return {"badge_id": badge.id, "code": code.code, "status": code.status.value}
