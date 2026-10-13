# Issues — Serviço de Autenticação

Cada issue corresponde a um endpoint do serviço. Referências: RF01–RF05, RF07, RF22–RF25.

| Título | Descrição |
|---|---|
| `POST /session` — login email+senha | Autentica usuário por email e senha (bcrypt, work factor 12). Retorna `TokenResponse` com `access_token` (15 min), `refresh_token` (7 dias) e `expires_in`. Registra acesso no insights via evento `access.registered` (RF07). Qualquer falha (credenciais inválidas, funcionário revogado) retorna um único 401 `invalid_credentials`, sem revelar o motivo. |
| `POST /session/refresh` — renovação de access token | Troca um refresh token válido por um novo access token, emitido com o papel atual do usuário lido do banco. Devolve o **mesmo** refresh token (sem rotação). |
| `DELETE /session` — logout | Logout stateless/no-op: retorna 204 e o cliente descarta os tokens. Não há revogação real — o `jti` nunca é persistido e os tokens emitidos continuam válidos até expirarem. |
| `POST /tourists` — cadastro de turista | Cria conta de turista (201). Exige CPF **ou** passaporte (422 `document_required`); PII (telefone, CPF, passaporte) criptografado com Fernet. Unicidade de email e de documento garantidas por hash HMAC-SHA256 do documento (CPF e passaporte no mesmo espaço de hash); email ou documento repetido → 409 `duplicate_identity`. |
| `GET /me` — perfil do usuário autenticado | Retorna o perfil do usuário logado como `MeResponse` (dados pessoais, papel, interesses relevantes). |
| `PATCH /me` — atualização do próprio perfil | Atualiza campos permitidos do perfil do usuário autenticado (`name`, `surname`, `phone`). |
| `PUT /me/interests` — substitui interesses | Substitui integralmente os interesses do turista a partir de `category_ids` (delete-then-insert). Constraint `uq_user_category` garante ausência de duplicados. |
| `GET /me/interests` — lê interesses | Retorna os `category_ids` atualmente associados ao usuário autenticado. |
| `GET /employees` — lista funcionários (admin) | Lista os funcionários cadastrados. Requer papel `admin` (RBAC via `require_role`). |
| `POST /employees` — cria funcionário (admin) | Cria uma conta de funcionário (201). Email repetido → 409 `duplicate_email`. Ação auditada em banco (`AuditLog` gravado na mesma transação). Requer papel `admin`. |
| `PATCH /employees/{employee_id}` — atualiza funcionário (admin) | Atualiza dados de um funcionário. Ação auditada em banco na mesma transação. Requer papel `admin`. |
| `DELETE /employees/{employee_id}` — revogação lógica (admin) | Não apaga a linha: marca `is_active=False` (revogação lógica). O login passa a falhar, mas tokens já emitidos continuam válidos até expirar. Ação auditada. 204 em caso de sucesso. Requer papel `admin`. |
| `GET /internal/users/{user_id}` — snapshot de usuário | Endpoint entre serviços: devolve `{id, country_of_origin, role}` **sem PII** (RNF08). Sem autenticação no código — a proteção é a ausência de rota para `/internal/*` no Kong (404 na borda). |