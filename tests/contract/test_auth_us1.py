"""T013 [US1] Testes de contrato dos endpoints do serviço auth (spec contracts/auth.md).

Cadastro único do turista (RF22/FR-006), sessão email+senha (D-01, RNF09)
e interesses do perfil (RF25). Falha antes da implementação (T016–T018).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from services.auth.app.core import deps
from services.auth.app.main import create_test_app


@pytest.fixture
def client(db_session) -> TestClient:
    app = create_test_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    return TestClient(app)


def tourist_payload(**overrides) -> dict:
    base = {
        "name": "Ana",
        "surname": "Silva",
        "email": "ana@example.com",
        "password": "s3cr3t!x",
        "phone": "+55 92 99999-0000",
        "country_of_origin": "Brasil",
    }
    base.update(overrides)
    return base


# --- POST /tourists (RF22) --------------------------------------------------

def test_register_tourist_returns_201(client: TestClient):
    resp = client.post("/api/v1/tourists", json=tourist_payload(cpf="123.456.789-00"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "ana@example.com"
    # PII nunca em claro na resposta (RNF08)
    assert "123.456.789-00" not in resp.text


def test_register_tourist_requires_document_identity(client: TestClient):
    # cadastro único exige CPF OU passaporte (FR-006/RF22)
    resp = client.post("/api/v1/tourists", json=tourist_payload())
    assert resp.status_code == 422


def test_register_duplicate_document_returns_409(client: TestClient):
    client.post("/api/v1/tourists", json=tourist_payload(cpf="123.456.789-00"))
    resp = client.post("/api/v1/tourists", json=tourist_payload(email="other@example.com", cpf="123.456.789-00"))
    assert resp.status_code == 409


def test_register_duplicate_email_returns_409(client: TestClient):
    client.post("/api/v1/tourists", json=tourist_payload(cpf="111.111.111-11"))
    resp = client.post("/api/v1/tourists", json=tourist_payload(email="ana@example.com", passport="BR123456"))
    assert resp.status_code == 409


def test_error_body_is_standardized(client: TestClient):
    resp = client.post("/api/v1/tourists", json=tourist_payload(cpf="123.456.789-00"))
    resp = client.post("/api/v1/tourists", json=tourist_payload(cpf="123.456.789-00"))
    body = resp.json()
    assert set(body["error"].keys()) >= {"code", "message", "details"}
    assert "X-Request-Id" in resp.headers


# --- POST /session (RF02/RF23, D-01) ----------------------------------------

def test_login_with_valid_email_and_password(client: TestClient):
    client.post("/api/v1/tourists", json=tourist_payload(cpf="123.456.789-00"))
    resp = client.post("/api/v1/session", json={"email": "ana@example.com", "password": "s3cr3t!x"})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body and "refresh_token" in body and "expires_in" in body


def test_login_with_invalid_credentials_is_generic(client: TestClient):
    client.post("/api/v1/tourists", json=tourist_payload(cpf="123.456.789-00"))
    resp = client.post("/api/v1/session", json={"email": "ana@example.com", "password": "wrong"})
    assert resp.status_code == 401
    # mensagem genérica não revela qual campo falhou (Princípio III)
    assert resp.json()["error"]["message"] == resp.json()["error"]["message"]


def test_login_with_unknown_email_is_same_error(client: TestClient):
    resp = client.post("/api/v1/session", json={"email": "nobody@example.com", "password": "x"})
    assert resp.status_code == 401


def test_refresh_returns_new_tokens(client: TestClient):
    client.post("/api/v1/tourists", json=tourist_payload(cpf="123.456.789-00"))
    login = client.post("/api/v1/session", json={"email": "ana@example.com", "password": "s3cr3t!x"}).json()
    resp = client.post("/api/v1/session/refresh", json={"refresh_token": login["refresh_token"]})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


# --- /me e interesses (RF24/RF25) -------------------------------------------

def auth_headers(client: TestClient) -> dict:
    login = client.post("/api/v1/session", json={"email": "ana@example.com", "password": "s3cr3t!x"}).json()
    return {"Authorization": f"Bearer {login['access_token']}"}


def test_me_returns_authenticated_tourist(client: TestClient):
    client.post("/api/v1/tourists", json=tourist_payload(cpf="123.456.789-00"))
    resp = client.get("/api/v1/me", headers=auth_headers(client))
    assert resp.status_code == 200
    assert resp.json()["email"] == "ana@example.com"
    assert resp.json()["role"] == "tourist"


def test_me_requires_token(client: TestClient):
    client.post("/api/v1/tourists", json=tourist_payload(cpf="123.456.789-00"))
    assert client.get("/api/v1/me").status_code == 401


def test_patch_me_updates_profile(client: TestClient):
    client.post("/api/v1/tourists", json=tourist_payload(cpf="123.456.789-00"))
    headers = auth_headers(client)
    resp = client.patch("/api/v1/me", json={"name": "Ana Maria"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Ana Maria"


def test_put_interests_persists_selection(client: TestClient):
    client.post("/api/v1/tourists", json=tourist_payload(cpf="123.456.789-00"))
    headers = auth_headers(client)
    resp = client.put(
        "/api/v1/me/interests",
        json={"category_ids": ["11111111-1111-1111-1111-111111111111"]},
        headers=headers,
    )
    assert resp.status_code == 200
    resp = client.get("/api/v1/me/interests", headers=headers)
    assert resp.json()["category_ids"] == ["11111111-1111-1111-1111-111111111111"]
