"""App FastAPI do serviço auth (T011)."""

from fastapi import FastAPI

from services.auth.app.api import employees, me, session, tourists
from shared.app import create_app


def create_test_app() -> FastAPI:
    """App completo para testes de contrato (routers com dependências sobrescritáveis)."""
    return create_app("auth", routers=[tourists.router, session.router, me.router, employees.router])


app = create_test_app()
