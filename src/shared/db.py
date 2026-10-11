"""Banco compartilhado: Base declarativa, engine e sessão por serviço (T011).

Cada microsserviço aponta DATABASE_URL para o SEU database (Princípio I).
"""

from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")
    return url


def create_service_engine(echo: bool = False):
    return create_engine(database_url(), echo=echo, pool_pre_ping=True)


def make_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@lru_cache(maxsize=1)
def service_session_factory() -> sessionmaker[Session]:
    """Factory de sessão cacheada por processo — usada pelos consumers AMQP
    (o `get_db` dos endpoints reconstrói engine por request; o consumer
    reusa um só engine)."""
    return make_session_factory(create_service_engine())
