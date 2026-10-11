"""Fixtures compartilhadas de teste: banco em memória por serviço (T010).

Cada teste usa um engine SQLite em memória (paridade de comportamento com
PostgreSQL nos limites deste escopo; integração ponta a ponta usa
docker-compose/quickstart). O barramento de eventos (RabbitMQ) é simulado
pelo fixture `events`: captura as publicações e `replay()` entrega os
eventos capturados aos handlers do serviço alvo — "fast-forward do broker".
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy.orm import Session

sys.path.insert(0, "src")

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from shared import messaging  # noqa: E402
from shared.db import (
    Base,  # noqa: E402
    make_session_factory,  # noqa: E402
)

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def db_session() -> Iterator[Session]:
    # SQLite em memória compartilhado entre threads (TestClient roda em outra thread)
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def events() -> Iterator[list[dict[str, Any]]]:
    """Captura toda publicação do barramento (RABBITMQ_URL nunca é lido aqui)."""
    published: list[dict[str, Any]] = []

    def capture(event_type: str, data: dict, request_id: str | None) -> None:
        published.append({"type": event_type, "data": data, "request_id": request_id})

    messaging.set_publisher(capture)
    yield published
    messaging.set_publisher(None)


@pytest.fixture
def replay(events: list[dict[str, Any]]) -> Callable[..., None]:
    """Reproduz no serviço alvo os eventos capturados (o broker "acontece")."""

    def apply(service: str, db: Session) -> None:
        rest: list[dict[str, Any]] = []
        for event in events:
            if not _deliver(service, db, event):
                rest.append(event)
        events[:] = rest

    return apply


def _deliver(service: str, db: Session, event: dict[str, Any]) -> bool:
    if service == "insights":
        from services.insights.app.core import handlers as insights_handlers

        if event["type"] == "visit.validated":
            insights_handlers.ingest_visit_fact(db, event["data"])
            return True
        if event["type"] == "access.registered":
            insights_handlers.ingest_access(db, event["data"])
            return True
    elif service == "notifications":
        from services.notifications.app.core import dispatcher

        if event["type"] == "notification.dispatch":
            dispatcher.apply_dispatch(db, event["data"])
            return True
    elif service == "chatbot":
        from services.chatbot.app.core import indexer

        if event["type"] == "catalog.index.refresh":
            indexer.refresh_from_payload(db, event["data"])
            return True
    return False
