# Serviço Gateway (porta 8000)

Borda única dos 7 microsserviços (D-02, Princípio V): os clientes conversam só com este endereço. Uma única rota catch-all `ANY /api/v1/{path}` (oculta do OpenAPI) roteia cada request para o serviço dono do prefixo, valida o JWT na borda, aplica autorização coarse-grained (rota → papéis), bloqueia rotas `/internal/*` com **404** (esconde a existência delas) e centraliza o CORS.

Não tem banco próprio nem `alembic/` — é um proxy stateless (sem `DATABASE_URL`).

## Como rodar

```bash
uv run uvicorn services.gateway.app.main:app --port 8000
```

Ou com o docker-compose (raiz do monorepo): `docker compose up gateway`.

Os demais serviços precisam estar no ar (localmente nas portas 8001–8007 ou via compose). Docs interativos: `http://localhost:8000/docs` (só expõem `GET /health`, pois o proxy é oculto do schema).

## Roteamento e autorização

`app/core/routing.py` resolve duas perguntas por request — qual serviço é dono do prefixo e quais papéis podem acessá-la:

| Prefixo(s) | Serviço |
|---|---|
| `/tourist-spots`, `/admin/tourist-spots`, `/categories`, `/events` | catalog |
| `/tourists`, `/session`, `/me`, `/employees` | auth |
| `/visits` | validation |
| `/routes`, `/enrollments`, `/redemptions`, `/prizes`, `/badges`, `/redeem-codes` | gamification |
| `/heatmap`, `/accesses`, `/rankings`, `/distributions` | insights |
| `/subscriptions`, `/notifications` | notifications |
| `/conversations` | chatbot |

Regras de acesso na borda (`PUBLIC` sem token / `ANY` qualquer papel autenticado / `ADMIN` / `TOURIST` / `EMPLOYEE`):

- **Público:** login e refresh de sessão, cadastro de turista, leitura do catálogo (pontos, categorias, eventos, links) e `GET /routes`.
- **ANY:** sessão (logout), perfil `/me` e interesses, visitas.
- **ADMIN:** funcionários, escrita do catálogo, escrita de rotas, brindes e estoque, dashboards de insights.
- **TOURIST:** inscrições, insígnias, códigos de resgate, inscrições por interesse/notificações, conversas do chatbot.
- **EMPLOYEE:** `POST /redemptions`.
- **Fallback:** rota de serviço conhecido sem regra específica fica acessível a qualquer papel autenticado — o serviço decide o resto (`require_role` próprio = defesa em profundidade). Prefixo desconhecido → 404.
- `/internal/*` → sempre 404 na borda (nunca 403); só alcançáveis na rede interna, sem autenticação entre serviços.
- Detalhe de matching: `{x}` casa um único segmento — ex. `GET /rankings/{rest}` cobre `/rankings/prizes` mas não caminhos mais profundos, que caem no fallback `ANY` (o insights reforça admin no serviço).

## O que o proxy faz

- Repassa body, query params, `Authorization` e headers relevantes; descarta headers hop-by-hop (RFC 7230 §6.1); força `Accept-Encoding: identity` a jusante e re-serva a resposta sem compressão, em streaming (`StreamingResponse` fecha o response a jusante via background task).
- Valida `Bearer` access token (`decode_token`, `expected_type="access"`) — qualquer `PyJWTError` → 401 `unauthorized`; papel fora da regra → 403 `forbidden`.
- Responde `504` `gateway_timeout` (timeout) ou `502` `service_unavailable` (serviço indisponível) com o corpo de erro padrão do `shared.errors` — 1 tentativa, sem retry.
- Correlation ID: herda ou gera `X-Request-Id` (via `CorrelationIdMiddleware`) e propaga a jusante; a resposta do serviço vem tal qual (incluindo `Set-Cookie` e headers repetidos).
- CORS centralizado (`expose_headers=["X-Request-Id"]`); `*` desativa credenciais.
- Não modifica corpo nem traduz erros do downstream.

## Variáveis de ambiente

| Variável | Uso | Default |
|---|---|---|
| `<SERVIÇO>_SERVICE_URL` | URL base de cada um dos 7 serviços (`AUTH_`, `CATALOG_`, `VALIDATION_`, `GAMIFICATION_`, `INSIGHTS_`, `NOTIFICATIONS_`, `CHATBOT_`) | `http://localhost:<porta>` |
| `ALLOWED_ORIGINS` | origens CORS, vírgula-separada; `*` desativa credenciais | `*` |
| `GATEWAY_TIMEOUT_S` | timeout total do proxy (connect fixo em 5s) | `30` |
| `JWT_SECRET` | valida o access token na borda (mesmo segredo dos serviços) | compose: `change-me-in-production`; código: default de desenvolvimento |

## Estrutura

- `app/main.py` — app factory do proxy (`create_gateway_app`), CORS, lifespan do `httpx.AsyncClient`, handler catch-all. `create_gateway_app(transport=...)` permite injetar `httpx.MockTransport` em testes.
- `app/core/routing.py` — tabela de prefixos → serviço e regras (método, caminho, papéis)