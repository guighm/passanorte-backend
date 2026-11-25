from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.settings import Settings

DOMAINS = ("auth", "catalog", "gamification", "benefits", "insights", "notifications", "chatbot")


def database_url() -> str:
    url = Settings.load().database_url.get_secret_value()
    return url


def create_service_engine(echo: bool = False) -> Engine:
    url = database_url()
    engine = create_engine(
        url, echo=echo, pool_pre_ping=True, hide_parameters=True,
        **({"pool_size": 5, "max_overflow": 2, "pool_timeout": 5, "connect_args": {"connect_timeout": 3}}
           if url.startswith("postgresql") else {}),
    )
    if engine.dialect.name == "sqlite":
        return engine.execution_options(schema_translate_map={name: None for name in DOMAINS})
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@lru_cache(maxsize=1)
def service_session_factory() -> sessionmaker[Session]:
    """One pool per service process, shared by HTTP dependencies and consumers."""
    return make_session_factory(create_service_engine())
