"""Small contracts for authenticated service-to-service calls."""
from typing import Any

import httpx
from pydantic import BaseModel

from shared.errors import ApiError
from shared.logging import get_request_id
from shared.settings import secret


class RouteSnapshot(BaseModel):
    id: str
    name: str
    is_active: bool
    prize_id: str
    points: list[str]


def call_internal(base: str, method: str, path: str, *, missing_ok: bool = False, **kwargs: Any) -> Any:
    headers = {"X-Internal-Token": secret("INTERNAL_API_TOKEN"), "X-Request-Id": get_request_id()}
    try:
        response = httpx.request(method, f"{base.rstrip('/')}/api/v1{path}", headers=headers, timeout=5, **kwargs)
        if missing_ok and response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise ApiError(
            code="dependency_unavailable", message="Serviço interno indisponível.", status_code=503,
        ) from None
