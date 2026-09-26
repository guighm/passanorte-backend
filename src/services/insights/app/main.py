"""App FastAPI do serviço insights (T011)."""

from fastapi import FastAPI

from services.insights.app.api import dashboard, internal
from shared.app import create_app


def create_test_app() -> FastAPI:
    """App completo para testes de contrato (dependências sobrescritáveis)."""
    return create_app("insights", routers=[dashboard.router, internal.router])


app = create_test_app()
