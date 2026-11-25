"""App factory compartilhada dos 7 microsserviços (T009, Princípios II e V).

Fornece /health em cada serviço, middleware de correlation ID, handlers de
erro padronizados, roteamento sob /api/v1 e, quando o serviço tem consumers,
o ciclo de vida do barramento AMQP (RabbitMQ).
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from hmac import compare_digest
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from shared import delivery, messaging
from shared.db import service_session_factory
from shared.errors import install_error_handlers
from shared.logging import CorrelationIdMiddleware, configure_logging, log_event
from shared.settings import Settings, secret, validate_service


def create_app(
    service_name: str,
    include_in_schema: bool = True,
    routers: list[APIRouter] | None = None,
    consumers: list[messaging.ConsumerSpec] | None = None,
    development_routers: list[APIRouter] | None = None,
) -> FastAPI:
    """Create a service with APIRouter instances and validated settings.

    Broker configuration is mandatory outside tests. Health remains liveness-only.
    """
    configure_logging(service_name)
    logger = logging.getLogger(service_name)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        settings = validate_service(service_name)
        messaging.configure(settings.rabbitmq_url.get_secret_value(), service_name)
        relay = None
        if settings.app_env != "test":
            messaging.start_consumers(consumers or [])
            relay = asyncio.create_task(messaging.relay(service_name))
        try:
            yield
        finally:
            if relay is not None:
                relay.cancel()
                with suppress(asyncio.CancelledError):
                    await relay
            messaging.stop()

    app = FastAPI(
        title=f"PassaNorte — {service_name}",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    install_error_handlers(app)

    # Scheme `bearerAuth` no OpenAPI: habilita o botão Authorize do Swagger UI
    # para as rotas protegidas (JWT via header Authorization). Só metadados do
    # schema — as dependências continuam lendo o header em runtime, e endpoints
    # públicos seguem sem exigir nada.
    def _openapi_schema() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
                servers=[{"url": str(Settings.load().edge_public_url).rstrip("/")}],
            )
            app.openapi_schema["paths"] = {
                path: operations for path, operations in app.openapi_schema["paths"].items()
                if not path.startswith("/api/v1/internal/")
            }
            app.openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})[
                "bearerAuth"
            ] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            app.openapi_schema["security"] = [{"bearerAuth": []}]
        return app.openapi_schema

    app.openapi = _openapi_schema  # type: ignore[method-assign]

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": service_name}

    @app.get("/ready", include_in_schema=False)
    def ready() -> JSONResponse:
        try:
            with service_session_factory()() as db:
                db.execute(delivery.outbox_table(service_name).select().limit(0))
            available = messaging.broker_ready() or os.environ.get("APP_ENV") == "test"
        except Exception:
            available = False
        return JSONResponse({"status": "ready" if available else "unavailable"}, status_code=200 if available else 503)

    development = os.environ.get("APP_ENV") in {"test", "development"}
    if development:
        @app.get(f"/docs/{service_name}", include_in_schema=False)
        def swagger():
            return get_swagger_ui_html(openapi_url=f"/openapi/{service_name}.json", title=app.title)

        @app.get(f"/openapi/{service_name}.json", include_in_schema=False)
        def openapi_document():
            return app.openapi()

    @app.middleware("http")
    async def protect_internal(request: Request, call_next):
        path = request.scope["path"].rstrip("/")
        if path == "/api/v1/internal" or path.startswith("/api/v1/internal/"):
            supplied = request.headers.get("X-Internal-Token", "").encode()
            expected = secret("INTERNAL_API_TOKEN", required=False).encode()
            if not expected or not compare_digest(supplied, expected):
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)

    app.add_middleware(CorrelationIdMiddleware, service_name=service_name)
    for router in routers or []:
        app.include_router(router, prefix="/api/v1", include_in_schema=include_in_schema)
    if development:
        for router in development_routers or []:
            app.include_router(router, prefix="/api/v1", include_in_schema=False)

    log_event(logger, "service_created", service=service_name)
    return app
