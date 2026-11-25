"""Transactional delivery tables and consumer deduplication."""
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, MetaData, String, Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from shared.db import service_session_factory


def outbox_table(domain: str) -> Table:
    return Table(
        "outbox", MetaData(), Column("event_id", String(64), primary_key=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("available_at", DateTime(timezone=True), nullable=False, index=True),
        Column("envelope", JSON, nullable=False), schema=domain,
    )


def inbox_table(domain: str) -> Table:
    return Table(
        "inbox", MetaData(), Column("consumer", String(255), primary_key=True),
        Column("event_id", String(64), primary_key=True),
        Column("received_at", DateTime(timezone=True), nullable=False), schema=domain,
    )


def consume(domain: str, consumer: str, event_id: str, data: dict, handler: Callable[[Session, dict], object]) -> None:
    table = inbox_table(domain)
    with service_session_factory().begin() as session:
        claimed = session.scalar(insert(table).values(
            consumer=consumer, event_id=event_id, received_at=datetime.now(UTC),
        ).on_conflict_do_nothing().returning(table.c.event_id))
        if claimed is not None:
            handler(session, data)
