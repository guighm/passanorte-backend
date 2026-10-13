# Issues — Serviço de Validação

Cada issue corresponde a um endpoint do serviço. Referências: RF31–RF34, D-05.

| Título | Descrição |
|---|---|
| `POST /visits` — registra visita por GPS | Valida presença do turista por Haversine (R=6.371.000 m) contra o `tolerance_radius_m` do snapshot do catalog (sem default local). Exige role `tourist` no serviço (403 para os demais). Resultados: 201 validada (com `distance_m` arredondado a 2 casas e `tolerance_m`) / 200 idempotente (visita já validada, `tolerance_m: null`, não re-propaga) / 422 rejeitada com corpo plano `{"status", "distance_m", "tolerance_m"}` (única rota que foge do envelope padrão) / 422 `gps_unavailable` / 503 `catalog_unavailable` (snapshot indisponível, sem retry). Visitas `rejected` são gravadas a cada tentativa (trilha de auditoria, RF33); `validated` é idempotente por índice parcial único `(user_id, tourist_spot_id)`. Na primeira validação publica o evento `visit.validated` no barramento (fire-and-forget, D-05). |
| `GET /visits` — lista visitas validadas | Lista apenas as visitas com status `validated` do usuário autenticado (qualquer papel), formato `{"items", "total"}`. Consumido pelo gamification para o progresso derivado. |
| `GET /visits/{spot_id}` — visita de um ponto | Retorna a visita validada do usuário autenticado para o ponto informado; 404 se não existir. |
| `POST /internal/visits/propagate` — re-propaga fato de visita | Endpoint entre serviços: re-publica o fato de uma visita validada para o insights; idempotente do lado do insights. Sem auth (sem rota no Kong — 404 na borda). |