# Issues — Serviço de Notificações

Cada issue corresponde a um endpoint do serviço. Referência: RF37. Todos exigem papel `tourist` (não há visão admin); o serviço é um puro *sink* — não faz chamadas a outros serviços.

| Título | Descrição |
|---|---|
| `PUT /subscriptions` — substitui inscrições | Substitui **integralmente** as inscrições por interesse do turista via `{"category_ids": [...]}`. Sem FK ao catalog (outro banco); constraint `uq_subscription_user_category` evita duplicados. |
| `GET /subscriptions` — lê inscrições | Retorna os `category_ids` atualmente inscritos pelo turista autenticado. |
| `GET /notifications` — inbox do turista | Caixa de entrada in-app (D-06) do turista autenticado, mais recentes primeiro, formato `{items, total}`. Alimentado pelo consumer da fila `notification.dispatch` (dedup por `(user, kind, source_id)`); sem canal externo (sem push/email/websocket). |
| `PATCH /notifications/{notification_id}/read` — marca como lida | Seta `read_at` somente se ainda nulo (idempotente). 404 se a notificação não existir ou não pertencer ao turista. |