"""RabbitMQ transport with a transactional outbox and per-consumer inbox."""
from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections.abc import Awaitable, Callable
from concurrent.futures import Future
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import aio_pika
from aio_pika import DeliveryMode, ExchangeType
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue
from pamqp.commands import Basic
from pydantic import AliasChoices, BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from shared import delivery
from shared.db import service_session_factory
from shared.logging import get_request_id, log_event, new_request_id, request_id_var

logger = logging.getLogger("messaging")

EXCHANGE_EVENTS = "passanorte.events"
EXCHANGE_DLX = "passanorte.dlx"
QUEUE_DLQ = "passanorte.dlq"
RECONNECT_INTERVAL = 5.0
CONNECT_TIMEOUT = 10.0

PublisherFn = Callable[[str, dict, str | None], None]


class EventEnvelope(BaseModel):
    """Envelope do evento: request_id propaga o correlation ID entre serviços."""

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: str = Field(validation_alias=AliasChoices("event_type", "type"), serialization_alias="event_type")
    occurred_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    request_id: str = Field(default="", validation_alias=AliasChoices("correlation_id", "request_id"),
                            serialization_alias="correlation_id")
    data: dict = Field(validation_alias=AliasChoices("payload", "data"), serialization_alias="payload")
    schema_version: int = Field(default=1, ge=1, le=1)
    producer: str = "legacy"
    aggregate_id: str | None = None
    aggregate_version: int | None = None


@dataclass(frozen=True)
class ConsumerSpec:
    """Consumidor: fila durable por (serviço, routing key) + handler sync."""

    service: str
    routing_key: str
    handler: Callable[..., object]
    transactional: bool = False

    def queue_name(self) -> str:
        return f"passanorte.{self.service}.{self.routing_key}"


class _State:
    """Estado do broker: o loop/thread guardados na lock; o restante é
    confinado ao loop daemon (connection, tasks, exchange)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.url = ""
        self.domain = ""
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self.stopping = False
        self.supervisor = False
        self.consumers: list[ConsumerSpec] = []
        self.publisher_override: PublisherFn | None = None
        self.degraded_warned = False

        # confinado ao loop daemon (só o thread do AMQP toca neles)
        self.connection: aio_pika.RobustConnection | None = None
        self.publish_exchange: aio_pika.abc.AbstractExchange | None = None
        self.tasks: set[asyncio.Task] = set()
        self.connected = asyncio.Event()


_state = _State()


def configure(url: str | None, domain: str = "") -> None:
    """Define a URL do broker (chamada no lifespan). Vazio → degradado."""
    _state.url = (url or "").strip()
    _state.domain = domain


def set_publisher(fn: PublisherFn | None) -> None:
    """Seam de teste (padrão do `get_propagator`): intercepta toda publicação."""
    _state.publisher_override = fn


def publish(event_type: str, data: dict, request_id: str | None = None) -> None:
    """Publica um evento no exchange topic. Sync, nunca levanta e nunca
    bloqueia — a entrega tolerante a falha acontece no loop daemon."""
    override = _state.publisher_override
    if override is not None:
        override(event_type, data, request_id)
        return
    if not _state.url:
        _warn_degraded_once()
        return
    envelope = EventEnvelope(
        type=event_type,
        data=data,
        request_id=request_id if request_id is not None else get_request_id(),
    )
    try:
        loop = _ensure_supervisor()
    except RuntimeError:  # interpreter encerrando — evento perdido (tolerável)
        return
    if loop is None:
        return
    future = asyncio.run_coroutine_threadsafe(_publish_async(envelope), loop)
    future.add_done_callback(_log_scheduling_error)


def enqueue(db: Session | None, event_type: str, data: dict) -> None:
    """Persist the event within the caller's transaction."""
    if db is None or _state.publisher_override is not None:
        publish(event_type, data)
        return
    envelope = EventEnvelope(
        type=event_type, data=data, producer=_state.domain, request_id=get_request_id(),
        aggregate_id=data.get("source_id") or data.get("tourist_spot_id") or data.get("user_id"),
    )
    db.execute(delivery.outbox_table(_state.domain).insert().values(
        event_id=envelope.event_id, created_at=datetime.now(UTC), available_at=datetime.now(UTC),
        envelope=envelope.model_dump(by_alias=True),
    ))


def _relay_once(domain: str) -> None:
    if not broker_ready():
        return
    loop = _state.loop
    if loop is None:
        return
    table = delivery.outbox_table(domain)
    with service_session_factory().begin() as session:
        row = session.execute(
            table.select().where(table.c.available_at <= datetime.now(UTC))
            .order_by(table.c.created_at, table.c.event_id).limit(1).with_for_update(skip_locked=True)
        ).first()
        if row is None:
            return
        event = EventEnvelope.model_validate(row.envelope)
        future = asyncio.run_coroutine_threadsafe(_publish_confirmed(event), loop)
        try:
            future.result(timeout=5)
        except Exception as exc:
            future.cancel()
            session.execute(table.update().where(table.c.event_id == event.event_id).values(
                available_at=datetime.now(UTC) + timedelta(seconds=5),
            ))
            log_event(logger, "outbox_retry", event_id=event.event_id, error=type(exc).__name__)
        else:
            session.execute(table.delete().where(table.c.event_id == event.event_id))


async def relay(domain: str) -> None:
    while True:
        try:
            await asyncio.to_thread(_relay_once, domain)
        except Exception as exc:
            log_event(logger, "outbox_relay_failed", error=type(exc).__name__)
        await asyncio.sleep(0.25)


def broker_ready() -> bool:
    connection = _state.connection
    return bool(connection and connection.connected.is_set() and _state.connected.is_set())


async def _publish_confirmed(envelope: EventEnvelope) -> None:
    exchange = _state.publish_exchange
    if exchange is None:
        raise ConnectionError("Broker is not ready")
    confirmation = await exchange.publish(
        aio_pika.Message(body=envelope.model_dump_json(by_alias=True).encode(),
                         delivery_mode=DeliveryMode.PERSISTENT, message_id=envelope.event_id),
        routing_key=envelope.type, mandatory=True, timeout=4,
    )
    if not isinstance(confirmation, Basic.Ack):
        raise ConnectionError("Broker did not confirm publication")


def start_consumers(specs: list[ConsumerSpec]) -> None:
    """Registra consumers (substitui os anteriores) e garante a conexão."""
    _state.consumers = list(specs)
    if not _state.url:
        _warn_degraded_once()
        return
    _ensure_supervisor()


def stop() -> None:
    """Shutdown graciosa: cancela tasks, fecha a conexão e encerra o thread."""
    with _state.lock:
        thread, loop = _state.thread, _state.loop
    if thread is None or loop is None or not thread.is_alive():
        return
    try:
        asyncio.run_coroutine_threadsafe(_graceful_close(), loop).result(timeout=10)
    except Exception:  # noqa: BLE001 — shutdown o melhor esforço possível
        pass
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)
    if not thread.is_alive():
        _state.connection = None
        _state.publish_exchange = None
        _state.tasks.clear()
        _state.connected = asyncio.Event()
        _state.stopping = False


def _warn_degraded_once() -> None:
    with _state.lock:
        if _state.degraded_warned:
            return
        _state.degraded_warned = True
    log_event(logger, "event_publish_degraded", detail="RABBITMQ_URL ausente — eventos não são publicados")


def _log_scheduling_error(future: Future[None]) -> None:
    if not future.cancelled() and (exc := future.exception()) is not None:
        log_event(logger, "event_publish_failed", error=type(exc).__name__)


def _ensure_supervisor() -> asyncio.AbstractEventLoop | None:
    """Inicia o thread do loop AMQP e nele a tarefa-supervisora (idempotente).

    Devolve None quando o broker está encerrando (evento perdido, tolerável).
    """
    with _state.lock:
        if _state.stopping:
            return None
        if _state.thread is not None and _state.thread.is_alive() and _state.supervisor:
            return _state.loop
        loop = asyncio.new_event_loop()
        _state.loop = loop
        _state.supervisor = True
        thread = threading.Thread(target=_run_loop, args=(loop,), name="amqp", daemon=True)
        _state.thread = thread
        thread.start()

        async def _spawn() -> None:
            _state.tasks.add(asyncio.create_task(_supervisor()))

        asyncio.run_coroutine_threadsafe(_spawn(), loop)
        return loop


def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    finally:
        loop.close()


async def _supervisor() -> None:
    """Conecta, declara a topologia e consome; reconecta indefinidamente."""
    while not _state.stopping:
        try:
            connection = await aio_pika.connect_robust(
                _state.url,
                reconnect_interval=RECONNECT_INTERVAL,
            )
        except Exception as exc:  # noqa: BLE001 — disponibilidade é tolerância a falhas
            _state.connected.clear()
            log_event(logger, "event_broker_unavailable", error=type(exc).__name__)
            await asyncio.sleep(RECONNECT_INTERVAL)
            continue
        _state.connection = connection
        try:
            # publisher confirms já vêm ligados por default (publisher_confirms=True)
            channel = await connection.channel(on_return_raises=True)
            _state.publish_exchange = await channel.declare_exchange(
                EXCHANGE_EVENTS, ExchangeType.TOPIC, durable=True
            )
            dlx = await channel.declare_exchange(EXCHANGE_DLX, ExchangeType.TOPIC, durable=True)
            dlq = await channel.declare_queue(QUEUE_DLQ, durable=True)
            await dlq.bind(dlx, routing_key="#")
            for consumer, routing_key in (
                ("insights", "visit.validated"), ("insights", "access.registered"), ("insights", "tourist.login"),
                ("notifications", "notification.dispatch"), ("chatbot", "catalog.index.refresh"),
            ):
                await _declare_queue(channel, f"passanorte.{consumer}.{routing_key}", routing_key)
            for spec in _state.consumers:
                await _consume_forever(connection, spec)
        except Exception as exc:
            await connection.close()
            log_event(logger, "event_topology_unavailable", error=type(exc).__name__)
            await asyncio.sleep(RECONNECT_INTERVAL)
            continue
        log_event(logger, "event_broker_connected", exchange=EXCHANGE_EVENTS)
        _state.connected.set()
        while not connection.is_closed and not _state.stopping:
            await asyncio.sleep(0.5)
        if _state.stopping:
            return
        _state.connected.clear()  # queda: publishes aguardam a reconexão
        log_event(logger, "event_broker_disconnected")



async def _consume_forever(
    connection: aio_pika.RobustConnection,
    spec: ConsumerSpec,
) -> None:
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    queue = await _declare_queue(channel, spec.queue_name(), spec.routing_key)
    await queue.consume(_make_callback(spec))


async def _declare_queue(channel, name: str, routing_key: str) -> AbstractQueue:
    queue = await channel.declare_queue(
        name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": EXCHANGE_DLX,
            "x-dead-letter-routing-key": name,
        },
    )
    await queue.bind(EXCHANGE_EVENTS, routing_key=routing_key)
    return queue


def _make_callback(spec: ConsumerSpec) -> Callable[[AbstractIncomingMessage], Awaitable[None]]:
    async def callback(message: AbstractIncomingMessage) -> None:
        try:
            envelope = EventEnvelope.model_validate_json(message.body)
        except ValidationError:
            log_event(
                logger,
                "event_poison",
                queue=spec.queue_name(),
            )
            await _finish(message, ack=False, requeue=False)  # veneno → DLQ
            return
        request_id_var.set(envelope.request_id or new_request_id())
        try:
            if envelope.type != spec.routing_key:
                await _finish(message, ack=False, requeue=False)
                return
            if spec.transactional:
                await asyncio.to_thread(
                    delivery.consume, spec.service, spec.queue_name(), envelope.event_id, envelope.data, spec.handler,
                )
            else:
                await asyncio.to_thread(spec.handler, envelope.data)
        except Exception as exc:  # noqa: BLE001 — handler não pode derrubar o consumer
            log_event(
                logger,
                "event_handler_failed",
                queue=spec.queue_name(),
                event_type=envelope.type,
                error=type(exc).__name__,
                redelivered=message.redelivered,
            )
            # 1ª falha → requeue; na redelivery → DLQ (MAX_ATTEMPTS=2)
            if not message.redelivered:
                await asyncio.sleep(2)
            await _finish(message, ack=False, requeue=not message.redelivered)
        else:
            await _finish(message, ack=True, requeue=False)
            log_event(
                logger,
                "event_received",
                event_type=envelope.type,
                event_id=envelope.event_id,
                queue=spec.queue_name(),
            )

    return callback


async def _finish(
    message: AbstractIncomingMessage,
    *,
    ack: bool,
    requeue: bool,
) -> None:
    try:
        if ack:
            await message.ack()
        else:
            await message.nack(requeue=requeue)
    except Exception as exc:  # noqa: BLE001 — message já entregue/processada
        log_event(logger, "event_delivery_finish_failed", error=type(exc).__name__)


async def _publish_async(envelope: EventEnvelope) -> None:
    """Publica com PERSISTENT no exchange; falha é logada, não levantada.

    Aguarda a conexão (a `connected` é limpa em queda do broker, então uma
    publicação feita durante a queda espera a reconexão, até CONNECT_TIMEOUT).
    """
    for _attempt in range(2):
        try:
            await asyncio.wait_for(_state.connected.wait(), timeout=CONNECT_TIMEOUT)
        except TimeoutError:
            log_event(
                logger,
                "event_publish_failed",
                event_type=envelope.type,
                event_id=envelope.event_id,
                reason="broker indisponível",
            )
            return
        try:
            message = aio_pika.Message(
                body=envelope.model_dump_json(by_alias=True).encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                message_id=envelope.event_id,
            )
            exchange = _state.publish_exchange
            if exchange is None:  # desconectou entre o wait e o publish
                raise ConnectionError("sem exchange para publicar")
            await exchange.publish(message, routing_key=envelope.type)
            log_event(logger, "event_published", event_type=envelope.type, event_id=envelope.event_id)
            return
        except Exception as exc:  # noqa: BLE001 — publish é fire-and-forget
            log_event(
                logger,
                "event_publish_retry",
                event_type=envelope.type,
                event_id=envelope.event_id,
                error=type(exc).__name__,
            )

    log_event(logger, "event_publish_failed", event_type=envelope.type, event_id=envelope.event_id,
              reason="broker indisponível")


async def _graceful_close() -> None:
    _state.stopping = True
    for task in list(_state.tasks):
        task.cancel()
    await asyncio.gather(*list(_state.tasks), return_exceptions=True)
    if _state.connection is not None:
        await _state.connection.close()
