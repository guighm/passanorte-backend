"""T048 [US5] Testes de contrato do dashboard (contracts/insights.md, RF06–RF10).

Cinco visões sobre um dataset conhecido; todos os endpoints exigem role=admin.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from services.insights.app.main import create_test_app as insights_factory  # noqa: E402
from shared.security import create_access_token  # noqa: E402


def admin_headers() -> dict:
    token, _ = create_access_token("admin-1", "admin")
    return {"Authorization": f"Bearer {token}"}


def ingest(client, **fact):
    resp = client.post("/api/v1/internal/visit-facts", json=fact)
    assert resp.status_code == 201, resp.text


@pytest.fixture
def client(db_session):
    app = insights_factory()
    app.dependency_overrides[app_state["get_db"]] = lambda: db_session
    return TestClient(app)


app_state: dict = {}


def test_dashboard_views_with_known_dataset(db_session):
    from services.insights.app.core import deps as insights_deps

    app = insights_factory()
    app.dependency_overrides[insights_deps.get_db] = lambda: db_session
    client = TestClient(app)

    # dataset: 3 visitas (2 no spot-a, 1 no spot-b), países Brasil/Portugal,
    # interesses cultura/natureza, 2 acessos
    now = datetime.now(UTC)
    base = {"country_of_origin": "Brasil", "interests": ["cultura"]}
    ingest(client, user_id="u1", tourist_spot_id="spot-a", region_hint="Centro",
           occurred_at=now.isoformat(), **base)
    ingest(client, user_id="u2", tourist_spot_id="spot-a", region_hint="Centro",
           occurred_at=(now - timedelta(days=3)).isoformat(), country_of_origin="Brasil",
           interests=["natureza"])
    ingest(client, user_id="u3", tourist_spot_id="spot-b", region_hint="Zona Leste",
           occurred_at=(now - timedelta(days=40)).isoformat(), country_of_origin="Portugal",
           interests=["cultura"])

    for _ in range(2):
        resp = client.post("/api/v1/internal/accesses", json={"user_id": "u1", "client": "mobile"})
        assert resp.status_code == 201

    headers = admin_headers()

    # RF06: mapa de calor por concentração
    heatmap = client.get("/api/v1/heatmap", headers=headers).json()
    by_spot = {row["tourist_spot_id"]: row for row in heatmap["items"]}
    assert by_spot["spot-a"]["visit_count"] == 2
    assert by_spot["spot-a"]["weight"] > by_spot["spot-b"]["weight"]

    # RF07: contador de acessos por período
    accesses = client.get("/api/v1/accesses", params={"period": "day"}, headers=headers).json()
    assert accesses["total"] == 2
    assert len(accesses["by_period"]) >= 1

    # RF08: ranking segmentado por mês (2 no spot-a, 1 no spot-b)
    ranking = client.get("/api/v1/rankings/tourist-spots", params={"segment": "month"}, headers=headers).json()
    items = ranking["items"]
    assert items[0]["tourist_spot_id"] == "spot-a"
    assert items[0]["visit_count"] >= items[-1]["visit_count"]

    # RF09: distribuição por país
    countries = client.get("/api/v1/distributions/country-of-origin", headers=headers).json()
    dist = {row["country_of_origin"]: row["count"] for row in countries["items"]}
    assert dist["Brasil"] == 2
    assert dist["Portugal"] == 1

    # RF10: distribuição por interesses
    interests = client.get("/api/v1/distributions/interests", headers=headers).json()
    dist = {row["interest"]: row["count"] for row in interests["items"]}
    assert dist["cultura"] == 2
    assert dist["natureza"] == 1

    # RF03: apenas admin acessa o dashboard
    tourist_token, _ = create_access_token("u1", "tourist")
    resp = client.get("/api/v1/heatmap", headers={"Authorization": f"Bearer {tourist_token}"})
    assert resp.status_code == 403
    assert client.get("/api/v1/heatmap").status_code == 401

    # idempotência do ingest (D-05): repetir o fato não duplica
    ingest(client, user_id="u1", tourist_spot_id="spot-a", region_hint="Centro",
           occurred_at=now.isoformat(), **base)
    heatmap = client.get("/api/v1/heatmap", headers=headers).json()
    assert {row["tourist_spot_id"]: row["visit_count"] for row in heatmap["items"]}["spot-a"] == 2
