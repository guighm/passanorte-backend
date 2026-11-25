"""Fixtures compartilhadas de teste: banco em memória por serviço (T010).

Cada teste usa um engine SQLite em memória (paridade de comportamento com
PostgreSQL nos limites deste escopo; integração ponta a ponta usa
docker-compose/quickstart). O barramento de eventos (RabbitMQ) é simulado
pelo fixture `events`: captura as publicações e `replay()` entrega os
eventos capturados aos handlers do serviço alvo — "fast-forward do broker".
"""

from __future__ import annotations

import atexit
import os
import secrets
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.orm import Session

sys.path.insert(0, "src")


_test_keys = tempfile.TemporaryDirectory()
atexit.register(_test_keys.cleanup)
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_key_dir = Path(_test_keys.name)
(_key_dir / "test.pem").write_bytes(_key.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
# Private file outside public directory, preventing accidental exposure to verifiers.
_private = _key_dir / "signing.key"
_private.write_bytes(_key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
for _name in (
    "DATABASE_URL_FILE", "RABBITMQ_URL", "RABBITMQ_URL_FILE", "JWT_PRIVATE_KEY",
    "PII_ENCRYPTION_KEY_FILE", "PII_HMAC_KEY_FILE",
):
    os.environ.pop(_name, None)
os.environ["JWT_ISSUER"] = "passanorte"
os.environ["JWT_AUDIENCE"] = "passanorte-api"
os.environ["ACCESS_TOKEN_MINUTES"] = "15"
os.environ["REFRESH_TOKEN_DAYS"] = "7"
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_ACTIVE_KID"] = "test"
os.environ["JWT_PUBLIC_KEYS_DIR"] = str(_key_dir)
os.environ["JWT_PRIVATE_KEY_FILE"] = str(_private)
os.environ.pop("INTERNAL_API_TOKEN_FILE", None)
os.environ["INTERNAL_API_TOKEN"] = secrets.token_urlsafe(48)
os.environ["PII_HMAC_KEY"] = secrets.token_urlsafe(48)
os.environ["PII_ENCRYPTION_KEY"] = Fernet.generate_key().decode()


from sqlalchemy import Engine, create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from shared import messaging  # noqa: E402
from shared.db import DOMAINS, make_session_factory  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable


def create_test_tables(engine: Engine) -> Engine:
    from importlib import import_module

    translated = engine.execution_options(schema_translate_map={name: None for name in DOMAINS})
    import_module("services.validation.app.models.visit")
    for name in DOMAINS:
        import_module(f"services.{name}.app.models")
        base = import_module(f"services.{name}.app.db").Base
        base.metadata.create_all(translated)
    return translated


@pytest.fixture
def db_session() -> Iterator[Session]:
    # SQLite em memória compartilhado entre threads (TestClient roda em outra thread)
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = make_session_factory(create_test_tables(engine))
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
        if event["type"] == "tourist.login":
            insights_handlers.ingest_tourist_login(db, event["data"])
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


@pytest.fixture
def internal_headers() -> dict[str, str]:
    return {"X-Internal-Token": os.environ["INTERNAL_API_TOKEN"]}


@pytest.fixture
def connect_partner_services(internal_headers):
    from fastapi.testclient import TestClient

    from services.auth.app.core.partners import get_partner_lookup
    from services.benefits.app.api.partners import get_db
    from services.benefits.app.main import app

    def connect(auth_app, session):
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)

        def lookup(partner_id):
            response = client.get(f"/api/v1/internal/partners/{partner_id}", headers=internal_headers)
            if response.status_code == 404:
                return None
            return response.raise_for_status().json()

        auth_app.dependency_overrides[get_partner_lookup] = lambda: lookup
        return client

    yield connect

    app.dependency_overrides.clear()


@pytest.fixture
def connect_route_services(db_session, internal_headers):
    """Exercise both HTTP contracts without a Docker network."""
    from fastapi.testclient import TestClient

    from services.catalog.app.api.routes import get_prize_service
    from services.catalog.app.core.deps import get_db
    from services.catalog.app.main import create_test_app
    from services.gamification.app.core.deps import get_route_lookup
    from shared.internal_client import RouteSnapshot

    def connect(gamification_app):
        catalog_app = create_test_app()
        catalog_app.dependency_overrides[get_db] = lambda: db_session
        catalog = TestClient(catalog_app)
        gamification = TestClient(gamification_app)

        def prizes(method, path, **kwargs):
            response = gamification.request(method, f"/api/v1{path}", headers=internal_headers, **kwargs)
            return response.raise_for_status().json()

        def lookup(route_id):
            response = catalog.get(f"/api/v1/internal/routes/{route_id}", headers=internal_headers)
            if response.status_code == 404:
                return None
            return RouteSnapshot.model_validate(response.raise_for_status().json())

        catalog_app.dependency_overrides[get_prize_service] = lambda: prizes
        gamification_app.dependency_overrides[get_route_lookup] = lambda: lookup
        return catalog, gamification

    return connect
