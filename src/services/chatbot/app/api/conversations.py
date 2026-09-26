"""Endpoints de conversa/planejamento com RAG (RF38/RF39) — T062."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.chatbot.app.core import retrieval
from services.chatbot.app.core.deps import (
    get_db,
    get_embedder,
    get_provider,
    require_tourist,
)
from services.chatbot.app.core.provider import ProviderUnavailable
from services.chatbot.app.models.conversation import Conversation, Message
from shared.errors import ApiError

router = APIRouter(prefix="/conversations", tags=["conversations"])


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


def _load_conversation(db: Session, conversation_id: str, user_id: str) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if conversation is None:
        raise ApiError(code="not_found", message="Conversa não encontrada.", status_code=404)
    return conversation


@router.post("", status_code=status.HTTP_201_CREATED)
def create_conversation(claims: dict = Depends(require_tourist), db: Session = Depends(get_db)) -> dict:
    conversation = Conversation(user_id=claims["sub"])
    db.add(conversation)
    db.commit()
    return {"id": conversation.id, "user_id": conversation.user_id, "created_at": str(conversation.created_at)}


@router.get("")
def list_conversations(claims: dict = Depends(require_tourist), db: Session = Depends(get_db)) -> dict:
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == claims["sub"])
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return {"items": [{"id": c.id, "created_at": str(c.created_at)} for c in conversations]}


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: str, claims: dict = Depends(require_tourist), db: Session = Depends(get_db)
) -> dict:
    conversation = _load_conversation(db, conversation_id, claims["sub"])
    return {
        "id": conversation.id,
        "created_at": str(conversation.created_at),
        "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "references_ids": m.retrieved_context_ids}
            for m in conversation.messages
        ],
    }


@router.post("/{conversation_id}/messages")
def send_message(
    conversation_id: str,
    payload: MessageCreate,
    claims: dict = Depends(require_tourist),
    db: Session = Depends(get_db),
    embedder=Depends(get_embedder),
    provider=Depends(get_provider),
) -> dict:
    """Pipeline RAG: recuperar → prompt restrito → resposta com referências (RF38/RF39)."""
    conversation = _load_conversation(db, conversation_id, claims["sub"])
    db.add(Message(conversation_id=conversation.id, role="user", content=payload.content))
    db.flush()

    rows = retrieval.retrieve(db, embedder, payload.content, top_k=5)
    context = retrieval.as_context(rows)
    try:
        reply = provider.generate(question=payload.content, context=context)
    except ProviderUnavailable:
        db.rollback()
        raise ApiError(
            code="assistant_unavailable",
            message="Assistente indisponível no momento; tente novamente em breve.",
            status_code=503,
        ) from None

    # custo estimado considera somente conteúdos disponíveis no roteiro (RF39)
    available = [row for row in rows if not retrieval.is_closed(row)]
    estimated_cost = sum(float(r.ticket_price or 0.0) for r in available)
    assistant = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=reply,
        retrieved_context_json=json.dumps(context, ensure_ascii=False),
    )
    db.add(assistant)
    db.commit()
    return {
        "conversation_id": conversation.id,
        "message_id": assistant.id,
        "reply": reply,
        "references": [
            {"source_type": row.source_type, "source_id": row.source_id, "title": row.title}
            for row in rows
        ],
        "estimated_cost": estimated_cost,
    }
