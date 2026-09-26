"""T052 [US5] Integração: as cinco visões do dashboard (quickstart S5).

Login (auth) e listagem (catalog) propagam acessos ao insights (D-05);
fatos de visita ingeridos; admin consulta as 5 visões com dataset conhecido.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from services.insights.app.core import deps as insights_deps  # noqa: E402
from services.insights.app.main import create_test_app as insights_factory  # noqa: E402
from shared.db import Base, make_session_factory  # noqa: E402
from shared.security import create_access_token  # noqa: E402


@pytest.fixture
def client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app = insights_factory()
    app.dependency_overrides[insights_deps.get_db] = lambda: make_session_factory(engine)()
    return TestClient(app)


def test_us5_dashboard_five_views(client):
    # acesso do turista no login/listagem propagado ao insights (D-05, RF07)
    client.post("/api/v1/internal/accesses", json={"user_id": "u1", "client": "mobile"})
    client.post("/api/v1/internal/accesses", json={"user_id": "u2", "client": "web"})

    # fatos de visita com snapshot de país/interesses (LGPD, RNF08)
    now = datetime.now(UTC)
    for user, spot, country, interests in [
        ("u1", "spot-a", "Brasil", ["cultura"]),
        ("u2", "spot-a", "Portugal", ["cultura", "natureza"]),
        ("u3", "spot-b", "Brasil", ["natureza"]),
    ]:
        resp = client.post(
            "/api/v1/internal/visit-facts",
            json={"user_id": user, "tourist_spot_id": spot, "region_hint": "Centro",
                  "occurred_at": (now - timedelta(days=1)).isoformat(),
                  "country_of_origin": country, "interests": interests},
        )
        assert resp.status_code == 201, resp.text

    token, _ = create_access_token("admin-1", "admin")
    admin = {"Authorization": f"Bearer {token}"}
    tourist_token, _ = create_access_token("u1", "tourist")
    tourist = {"Authorization": f"Bearer {tourist_token}"}

    # RF06: mapa de calor
    heatmap = client.get("/api/v1/heatmap", headers=admin).json()
    assert {r["tourist_spot_id"]: r["visit_count"] for r in heatmap["items"]} == {"spot-a": 2, "spot-b": 1}

    # RF07: contador de acessos
    accesses = client.get("/api/v1/accesses", params={"period": "day"}, headers=admin).json()
    assert accesses["total"] == 2

    # RF08: ranking segmentado
    ranking = client.get("/api/v1/rankings/tourist-spots", params={"segment": "month"}, headers=admin).json()
    assert ranking["items"][0]["tourist_spot_id"] == "spot-a"

    # RF09/RF10: distribuições por país e interesses
    countries = client.get("/api/v1/distributions/country-of-origin", headers=admin).json()
    dist = {r["country_of_origin"]: r["count"] for r in countries["items"]}
    assert dist == {"Brasil": 2, "Portugal": 1}

    interests = client.get("/api/v1/distributions/interests", headers=admin).json()
    dist = {r["interest"]: r["count"] for r in interests["items"]}
    assert dist["cultura"] == 2
    assert dist["natureza"] == 2

    # RF03: apenas admin acessa o dashboard
    assert client.get("/api/v1/heatmap", headers=tourist).status_code == 403
    assert client.get("/api/v1/heatmap").status_code == 401
