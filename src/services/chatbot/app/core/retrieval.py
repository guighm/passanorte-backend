"""Recuperação RAG sobre EmbeddedContent (RF38/RF39) — T058/T062.

Retorna os trechos mais similares do índice; conteúdo fechado
(`temporarily_closed`/`permanently_closed`) é sinalizado e removido das
opções de roteiro (`retrieve_available`), nunca inventado (SC-009).
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from services.chatbot.app.core.embeddings import Embedder, cosine_similarity
from services.chatbot.app.models.embedding import EmbeddedContent, embedding_as_list

_CLOSED = {"temporarily_closed", "permanently_closed"}


def _rows(db: Session) -> list[EmbeddedContent]:
    return db.query(EmbeddedContent).all()


def retrieve(db: Session, embedder: Embedder, query: str, top_k: int = 5) -> list[EmbeddedContent]:
    """Top-k conteúdos indexados mais similares à consulta (RF38)."""
    rows = _rows(db)
    if not rows:
        return []
    vectors = embedder([query])
    query_vec = vectors[0]
    scored = [(cosine_similarity(query_vec, embedding_as_list(row.embedding)), row) for row in rows]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [row for score, row in scored[:top_k] if score > 0.0]


def retrieve_available(
    db: Session, embedder: Embedder, query: str, top_k: int = 5
) -> list[EmbeddedContent]:
    """Top-k apenas com conteúdo disponível (fechados excluídos do roteiro, RF38)."""
    return [row for row in retrieve(db, embedder, query, top_k=top_k) if row.status not in _CLOSED]


def is_closed(row: EmbeddedContent) -> bool:
    return row.status in _CLOSED


def make_retriever(db: Session, embedder: Callable[..., list[list[float]]]):
    """Closure para injeção de dependência nos endpoints."""
    return retrieve_available


def as_context(rows: list[EmbeddedContent]) -> list[dict]:
    """Serializa conteúdos recuperados para o prompt/referências (custo, horários, RF39)."""
    return [
        {
            "source_type": row.source_type,
            "source_id": row.source_id,
            "spot_id": row.spot_id or row.source_id,
            "title": row.title,
            "status": row.status,
            "ticket_price": float(row.ticket_price) if row.ticket_price is not None else 0.0,
            "schedule_text": row.schedule_text,
            "occurs_at": str(row.occurs_at) if row.occurs_at is not None else None,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "description": row.text_chunk,
        }
        for row in rows
    ]
