"""Modelo EmbeddedContent — índice RAG do chatbot (D-08) — T060.

Produção (PostgreSQL): a coluna `embedding` usa **pgvector** (`vector(384)`),
habilitada no banco `passanorte_chatbot` via `CREATE EXTENSION vector;`
docker-compose já ativa a extensão. Testes/SQLite: embedding é persistido
como JSON — a interface na aplicação é sempre `list[float]` (TypeDecorator).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from shared.db import Base

# dimensão do modelo de embeddings (paraphrase-multilingual-MiniLM-L12-v2 = 384)
EMBEDDING_DIM = 384

try:  # pragma: no cover — ambiente de produção tem pgvector instalado
    from pgvector.sqlalchemy import Vector as _VectorImpl  # type: ignore[import-not-found]

    _HAS_PGVECTOR = True
except ImportError:
    _VectorImpl = Text
    _HAS_PGVECTOR = False


class EmbeddingType(TypeDecorator):
    """`list[float]` na aplicação; pgvector em produção, JSON-texto em SQLite."""

    impl = _VectorImpl(EMBEDDING_DIM) if _HAS_PGVECTOR else Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return list(value) if _HAS_PGVECTOR else json.dumps(list(value))

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return [float(v) for v in value] if _HAS_PGVECTOR else [float(v) for v in json.loads(value)]


class EmbeddedContent(Base):
    """Trecho do catálogo indexado para recuperação (RF38). Idempotente por (tipo, id)."""

    __tablename__ = "embedded_contents"
    __table_args__ = (
        Index("uq_embedded_source", "source_type", "source_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type: Mapped[str] = mapped_column(String(16))  # tourist_spot | event | route
    source_id: Mapped[str] = mapped_column(String(36), index=True)
    spot_id: Mapped[str | None] = mapped_column(String(36))  # spot pai (para eventos)
    title: Mapped[str] = mapped_column(String(255))
    text_chunk: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="open")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    ticket_price: Mapped[float | None] = mapped_column(Float)
    occurs_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    schedule_text: Mapped[str | None] = mapped_column(String(500))
    embedding: Mapped[object] = mapped_column(EmbeddingType())
    embedded_at: Mapped[object] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


def embedding_as_list(value: object) -> list[float]:
    """Lê a coluna embedding como lista de floats (TypeDecorator já devolve list)."""
    if isinstance(value, (list, tuple)):
        return [float(v) for v in value]
    return [float(v) for v in json.loads(str(value))]
