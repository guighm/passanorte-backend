import os
from collections.abc import Callable
from urllib.parse import quote

from shared.internal_client import call_internal


def get_partner_lookup() -> Callable[[str], dict | None]:
    def lookup(partner_id: str) -> dict | None:
        base = os.environ.get("BENEFITS_SERVICE_URL", "http://benefits:8008")
        result: dict | None = call_internal(
            base, "GET", f"/internal/partners/{quote(partner_id, safe='')}", missing_ok=True,
        )
        return result

    return lookup
