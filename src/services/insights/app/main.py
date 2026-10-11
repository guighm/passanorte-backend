"""App FastAPI do serviço insights (T011)."""

from fastapi import FastAPI

from services.insights.app.api import dashboard
from services.insights.app.core import handlers
from shared.app import create_app
from shared.messaging import ConsumerSpec


def create_test_app() -> FastAPI:
    """App completo para testes de contrato (dependências sobrescritáveis)."""
    return create_app(
        "insights",
        routers=[dashboard.router],
        consumers=[
            ConsumerSpec(service="insights", routing_key="visit.validated", handler=handlers.handle_visit_fact),
            ConsumerSpec(service="insights", routing_key="access.registered", handler=handlers.handle_access),
        ],
    )


app = create_test_app()
