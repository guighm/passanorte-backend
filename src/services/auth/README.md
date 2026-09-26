# Serviço de Autenticação (RF01–RF05, RF22–RF25)

Identidade e sessões: cadastro/login por email+senha, JWT de acesso (15 min) e refresh (7 dias) HS256, perfis admin/funcionário/turista, RBAC por endpoint (`require_role`) e revogação lógica de funcionários (`is_active=False`; o login passa a falhar, mas tokens emitidos continuam válidos até expirar — `DELETE /session` é stateless/no-op e o `jti` nunca é persistido). O `/session/refresh` emite novo access com o papel atual do banco e devolve o **mesmo** refresh token (sem rotação).

Turistas exigem CPF **ou** passaporte (422 `document_required`); unicidade de email e de documento é garantida por hash HMAC-SHA256 do documento (CPF e passaporte compartilham o mesmo espaço de hash). PII (telefone, CPF, passaporte) criptografado com Fernet; email fica em claro (coluna unique). Senhas em bcrypt (work factor 12).

## Como rodar

```bash
uv run uvicorn services.auth.app.main:app --port 8001
```

Ou com o docker-compose (raiz do monorepo): `docker compose up auth`.

Docs interativos: `http://localhost:8001/docs` (OpenAPI em `/openapi.json`).

## Endpoints

**Público** — `app/api/session.py`, `app/api/tourists.py`:

| Método | Caminho | Função |
|---|---|---|
| POST | `/session` | login email+senha → `TokenResponse` (`access_token`, `refresh_token`, `expires_in`); registra acesso no insights (RF07) |
| POST | `/session/refresh` | troca refresh por novo access (sem rotação do refresh) |
| DELETE | `/session` | logout no-op (204) — cliente descarta os tokens |
| POST | `/tourists` | cadastro de turista (201): exige CPF ou passaporte (422 `document_required`); email/documento repetido → 409 `duplicate_identity` |

**Autenticado** — `app/api/me.py`:

| Método | Caminho | Função |
|---|---|---|
| GET / PATCH | `/me` | perfil (`MeResponse`) e atualização de name/surname/phone |
| PUT / GET | `/me/interests` | substitui/lê interesses (`category_ids`, delete-then-insert) |

**Admin** — `app/api/employees.py`:

| Método | Caminho | Função |
|---|---|---|
| GET / POST | `/employees` | lista/cria funcionário (409 `duplicate_email`) |
| PATCH / DELETE | `/employees/{id}` | atualiza; DELETE é revogação lógica (`is_active=False`) |

**Interno** — `GET /internal/users/{user_id}` devolve `{id, country_of_origin, role}` **sem PII** (RNF08), consumido por outros serviços; sem auth no código — a proteção é o gateway bloquear `/internal/*` na borda.

## Variáveis de ambiente

| Variável | Uso | Default |
|----------|-----|---------|
| `DATABASE_URL` | banco `passanorte_auth` | sem env: `sqlite:///./dev.db` |
| `JWT_SECRET` | assinatura HS256 dos tokens | default de desenvolvimento |
| `PII_ENCRYPTION_KEY` | chave Fernet do PII **e** do HMAC de unicidade; se definida mas vazia, a importação falha — sem ela, é gerada uma chave efêmera por processo (dados criptografados ficam irrecuperáveis em restart) | efêmera |
| `ACCESS_TOKEN_MINUTES` / `REFRESH_TOKEN_DAYS` | validade dos tokens | `15` / `7` |
| `INSIGHTS_SERVICE_URL` | log de acessos no login (RF07, fire-and-forget, 1 tentativa) | `http://localhost:8005` |

## Estrutura e notas de implementação

- `app/api/` — endpoints (públicos, admin e `/internal/*` entre serviços)
- `app/core/` — dependências (sessão, JWT), `require_role`, `load_user` e lógica de domínio
- `app/models/` — `User`, `TouristProfile`, `TouristInterest` (constraint `uq_user_category`) + `AuditLog`
- Auditoria em banco só nas ações de funcionário (create/update/revoke), gravada na mesma transação; login/cadastro só log estruturado JSON.
- Login retorna um único 401 `invalid_credentials` para todos os casos de falha.
- Notas de segurança conhecidas: timing no login (usuário inexistente não roda bcrypt), sem rotação/detecção de reuso do refresh token, e `/me/interests` não valida `role == tourist`.