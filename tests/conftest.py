"""Fixtures compartilhadas de teste: banco em memória por serviço (T010).

Cada teste usa um engine SQLite em memória (paridade de comportamento com
PostgreSQL nos limites deste escopo; integração ponta a ponta usa
docker-compose/quickstart).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

sys.path.insert(0, "src")

os.environ.setdefault("JWT_SECRET", "test-secret-32-bytes-for-hs256-00")
os.environ.setdefault("PII_ENCRYPTION_KEY", "MgBPF0RbsIxVX4Vi5ZCp0P5ylutyWhnhSeB_9xIrsMY=")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from shared.db import (
    Base,  # noqa: E402
    make_session_factory,  # noqa: E402
)


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
