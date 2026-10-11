# SPD-PassaNorte — Backend

Backend do sistema distribuído de gamificação do turismo de Manaus: turistas validam visitas a pontos turísticos por geolocalização, completam rotas e recebem insígnias/brindes; a prefeitura administra o catálogo e acompanha insights. Inclui chatbot de planejamento de roteiro com RAG.

> Cada serviço tem seu próprio `README.md` em `src/services/<serviço>/`, com endpoints, comandos, variáveis de ambiente e notas de implementação.

**Stack:** Python 3.11+ · FastAPI · SQLAlchemy 2.x · Alembic · PostgreSQL 16 (pgvector) · aio-pika (RabbitMQ) · httpx (pull) · JWT HS256 · bcrypt · Fernet · uv · Kong Gateway (DB-less) · Docker Compose

---

## Arquitetura em uma página

Kong Gateway na borda (porta 8000, config declarativa DB-less em `kong/kong.yml`) + 7 microsserviços + 1 banco por serviço (Princípio I — a query nunca sai do banco próprio), comunicação **REST síncrona (httpx) para consultas pull** e **RabbitMQ (aio-pika) como barramento de eventos** para os efeitos colaterais tolerantes a falhas (D-05), mais um `src/shared/` de biblioteca interna (não é um serviço). Infraestrutura inteira em Docker Compose, custo zero.

| Componente | Porta | Responsabilidade |
|---|---|---|
| [kong](kong/kong.yml) | 8000 | **Borda única**: roteamento `/api/v1/*`, verificação de JWT (plugin `jwt`, `key_claim_name: iss`), CORS centralizado, correlation ID (`X-Request-Id`), rate limiting, `/internal/*` sem rota (404) |
| [rabbitmq](docker-compose.yml) | 5672 / 15672 | **Barramento de eventos** (AMQP): exchange topic `passanorte.events`; UI de gestão em `:15672` (passanorte/passanorte) |
| [auth](src/services/auth/README.md) | 8001 | Identidade, RBAC (`admin`/`employee`/`tourist`), sessão JWT, perfis, PII criptografado (Fernet/HMAC) |
| [catalog](src/services/catalog/README.md) | 8002 | Pontos turísticos, categorias, eventos, cronogramas, deep links |
| [validation](src/services/validation/README.md) | 8003 | Validação de presença por geolocalização (Haversine + índice parcial único) |
| [gamification](src/services/gamification/README.md) | 8004 | Rotas, inscrições, progresso derivado, insígnias, brindes, resgate exatamente-uma-vez |
| [insights](src/services/insights/README.md) | 8005 | Dashboard analítico admin: heatmap, acessos, rankings, distribuições |
| [notifications](src/services/notifications/README.md) | 8006 | Inscrições por interesse, inbox, dispatch idempotente |
| [chatbot](src/services/chatbot/README.md) | 8007 | Chatbot de roteiro com RAG sobre o catálogo (pgvector 384d) |

### Eventos entre serviços (RabbitMQ, D-05)

Os efeitos colaterais que antes eram HTTP fire-and-forget agora são eventos publicados em `passanorte.events` (routing key = tipo) e consumidos por filas durable dentro do próprio processo FastAPI (lifespan). Falha na 1ª entrega → requeue; na redelivery → DLQ `passanorte.dlq` (visível na UI de gestão). Sem `RABBITMQ_URL`, o módulo fica **degradado**: publicação é no-op com um warn único e consumers não iniciam (dev sem docker).

| Evento (routing key) | Produtor | Consumer (fila durable) |
|---|---|---|
| `visit.validated` | validation (`propagator.py`) | insights (`passanorte.insights.visit.validated` — fatos de visita) |
| `access.registered` | auth (login) | insights (`passanorte.insights.access.registered` — at-least-once, analytics) |
| `notification.dispatch` | catalog (spot/event), gamification (rota concluída) | notifications (`passanorte.notifications.dispatch` — dedup por user/kind/source) |
| `catalog.index.refresh` | catalog (spot/event) | chatbot (`passanorte.chatbot.index.refresh` — re-embed do RAG) |

- Envelope (`shared/messaging.EventEnvelope`): `{event_id, type, occurred_at, request_id, data}` — o `request_id` propaga o correlation ID entre serviços (logs JSON).
- Entrega **at-least-once**; os consumers deduplicam (fatos por user+spot+momento, notificações por user+kind+source, índice por delete-then-insert).
- `GET /health` continua **liveness-only** (sem ping do broker): queda do RabbitMQ não derruba os healthchecks dos serviços; a reconexão é automática (`RobustConnection`).

### `src/shared/` (biblioteca interna)

- `app.py` — app factory: prefixo `/api/v1`, `GET /health` (liveness, sem ping de banco), middleware de correlation ID, handlers de erro, lifespan do barramento AMQP
- `errors.py` — envelope único `{"error": {code, message, details}}` + header `X-Request-Id` em toda resposta; 500 nunca vaza detalhes
- `logging.py` — log JSON por linha com `request_id`; `X-Request-Id` gerado pelo Kong na borda ou herdado do cliente, propagado ao serviço
- `security.py` — JWT HS256 (access 15 min / refresh 7 dias), bcrypt (rounds 12), Fernet para PII, HMAC-SHA256 para unicidade de documento
- `db.py` — `Base` compartilhado, engine por request (com `pool_pre_ping`), um database por serviço; `service_session_factory()` cacheada para os consumers
- `messaging.py` — barramento RabbitMQ (aio-pika): envelope de eventos, `publish()` sync nunca-bloqueante, consumers com requeue/DLQ, seam de teste `set_publisher`
- `audit.py` / `audit_model.py` — `AuditLog` declarado uma vez, reexportado; auditoria gravada na mesma transação da ação
- `*_client.py` — wrappers de publicação de eventos (notifications, tracking de insights, chatbot): mesmas assinaturas do antigo HTTP fire-and-forget, agora via `messaging.publish`

Defesa em profundidade: o Kong valida a assinatura/expiração dos JWTs na borda (single Consumer casando o claim `iss`) e cada serviço repete a verificação de tipo de token e papéis com `require_role`. `/internal/*` não tem autenticação entre serviços — a proteção é a ausência de rota no Kong (404) e a rede interna. Rotas públicas (cadastro, login, leitura do catálogo, `GET /routes`) passam pela borda sem token; `POST /categories`/`POST /events` e demais escritas exigem JWT no Kong e são filtradas por papel no serviço.

> **Nota sobre o envelope de erro na borda:** respostas geradas no próprio Kong (401 de token inválido, 404 de rota desconhecida, 429 de rate limit, 502/504 de serviço indisponível/timeout) usam o formato do Kong (`{"message": ...}`), não o envelope `{"error": {code, message, details}}` do projeto — o `X-Request-Id` continua presente em todas. Clientes devem ramificar por HTTP status quando a resposta não tem a chave `error`.

---

## Pré-requisitos

- [uv](https://docs.astral.sh/uv/) 0.12+
- Docker Compose (para banco e serviços)
- Python 3.11+

## Como rodar

### Com Docker Compose (recomendado)

```bash
docker compose up --build
```

Sobe o Postgres (`pgvector/pgvector:pg16`), o RabbitMQ (`rabbitmq:3.13-management-alpine`, AMQP :5672 + UI :15672), o Kong (`kong:3.9`, DB-less) e os 7 microsserviços (portas 8001–8007). O script `scripts/init-databases.sh` cria automaticamente os 7 databases (`passanorte_auth`, `passanorte_catalog`, ...) e a extensão `vector` no banco do chatbot.

Borda única em `http://localhost:8000/api/v1/...` — os clientes só precisam desse endereço (o Kong não serve `/docs`; cada serviço mantém o próprio em `http://localhost:<porta>/docs`, exposto apenas no loopback). A config declarativa do Kong (`kong/kong.yml`) renderiza `JWT_SECRET`/`JWT_ISSUER` do `.env` no boot via `kong/entrypoint-render.sh`.

### Desenvolvimento local (sem Docker)

1. Suba apenas o banco e crie os databases:

   ```bash
   docker compose up db -d
   ```

2. Instale as dependências e rode um serviço (ex.: auth):

   ```bash
   uv sync
   uv run uvicorn services.auth.app.main:app --port 8001
   ```

   Cada serviço resolve seu banco por `DATABASE_URL` (ex.: `postgresql://passanorte:passanorte@localhost:5432/passanorte_auth`; sem a variável, cai em `sqlite:///./dev.db`). A raiz de imports é `src/` (`services.*` e `shared.*`).

3. Credencial inicial de admin (RF01):

   ```bash
   uv run python scripts/create_admin.py --email admin@passanorte.com --password '...'
   # sem --password, gera uma senha forte aleatória e a imprime
   ```

### Variáveis de ambiente

Compartilhadas por todos os serviços (ver `docker-compose.yml`; há um `.env.example` na raiz):

| Variável | Uso | Default |
|---|---|---|
| `DATABASE_URL` | Postgres do serviço | obrigatória em produção (sem ela cai em SQLite silenciosamente) |
| `JWT_SECRET` | assinatura/validação de tokens, compartilhado (serviços + Kong) | compose: `change-me-in-production`; código: default de desenvolvimento |
| `JWT_ISSUER` | claim `iss` dos JWTs; deve casar com a credencial do Consumer no `kong/kong.yml` | `passanorte` |
| `PII_ENCRYPTION_KEY` | criptografia de PII (CPF/passaporte, Fernet) **e** chave do HMAC de unicidade; se definida mas **vazia**, a importação de `shared.security` falha | sem ela, uma chave **efêmera** é gerada a cada processo (dados ficam irrecuperáveis em restart) |
| `<SERVIÇO>_SERVICE_URL` | URL base de cada serviço p/ consultas REST inter-serviço (pull) | fallback `http://localhost:<porta>` |
| `RABBITMQ_URL` | barramento de eventos entre serviços (D-05); compose fixa `amqp://passanorte:passanorte@rabbitmq:5672/`. **Vazio = degradado** (publicação no-op com warn 1 vez, consumers não rodam) | compose define sempre; dev sem docker: vazio |
| `ACCESS_TOKEN_MINUTES` / `REFRESH_TOKEN_DAYS` | validade dos JWTs (compartilhadas via `shared/security`) | `15` / `7` |
| `LLM_PROVIDER` | provider do chatbot: `stub` \| `gemini` \| `ollama` | `stub` |
| `LLM_GEMINI_API_KEY` / `LLM_OLLAMA_URL` / `LLM_OLLAMA_MODEL` | credenciais do provider escolhido | ollama: `http://localhost:11434`, modelo `llama3.1` |

> O compose repassa ao container do chatbot apenas `LLM_PROVIDER` — as credenciais do provider (`LLM_GEMINI_API_KEY`, `LLM_OLLAMA_*`) precisam ser injetadas à parte em produção.
>
> **Cuidado:** o `.env.example` atual usa os nomes `GEMINI_API_KEY` e `OLLAMA_BASE_URL`, que o código **não lê** (os nomes válidos são `LLM_GEMINI_API_KEY` e `LLM_OLLAMA_URL`); `TOLERANCE_RADIUS_DEFAULT_M` também não é lida (o raio de tolerância vive no catalog, por ponto).

> **Nota sobre migrations:** cada serviço tem scaffold Alembic (`alembic/env.py`), mas nenhuma revisão foi gerada (`alembic/versions/` vazio em todos — e os `app/models/__init__.py` vazios registram nenhuma tabela no metadata do Alembic). Em dev, o schema é criado via `Base.metadata.create_all` pelos testes; ao rodar um serviço com banco novo pela primeira vez, gere as migrations com `alembic revision --autogenerate` dentro de `src/services/<serviço>/` (ajustando o import de models no `env.py`).

---

## Testes e qualidade

```bash
uv run pytest                 # unit, integration e contract (pytest-asyncio, modo auto)
uv run pytest --cov           # cobertura (fontes: src/services, src/shared)
uv run ruff check .           # lint (line-length 120)
uv run ruff format .
uv run mypy src               # type check (namespace packages, alembic excluído)
```

Os testes de contrato cobrem os 7 user stories (`tests/contract/test_*_us*.py`); os de integração exercem as jornadas completas (turista, admin, visitas, gamificação, insights, notificações, chatbot); os unit cobrem invariantes (RBAC, Haversine, sessão, RAG, invariants de gamificação). O Kong não participa dos testes em processo — a config é validada no boot (`kong config parse`, ver abaixo).

---

## Estrutura do repositório

```
├── docker-compose.yml        # Postgres (pgvector) + RabbitMQ (:5672) + Kong :8000 + 7 serviços, portas 8001–8007
├── Dockerfile                # imagem única uv + python3.11-slim (comando por serviço no compose)
├── .env.example              # variáveis compartilhadas (ver caveat sobre nomes do provider acima)
├── kong/
│   ├── kong.yml              # config declarativa DB-less do gateway (rotas, plugins, Consumer jwt)
│   └── entrypoint-render.sh  # injeta JWT_SECRET/JWT_ISSUER do .env no boot
├── scripts/
│   ├── init-databases.sh     # cria 7 databases + ext. vector (roda no init do Postgres)
│   └── create_admin.py       # credencial inicial do admin (RF01)
├── src/
│   ├── shared/               # biblioteca interna (não é serviço): app factory, security, db, erros, logging, audit, barramento RabbitMQ
│   └── services/             # 7 microsserviços de domínio, cada um com app/, alembic/ e README.md
├── specs/                    # contratos REST por user story (specs/001-passaporte-turistico-backend)
└── tests/                    # unit / integration / contract
```