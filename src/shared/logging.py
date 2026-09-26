"""Logging estruturado JSON com correlation ID (Princípio V, D-05).

Cada request recebe um correlation ID (X-Request-Id, herdado quando o cliente
propaga) registrado em ContextVar e injetado em todas as linhas de log.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_request_id() -> str:
    return request_id_var.get()


def new_request_id() -> str:
    value = uuid.uuid4().hex
    request_id_var.set(value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "service": getattr(record, "service", None) or record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(service_name: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").disabled = True


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    """Log estruturado: cada linha é um JSON com o evento e campos extras."""
    logger.info(event, extra={"extra_fields": {"event": event, **fields}})


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Atribui/propaga o correlation ID em cada request HTTP."""

    def __init__(self, app: object, service_name: str) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        inherited = request.headers.get("X-Request-Id") or new_request_id()
        request_id_var.set(inherited)
        response = await call_next(request)
        response.headers["X-Request-Id"] = get_request_id()
        return response
