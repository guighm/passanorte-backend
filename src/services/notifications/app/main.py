"""App FastAPI do serviço notifications (T011)."""

from fastapi import FastAPI

from services.notifications.app.api import notifications
from services.notifications.app.core import dispatcher
from shared.app import create_app
from shared.messaging import ConsumerSpec


def create_test_app() -> FastAPI:
    """App completo para testes de contrato (dependências sobrescritáveis)."""
    return create_app(
        "notifications",
        routers=[notifications.router],
        consumers=[
            ConsumerSpec(
                service="notifications", routing_key="notification.dispatch", handler=dispatcher.handle_dispatch
            ),
        ],
    )


app = create_test_app()
