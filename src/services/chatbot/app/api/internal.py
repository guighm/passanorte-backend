"""Gatilho interno de rebuild do índice RAG (catalog → chatbot, D-08) — T063."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.orm import Session

from services.chatbot.app.core.deps import get_db
from services.chatbot.app.core.embeddings import get_embedder
from services.chatbot.app.models.embedding import EmbeddedContent
from shared.logging import log_event

router = APIRouter(tags=["internal"])
logger = __import__("logging").getLogger("chatbot")


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


class IndexRefresh(BaseModel):
    items: list[IndexItem]


@router.post("/internal/index/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_index(
    payload: IndexRefresh,
    db: Session = Depends(get_db),
    embedder=Depends(get_embedder),
) -> dict:
    """Rebuild idempotente dos embeddings dos itens alterados do catálogo (D-08)."""
    if not payload.items:
        return {"indexed": 0}
    keys = [(item.source_type, item.source_id) for item in payload.items]
    for source_type, source_id in keys:
        db.execute(
            delete(EmbeddedContent).where(
                EmbeddedContent.source_type == source_type,
                EmbeddedContent.source_id == source_id,
            )
        )
    db.flush()
    texts = []
    for item in payload.items:
        chunk = f"{item.title}. {item.description}"
        if item.schedule_text:
            chunk += f" Horários: {item.schedule_text}."
        if item.occurs_at:
            chunk += f" Ocorre em {item.occurs_at}."
        if item.status != "open":
            chunk += f" Status: {item.status}."
        texts.append(chunk)
    vectors = embedder(texts)
    for item, chunk, vector in zip(payload.items, texts, vectors, strict=True):
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
    log_event(logger, "index_refreshed", count=len(payload.items))
    return {"indexed": len(payload.items)}
