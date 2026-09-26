# Serviço de Catálogo (RF11–RF17, RF26–RF29)

Catálogo de pontos turísticos, categorias e eventos: leitura pública (detalhe, horários, eventos, deep links para mapas/transporte, ordenação por proximidade) e CRUD administrativo com validações de negócio (janela de horário sem sobreposição, `permanently_closed` terminal, remoção lógica de pontos). Após mutações, dispara fire-and-forget: dispatch de notificações por categoria (RF37) e rebuild do índice do chatbot (D-08). Registra acessos no insights quando a listagem pública vem com JWT válido (RF07).

## Como rodar

```bash
uv run uvicorn services.catalog.app.main:app --port 8002
```

Ou com o docker-compose (raiz do monorepo): `docker compose up catalog`.

Docs interativos: `http://localhost:8002/docs` (OpenAPI em `/openapi.json`).

## Endpoints

**Público (sem auth)** — `app/api/spots.py`, `app/api/events.py`:

| Método | Caminho | Função |
|---|---|---|
| GET | `/categories` | categorias ativas |
| GET | `/tourist-spots` | lista; filtros `category`, `status`, `lat`/`lng` (ordenação Haversine em memória, RF26) |
| GET | `/tourist-spots/{id}` | detalhe: horários, eventos, `tolerance_radius_m` |
| GET | `/tourist-spots/{id}/external-links` | deep links Google Maps / Uber / 99 (URLs construídas localmente) |
| GET | `/events` | eventos ordenados por data; filtros `tourist_spot_id`, `from_date` (inválido → 422 `invalid_filter`) |

**Admin** — `app/api/spots_admin.py`, `app/api/events.py` (`require_role("admin")`):

| Método | Caminho | Função |
|---|---|---|
| POST/PATCH/DELETE | `/tourist-spots[/{id}]` | CRUD; DELETE é remoção lógica (`is_removed=True`); create/update dispara notificações (se houver categorias) e reindexa o chatbot |
| PUT | `/tourist-spots/{id}/schedule` | substitui horários; sobrepõe com linhas existentes → 422 `schedule_overlap` |
| PATCH | `/tourist-spots/{id}/status` | `permanently_closed` é terminal → 409 `invalid_status_transition`; mudança reindexa o chatbot |
| GET | `/admin/tourist-spots/{id}` | visão admin `{id, name, status, categories}` |
| POST/PATCH/DELETE | `/events[/{id}]` | CRUD de eventos (PATCH/DELETE não reindexam o chatbot) |
| POST | `/categories` | nome duplicado → 409 `duplicate_category` |

**Internos** (`/internal/*`, sem auth — o gateway bloqueia na borda):

- `GET /internal/tourist-spots/{id}` — snapshot para o validation (raio, coordenadas, status, categorias).
- `GET /internal/tourist-spots?ids=` — lista para feed/recomendação (RF26), `category_ids` por ponto.
- `POST /internal/tourist-spots` — seed de ponto (usado por seeds/testes).
- `POST /internal/events/notify-subscribers` — re-dispara `new_event` de um evento (dedup fica no notifications).

## Variáveis de ambiente

| Variável | Uso | Default |
|----------|-----|---------|
| `DATABASE_URL` | banco `passanorte_catalog` | sem env: `sqlite:///./dev.db` |
| `JWT_SECRET` | validação dos tokens | default de desenvolvimento |
| `NOTIFICATIONS_SERVICE_URL` | dispatch de novidades (RF37) — 1 chamada por categoria, falhas ignoradas | `http://localhost:8006` |
| `CHATBOT_SERVICE_URL` | rebuild de embeddings (D-08), timeout 10s, falhas ignoradas | `http://localhost:8007` |
| `INSIGHTS_SERVICE_URL` | registro de acessos na listagem pública (RF07, só com JWT válido) | `http://localhost:8005` |

## Estrutura e notas de implementação

- `app/api/` — endpoints (público, admin e `/internal/*` entre serviços)
- `app/core/` — dependências (sessão, JWT) e Haversine local para ordenação por proximidade
- `app/models/` — `TouristSpot`, `Category`, `SpotCategory`, `OpeningSchedule`, `Event` + `AuditLog`
- DELETE de ponto é lógico (`is_removed`); linhas removidas somem até para o admin (todos os endpoints filtram).
- Remoção de evento é física (DELETE de linha).
- Auditoria gravada na mesma transação da ação (`shared.audit`).
- `get_db` cria engine/sessão por request (com `pool_pre_ping`), sem cache global.