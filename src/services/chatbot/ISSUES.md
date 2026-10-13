# Issues — Serviço de Chatbot

Cada issue corresponde a um endpoint do serviço. Referências: RF28, RF38–RF39. Todos exigem papel `tourist` e escopo por dono (conversa alheia → 404).

| Título | Descrição |
|---|---|
| `POST /conversations` — cria conversa de planejamento | Cria uma nova conversa de planejamento de roteiro para o turista autenticado (201). |
| `GET /conversations` — lista próprias conversas | Lista as conversas do turista autenticado, mais recentes primeiro. |
| `GET /conversations/{conversation_id}` — conversa + histórico | Retorna a conversa com seu histórico de mensagens, incluindo `references_ids` das referências do catálogo usadas em cada resposta. Conversa de outro turista → 404. |
| `POST /conversations/{conversation_id}/messages` — pipeline RAG | Recebe a mensagem do turista e executa o pipeline RAG (RF38): retrieve top-5 por similaridade de cosseno (full scan de `embedded_contents`, descarta score ≤ 0) → prompt restrito → resposta do provider (`stub` default, `gemini` ou `ollama`) com `references` e `estimated_cost` (soma `ticket_price` dos itens não fechados). Falha do provider → 503 `assistant_unavailable` e rollback (a mensagem do usuário não é persistida nesses casos); sem `LLM_GEMINI_API_KEY` (provider gemini) → 503. A mensagem fica auditada em `retrieved_context_json`. |