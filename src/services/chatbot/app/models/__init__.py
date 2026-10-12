"""Modelos do serviço chatbot: imports registram as tabelas no metadata do Alembic."""
from services.chatbot.app.models.conversation import Conversation, Message  # noqa: F401
from services.chatbot.app.models.embedding import EmbeddedContent  # noqa: F401
