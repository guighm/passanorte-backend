"""App FastAPI do serviço gamification (T011)."""

from fastapi import FastAPI

from services.gamification.app.api import admin, enrollments, redemptions
from services.validation.app.api import internal, visits
from shared.app import create_app


def create_test_app() -> FastAPI:
    """App completo para testes de contrato (dependências sobrescritáveis)."""
    return create_app(
        "gamification", routers=[admin.router, enrollments.router, redemptions.router, visits.router],
        development_routers=[internal.router],
    )


app = create_test_app()
