"""T014 [US1] Testes de contrato dos endpoints de leitura do catalog (contracts/catalog.md).

Listagem com filtros (RF26), detalhes (RF27) e links externos (RF28).
Falha antes da implementação (T019–T021).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from services.catalog.app.core import deps
from services.catalog.app.main import create_test_app


@pytest.fixture
def client(db_session, internal_headers) -> TestClient:
    app = create_test_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    return TestClient(app, headers=internal_headers)


def create_spot(client: TestClient, **overrides) -> dict:
    """Cria um ponto turístico via endpoint interno de seed (admin via seed)."""
    payload = {
        "name": "Teatro Amazonas",
        "description": "Teatro histórico de Manaus",
        "latitude": -3.4704,
        "longitude": -60.0238,
        "category_ids": [str(uuid.uuid4())],
    }
    payload.update(overrides)
    resp = client.post("/api/v1/internal/tourist-spots", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- GET /tourist-spots (RF26) ----------------------------------------------

def test_list_spots_empty_returns_empty_list(client: TestClient):
    resp = client.get("/api/v1/tourist-spots")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


def test_list_spots_returns_created_spot(client: TestClient):
    created = create_spot(client)
    resp = client.get("/api/v1/tourist-spots")
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_list_spots_filters_by_category(client: TestClient):
    cat = str(uuid.uuid4())
    create_spot(client, name="A", category_ids=[cat])
    create_spot(client, name="B", category_ids=[str(uuid.uuid4())])
    resp = client.get("/api/v1/tourist-spots", params={"category": cat})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "A"


def test_list_spots_filters_by_status(client: TestClient):
    create_spot(client, name="A", status="open")
    create_spot(client, name="B", status="permanently_closed")
    resp = client.get("/api/v1/tourist-spots", params={"status": "open"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "A"


def test_list_spots_orders_by_proximity_when_coordinates_given(client: TestClient, db_session):
    from services.catalog.app.models.spot import Category

    db_session.add(Category(id="interest", name="Cultura"))
    db_session.commit()
    # Teatro Amazonas (centro de Manaus) vs. ponto distante
    create_spot(client, name="Perto", latitude=-3.4711, longitude=-60.0237, category_ids=["interest"])
    create_spot(client, name="Longe", latitude=-3.0, longitude=-60.0, category_ids=["interest"])
    resp = client.get("/api/v1/tourist-spots", params={"lat": "-3.4704", "lng": "-60.0238", "interests": "interest"})
    names = [item["name"] for item in resp.json()["items"]]
    assert names[0] == "Perto"


def test_discovery_interest_priority_and_name_fallback(client, db_session):
    from services.catalog.app.models.spot import Category

    db_session.add(Category(id="culture", name="Cultura"))
    db_session.commit()
    create_spot(client, name="Alameda", latitude=0, longitude=0)
    create_spot(client, name="Zoológico", latitude=20, longitude=20, category_ids=["culture"])
    create_spot(client, name="Atrativo removido", status="permanently_closed")
    params = {"lat": 0, "lng": 0, "interests": "culture"}
    ranked = client.get("/api/v1/tourist-spots", params=params).json()["items"]
    assert [row["name"] for row in ranked] == ["Zoológico", "Alameda"]
    for partial in ({"interests": "culture"}, {"lat": 0, "lng": 0}):
        fallback = client.get("/api/v1/tourist-spots", params=partial).json()["items"]
        assert [row["name"] for row in fallback] == ["Alameda", "Zoológico"]
    assert ranked[0]["maps_url"].startswith("https://www.google.com/maps/")


# --- GET /tourist-spots/{id} (RF27) ------------------------------------------

def test_spot_details_include_schedule_status_and_events(client: TestClient):
    created = create_spot(client)
    resp = client.get(f"/api/v1/tourist-spots/{created['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Teatro Amazonas"
    assert body["status"] == "open"
    assert "schedule" in body and "events" in body and "categories" in body


def test_spot_details_404_for_unknown(client: TestClient):
    resp = client.get(f"/api/v1/tourist-spots/{uuid.uuid4()}")
    assert resp.status_code == 404


# --- GET /tourist-spots/{id}/external-links (RF28, D-07) ----------------------

def test_external_links_include_maps_and_rides(client: TestClient):
    created = create_spot(client)
    resp = client.get(f"/api/v1/tourist-spots/{created['id']}/external-links")
    assert resp.status_code == 200
    links = resp.json()["links"]
    assert links["google_maps"]
    assert links["uber"]
    assert links["ninenine"]
    # o link aponta para as coordenadas do ponto (destination)
    assert str(created["latitude"]) in links["google_maps"]
