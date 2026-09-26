# Serviço de Validação (RF31–RF34)

Validação de presença por GPS: Haversine em metros contra a tolerância do ponto (sempre do snapshot do catalog — `tolerance_radius_m`, não há default local). Visitas `validated` são idempotentes por par (usuário, ponto) — enforced por índice parcial único no banco; repetição retorna **200** com a visita existente (e não re-propaga). Visitas `rejected` são gravadas a cada tentativa fora do raio (trilha de auditoria, RF33) e retornam **422** com corpo plano `{"status": "rejected", "distance_m", "tolerance_m"}` — única rota que foge do envelope padrão de erro.

## Como rodar

```bash
uv run uvicorn services.validation.app.main:app --port 8003
```

Ou com o docker-compose (raiz do monorepo): `docker compose up validation`.

Docs interativos: `http://localhost:8003/docs` (OpenAPI em `/openapi.json`).

## Endpoints

| Método | Caminho | Auth | Função |
|---|---|---|---|
| POST | `/visits` | JWT (service exige role `tourist` → 403 para os demais; o gateway permite qualquer papel) | registra visita: 201 validada / 200 idempotente / 422 rejeitada / 422 `gps_unavailable` / 503 `catalog_unavailable` |
| GET | `/visits` | JWT (qualquer papel) | lista só as visitas `validated` do usuário (`{"items", "total"}`) |
| GET | `/visits/{spot_id}` | JWT (qualquer papel) | visita validada do usuário para o ponto; 404 se não existir |
| POST | `/internal/visits/propagate` | nenhuma (rota interna) | re-propaga um fato de visita; idempotente nos destinos |

## Propagação (D-05)

Na primeira validação, propaga fire-and-forget para `POST /api/v1/internal/visit-facts` (insights) e `POST /api/v1/internal/visit-notification` (gamification), payload `{user_id, tourist_spot_id, occurred_at}`. Até **2 tentativas** por destino (timeout 5s; 5xx e erros de rede são retentados), com log estruturado `visit_propagated` indicando sucesso por destino. Falha nunca invalida a visita.

## Variáveis de ambiente

| Variável | Uso | Default |
|----------|-----|---------|
| `DATABASE_URL` | banco `passanorte_validation` | sem env: `sqlite:///./dev.db` |
| `JWT_SECRET` | validação dos tokens | default de desenvolvimento |
| `CATALOG_SERVICE_URL` | snapshot do ponto (raio, coordenadas); sem retry — indisponível → 503 `catalog_unavailable` | `http://localhost:8002` |
| `INSIGHTS_SERVICE_URL` | propagação de fatos de visita | `http://localhost:8005` |
| `GAMIFICATION_SERVICE_URL` | propagação de visita para progresso/insígnias | `http://localhost:8004` |

## Estrutura e notas de implementação

- `app/api/` — `visits.py` (turista) e `internal.py` (re-propagação)
- `app/core/` — dependências (sessão, JWT), `get_catalog_snapshot`, Haversine (R=6.371.000 m) e `propagator`
- `app/models/` — `Visit` (coluna `status` é `String(16)`, não SQL Enum; enum só em Python)
- Idempotência: índice parcial único `uq_visit_validated` em `(user_id, tourist_spot_id)` onde `status = 'validated'` — linhas `rejected` podem se acumular sem conflito.
- Resposta idempotente (200) traz `tolerance_m: null`; a validada (201) traz o valor numérico e `distance_m` arredondado a 2 casas.