"""Testes unitários do gateway: roteamento, bloqueio de /internal/* e autorização.

O downstream é um MockTransport que ecoa o que o gateway repassou — nada sai
da rede local de testes.
"""

from __future__ import annotations

import os

import httpx
import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from fastapi.testclient import TestClient  # noqa: E402

from services.gateway.app.core.routing import (  # noqa: E402
    ADMIN,
    ANY,
    EMPLOYEE,
    INTERNAL,
    PUBLIC,
    TOURIST,
    resolve_route,
)
from services.gateway.app.main import create_gateway_app  # noqa: E402
from shared.security import create_access_token  # noqa: E402


def _echo_handler(state: dict) -> httpx.MockTransport:
    """Downstream de teste: devolve o que recebeu para as asserções."""

    def handler(request: httpx.Request) -> httpx.Response:
        state.setdefault("requests", []).append(request)
        return httpx.Response(200, json={"path": request.url.path, "query": dict(request.url.params)})

    return httpx.MockTransport(handler)


@pytest.fixture
def downstream_state():
    return {}


@pytest.fixture
def client(downstream_state):
    app = create_gateway_app(transport=_echo_handler(downstream_state))
    with TestClient(app) as test_client:
        yield test_client


def _token(role: str) -> str:
    return create_access_token("user-1", role)[0]


def _bearer(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(role)}"}


# --- Tabela de roteamento ----------------------------------------------------


def test_resolve_route_por_prefixo():
    assert resolve_route("GET", "/tourist-spots") == ("catalog", PUBLIC)
    assert resolve_route("GET", "/tourist-spots/x/external-links") == ("catalog", PUBLIC)
    assert resolve_route("GET", "/categories") == ("catalog", PUBLIC)
    assert resolve_route("POST", "/events") == ("catalog", ADMIN)
    assert resolve_route("POST", "/session") == ("auth", PUBLIC)
    assert resolve_route("GET", "/me") == ("auth", ANY)
    assert resolve_route("DELETE", "/employees/x") == ("auth", ADMIN)
    assert resolve_route("POST", "/visits") == ("validation", ANY)
    assert resolve_route("GET", "/routes") == ("gamification", PUBLIC)
    assert resolve_route("POST", "/routes") == ("gamification", ADMIN)
    assert resolve_route("POST", "/routes/r1/enrollments") == ("gamification", TOURIST)
    assert resolve_route("POST", "/redemptions") == ("gamification", EMPLOYEE)
    assert resolve_route("GET", "/badges") == ("gamification", TOURIST)
    assert resolve_route("GET", "/heatmap") == ("insights", ADMIN)
    assert resolve_route("GET", "/rankings/tourist-spots") == ("insights", ADMIN)
    assert resolve_route("GET", "/distributions/interests") == ("insights", ADMIN)
    assert resolve_route("PUT", "/subscriptions") == ("notifications", TOURIST)
    assert resolve_route("GET", "/notifications") == ("notifications", TOURIST)
    assert resolve_route("POST", "/conversations") == ("chatbot", TOURIST)


def test_resolve_route_desconhecida_retorna_none():
    assert resolve_route("GET", "/whatever") is None


def test_resolve_route_interna():
    assert resolve_route("POST", "/internal/visits/propagate") == (INTERNAL, frozenset())


def test_fallback_para_rota_de_servico_sem_regra():
    resolved = resolve_route("GET", "/tourists")
    assert resolved is not None
    service, access = resolved
    assert service == "auth"
    assert access == ANY


# --- Comportamento da borda --------------------------------------------------


def test_rota_publica_passa_sem_token(client, downstream_state):
    response = client.get("/api/v1/tourist-spots", params={"search": "praia"})
    assert response.status_code == 200
    request = downstream_state["requests"][0]
    assert request.url.path == "/api/v1/tourist-spots"
    assert dict(request.url.params) == {"search": "praia"}
    assert "Authorization" not in request.headers


def test_rota_protegida_sem_token_e_401(client):
    assert client.get("/api/v1/me").status_code == 401


def test_token_invalido_e_401(client):
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_tourista_em_rota_admin_e_403(client, downstream_state):
    response = client.get("/api/v1/prizes", headers=_bearer("tourist"))
    assert response.status_code == 403
    assert "requests" not in downstream_state  # nem chega ao serviço


def test_admin_repassa_authorization_ao_servico(client, downstream_state):
    token = _token("admin")
    response = client.get("/api/v1/prizes", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert downstream_state["requests"][0].headers["Authorization"] == f"Bearer {token}"


def test_employee_registra_resgate(client):
    assert client.post("/api/v1/redemptions", headers=_bearer("employee")).status_code == 200


def test_tourista_nao_registra_resgate(client):
    assert client.post("/api/v1/redemptions", headers=_bearer("tourist")).status_code == 403


def test_rota_interna_bloqueada_na_borda(client, downstream_state):
    response = client.post(
        "/api/v1/internal/visits/propagate", json={}, headers=_bearer("admin")
    )
    assert response.status_code == 404
    assert "requests" not in downstream_state


def test_rota_desconhecida_e_404(client):
    assert client.get("/api/v1/o-que-isto").status_code == 404


def test_x_request_id_propagado_downstream_e_na_resposta(client, downstream_state):
    response = client.get("/api/v1/tourist-spots", headers={"X-Request-Id": "rid-123"})
    assert response.status_code == 200
    assert downstream_state["requests"][0].headers["x-request-id"] == "rid-123"
    assert response.headers["X-Request-Id"] == "rid-123"


def test_body_repassado_ao_servico(client, downstream_state):
    response = client.post(
        "/api/v1/tourists", json={"email": "a@b.co", "password": "x"}, headers=_bearer("tourist")
    )
    assert response.status_code == 200
    request = downstream_state["requests"][0]
    assert request.headers["content-type"] == "application/json"
