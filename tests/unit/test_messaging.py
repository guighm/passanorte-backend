"""Unit: barramento de eventos (shared/messaging) — sem broker real.

Envelope, seam de publisher, degradação sem RABBITMQ_URL e nomes de filas.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

import shared.messaging as messaging  # noqa: E402
from shared.messaging import ConsumerSpec, EventEnvelope, configure, publish, set_publisher  # noqa: E402


def test_envelope_defaults_and_roundtrip():
    envelope = EventEnvelope(type="visit.validated", data={"user_id": "u1"})
    assert envelope.event_id and len(envelope.event_id) == 32
    assert uuid.UUID(hex=envelope.event_id)  # é um uuid4 hex válido
    assert envelope.occurred_at  # ISO-8601
    assert envelope.request_id == ""

    parsed = EventEnvelope.model_validate_json(envelope.model_dump_json())
    assert parsed.data == {"user_id": "u1"}
    assert parsed.type == "visit.validated"


def test_envelope_rejects_missing_type():
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate_json('{"data": {"a": 1}}')


def test_consumer_spec_queue_naming():
    spec = ConsumerSpec(service="insights", routing_key="visit.validated", handler=lambda data: None)
    assert spec.queue_name() == "passanorte.insights.visit.validated"


def test_publish_uses_publisher_override():
    captured: list[tuple[str, dict, str | None]] = []
    set_publisher(lambda et, data, rid: captured.append((et, data, rid)))
    try:
        publish("notification.dispatch", {"kind": "new_spot"}, request_id="req-1")
        publish("access.registered", {"user_id": "u1"})
    finally:
        set_publisher(None)  # restaura (o fixture autouse também garante)

    assert captured == [
        ("notification.dispatch", {"kind": "new_spot"}, "req-1"),
        ("access.registered", {"user_id": "u1"}, None),
    ]


def test_publish_without_url_is_degraded_noop(events):
    # com o seam instado (override), o publish NÃO chega na branch degradada;
    # removo-o manualmente para exercitar o caminho degradado real
    messaging.set_publisher(None)
    configure("")
    thread_before = messaging._state.thread
    publish("visit.validated", {"user_id": "u1"})
    publish("visit.validated", {"user_id": "u2"})
    assert messaging._state.thread == thread_before
    assert messaging._state.degraded_warned  # warn único, publica nada
