"""App factory compartilhada dos 7 microsserviços (T009, Princípios II e V).

Fornece /health em cada serviço, middleware de correlation ID, handlers de
erro padronizados e roteamento sob /api/v1.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

from shared.errors import install_error_handlers
from shared.logging import CorrelationIdMiddleware, configure_logging, log_event


def create_app(
    service_name: str,
    include_in_schema: bool = True,
    routers: list[Callable[..., Any]] | None = None,
) -> FastAPI:
    """Cria o app FastAPI do serviço com padrões transversais aplicados.

    `routers` são objetos FastAPI APIRouter; a lista aceita routers já
    construídos (instâncias APIRouter) ou callables que os retornam.
    """
    configure_logging(service_name)
    logger = logging.getLogger(service_name)

    app = FastAPI(
        title=f"PassaNorte — {service_name}",
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.add_middleware(CorrelationIdMiddleware, service_name=service_name)
    install_error_handlers(app)

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": service_name}

    for router in routers or []:
        app.include_router(router, prefix="/api/v1")

    log_event(logger, "service_created", service=service_name)
    return app
