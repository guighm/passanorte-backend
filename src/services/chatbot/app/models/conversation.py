"""Modelos Conversation e Message (RF38/RF39) — T062.

Histórico e auditoria de respostas com base nos dados recuperados
(`retrieved_context_ids` — data-model.md).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base


class Conversation(Base):
    """Conversa de planejamento de um turista (RF38)."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[object] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", order_by="Message.created_at"
    )


class Message(Base):
    """Mensagem (role user|assistant) com os ids de contexto recuperados."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    retrieved_context_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    @property
    def retrieved_context_ids(self) -> list[str]:
        if not self.retrieved_context_json:
            return []
        return [item["source_id"] for item in json.loads(self.retrieved_context_json)]
