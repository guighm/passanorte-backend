# Serviço de Chatbot (RF28, RF38–RF39)

Assistente de planejamento de roteiro com RAG: o catalog empurra conteúdo indexado (`/api/v1/internal/index/refresh`, delete+reinsert idempotente por `(source_type, source_id)`), a recuperação faz full scan de `embedded_contents` com similaridade de cosseno em Python (top-5, descarta score ≤ 0) e o provider de LLM é abstrato (`stub` default — monta roteiro determinístico a partir do contexto).

Notas de implementação: `pgvector` e `sentence-transformers` **não** são dependências do projeto — sem eles, a coluna de embedding cai em `Text`/JSON e o embedder é um stub hash determinístico de **256 dims** (com `sentence-transformers`, usa `paraphrase-multilingual-MiniLM-L12-v2`, 384 dims). Como a coluna pgvector é declarada como `Vector(384)`, embeddings do stub falhariam no Postgres de produção — em dev (SQLite/JSON) não há conflito. O custo estimado (`estimated_cost`) soma `ticket_price` apenas dos itens não fechados, mas a recuperação (`retrieve`) **não** exclui pontos fechados — a exclusão só vale para o custo.

## Como rodar

```bash
uv run uvicorn services.chatbot.app.main:app --port 8007
```

Ou com o docker-compose (raiz do monorepo): `docker compose up chatbot`.

Docs interativos: `http://localhost:8007/docs` (OpenAPI em `/openapi.json`).

## Endpoints

**Turista** — `app/api/conversations.py` (exige role `tourist`; escopo por dono — conversa alheia → 404):

| Método | Caminho | Função |
|---|---|---|
| POST | `/conversations` | cria conversa de planejamento (201) |
| GET | `/conversations` | lista as próprias conversas, mais recentes primeiro |
| GET | `/conversations/{id}` | conversa + histórico de mensagens (com `references_ids`) |
| POST | `/conversations/{id}/messages` | pipeline RAG: retrieve → prompt restrito → resposta com `references` e `estimated_cost` |

**Interno** — `app/api/internal.py` (sem auth; o gateway bloqueia `/internal/*` na borda):

- `POST /internal/index/refresh` (202) — reconstrói embeddings dos itens alterados (D-08): payload `{items: [{source_type: tourist_spot|event|route, source_id, spot_id?, title, description, status, latitude?, longitude?, ticket_price?, occurs_at?, schedule_text?}]}`; resposta `{"indexed": n}`. Delete+reinsert por par — cada refresh gera novos UUIDs e `embedded_at` novo.

## Variáveis de ambiente

| Variável | Uso | Default |
|----------|-----|---------|
| `DATABASE_URL` | banco `passanorte_chatbot` (pgvector/pgvector:pg16) | sem env: `sqlite:///./dev.db` |
| `JWT_SECRET` | validação dos tokens | default de desenvolvimento |
| `LLM_PROVIDER` | `stub` (default) \| `gemini` \| `ollama`; valor desconhecido cai no stub | `stub` |
| `LLM_GEMINI_API_KEY` | sem chave → 503 `assistant_unavailable` nas conversas | vazia |
| `LLM_OLLAMA_URL` / `LLM_OLLAMA_MODEL` | endpoint e modelo do Ollama | `http://localhost:11434` / `llama3.1` |

> O compose só repassa `LLM_PROVIDER` para o container do chatbot — as demais variáveis do provider precisam ser injetadas à parte em produção.

## Estrutura e notas de implementação

- `app/api/` — conversas do turista (`conversations.py`) e rebuild do índice (`internal.py`)
- `app/core/` — `embeddings` (stub/sentence-transformers), `retrieval` (cosseno em Python), `provider` (stub/gemini/ollama)
- `app/models/` — `Conversation`, `Message` (com `retrieved_context_json` de auditoria) e `EmbeddedContent` (índice único `uq_embedded_source`)
- Providers externos: Gemini (`gemini-1.5-flash`, timeout 15s) e Ollama (`/api/generate`, timeout 60s); qualquer falha → 503 `assistant_unavailable` e rollback (a mensagem do usuário não é persistida nesse caso).
- Eventos reindexam na criação; **PATCH/DELETE de evento, remoção lógica de ponto e alteração de horários não reindexam** — o índice pode ficar defasado nesses casos. Rotas do gamification nunca são indexadas (apesar do `source_type:"route"` aceito).