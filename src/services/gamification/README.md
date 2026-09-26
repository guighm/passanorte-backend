# Serviço de Gamificação (RF18–RF21, RF29–RF30, RF35–RF36)

Rotas turísticas (CRUD admin, remoção lógica — o progresso em andamento não quebra), brindes/estoque (`stock_quantity >= 0`, ajuste absoluto via `PATCH /prizes/{id}/stock`), inscrição, progresso **derivado a cada leitura** (D-13 — cruza com as visitas validadas do serviço validation, incluindo visitas anteriores à inscrição), insígnias e códigos de resgate (`PN-` + 16 hex maiúsculos) emitidos na conclusão da rota; resgate por funcionário com transições atômicas condicionais (`UPDATE ... WHERE status='issued'` / `WHERE stock_quantity > 0` → `code_already_used`, `prize_out_of_stock`). Não expõe `/internal/*` — apenas chama o dispatch de notificações e lê visitas do validation.

## Como rodar

```bash
uv run uvicorn services.gamification.app.main:app --port 8004
```

Ou com o docker-compose (raiz do monorepo): `docker compose up gamification`.

Docs interativos: `http://localhost:8004/docs` (OpenAPI em `/openapi.json`).

## Endpoints

**Público** — `app/api/admin.py`: `GET /routes` lista rotas ativas com pontos e brinde (RF18).

**Admin** — `app/api/admin.py`:

| Método | Caminho | Função |
|---|---|---|
| POST / PATCH / DELETE | `/routes[/{id}]` | cria rota + brinde embutido (`prize: {name}`) + pontos por posição; PATCH recria os pontos; DELETE é lógico (`is_active=False`) |
| GET / POST | `/prizes` | lista/cria brinde (estoque inicial 0) |
| PATCH | `/prizes/{id}/stock` | define estoque absoluto (`ge=0`) |

**Turista** — `app/api/enrollments.py` (e `GET /badges`, `GET /redeem-codes` em `admin.py`):

| Método | Caminho | Função |
|---|---|---|
| POST | `/routes/{route_id}/enrollments` | inscreve (409 `already_enrolled`, 404 se rota inexistente/inativa); retorna progresso derivado |
| GET | `/enrollments` · `/enrollments/{route_id}` | inscrições próprias com progresso e checagem de conclusão |
| GET | `/badges` · `/redeem-codes` | insígnias e códigos do turista autenticado |

**Funcionário** — `app/api/redemptions.py`: `POST /redemptions` com `{"code": ...}` → valida, concede brinde e decrementa estoque (RF21).

## Conclusão e resgate

- Conclusão dispara quando `percent == 100.0` e status é `in_progress`: cria `Badge` + `RedeemCode` (idempotente — código existente é retornado), notifica o turista (`new_route`, `source_id` = código → dedup no notifications) e marca a inscrição como `completed`.
- **Um GET pode mutar estado**: a checagem de conclusão roda em `POST /enrollments` e nos `GET /enrollments*`.
- Resgate é exatamente-uma-vez: `UPDATE` condicional no código (0 linhas → 409 `code_already_used`), depois no estoque (0 linas → rollback do passo anterior e 409 `prize_out_of_stock`). Qualquer funcionário pode resgatar o código de qualquer turista.
- Progresso nunca é persistido — derivado a cada leitura; se a busca de visitas falhar, o progresso vem vazio (o serviço não trava, D-13).

## Variáveis de ambiente

| Variável | Uso | Default |
|----------|-----|---------|
| `DATABASE_URL` | banco `passanorte_gamification` | sem env: `sqlite:///./dev.db` |
| `JWT_SECRET` | validação dos tokens | default de desenvolvimento |
| `VALIDATION_SERVICE_URL` | `GET /api/v1/visits` com o Bearer do turista repassado verbatim (D-02), timeout 5s, sem retry | `http://localhost:8003` |
| `NOTIFICATIONS_SERVICE_URL` | dispatch de conclusão (fire-and-forget) | `http://localhost:8006` |

## Estrutura e notas de implementação

- `app/api/` — `admin.py` (rotas, brindes, badges, códigos), `enrollments.py`, `redemptions.py`
- `app/core/` — dependências (sessão, JWT, `get_validated_visits`), conclusão (`completion.py`) e resgates (`redemptions.py`)
- `app/models/` — `Prize` (CHECK de estoque), `Route`, `RoutePoint` (`tourist_spot_id` sem FK — catálogo é outro banco), `RouteEnrollment` (`uq_enrollment_user_route`), `Badge` (`uq_badge_user_route`), `RedeemCode` (`code` único, `issued|redeemed`)
- Auditoria em banco só nas mutações admin (`create_route`, `update_route`, `remove_route`, `create_prize`, `update_stock`), na mesma transação; inscrições/conclusões/resgates ficam no log estruturado JSON.