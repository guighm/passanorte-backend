# Serviço de Notificações (RF37)

Inscrições por interesse e caixa de entrada in-app (D-06). É um puro *sink*: não faz chamadas a outros serviços. O dispatch é idempotente por `(usuário, kind, source_id)` — constraint `uq_notification_dispatch` + pre-check por alvo — para eventos (`new_event`), pontos (`new_spot`) e conclusão de rota (`new_route`). Sem entrega por canal externo (sem push/email/websocket): tudo vira linha no inbox.

## Como rodar

```bash
uv run uvicorn services.notifications.app.main:app --port 8006
```

Ou com o docker-compose (raiz do monorepo): `docker compose up notifications`.

Docs interativos: `http://localhost:8006/docs` (OpenAPI em `/openapi.json`).

## Endpoints

**Turista** — `app/api/notifications.py` (só role `tourist`; não há visão admin):

| Método | Caminho | Função |
|---|---|---|
| PUT | `/subscriptions` | **substitui** integralmente as inscrições (`{"category_ids": [...]}`) |
| GET | `/subscriptions` | `category_ids` inscritos |
| GET | `/notifications` | inbox próprio, mais recentes primeiro (`{items, total}`) |
| PATCH | `/notifications/{id}/read` | marca como lida (seta `read_at` só se nula — idempotente); 404 se inexistente/alheia |

**Consumer do barramento** — fila durable `passanorte.notifications.dispatch` (evento `notification.dispatch`), iniciada no lifespan; handler `app/core/dispatcher.py:apply_dispatch` (função pura + wrapper `handle_dispatch`). Payload do evento: `kind` ∈ `new_event|new_spot|new_route` (outro → `invalid_kind`; a mensagem vai para a DLQ após o requeue), `source_id`, `title`, opcionais `body`, `payload`, `user_ids` (notificação direta) ou `category_id` (fan-out para todos os inscritos da categoria). Sem nenhum dos dois → no-op. Idempotente por `(user, kind, source_id)` (duplicados já existentes são pulados).

## Variáveis de ambiente

| Variável | Uso | Default |
|----------|-----|---------|
| `DATABASE_URL` | banco `passanorte_notifications` | sem env: `sqlite:///./dev.db` |
| `JWT_SECRET` | validação dos tokens | default de desenvolvimento |
| `RABBITMQ_URL` | barramento (consumidor da fila `notification.dispatch`) | vazio → degradado (não consome) |

## Estrutura e notas de implementação

- `app/api/` — `notifications.py` (turista) — `/internal/dispatch` foi substituído pelo consumer do barramento
- `app/core/` — dependências (sessão, JWT) e dispatcher (`dispatcher.py`)
- `app/models/` — `NotificationSubscription` (`uq_subscription_user_category`, sem FK ao catalog — outro banco) e `Notification` (`kind` String(16), `uq_notification_dispatch`)
- Quem despacha: catalog (`new_event` na criação de evento, `new_spot` na criação de ponto com categorias) e gamification (`new_route` na conclusão de rota).
- Falha conhecida: payload interno sem `kind`/`source_id`/`title` gera `KeyError` → 500 genérico em vez de 422.