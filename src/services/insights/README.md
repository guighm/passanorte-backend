# Serviço de Insights (RF06–RF10)

Ingestão de fatos (acessos e visitas, idempotente por `(user_id, tourist_spot_id, occurred_at)`) e dashboards administrativos. Agregações 100% em SQL sobre o banco próprio — a query nunca sai do serviço (Princípio I). Não faz chamadas a outros serviços; é alimentado fire-and-forget por auth (login), catalog (listagem com JWT) e validation (visita validada).

## Como rodar

```bash
uv run uvicorn services.insights.app.main:app --port 8005
```

Ou com o docker-compose (raiz do monorepo): `docker compose up insights`.

Docs interativos: `http://localhost:8005/docs` (OpenAPI em `/openapi.json`).

## Endpoints

**Dashboards** — `app/api/dashboard.py`, todos `require_role("admin")`:

| Método | Caminho | Função |
|---|---|---|
| GET | `/heatmap` | concentração de visitas por ponto (RF06): contagem, coordenadas e `weight = count / total` |
| GET | `/accesses` | acessos por período (RF07): `period` = `day\|week\|month\|year\|custom` (default `day`); `custom` exige `from`/`to` (ISO) → 422 `invalid_period` |
| GET | `/rankings/tourist-spots` | pontos mais visitados (RF08): `segment` = `day\|month\|year` (default `month`) |
| GET | `/distributions/country-of-origin` | participação por país (RF09) — snapshot sem PII (RNF08) |
| GET | `/distributions/interests` | participação por interesse (RF10) |

**Internos** (`/internal/*`, sem auth — o gateway bloqueia na borda) — `app/api/internal.py`:

- `POST /internal/visit-facts` — ingere fato de visita; idempotente (D-05) por `(user_id, tourist_spot_id, occurred_at)`, responde `{"id", "status": "ingested" | "already_ingested"}`. Payload não tipado (dict bruto): `user_id` e `tourist_spot_id` obrigatórios; aceita `spot_name`, `latitude`/`longitude`, `region_hint`, `country_of_origin`, `interests` (CSV snapshot), `occurred_at` (ISO; default agora UTC).
- `POST /internal/accesses` — registra acesso: `{user_id, client? ("web"|"mobile")}`.

## Variáveis de ambiente

| Variável | Uso | Default |
|----------|-----|---------|
| `DATABASE_URL` | banco `passanorte_insights` | sem env: `sqlite:///./dev.db` |
| `JWT_SECRET` | validação dos tokens (dashboards: só `admin`) | default de desenvolvimento |

> O código lê também, por efeito colateral da importação de `shared.security`: `PII_ENCRYPTION_KEY`, `ACCESS_TOKEN_MINUTES`, `REFRESH_TOKEN_DAYS` (sem uso neste serviço).

## Estrutura e notas de implementação

- `app/api/` — dashboards admin (`dashboard.py`) e ingestão (`internal.py`)
- `app/core/` — dependências (sessão, JWT)
- `app/models/` — `AccessLog` (`access_logs`) e `VisitFact` (`visit_facts`, constraint `uq_visitfact_key`)
- O heatmap **não é** grade Haversine: é um `GROUP BY tourist_spot_id` sobre todos os `visit_facts` (sem filtro temporal). O campo `total` da resposta é o número de pontos distintos, não o total de visitas.
- Distribuição de interesses agrega em Python (split do CSV de interesses por fato, dedup por `set`).
- Falha conhecida: payload interno sem `user_id`/`tourist_spot_id` gera `KeyError` → 500 genérico em vez de 422.