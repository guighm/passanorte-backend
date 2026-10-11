"""App factory compartilhada dos 7 microsserviços (T009, Princípios II e V).

Fornece /health em cada serviço, middleware de correlation ID, handlers de
erro padronizados, roteamento sob /api/v1 e, quando o serviço tem consumers,
o ciclo de vida do barramento AMQP (RabbitMQ).
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from shared import messaging
from shared.errors import install_error_handlers
from shared.logging import CorrelationIdMiddleware, configure_logging, log_event


def create_app(
    service_name: str,
    include_in_schema: bool = True,
    routers: list[Callable[..., Any]] | None = None,
    consumers: list[messaging.ConsumerSpec] | None = None,
) -> FastAPI:
    """Cria o app FastAPI do serviço com padrões transversais aplicados.

    `routers` são objetos FastAPI APIRouter; a lista aceita routers já
    construídos (instâncias APIRouter) ou callables que os retornam.
    `consumers` registra consumers do barramento AMQP, iniciados no
    lifespan (sem `RABBITMQ_URL`, o broker fica degradado e nada roda).
    O `/health` continua liveness-only — nunca faz ping do banco/broker,
    porque os healthchecks do compose e do Kong dependem dele.
    """
    configure_logging(service_name)
    logger = logging.getLogger(service_name)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        messaging.configure(os.environ.get("RABBITMQ_URL", ""))
        if consumers:
            messaging.start_consumers(consumers)
        yield
        messaging.stop()

    app = FastAPI(
        title=f"PassaNorte — {service_name}",
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
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
