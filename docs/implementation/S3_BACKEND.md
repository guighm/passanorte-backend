# S3 — Contrato de Identidade, Benefícios e Catálogo

Os fluxos de backend da S3 são aceitos com testes de API e migração. A implementação e a validação ponta a ponta no Android e no React ficam pendentes no [pós-MVP, item P4](../planning/PASSANORTE_IMPLEMENTATION_PLAN.md#post_mvp).

Todas as rotas abaixo são servidas pelo Kong sob `/api/v1`. Envie o access token como `Authorization: Bearer ...` nas operações protegidas.

| Recurso | Contrato |
| --- | --- |
| Sessão | `POST /session` recebe `email`, `password` e, no painel, `panel: true`. O painel aceita `admin` e `supplier`. `GET /me` retorna o perfil e `partner_id`. |
| Parceiros | `GET/POST /partners`, `GET/PATCH/DELETE /partners/{id}`. Envie `name`, `cnpj` e `contact` na criação. Somente administradores gerenciam parceiros. O DELETE equivale à desativação. |
| Usuários do painel | `GET/POST /panel/users` e `PATCH/DELETE /panel/users/{id}`. Na criação, envie `name`, `surname`, `email`, `password`, `role` e, para fornecedores, `partner_id` de um parceiro ativo. |
| Cadastro do turista | `POST /tourists` recebe `name`, `surname`, `email`, `password`, `phone`, `country_of_origin`, CPF ou passaporte, `accept_terms: true`, `accept_privacy: true`, `consent_version: "1"` e `category_ids` opcionais. |
| Interesses | `GET /categories` lista as categorias ativas. `GET/PUT /me/interests` lê ou substitui a seleção do turista por `{"category_ids": [...]}`. |
| Descoberta | `GET /tourist-spots` aceita `q`, `category` e o par `lat`/`lng`. Com interesses e coordenadas, ordena por afinidade e distância. Sem um dos dois, ordena por nome. O detalhe traz agenda, eventos vigentes e `maps_url`. |
| Pontos | `GET /admin/tourist-spots` e `GET /admin/tourist-spots/{id}` são administrativos. Criação e edição usam `/tourist-spots`. Na criação, envie nome, descrição, endereço, latitude, longitude e pelo menos uma categoria ativa. `image_url`, `duration_minutes` e `tolerance_radius_m` são opcionais. |
| Agenda | `PUT /tourist-spots/{id}/schedule` substitui a agenda. Cada entrada tem `day_of_week` (0 para domingo), `opens_at` e `closes_at` em HH:MM, ou `all_day: true`. Reenviar a agenda não a altera novamente. |
| Eventos | `GET /events` lista eventos vigentes. `GET /admin/events` inclui o histórico. Para criar, envie `tourist_spot_id`, `title`, `description`, `starts_at`, `ticket_price` e, se disponível, `ends_at`. Horários sem offset usam o fuso configurado. Sem fim informado, o evento deixa a listagem pública no início. |

## Atualização de uma base S2

Use `docker compose --env-file .env.example up --build -d --wait --wait-timeout 180` no ambiente local. O ensaio `bash scripts/verify_s2_migration.sh` também verifica a passagem da S2 para a S3 em um banco isolado.

Para verificar as rotas pela borda, execute `uv run --frozen python scripts/smoke_s2.py --email admin@example.com --s3`.

Contas do papel antigo conservam seus IDs e passam a fornecedores inativos. O servidor recusa tokens com o papel antigo e as sessões de renovação das contas migradas são revogadas. O administrador pode vincular cada conta a um parceiro ativo antes de reativá-la.

```sql
SELECT entity_id AS user_id, occurred_at
FROM auth.audit_logs
WHERE action = 'supplier_missing_partner_s3'
ORDER BY occurred_at, entity_id;
```

O seed preserva os IDs existentes e inclui **Lazer**, **Cultura** e **Gastronomia**, as categorias nomeadas na matriz do projeto.
