"""App FastAPI do serviço chatbot (T011) — RAG de planejamento (RF38/RF39)."""

from fastapi import FastAPI

from services.chatbot.app.api import conversations
from services.chatbot.app.core import indexer
from shared.app import create_app
from shared.messaging import ConsumerSpec


def create_test_app() -> FastAPI:
    """App completo para testes de contrato (dependências sobrescritáveis)."""
    return create_app(
        "chatbot",
        routers=[conversations.router],
        consumers=[
            ConsumerSpec(service="chatbot", routing_key="catalog.index.refresh", handler=indexer.handle_refresh),
        ],
    )


app = create_test_app()
