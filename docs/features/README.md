# Features — SPD-PassaNorte Backend · Issues por feature

> Gerado em 2026-10-10 a partir de uma análise do estado do repositório (`trunk` @ `6ff615c`), dos READMEs de cada serviço e do backlog geral ([`docs/backlog/README.md`](../backlog/README.md)).
> Cada seção descreve o recorte de uma feature (serviço) e lista os **issues abertos nela** — funcionais, de segurança, de consistência e de documentação. Issues que atravessam todas as features estão na seção **Plataforma**.

Prioridade (mesma escala do backlog):

- **P0** — bug objetivo ou bloqueio de produção
- **P1** — segurança/consistência ou dívida que cresce com o tempo
- **P2** — robustez, escala, decisão de produto ou documentação

Refs em `(BL-xx)` apontam para o backlog geral, que concentra critérios de aceite e estimativas.

Índice: [Auth](#auth-rf01rf05-rf22rf25) · [Catalog](#catalog-rf11rf17-rf26rf29) · [Validation](#validation-rf31rf34) · [Gamification](#gamification-rf18rf21-rf29rf30-rf35rf36) · [Insights](#insights-rf06rf10) · [Notifications](#notifications-rf37) · [Chatbot](#chatbot-rf28-rf38rf39) · [Plataforma](#plataforma-transversal)

| Feature | P0 | P1 | P2 |
|---|---|---|---|
| Auth | 0 | 3 | 1 |
| Catalog | 0 | 1 | 2 |
| Validation | 0 | 1 | 3 |
| Gamification | 0 | 2 | 1 |
| Insights | 1 | 0 | 2 |
| Notifications | 0 | 1 | 2 |
| Chatbot | 1 | 1 | 4 |
| Plataforma | 1 | 5 | 4 |

---

## Auth (RF01–RF05, RF22–RF25)

Identidade e sessão JWT (access 15 min / refresh 7 dias), RBAC `admin`/`employee`/`tourist`, PII em Fernet, unicidade de documento por HMAC-SHA256. Ref.: [`src/services/auth/README.md`](../../src/services/auth/README.md).

### AUTH-01 · Refresh token sem rotação nem detecção de reuso — **P1** (BL-07)

`POST /session/refresh` devolve o **mesmo** refresh token sempre: um refresh roubado funciona por 7 dias, infinitamente. Implementar rotação com revogação da cadeia em reuso (refresh token rotation), com testes em `tests/unit/test_session_security.py`.

### AUTH-02 · Revogação de funcionário não invalida tokens emitidos — **P1** (BL-07)

`DELETE /employees/{id}` (revogação lógica, `is_active=False`) bloqueia só o próximo login. Access tokens emitidos antes seguem válidos até expirar; o refresh checka o banco, mas o access não. Mínimo: checar `is_active`/papel no refresh e nos endpoints de escrita.

### AUTH-03 · `PII_ENCRYPTION_KEY` ausente gera chave efêmera silenciosamente — **P1**

Sem a env var, cada processo gera uma chave Fernet própria: dados de telefone/CPF/passaporte ficam **irrecuperáveis** em restart e ilegíveis entre réplicas — sem nenhum erro ou warning explícito em produção. Adicionar guard de startup (fail-fast) quando o ambiente é produção sem a chave definida.

### AUTH-04 · Logout stateless (`DELETE /session` no-op) — **P2**

Deliberado (o `jti` nunca é persistido), mas revisível junto com AUTH-01/rotação de refresh: se a cadeia de refresh passa a ser revogável, o logout pode revogar de verdade.

Pendências deste serviço rastreadas direto no backlog (não duplicadas aqui): [BL-07](../backlog/README.md#bl-07) — `/me/interests` não valida `role == tourist` e o timing do login permite enumeração de emails (bcrypt não roda para usuário inexistente).
Não é issue: unicidade de documento via HMAC cobre CPF e passaporte no mesmo espaço; login devolve 401 único para todos os casos de falha.

---

## Catalog (RF11–RF17, RF26–RF29)

Catálogo de pontos, categorias e eventos: leitura pública, CRUD admin, schedules com validação de sobreposição, deep links; publica `notification.dispatch` e `catalog.index.refresh` após mutações. Ref.: [`src/services/catalog/README.md`](../../src/services/catalog/README.md).

### CAT-01 · Mutações de evento não reindexam o chatbot — **P1**

`POST` de evento reindexa, mas `PATCH` e `DELETE` de evento não — o índice RAG fica com título/descrição/data desatualizados (ou apontando para evento removido) até o próximo refresh do ponto. Corrigir em `app/api/events.py` e cobrir em `tests/integration/test_us7_chatbot.py`.

### CAT-02 · Ponto removido logicamente desaparece até do admin — **P2**

`is_removed=True` filtra a linha em **todos** os endpoints, inclusive `GET /admin/tourist-spots/{id}`: sem como listar, auditar ou restaurar pontos removidos. Adicionar visão admin (ou flag de query) para remoções lógicas.

### CAT-03 · Ordenação por proximidade em memória, sem paginação — **P2**

`GET /tourist-spots?lat/lng` calcula Haversine em Python para o resultado inteiro e devolve tudo (RF26). Com crescimento do catálogo vira custo linear por request e resposta sem limite. Paginar ou limitar raio de busca.

---

## Validation (RF31–RF34)

Validação de presença por GPS (Haversine × `tolerance_radius_m` do snapshot do catalog), visitas `validated` idempotentes por índice parcial único, `rejected` como trilha de auditoria; propaga `visit.validated` via RabbitMQ. Ref.: [`src/services/validation/README.md`](../../src/services/validation/README.md).

### VAL-01 · Snapshot do catalog sem retry → 503 para o turista — **P1** (BL-13)

`get_catalog_snapshot` (`app/core/deps.py`) faz uma única chamada httpx com timeout; uma falha transitória do catalog vira 503 na submissão de visita. Retry curto com backoff na leitura idempotente.

### VAL-02 · Rejeições (`rejected`) se acumulam sem política de retenção — **P2** (BL-15)

Cada tentativa fora do raio grava uma linha (trilha RF33); um usuário insistente gera volume ilimitado. Job de purge idempotente ou retenção configurável.

### VAL-03 · Resposta de rejeição foge do envelope de erro — **P2**

`POST /visits` rejeitada retorna 422 com corpo plano `{"status: rejected", distance_m, tolerance_m}` — única rota fora do envelope `{"error": {...}}`. Decisão de contrato a documentar (ou normalizar mantendo os campos como `details`).

### VAL-04 · README do serviço lista env vars removidas do código — **P2 (docs)**

A tabela de variáveis cita `INSIGHTS_SERVICE_URL` e `GAMIFICATION_SERVICE_URL`, mas a propagação é via RabbitMQ desde `6ff615c` — no código só sobra `CATALOG_SERVICE_URL` (`app/core/deps.py:41`). Remover as linhas defasadas do README.

---

## Gamification (RF18–RF21, RF29–RF30, RF35–RF36)

Rotas, inscrições, progresso derivado das visitas (D-13), insígnias e códigos de resgate exatamente-uma-vez; publica `notification.dispatch` na conclusão. Ref.: [`src/services/gamification/README.md`](../../src/services/gamification/README.md).

### GAM-01 · GET de inscrição muta estado — **P1** (BL-11)

`POST /enrollments` e os `GET /enrollments*` rodam `_check_completion` (`app/api/enrollments.py:37`), que pode criar Badge, RedeemCode e notificar. Mover a conclusão para o caminho de escrita (consumer do evento `visit.validated`).

### GAM-02 · Resgate sem vínculo nem trilha consultável — **P1** (BL-16)

Qualquer funcionário resgata o código de qualquer turista (`POST /redemptions`), e o resgate — ação do turista/funcionário mais sensível ao produto — fica só no log JSON estruturado, sem `AuditLog` consultável. Definir política de auditoria e autorização (hoje não há restrição documentada de por quem).

### GAM-03 · Falha silenciosa na leitura de visitas deixa progresso vazio — **P2**

Se `get_validated_visits` (validation) falha, o progresso vem vazio sem qualquer indicação na resposta (D-13 parcialmente deliberado — o serviço não trava). Sempre que o erro for de infraestrutura e não de "turista sem visitas", sinalizar (campo ou log com request_id correlacionado).

---

## Insights (RF06–RF10)

Dashboards admin (heatmap, acessos, rankings, distribuições) sobre fatos recebidos via RabbitMQ (`visit.validated`, `access.registered`), ingestão idempotente. Ref.: [`src/services/insights/README.md`](../../src/services/insights/README.md).

### INS-01 · Payload de evento malformado estoura `KeyError` — **P0**

Fato sem `user_id`/`tourist_spot_id` (obrigatórios) gera `KeyError` no handler (`app/core/handlers.py`) — requeue a requeue até a DLQ, com nenhuma sinalização de causa. Validar o payload e descartar com log estruturado `invalid_payload` (e mesma correção no dispatcher do notifications).

### INS-02 · Semântica duvidosa do heatmap (`total` não é total de visitas) — **P2**

`GET /heatmap` é um `GROUP BY tourist_spot_id` sem filtro temporal, e `total` da resposta é o número de **pontos distintos**, não o total de visitas — leitura natural do consumidor do dashboard quebra. Corrigir o campo, renomear ou documentar; avaliar filtro `from/to`.

### INS-03 · Distribuição de interesses agregada em Python — **P2**

`GET /distributions/interests` faz split de CSV e dedup por `set` em aplicação, sobre todos os fatos — escala pior que as agregações SQL do resto do serviço. Migrar para SQL (tabela normalizada ou `unnest`) quando o volume crescer.

---

## Notifications (RF37)

Inscrições por interesse e inbox in-app; puro sink, dispatch idempotente por `(user, kind, source_id)` via fila `passanorte.notifications.dispatch`. Ref.: [`src/services/notifications/README.md`](../../src/services/notifications/README.md).

### NOT-01 · Payload de dispatch malformado não é tratado formalmente — **P1**

Mesma família do INS-01: payload sem `kind`/`source_id`/`title` derruba o handler com exceção (requeue → DLQ) em vez de descartar com log; a falha conhecida ainda citada como "500 genérico" no README data da era HTTP. Renomear para o consumer e tratar `invalid_kind`/payload ausente como descarte com log.

### NOT-02 · Nenhum canal externo de entrega — **P2**

Toda notificação é linha no inbox (`GET /notifications` com polling do cliente). Deliberado hoje (RNF de custo), mas o produto não notifica se o turista não abrir o app. Decision record antes de qualquer push/email/websocket.

### NOT-03 · Sem visão admin das notificações — **P2**

Os endpoints são só do turista; não há leitura admin para suporte/debug (ex.: verificar se um dispatch chegou). Baixa prioridade, mas facilita operar o RF37.

---

## Chatbot (RF28, RF38–RF39)

RAG sobre o catálogo: índice `embedded_contents` reconstruído pelo consumer de `catalog.index.refresh`, recuperação por cosseno top-5, provider LLM abstrato (stub/gemini/ollama). Ref.: [`src/services/chatbot/README.md`](../../src/services/chatbot/README.md).

### CHB-01 · Embeddings do stub (256d) são incompatíveis com o `Vector(384)` de produção — **P0**

`pgvector` e `sentence-transformers` **não são** dependências do projeto: sem eles, o embedder é um hash de 256 dims sobre coluna declarada `Vector(384)` — dev (SQLite/JSON) passa, produção (Postgres pgvector) **quebra o insert na reindexação**. Decidir: instalar `sentence-transformers` + pgvector na imagem/docker (dims batem em 384) ou parametrizar a dimensão da coluna; critério: reindexação e retrieval provados no compose.

### CHB-02 · Índice RAG fica defasado em vários caminhos de mutação — **P1** (+ CAT-01)

Não reindexam: `PATCH`/`DELETE` de evento (CAT-01), remoção lógica de ponto e substituição de horários (`PUT /tourist-spots/{id}/schedule`). O chatbot recomenda com dados velhos. Cobertura do payload/evento nesses fluxos ou reindexação do item na mesma transação do evento.

### CHB-03 · Rotas turísticas nunca são indexadas — **P2**

`refresh_from_payload` aceita `source_type:"route"`, mas o gamification nunca publica o evento — o chatbot não conhece rotas no RAG (RF38 menciona roteiro). Confirmar se é escopo deliberado; se não, gamification publica `catalog.index.refresh` na criação de rota.

### CHB-04 · Recuperação não exclui pontos fechados/removidos — **P2**

`retrieve` não filtra `permanently_closed`/removidos — só o custo estimado exclui itens fechados. Turista pode receber roteiro com ponto fechado. Filtrar no retrieve (o payload já traz `status`).

### CHB-05 · Recuperação é full scan em Python — **P2** (ligado a CHB-01)

Sem pgvector no runtime, a similaridade é cosseno calculado em Python sobre todas as linhas. Resolvido pelo CHB-01; registrar como dependência, não como trabalho separado.

### CHB-06 · Credenciais do provider não chegam ao container — **P2** (BL-02, BL-03)

`.env.example` usa nomes que o código não lê (`GEMINI_API_KEY` vs `LLM_GEMINI_API_KEY`, `OLLAMA_BASE_URL` vs `LLM_OLLAMA_URL`) e o compose só repassa `LLM_PROVIDER`. Com `LLM_PROVIDER=gemini` sem chave → 503 `assistant_unavailable` no chat (e a mensagem do usuário se perde — provider falha faz rollback antes de persistir).

---

## Plataforma (transversal)

### FX-01 · Migrations Alembic de todos os serviços vazias — **P0** (BL-01)

Caminho de deploy do schema inexistente (`versions/` vazio nos 7 serviços). Detalhes e critérios no [BL-01](../backlog/README.md#bl-01).

### FX-02 · Sem CI no repositório — **P1** (BL-04)

Depende de zerar o mypy (FX-03) para não nascer vermelho.

### FX-03 · 13 erros de mypy em 9 arquivos — **P1** (BL-05)

### FX-04 · Compose sem `restart` e `depends_on` sem condição de health — **P1** (BL-06)

### FX-05 · Envelope de erro duplo na borda do Kong — **P1** (BL-08)

4xx/5xx do Kong saem em `{"message": ...}` e as dos serviços em `{"error": {...}}`.

### FX-06 · DLQ sem observabilidade — **P1** (BL-09)

Mensagens em `passanorte.dlq` (visitas, notificações, re-embeds) desaparecem silenciosamente — sem alerta nem reinjeção.

### FX-07 · Envelope de erro e rate limit não calibrados — **P2** (BL-12)

Rate limit único global trata leitura do catálogo e chamada de LLM igual.

### FX-08 · Sem OpenAPI agregado da borda — **P2** (BL-14)

Cada serviço serve `/docs` só no loopback; não há visão única de `:8000/api/v1`.

### FX-09 · README da raiz referencia `specs/` inexistente — **P2 (docs)** (BL-10)

### FX-10 · Trilha de auditoria desigual entre serviços — **P2** (BL-16)

Mutations admin gravam `AuditLog`, ações de turista (cadastro, conclusão, resgate) só ficam em log JSON — GAM-02 cobre o caso concreto mais sensível.

---

## Issues que não são dívida (decisões deliberadas do produto)

Não abrir issues para o que segue — registrado para evitar retrabalho (mesma lista do backlog e dos READMEs):

- `/health` liveness-only (sem ping de banco/broker); reconexão ao RabbitMQ é automática.
- `/internal/*` sem autenticação entre serviços — proteção pela ausência de rota no Kong + rede interna.
- Progresso de rota derivado, nunca persistido (D-13) — ver GAM-03 apenas para a sinalização de falha.
- Remoção lógica de pontos/rotas para preserve progresso em andamento — ver CAT-02 para visibilidade admin.
- Notificações exclusivamente in-app (sem push/email) — ver NOT-02 como decision record futuro.