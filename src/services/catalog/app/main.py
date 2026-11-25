"""App FastAPI do serviço catalog (T011)."""

from fastapi import FastAPI

from services.catalog.app.api import events, routes, spots, spots_admin
from shared.app import create_app


def create_test_app() -> FastAPI:
    """App completo para testes de contrato (dependências sobrescritáveis)."""
    return create_app(
        "catalog", routers=[spots.router, spots_admin.router, events.router, routes.router],
        development_routers=[spots.development_router, events.development_router],
    )


app = create_test_app()
