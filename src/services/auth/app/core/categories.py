import os
from collections.abc import Callable

from shared.errors import ApiError
from shared.internal_client import call_internal


def get_category_lookup() -> Callable[[list[str]], set[str]]:
    def lookup(ids: list[str]) -> set[str]:
        base = os.environ.get("CATALOG_SERVICE_URL", "http://catalog:8002")
        return set(call_internal(base, "POST", "/internal/category-ids", json=ids)["ids"])

    return lookup


def validate_categories(ids: list[str], lookup: Callable[[list[str]], set[str]]) -> list[str]:
    unique = list(dict.fromkeys(ids))
    if unique and lookup(unique) != set(unique):
        raise ApiError("invalid_categories", "Selecione categorias ativas do catálogo.", 422)
    return unique
