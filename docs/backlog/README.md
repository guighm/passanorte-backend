# Backlog — SPD-PassaNorte Backend

> Gerado em 2026-10-10, a partir de uma análise do estado atual do repositório (`trunk` @ `6ff615c`).
> Estado na análise: **106 testes passando** (unit/integration/contract), ruff limpo, 13 erros de mypy em 9 arquivos, sem CI.

Legenda de prioridade:

- **P0** — bloqueia produção ou corrige bugs objetivos (env vars quebradas, schema sem migrations)
- **P1** — endireitamento de segurança/consistência ou dívida que cresce com o tempo
- **P2** — melhorias e robustez

Estimativas: **S** (≤ 1 dia) · **M** (2–4 dias) · **G** (≥ 1 semana).

---

## P0 — Correções e pré-requisitos de produção

### BL-01 · Gerar as migrations Alembic dos 7 serviços — **G**

Os scaffolds Alembic existem em todos os serviços, mas `alembic/versions/` está **vazio em todos** e os `app/models/__init__.py` não registram tabelas no metadata. Hoje o schema só é criado via `Base.metadata.create_all` (nos testes) — em produção com banco novo não há caminho de deploy.

- Registrar os models no metadata de cada serviço (ou importar no `env.py`)
- Gerar a revisão inicial (`alembic revision --autogenerate`) por serviço
- Critérios de aceite: `alembic upgrade head` em `passanorte_*` novinho cria o schema completo e idêntico ao `create_all`; a suíte de testes roda sobre o schema das migrations (não do `create_all`)
- Ref.: nota no `README.md` da raiz («Nota sobre migrations»), `src/services/<svc>/alembic/env.py`

### BL-02 · Corrigir nomes de variáveis no `.env.example` — **S**

O `.env.example` usa `GEMINI_API_KEY` e `OLLAMA_BASE_URL`, mas o código lê `LLM_GEMINI_API_KEY` e `LLM_OLLAMA_URL` — quem copiar o exemplo e escolher `LLM_PROVIDER=gemini|ollama` terá as credenciais silenciosamente ignoradas. O comentário também menciona "AES-256-GCM" quando o mecanismo é Fernet.

- Renomear as chaves; corrigir o comentário
- Critério de aceite: `uv run python -c` de verificação lê o provider correto com base em um `.env` puramente copiado do exemplo
- Ref.: caveat no `README.md` da raiz, `src/services/chatbot/app/core/provider.py`

### BL-03 · Injetar credenciais do LLM no chatbot via compose — **S**

O `docker-compose.yml` repassa ao container do chatbot apenas `LLM_PROVIDER`; `LLM_GEMINI_API_KEY` / `LLM_OLLAMA_*` não chegariam em um deploy via compose.

- Adicionar as variáveis ao `svc_env`/serviço `chatbot` com `${VAR:-}` (default vazio mantém o stub funcional)
- Critério de aceite: `docker compose config` mostra as credenciais; com `LLM_PROVIDER=gemini` + chave real, o chatbot responde
- Ref.: nota no `README.md` da raiz, `docker-compose.yml` (serviço `chatbot`)

### BL-04 · Instalar CI (GitHub Actions) — **M**

Não há `.github/`. Toda verificação é manual.

- Workflow de PR executando `uv sync` → `ruff check` → `mypy src` → `pytest --cov`
- Dependência: BL-05 precisa estar resolvido (ou o mypy entra como baseline/aviso) para o CI não nascer vermelho
- Critérios de aceite: PR aberto dispara o pipeline; job vermelho reprova merge

### BL-05 · Zerar o mypy (13 erros em 9 arquivos) — **S**

Erros atuais: `shared/security.py` (2, anotações de bcrypt), `shared/app.py` (include_router), `shared/notifications_client.py`, `gamification/app/core/redemptions.py` (2, `rowcount`), `insights/app/api/dashboard.py` (2), `auth/app/api/tourists.py`, `catalog/app/api/spots.py`, `catalog/app/api/spots_admin.py`, `validation/app/api/visits.py` (2, retorno `JSONResponse` vs `dict`).

- Critérios de aceite: `uv run mypy src` → 0 erros; nenhum teste quebra
- Ref.: `pyproject.toml` (config mypy), arquivos listados

### BL-06 · Política de restart e dependência de boot no compose — **S**

Nenhum serviço do compose tem `restart:` definido — uma queda do container (OOM, crash) derruba a rota no Kong até intervenção manual.

- `restart: unless-stopped` nos 7 serviços e no Kong
- Revisar `depends_on`: serviços devem subir com `condition: service_healthy` sobre `db` e `rabbitmq` (seus healthchecks já existem)
- Critério de aceite: `docker compose up -d` + `docker kill <svc>` → container retorna sozinho; healthchecks voltam a passar
- Ref.: `docker-compose.yml`

---

## P1 — Segurança e consistência

### BL-07 · Hardening da sessão JWT (auth) — **M**

Dívidas documentadas em `src/services/auth/README.md`:

1. **Refresh sem rotação** — `/session/refresh` devolve o mesmo refresh token sempre; sem detecção de reuso. Implementar rotação + revogação da cadeia em reuso (padrão "refresh token rotation")
2. **Revogação de funcionário não invalide tokens emitidos** — `is_active=False` só bloqueia o login; access tokens seguem válidos até expirar. Alternativa mínima: bloquear por papel/is_active nos endpoints escritos por funcionário (já filtrado por `require_role`? verificar) ou checar `is_active` no refresh
3. **Timing no login** — usuário inexistente não roda bcrypt (timing oracle de enumeração de emails); rodar bcrypt contra hash dummy
4. **`/me/interests` não valida `role == tourist`** — admin/funcionário podem criar interesses
- Critérios de aceite: cada item com teste em `tests/unit/test_session_security.py` ou `tests/contract/test_auth_us1.py`
- Ref.: `src/services/auth/README.md`, `shared/security.py`, `auth/app/api/session.py`

### BL-08 · Unificar o envelope de erro na borda Kong — **M**

Respostas geradas pelo Kong (401/404/429/502/504) saem no formato `{"message": ...}` e não no envelope `{"error": {code, message, details}}` do projeto — cada cliente precisa ramificar por exceção. O README documenta o problema, mas não o resolve.

- Opção A (preferida): plugin `response-transformer`/serverless para normalizar os erros do Kong no envelope do projeto, preservando `X-Request-Id`
- Opção B: aceitar o formato duplo definitivamente e mover essa garantia para a documentação da API consumida pelos clientes
- Critérios de aceite: qualquer resposta 4xx/5xx na porta 8000 (incluindo as do próprio Kong) segue um único formato documentado
- Ref.: nota no `README.md` da raiz, `kong/kong.yml`

### BL-09 · Observabilidade do barramento de eventos — **M**

Os consumers entregam com requeue e a 2ª falha vai para a DLQ `passanorte.dlq` — mas nada avisa nem permite reprocessar. Mensagem perdida na DLQ = fatos de visita, notificações e re-embeds desaparecem silenciosamente.

- Endpoint admin (ou job) que consulta a DLQ e permite reinjetar mensagens
- Alerta quando `passanorte.dlq` tem > 0 mensagens (ou métrica exportada)
- Critérios de aceite: teste de integração simula consumer que falha 2×, mensagem aparece na DLQ e é reinjetada com sucesso
- Ref.: `shared/messaging.py`, `docker-compose.yml` (UI RabbitMQ :15672)

### BL-10 · Resolver o `specs/` fantasma na documentação — **S**

O `README.md` da raiz lista `specs/001-passaporte-turistico-backend` na estrutura do repositório, mas o diretório não existe (está gitignored). Quebra a orientação de quem entra no projeto.

- Decidir: (a) versionar os contratos das user stories no repo, ou (b) remover a menção e apontar para os READMEs por serviço + OpenAPI
- Critério de aceite: `README.md` da raiz não referencia caminho inexistente
- Ref.: `.gitignore`, seção «Estrutura do repositório»

### BL-11 · Remover o efeito colateral dos GETs de inscrição — **M**

A checagem de conclusão de rota (criar Badge + RedeemCode + emitir notificação) roda dentro dos `GET /enrollments*` — "um GET pode mutar estado" (documentado). Isso é difícil de escalar, cachear e raciocinar.

- Mover a conclusão para o caminho de escrita correto: o evento `visit.validated` (consumido via RabbitMQ) ou um hook na validação de visita — conclui antes de qualquer leitura
- Critérios de aceite: GETs puros (idempotentes, sem escrita); conclusão continua disparando exatamente uma vez; testes de `tests/integration/test_us4_gamification.py` cobrem o novo caminho
- Ref.: `src/services/gamification/README.md`, `gamification/app/core/completion.py`, `shared/insights_client.py`

---

## P2 — Robustez e melhorias

### BL-12 · Revisar rate limiting por rota — **S**

Hoje há um `rate-limiting` global no Kong (`kong.yml` ~linha 217). Endpoints como `/visits` (escrita com consulta inter-serviço) e o chatbot (chamada a LLM) têm custos muito diferentes de leitura do catálogo — limites globais únicos os tratam igual.

- Definir limites por rota/serviço no Kong (ou por papel), com métricas de uso para calibrar
- Critérios de aceite: limites distintos documentados e aplicados; teste manual de 429 nas rotas mais caras

### BL-13 · Retry/resiliência nas chamadas REST inter-serviço — **M**

As consultas pull (`validation → catalog`, `gamification → validation`) são timeout único sem retry. A falha do catalog vira 503 para o turista; a da validation deixa progresso vazio.

- Adicionar retry curto com backoff (httpx transport retries) nas leituras idempotentes; manter falha rápida nos escritos
- Critérios de aceite: queda de 1–2 requests transitória não vira 503; testes de integração com `httpx.MockTransport` simulando retry
- Ref.: `validation/app/core/deps.py` (`get_catalog_snapshot`), `gamification/app/core/deps.py` (`get_validated_visits`), D-13

### BL-14 · Cadastro de endpoints admin no OpenAPI agregado — **S**

O Kong não serve `/docs` e cada serviço mantém o próprio só no loopback — não há visão única da API pública (`/api/v1`) para os clientes.

- Gerar/ manter um OpenAPI agregado da borda (merge dos schemas dos 7 serviços, respeitando o mapeamento de rotas do `kong.yml`) e publicá-lo como artefato versionado
- Complemento natural do BL-10
- Critérios de aceite: documento único listando toda a superfície `:8000/api/v1`, incluindo o formato de erro definido no BL-08

### BL-15 · Limpeza de visitas `rejected` — **S**

O índice parcial único permite que linhas `rejected` de `Visit` se acumulem indefinidamente (postman insistindo fora do raio). Volume de lixo cresce sem limite.

- Política de retenção (job/cron de purge com idade configurável) ou mover rejeitas recentes para uma tabela rotativa
- Critérios de aceite: job documentado e idempotente; índice `uq_visit_validated` continua correto
- Ref.: `src/services/validation/README.md`, `validation/app/models/visit.py`

### BL-16 · Cobertura mínima nos gaps de auditoria — **M**

Hoje apenas mutações admin e de funcionário gravam `AuditLog` (na mesma transação — ok). Ações de turista (cadastro, resgate concluído, conclusão de rota) ficam só em log JSON estruturado, que não é consultável nem à prova de rotação de logs.

- Mapear quais ações de turista precisam de trilha consultável (ex.: resgate de brinde) e gravá-las em banco, ou documentar explicitamente a decisão de deixá-las só em log
- Critérios de aceite: decisão documentada por ação; eventos elegíveis com teste

---

## Backlog já realizado (não fazer de novo)

- Barramento RabbitMQ no lugar do HTTP fire-and-forget (`6ff615c`) — eventos, DLQ e modo degradado funcionando, com testes
- Kong DB-less na borda substituindo o gateway em Python (`b5b6499`) — JWT, CORS, correlation ID, rate limit e `/internal/*` invisível
- Suíte completa de testes (contract/integration/unit para as 7 user stories), ruff format/check e config mypy/ruff no `pyproject.toml`
- Script de credencial inicial de admin (RF01) e `init-databases.sh` (7 databases + pgvector)

---

## Não-backlog (decisões deliberadas, não tratar como dívida)

- `/health` **liveness-only** (sem ping de banco/broker): queda do RabbitMQ não derruba os healthchecks; reconexão é automática (`RobustConnection`)
- `/internal/*` sem autenticação entre serviços: proteção é a ausência de rota no Kong + rede interna
- `DELETE /session` no-op (logout stateless): cliente descarta os tokens, `jti` não é persistido — revisível apenas junto com o BL-07
- Progresso de rota **derivado, nunca persistido** (D-13): busca de visitas pode falhar e o progresso vem vazio