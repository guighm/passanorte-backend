import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func

from services.catalog.app.models.spot import Event
from shared.internal_client import call_internal


def deployment_timezone() -> str:
    return os.environ.get("DEPLOYMENT_TIMEZONE", "America/Manaus")


def event_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        name = deployment_timezone()
        try:
            zone: timezone | ZoneInfo = ZoneInfo(name)
        except ZoneInfoNotFoundError:
            if name != "America/Manaus":
                raise
            zone = timezone(timedelta(hours=-4))
        value = value.replace(tzinfo=zone)
    return value.astimezone(UTC).replace(tzinfo=None)


def upcoming():
    return func.coalesce(Event.ends_at, Event.occurs_at) > datetime.now(UTC).replace(tzinfo=None)


def event_body(event: Event) -> dict:
    start = event.occurs_at.replace(tzinfo=UTC).isoformat()
    return {
        "id": event.id, "tourist_spot_id": event.tourist_spot_id, "title": event.title,
        "description": event.description, "starts_at": start, "occurs_at": start,
        "ends_at": event.ends_at.replace(tzinfo=UTC).isoformat() if event.ends_at else None,
        "ticket_price": float(event.ticket_price),
    }


def get_interest_lookup() -> Callable[[str], set[str]]:
    def lookup(user_id: str) -> set[str]:
        base = os.environ.get("AUTH_SERVICE_URL", "http://auth:8001")
        return set(call_internal(base, "GET", f"/internal/users/{user_id}/interests")["category_ids"])

    return lookup
