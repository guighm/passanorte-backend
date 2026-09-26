"""T039 [US4] Testes unitários dos invariantes de gamificação (FR-027).

`issued→redeemed` exatamente uma vez; `stock_quantity ≥ 0` sob concessão;
conclusão idempotente (badge + código únicos).
Deve falhar antes de T045/T046.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from services.gamification.app.core import completion as completion_mod  # noqa: E402
from services.gamification.app.core import redemptions as redemptions_mod  # noqa: E402
from services.gamification.app.models.enrollment import Badge, RedeemCode  # noqa: E402
from services.gamification.app.models.route import Prize  # noqa: E402
from shared.db import Base, make_session_factory  # noqa: E402
from shared.errors import ApiError  # noqa: E402


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    try:
        yield factory
    finally:
        engine.dispose()


def test_redeem_code_exactly_once(session_factory):
    db = session_factory()
    prize = Prize(name="Camisa", description="d", stock_quantity=5)
    db.add(prize)
    db.flush()
    code = RedeemCode(code="CODIGO-1", user_id="u1", route_id="r1", prize_id=prize.id)
    db.add(code)
    db.commit()

    result = redemptions_mod.redeem(db, "CODIGO-1", actor_id="emp-1")
    assert result["status"] == "redeemed"
    assert db.query(RedeemCode).filter(RedeemCode.code == "CODIGO-1").first().status.value == "redeemed"
    assert prize.stock_quantity == 4

    # segunda concessão do mesmo código → 409 (FR-027)
    with pytest.raises(ApiError) as exc:
        redemptions_mod.redeem(db, "CODIGO-1", actor_id="emp-1")
    assert exc.value.status_code == 409


def test_redeem_unknown_code_is_404(session_factory):
    db = session_factory()
    with pytest.raises(ApiError) as exc:
        redemptions_mod.redeem(db, "NAO-EXISTE", actor_id="emp-1")
    assert exc.value.status_code == 404


def test_redeem_with_empty_stock_is_409_and_stock_stays_zero(session_factory):
    db = session_factory()
    prize = Prize(name="Caneca", description="d", stock_quantity=0)
    db.add(prize)
    db.flush()
    db.add(RedeemCode(code="CODIGO-2", user_id="u1", route_id="r1", prize_id=prize.id))
    db.commit()

    with pytest.raises(ApiError) as exc:
        redemptions_mod.redeem(db, "CODIGO-2", actor_id="emp-1")
    assert exc.value.status_code == 409
    db.expire_all()
    assert db.query(Prize).first().stock_quantity == 0  # nunca negativo (FR-027)


def test_completion_emits_badge_and_code_idempotently(session_factory):
    db = session_factory()
    prize = Prize(name="Chaveiro", description="d", stock_quantity=1)
    db.add(prize)
    db.flush()
    code = completion_mod.complete_route(db, user_id="u1", route_id="r1", prize_id=prize.id)

    second = completion_mod.complete_route(db, user_id="u1", route_id="r1", prize_id=prize.id)
    assert second["code"] == code["code"]  # mesmo código, sem duplicar (RF36)
    assert db.query(Badge).filter(Badge.user_id == "u1", Badge.route_id == "r1").count() == 1
    assert db.query(RedeemCode).filter(RedeemCode.user_id == "u1", RedeemCode.route_id == "r1").count() == 1


def test_prize_stock_constraint_rejects_negative(session_factory):
    db = session_factory()
    db.add(Prize(name="X", description="d", stock_quantity=-1))
    with pytest.raises(Exception):  # noqa: B017 — constraint do banco (FR-027)
        db.commit()
