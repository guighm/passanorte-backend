"""App FastAPI do serviço chatbot (T011) — RAG de planejamento (RF38/RF39)."""

from fastapi import FastAPI

from services.chatbot.app.api import conversations, internal
from shared.app import create_app


def create_test_app() -> FastAPI:
    """App completo para testes de contrato (dependências sobrescritáveis)."""
    return create_app("chatbot", routers=[conversations.router, internal.router])


app = create_test_app()
