# SPD-PassaNorte — Backend

Backend do sistema distribuído de gamificação do turismo de Manaus: turistas validam visitas a pontos turísticos por geolocalização, completam rotas e recebem insígnias/brindes; a prefeitura administra o catálogo e acompanha insights. Inclui chatbot de planejamento de roteiro com RAG.

> Cada serviço tem seu próprio `README.md` em `src/services/<serviço>/`, com endpoints, comandos, variáveis de ambiente e notas de implementação.

**Stack:** Python 3.11+ · FastAPI · SQLAlchemy 2.x · Alembic · PostgreSQL 16 (pgvector) · httpx · JWT HS256 · bcrypt · Fernet · uv · Docker Compose

---

## Arquitetura em uma página

7 microsserviços + 1 banco por serviço (Princípio I — a query nunca sai do banco próprio), comunicação REST síncrona (httpx, fire-and-forget tolerante a falhas — a propagação de visitas usa retry idempotente de 2 tentativas) e um `src/shared/` de biblioteca interna (não é um serviço). Sem broker, Redis ou cloud — infraestrutura inteira em Docker Compose, custo zero.

| Serviço | Porta | Responsabilidade |
|---|---|---|
| [gateway](src/services/gateway/README.md) | 8000 | Borda única: roteamento `/api/v1/*`, verificação de JWT, autorização coarse-grained, CORS centralizado, `/internal/*` bloqueado com 404 |
| [auth](src/services/auth/README.md) | 8001 | Identidade, RBAC (`admin`/`employee`/`tourist`), sessão JWT, perfis, PII criptografado (Fernet/HMAC) |
| [catalog](src/services/catalog/README.md) | 8002 | Pontos turísticos, categorias, eventos, cronogramas, deep links |
| [validation](src/services/validation/README.md) | 8003 | Validação de presença por geolocalização (Haversine + índice parcial único) |
| [gamification](src/services/gamification/README.md) | 8004 | Rotas, inscrições, progresso derivado, insígnias, brindes, resgate exatamente-uma-vez |
| [insights](src/services/insights/README.md) | 8005 | Dashboard analítico admin: heatmap, acessos, rankings, distribuições |
| [notifications](src/services/notifications/README.md) | 8006 | Inscrições por interesse, inbox, dispatch idempotente |
| [chatbot](src/services/chatbot/README.md) | 8007 | Chatbot de roteiro com RAG sobre o catálogo (pgvector 384d) |

### `src/shared/` (biblioteca interna)

- `app.py` — app factory: prefixo `/api/v1`, `GET /health` (liveness, sem ping de banco), middleware de correlation ID, handlers de erro
- `errors.py` — envelope único `{"error": {code, message, details}}` + header `X-Request-Id` em toda resposta; 500 nunca vaza detalhes
- `logging.py` — log JSON por linha com `request_id`; `X-Request-Id` herdado do cliente ou gerado, propagado gateway → serviço
- `security.py` — JWT HS256 (access 15 min / refresh 7 dias), bcrypt (rounds 12), Fernet para PII, HMAC-SHA256 para unicidade de documento
- `db.py` — `Base` compartilhado, engine por request (com `pool_pre_ping`), um database por serviço
- `audit.py` / `audit_model.py` — `AuditLog` declarado uma vez, reexportado; auditoria gravada na mesma transação da ação
- `*_client.py` — clientes httpx fire-and-forget (insights, notifications, chatbot): 1 tentativa, falhas silenciosas

Defesa em profundidade: o gateway valida JWT + papéis coarse-grained e cada serviço repete com `require_role`; `/internal/*` não tem autenticação entre serviços — a proteção é o bloqueio na borda (404) e a rede interna.

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

Sobe o Postgres (`pgvector/pgvector:pg16`) + os 8 serviços (portas 8000–8007). O script `scripts/init-databases.sh` cria automaticamente os 7 databases (`passanorte_auth`, `passanorte_catalog`, ...) e a extensão `vector` no banco do chatbot.

Gateway disponível em `http://localhost:8000/docs` — os clientes só precisam desse endereço.

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
| `JWT_SECRET` | assinatura/validação de tokens, compartilhado | compose: `change-me-in-production`; código: default de desenvolvimento |
| `PII_ENCRYPTION_KEY` | criptografia de PII (CPF/passaporte, Fernet) **e** chave do HMAC de unicidade; se definida mas **vazia**, a importação de `shared.security` falha | sem ela, uma chave **efêmera** é gerada a cada processo (dados ficam irrecuperáveis em restart) |
| `<SERVIÇO>_SERVICE_URL` | URL base de cada serviço p/ chamadas inter-serviço | fallback `http://localhost:<porta>` |
| `ALLOWED_ORIGINS` | CORS do gateway (vírgula-separada ou `*`) | `*` |
| `GATEWAY_TIMEOUT_S` | timeout do proxy do gateway (connect fixo em 5s) | `30` |
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

Os testes de contrato cobrem os 7 user stories (`tests/contract/test_*_us*.py`); os de integração exercem as jornadas completas (turista, admin, visitas, gamificação, insights, notificações, chatbot); os unit cobrem invariantes (RBAC, Haversine, sessão, RAG, invariants de gamificação e o gateway).

---

## Estrutura do repositório

```
├── docker-compose.yml        # Postgres (pgvector) + 8 serviços, portas 8000–8007
├── Dockerfile                # imagem única uv + python3.11-slim (comando por serviço no compose)
├── .env.example              # variáveis compartilhadas (ver caveat sobre nomes do provider acima)
├── scripts/
│   ├── init-databases.sh     # cria 7 databases + ext. vector (roda no init do Postgres)
│   └── create_admin.py       # credencial inicial do admin (RF01)
├── src/
│   ├── shared/               # biblioteca interna (não é serviço): app factory, security, db, erros, logging, audit, clients httpx
│   └── services/             # 8 microsserviços (gateway + 7 de domínio), cada um com app/, alembic/ e README.md
├── specs/                    # contratos REST por user story (specs/001-passaporte-turistico-backend)
└── tests/                    # unit / integration / contract
```