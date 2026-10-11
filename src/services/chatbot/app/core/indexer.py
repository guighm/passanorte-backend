"""Rebuild do índice RAG consumido do barramento (catalog → chatbot, D-08) — T063.

Função pura com session explícita (testes e o consumer chamam direto);
delete-then-insert por (source_type, source_id) — idempotente.
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.orm import Session

from services.chatbot.app.models.embedding import EmbeddedContent
from shared.db import service_session_factory
from shared.logging import log_event

logger = logging.getLogger("chatbot")


class IndexItem(BaseModel):
    source_type: str = Field(pattern="^(tourist_spot|event|route)$")
    source_id: str
    spot_id: str | None = None
    title: str
    description: str = ""
    status: str = "open"
    latitude: float | None = None
    longitude: float | None = None
    ticket_price: float | None = Field(default=None, ge=0)
    occurs_at: str | None = None
    schedule_text: str | None = None


def refresh_index_items(db: Session, embedder, items: list[IndexItem]) -> dict:
    """Rebuild idempotente dos embeddings dos itens alterados do catálogo (D-08)."""
    if not items:
        return {"indexed": 0}
    keys = [(item.source_type, item.source_id) for item in items]
    for source_type, source_id in keys:
        db.execute(
            delete(EmbeddedContent).where(
                EmbeddedContent.source_type == source_type,
                EmbeddedContent.source_id == source_id,
            )
        )
    db.flush()
    texts = []
    for item in items:
        chunk = f"{item.title}. {item.description}"
        if item.schedule_text:
            chunk += f" Horários: {item.schedule_text}."
        if item.occurs_at:
            chunk += f" Ocorre em {item.occurs_at}."
        if item.status != "open":
            chunk += f" Status: {item.status}."
        texts.append(chunk)
    vectors = embedder(texts)
    for item, chunk, vector in zip(items, texts, vectors, strict=True):
        occurs = None
        if item.occurs_at:
            occurs = datetime.fromisoformat(item.occurs_at.replace("Z", "+00:00")).replace(tzinfo=None)
        db.add(
            EmbeddedContent(
                source_type=item.source_type,
                source_id=item.source_id,
                spot_id=item.spot_id,
                title=item.title,
                text_chunk=chunk,
                status=item.status,
                latitude=item.latitude,
                longitude=item.longitude,
                ticket_price=item.ticket_price,
                occurs_at=occurs,
                schedule_text=item.schedule_text,
                embedding=list(vector),
            )
        )
    db.commit()
    log_event(logger, "index_refreshed", count=len(items))
    return {"indexed": len(items)}


def refresh_from_payload(db: Session, payload_data: dict) -> dict:
    """Converte o `data` do evento `catalog.index.refresh` e refaz o índice."""
    items = [IndexItem(**item) for item in payload_data.get("items", [])]
    from services.chatbot.app.core.embeddings import get_embedder

    return refresh_index_items(db, get_embedder(), items)


def handle_refresh(data: dict) -> None:
    db = service_session_factory()()
    try:
        refresh_from_payload(db, data)
    finally:
        db.close()
