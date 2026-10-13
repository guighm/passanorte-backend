# Issues — Serviço de Catálogo

Cada issue corresponde a um endpoint do serviço. Referências: RF07, RF11–RF17, RF26–RF29, RF37, D-08.

| Título | Descrição |
|---|---|
| `GET /tourist-spots` — lista pública de pontos | Lista pontos turísticos com filtros `category`, `status` e `lat`/`lng` (ordenação por proximidade via Haversine em memória, RF26). Quando a requisição vem com JWT válido, registra acesso no insights (RF07). |
| `GET /tourist-spots/{spot_id}` — detalhe de ponto | Detalhe público: horários de funcionamento, eventos vinculados e `tolerance_radius_m` (usado pelo validation para o raio de tolerância). |
| `GET /tourist-spots/{spot_id}/external-links` — deep links | Retorna deep links de Google Maps / Uber / 99 para o ponto (URLs construídas localmente, sem chamadas externas). |
| `GET /categories` — categorias ativas | Lista as categorias de pontos turístico ativas no catálogo. |
| `GET /events` — lista pública de eventos | Eventos ordenados por data. Filtros `tourist_spot_id` e `from_date` (valor inválido → 422 `invalid_filter`). |
| `POST /tourist-spots` — cria ponto (admin) | Cria ponto turístico (201). Se houver categorias, dispara notificação `new_spot` por categoria (RF37) e reindexa o chatbot via `catalog.index.refresh` (D-08). Ação auditada. Requer papel `admin`. |
| `PATCH /tourist-spots/{spot_id}` — atualiza ponto (admin) | Atualiza dados do ponto. Dispara notificações (se houver categorias) e reindexa o chatbot. Ação auditada. Requer papel `admin`. |
| `DELETE /tourist-spots/{spot_id}` — remoção lógica (admin) | Marca `is_removed=True` (não apaga a linha). Linhas removidas somem de todos os endpoints, inclusive para o admin. Requer papel `admin`. 204. |
| `PUT /tourist-spots/{spot_id}/schedule` — substitui horários | Substitui integralmente os horários de funcionamento. Se as novas linhas sobrepõem janelas existentes → 422 `schedule_overlap`. Requer papel `admin`. |
| `PATCH /tourist-spots/{spot_id}/status` — muda status (admin) | Transição de status do ponto. `permanently_closed` é terminal — tentar reverter → 409 `invalid_status_transition`. Mudança de status reindexa o chatbot. Requer papel `admin`. |
| `GET /admin/tourist-spots/{spot_id}` — visão admin do ponto | Retorno enxuto para administração: `{id, name, status, categories}`. Requer papel `admin`. |
| `POST /events` — cria evento (admin) | Cria evento vinculado ao ponto (201) e dispara notificação `new_event` (RF37) + reindexa o chatbot via evento. Requer papel `admin`. |
| `PATCH /events/{event_id}` — atualiza evento (admin) | Atualiza dados do evento. **Não** reindexa o chatbot (índice pode ficar defasado). Requer papel `admin`. |
| `DELETE /events/{event_id}` — remove evento (admin) | Remoção **física** da linha do evento (diferente de pontos). Não reindexa o chatbot. Requer papel `admin`. 204. |
| `POST /categories` — cria categoria (admin) | Cria categoria de pontos/eventos (201). Nome duplicado → 409 `duplicate_category`. Requer papel `admin`. |
| `POST /internal/tourist-spots` — seed de ponto | Endpoint entre serviços: cria um ponto diretamente (usado por seeds e testes). Sem auth — sem rota correspondente no Kong (404 na borda). |
| `GET /internal/tourist-spots/{spot_id}` — snapshot do ponto para validation | Devolve raio de tolerância, coordenadas, status e categorias do ponto — snapshot consumido pelo serviço validation para checagem geográfica. Sem auth (sem rota no Kong). |
| `GET /internal/tourist-spots?ids=` — lista para feed/recomendação | Snapshot em lote dos pontos por `ids` (RF26), incluindo `category_ids` por ponto. Sem auth (sem rota no Kong). |
| `POST /internal/events/notify-subscribers` — re-dispara new_event | Re-dispara a notificação `new_event` de um evento já criado. A deduplicação fica no serviço notifications (202). Sem auth (sem rota no Kong). |