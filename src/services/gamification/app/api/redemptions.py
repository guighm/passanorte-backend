"""Resgate de brindes pelo funcionário (RF21) — T046."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from services.gamification.app.core.deps import get_db, require_role
from services.gamification.app.core.redemptions import redeem

router = APIRouter(tags=["redemptions"])

require_employee = require_role("employee")


class RedemptionCreate(BaseModel):
    code: str


@router.post("/redemptions")
def create_redemption(
    payload: RedemptionCreate,
    claims: dict = Depends(require_employee),
    db: Session = Depends(get_db),
) -> dict:
    """Escaneia código: valida, concede brinde e baixa estoque (RF21, FR-027)."""
    return redeem(db, payload.code, actor_id=claims["sub"])
