"""App FastAPI do serviço notifications (T011)."""

from fastapi import FastAPI

from services.notifications.app.api import internal, notifications
from shared.app import create_app


def create_test_app() -> FastAPI:
    """App completo para testes de contrato (dependências sobrescritáveis)."""
    return create_app("notifications", routers=[notifications.router, internal.router])


app = create_test_app()
