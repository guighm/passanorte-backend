"""Tabela de roteamento e políticas de acesso do gateway.

Resolve duas perguntas para cada request da borda:
1. Qual serviço é dono do prefixo da rota? (`resolve_service`)
2. Quais papéis podem acessá-la? (`resolve_route`, regras coarse-grained)

As regras aqui são a primeira camada de autorização (defesa em profundidade):
os serviços mantêm suas próprias verificações de `require_role`.

Política de fallback: rotas de um serviço conhecido sem regra específica ficam
com `DEFAULT_ACCESS` (qualquer papel autenticado) — o serviço decide o resto.
Rotas `/internal/*` são bloqueadas na borda (uso exclusivo inter-serviço).
"""

from __future__ import annotations

import os

ROLES = ("admin", "employee", "tourist")

PUBLIC: frozenset[str] = frozenset()  # sem autenticação
ANY: frozenset[str] = frozenset(ROLES)  # qualquer papel autenticado
ADMIN: frozenset[str] = frozenset({"admin"})
EMPLOYEE: frozenset[str] = frozenset({"employee"})
TOURIST: frozenset[str] = frozenset({"tourist"})

INTERNAL = "internal"  # sentinel: rota inter-serviço, bloqueada na borda

DEFAULT_ACCESS = ANY


def _service_urls() -> dict[str, str]:
    """URL base de cada serviço (mesmas variáveis do D-05, com fallback local)."""
    ports = {
        "auth": 8001,
        "catalog": 8002,
        "validation": 8003,
        "gamification": 8004,
        "insights": 8005,
        "notifications": 8006,
        "chatbot": 8007,
    }
    return {
        name: os.environ.get(f"{name.upper()}_SERVICE_URL", f"http://localhost:{port}")
        for name, port in ports.items()
    }


SERVICE_URLS = _service_urls()

# Prefixo de primeiro segmento → serviço dono (sem colisões entre serviços).
PREFIX_TO_SERVICE: list[tuple[str, str]] = [
    ("/tourist-spots", "catalog"),
    ("/admin/tourist-spots", "catalog"),
    ("/categories", "catalog"),
    ("/events", "catalog"),
    ("/tourists", "auth"),
    ("/session", "auth"),
    ("/me", "auth"),
    ("/employees", "auth"),
    ("/visits", "validation"),
    ("/routes", "gamification"),
    ("/enrollments", "gamification"),
    ("/redemptions", "gamification"),
    ("/prizes", "gamification"),
    ("/badges", "gamification"),
    ("/redeem-codes", "gamification"),
    ("/heatmap", "insights"),
    ("/accesses", "insights"),
    ("/rankings", "insights"),
    ("/distributions", "insights"),
    ("/subscriptions", "notifications"),
    ("/notifications", "notifications"),
    ("/conversations", "chatbot"),
]

# (método, caminho, papéis permitidos) — sem colisão entre padrões de mesmo método,
# a ordem só importa para padrões que podem sombrear outros (ex.: /me/interests).
RULES: list[tuple[str, str, frozenset[str]]] = [
    # auth
    ("POST", "/tourists", PUBLIC),
    ("POST", "/session", PUBLIC),
    ("POST", "/session/refresh", PUBLIC),
    ("DELETE", "/session", ANY),
    ("GET", "/me", ANY),
    ("PATCH", "/me", ANY),
    ("GET", "/me/interests", ANY),
    ("PUT", "/me/interests", ANY),
    ("GET", "/employees", ADMIN),
    ("POST", "/employees", ADMIN),
    ("PATCH", "/employees/{employee_id}", ADMIN),
    ("DELETE", "/employees/{employee_id}", ADMIN),
    # catalog (leitura pública, escrita admin)
    ("GET", "/tourist-spots", PUBLIC),
    ("GET", "/tourist-spots/{spot_id}", PUBLIC),
    ("GET", "/tourist-spots/{spot_id}/external-links", PUBLIC),
    ("POST", "/tourist-spots", ADMIN),
    ("PATCH", "/tourist-spots/{spot_id}", ADMIN),
    ("DELETE", "/tourist-spots/{spot_id}", ADMIN),
    ("PUT", "/tourist-spots/{spot_id}/schedule", ADMIN),
    ("PATCH", "/tourist-spots/{spot_id}/status", ADMIN),
    ("GET", "/admin/tourist-spots/{spot_id}", ADMIN),
    ("GET", "/categories", PUBLIC),
    ("POST", "/categories", ADMIN),
    ("GET", "/events", PUBLIC),
    ("POST", "/events", ADMIN),
    ("PATCH", "/events/{event_id}", ADMIN),
    ("DELETE", "/events/{event_id}", ADMIN),
    # validation (qualquer papel autenticado; o serviço diferencia turista)
    ("POST", "/visits", ANY),
    ("GET", "/visits", ANY),
    ("GET", "/visits/{spot_id}", ANY),
    # gamification
    ("GET", "/routes", PUBLIC),
    ("POST", "/routes", ADMIN),
    ("PATCH", "/routes/{route_id}", ADMIN),
    ("DELETE", "/routes/{route_id}", ADMIN),
    ("POST", "/routes/{route_id}/enrollments", TOURIST),
    ("GET", "/enrollments", TOURIST),
    ("GET", "/enrollments/{route_id}", TOURIST),
    ("POST", "/redemptions", EMPLOYEE),
    ("GET", "/prizes", ADMIN),
    ("POST", "/prizes", ADMIN),
    ("PATCH", "/prizes/{prize_id}/stock", ADMIN),
    ("GET", "/badges", TOURIST),
    ("GET", "/redeem-codes", TOURIST),
    # insights (dashboard admin)
    ("GET", "/heatmap", ADMIN),
    ("GET", "/accesses", ADMIN),
    ("GET", "/rankings/{rest}", ADMIN),
    ("GET", "/distributions/{rest}", ADMIN),
    # notifications
    ("PUT", "/subscriptions", TOURIST),
    ("GET", "/subscriptions", TOURIST),
    ("GET", "/notifications", TOURIST),
    ("PATCH", "/notifications/{notification_id}/read", TOURIST),
    # chatbot
    ("POST", "/conversations", TOURIST),
    ("GET", "/conversations", TOURIST),
    ("GET", "/conversations/{conversation_id}", TOURIST),
    ("POST", "/conversations/{conversation_id}/messages", TOURIST),
]


def _matches(pattern: str, path: str) -> bool:
    """Padrão de segmentos: `{x}` casa um segmento; literais casam exatamente."""
    expected = pattern.strip("/").split("/")
    actual = path.strip("/").split("/")
    if len(expected) != len(actual):
        return False
    return all(
        (segment.startswith("{") and segment.endswith("}")) or segment == value
        for segment, value in zip(expected, actual, strict=True)
    )


def resolve_service(path: str) -> str | None:
    """Serviço dono do caminho; `INTERNAL` para rotas inter-serviço; None se desconhecido."""
    if path.startswith("/internal"):
        return INTERNAL
    for prefix, service in PREFIX_TO_SERVICE:
        if path.startswith(prefix):
            return service
    return None


def resolve_route(method: str, path: str) -> tuple[str, frozenset[str]] | None:
    """Resolve (serviço, papéis permitidos) para o request da borda.

    - `(INTERNAL, ...)` → rota inter-serviço, deve ser bloqueada;
    - `None` → serviço desconhecido, 404;
    - papéis vazios → pública; senão exige token com um dos papéis.
    """
    if path.startswith("/internal"):
        return (INTERNAL, frozenset())
    service = resolve_service(path)
    if service is None:
        return None
    for rule_method, pattern, access in RULES:
        if rule_method != method and rule_method != "*":
            continue
        if _matches(pattern, path):
            return (service, access)
    return (service, DEFAULT_ACCESS)
