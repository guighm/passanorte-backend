"""Integração dos fluxos de evento publicados pelos produtores (D-05).

Valida que os pontos de publicação produzem os envelopes esperados e que a
reprodução deles nos handlers dos serviços alvo ("o broker acontece") produz
os efeitos colaterais esperados em cada banco.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from services.auth.app.core import deps as auth_deps  # noqa: E402
from services.auth.app.main import create_test_app as auth_factory  # noqa: E402
from services.catalog.app.core import deps as catalog_deps  # noqa: E402
from services.catalog.app.main import create_test_app as catalog_factory  # noqa: E402
from services.validation.app.core.propagator import get_propagator  # noqa: E402
from shared.security import create_access_token  # noqa: E402


def test_propagator_publishes_visit_validated(events):
    propagate = get_propagator()
    fact = {"user_id": "u1", "tourist_spot_id": "s-1", "occurred_at": datetime.now(UTC).isoformat()}

    result = propagate(dict(fact, country_of_origin="Brasil", interests=["cultura"]))

    assert result == {"published": True}
    assert len(events) == 1
    event = events[0]
    assert event["type"] == "visit.validated"
    assert event["data"]["user_id"] == "u1"
    assert event["data"]["tourist_spot_id"] == "s-1"
    assert event["data"]["country_of_origin"] == "Brasil"


def test_visit_validated_replayed_ingests_fact(events, replay, db_session):
    propagate = get_propagator()
    propagate({"user_id": "u1", "tourist_spot_id": "spot-a", "occurred_at": datetime.now(UTC).isoformat()})

    replay("insights", db_session)
    assert len(events) == 0  # tudo foi entregue ao insights

    from services.insights.app.models.facts import VisitFact

    facts = db_session.query(VisitFact).all()
    assert len(facts) == 1
    assert facts[0].user_id == "u1"


def test_login_publishes_access_registered(events, replay, db_session):
    from services.insights.app.models.facts import AccessLog

    app = auth_factory()
    app.dependency_overrides[auth_deps.get_db] = lambda: db_session
    auth = TestClient(app)

    resp = auth.post(
        "/api/v1/tourists",
        json={
            "name": "Ana",
            "surname": "Silva",
            "email": "ana@example.com",
            "password": "s3cr3t!x",
            "phone": "+55 92 99999-0000",
            "country_of_origin": "Brasil",
            "cpf": "123.456.789-00",
        },
    )
    assert resp.status_code == 201, resp.text
    resp = auth.post("/api/v1/session", json={"email": "ana@example.com", "password": "s3cr3t!x"})
    assert resp.status_code == 200, resp.text

    access_events = [e for e in events if e["type"] == "access.registered"]
    assert len(access_events) >= 1
    assert access_events[0]["data"]["user_id"]

    replay("insights", db_session)
    assert db_session.query(AccessLog).count() >= 1


def test_catalog_spot_publishes_new_spot_and_index_refresh(events, db_session):
    app = catalog_factory()
    app.dependency_overrides[catalog_deps.get_db] = lambda: db_session
    catalog = TestClient(app)

    token, _ = create_access_token("admin-1", "admin")
    resp = catalog.post(
        "/api/v1/tourist-spots",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Teatro Amazonas",
            "description": "Teatro histórico",
            "latitude": -3.47,
            "longitude": -60.02,
            "category_ids": ["cat-cultura"],
        },
    )
    assert resp.status_code == 201, resp.text

    kinds = {(e["type"], e["data"].get("kind")) for e in events}
    assert ("notification.dispatch", "new_spot") in kinds
    assert ("catalog.index.refresh", None) in kinds
    refresh = next(e for e in events if e["type"] == "catalog.index.refresh")
    assert refresh["data"]["items"][0]["title"] == "Teatro Amazonas"
