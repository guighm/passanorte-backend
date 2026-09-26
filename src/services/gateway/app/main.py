"""App FastAPI do gateway: borda única dos 7 microsserviços (D-02, Princípio V).

Responsabilidades na borda:
- roteamento `/api/v1/*` para o serviço dono do prefixo (`core/routing.py`);
- verificação de JWT e autorização coarse-grained (rota → papéis);
- bloqueio das rotas `/internal/*` (exclusivas para chamadas inter-serviço);
- CORS centralizado (`ALLOWED_ORIGINS`).

O proxy repassa body, query params, `Authorization` e `X-Request-Id`; os
serviços mantêm suas próprias verificações de role (defesa em profundidade).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from contextlib import asynccontextmanager
from typing import Any

import httpx
import jwt
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.responses import Response

from services.gateway.app.core.routing import INTERNAL, SERVICE_URLS, resolve_route
from shared.app import create_app
from shared.errors import ApiError
from shared.logging import get_request_id
from shared.security import decode_token

# Headers de conexão que um proxy não deve repassar (RFC 7230 §6.1).
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)
# Headers que o gateway gerencia e não repassa como recebidos.
_REQUEST_STRIP = _HOP_BY_HOP | {"host", "content-length", "accept-encoding", "x-request-id"}
# httpx decodifica o corpo recebido; o gateway re-serva sem compressão.
_RESPONSE_STRIP = _HOP_BY_HOP | {"content-length", "content-encoding"}

_PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


def _timeout() -> httpx.Timeout:
    total = float(os.environ.get("GATEWAY_TIMEOUT_S", "30"))
    return httpx.Timeout(total, connect=5.0)


def _authenticate(headers: Mapping[str, str]) -> dict[str, Any]:
    """Valida o access token da borda; 401 se ausente ou inválido."""
    header = headers.get("Authorization", "")  # Headers do Starlette ignoram caixa
    if not header.startswith("Bearer "):
        raise ApiError(code="unauthorized", message="Autenticação necessária.", status_code=401)
    try:
        return decode_token(header.removeprefix("Bearer ").strip(), expected_type="access")
    except jwt.PyJWTError:
        raise ApiError(code="unauthorized", message="Autenticação necessária.", status_code=401) from None


def _forwarded_headers(request_headers: Mapping[str, str]) -> dict[str, str]:
    headers = {
        key: value
        for key, value in request_headers.items()
        if key.lower() not in _REQUEST_STRIP
    }
    headers["Accept-Encoding"] = "identity"
    request_id = get_request_id()
    if request_id:
        headers["X-Request-Id"] = request_id
    return headers


def create_gateway_app(transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    """Cria o app do gateway; `transport` permite injetar MockTransport nos testes."""
    app = create_app("gateway")

    origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
    if "*" in origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-Id"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-Id"],
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.http = httpx.AsyncClient(transport=transport, timeout=_timeout())
        try:
            yield
        finally:
            await app.state.http.aclose()

    app.router.lifespan_context = lifespan

    async def _proxy(full_path: str, request: Request) -> Response:
        path = f"/{full_path}"
        method = request.method
        resolved = resolve_route(method, path)
        if resolved is None:
            raise ApiError(code="not_found", message="Recurso não encontrado.", status_code=404)
        service, access = resolved
        if service == INTERNAL:
            # Rotas /internal/* existem apenas para tráfego inter-serviço;
            # a borda esconde a existência delas (404, não 403).
            raise ApiError(code="not_found", message="Recurso não encontrado.", status_code=404)

        if access:
            claims = _authenticate(request.headers)
            if claims.get("role") not in access:
                raise ApiError(code="forbidden", message="Acesso negado para o seu perfil.", status_code=403)

        url = f"{SERVICE_URLS[service]}/api/v1/{full_path}"
        client: httpx.AsyncClient = request.app.state.http
        try:
            downstream = await client.request(
                method,
                url,
                params=request.query_params,
                headers=_forwarded_headers(request.headers),
                content=await request.body() or None,
            )
        except httpx.TimeoutException as exc:
            raise ApiError(code="gateway_timeout", message="O serviço demorou a responder.", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise ApiError(code="service_unavailable", message="Serviço indisponível.", status_code=502) from exc

        response_headers = {
            key: value
            for key, value in downstream.headers.items()
            if key.lower() not in _RESPONSE_STRIP
        }
        return StreamingResponse(
            downstream.aiter_bytes(),
            status_code=downstream.status_code,
            headers=response_headers,
            background=BackgroundTask(downstream.aclose),
        )

    app.router.add_api_route(
        "/api/v1/{full_path:path}",
        _proxy,
        methods=_PROXY_METHODS,
        include_in_schema=False,
    )
    return app


app = create_gateway_app()
