# Issues — Serviço de Gamificação

Cada issue corresponde a um endpoint do serviço. Referências: RF18–RF21, RF29–RF30, RF35–RF36, D-02, D-13.

| Título | Descrição |
|---|---|
| `GET /routes` — lista rotas ativas | Lista as rotas turísticas ativas com seus pontos (por posição) e o brinde associado (RF18). Endpoint público. |
| `POST /routes` — cria rota (admin) | Cria rota com brinde embutido (`prize: {name}`) e pontos ordenados por posição. Ação auditada em banco (`create_route`, mesma transação). 201. Requer papel `admin`. |
| `PATCH /routes/{route_id}` — atualiza rota (admin) | Atualiza dados da rota; recria os pontos associados (replace-all). Ação auditada. Requer papel `admin`. |
| `DELETE /routes/{route_id}` — remoção lógica (admin) | Marca `is_active=False` — progressos em andamento dos turistas não quebram. Ação auditada (`remove_route`). 204. Requer papel `admin`. |
| `GET /prizes` — lista brindes (admin) | Lista os brindes cadastrados com estoque atual (`stock_quantity >= 0`, enforced por CHECK). Requer papel `admin`. |
| `POST /prizes` — cria brinde (admin) | Cria brinde com estoque inicial 0. Ação auditada (`create_prize`). 201. Requer papel `admin`. |
| `PATCH /prizes/{prize_id}/stock` — ajusta estoque (admin) | Define o estoque absoluto do brinde (`ge=0`). Ação auditada (`update_stock`). Requer papel `admin`. |
| `POST /routes/{route_id}/enrollments` — inscreve turista | Inscreve o turista autenticado na rota (409 `already_enrolled` se repetida; 404 se rota inexistente/inativa). Retorna o progresso derivado no momento da inscrição. Constraint `uq_enrollment_user_route`. |
| `GET /enrollments` — inscrições do turista | Lista as inscrições do turista autenticado com progresso e checagem de conclusão. **Um GET pode mutar estado**: ao detectar `percent == 100.0` com status `in_progress`, dispara a conclusão (badge + código + notificação) e marca `completed`. |
| `GET /enrollments/{route_id}` — inscrição de uma rota | Detalhe da inscrição do turista na rota informada, com progresso derivado e checagem de conclusão (mesma semântica da listagem). Progresso é derivado a cada leitura (D-13), cruzando com visitas do validation via Bearer repassado verbatim; falha na busca → progresso vazio, sem travar o serviço. |
| `GET /badges` — insígnias do turista | Retorna as insígnias conquistadas pelo turista autenticado. Constraint `uq_badge_user_route` (uma por rota). |
| `GET /redeem-codes` — códigos de resgate do turista | Lista os códigos de resgate do turista autenticado (`PN-` + 16 hex maiúsculos), com status `issued`\|`redeemed`. |
| `POST /redemptions` — resgate de brinde (funcionário) | Valida o código informado, concede o brinde e decrementa o estoque (RF21). Exatamente-uma-vez via `UPDATE` condicional: código não `issued` → 409 `code_already_used`; estoque esgotado → rollback e 409 `prize_out_of_stock`. Qualquer funcionário pode resgatar o código de qualquer turista. |