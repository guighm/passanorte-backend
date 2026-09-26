"""Resgate transacional de brindes pelo funcionário (RF21, FR-027) — T046."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from services.gamification.app.models.enrollment import CodeStatus, RedeemCode
from services.gamification.app.models.route import Prize
from shared.errors import ApiError
from shared.logging import log_event

logger = logging.getLogger("gamification")


def redeem(db: Session, code: str, *, actor_id: str) -> dict:
    """Valida código e baixa estoque em uma transação; reuso e estoque zero → 409."""
    record = db.query(RedeemCode).filter(RedeemCode.code == code).first()
    if record is None:
        raise ApiError(code="code_not_found", message="Código de resgate não encontrado.", status_code=404)

    # transição condicional: issued → redeemed exatamente uma vez (FR-027)
    result = db.execute(
        update(RedeemCode)
        .where(RedeemCode.code == code, RedeemCode.status == CodeStatus.issued)
        .values(status=CodeStatus.redeemed, redeemed_at=datetime.now(UTC))
    )
    if result.rowcount == 0:
        raise ApiError(code="code_already_used", message="Código já utilizado.", status_code=409)

    # baixa atômica de estoque: só decrementa se houver unidade (stock ≥ 0)
    stock_result = db.execute(
        update(Prize)
        .where(Prize.id == record.prize_id, Prize.stock_quantity > 0)
        .values(stock_quantity=Prize.stock_quantity - 1)
    )
    if stock_result.rowcount == 0:
        db.rollback()
        raise ApiError(code="prize_out_of_stock", message="Brinde sem estoque disponível.", status_code=409)

    db.commit()
    log_event(logger, "code_redeemed", actor_id=actor_id, code=code, prize_id=record.prize_id)
    return {"code": code, "status": "redeemed", "prize_id": record.prize_id}
