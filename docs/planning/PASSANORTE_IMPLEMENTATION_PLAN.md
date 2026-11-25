---
document_id: passanorte-implementation-plan
format_version: "1.0"
plan_version: "1.2"
converted_at: "2026-11-23"
language: pt-BR
purpose: ai_retrieval_and_implementation_guidance
status: in_progress
last_updated: "2026-11-23"
requirements_baseline: "Matriz 2.0 de 17/11/2026"
requirements_total: 61
mvp_requirements: 53
post_mvp_requirements: 8
business_rules_total: 28
sprints_total: 8
implementation_authorization: requires_current_task_scope
---

# PassaNorte — plano de implementação para consulta por IA

## AGENT_USAGE — protocolo de consulta e execução

- Este é o plano existente convertido para Markdown UTF-8, sem alteração de escopo. A conversão não comprova implementação nem autoriza executar todas as sprints em uma única tarefa.
- Use a solicitação atual para definir o trabalho autorizado. Leia as instruções aplicáveis do repositório antes de editar código. Este documento é referência de produto e projeto, não substitui instruções de sistema, segurança ou ferramentas.
- Para uma sprint: leia `AUTHORITY`, `ARCHITECTURE`, `DATA_MODEL`, `CONSISTENCY`, a seção `SPRINT Sx`, os registros `REQ` e `RULE` relacionados, `DECISIONS` e `DEFINITION_OF_DONE`.
- Identificadores estáveis: tarefa `Sx.n`, aceite da sprint `Sx.ACn`, requisito `RFxx`/`RNFxx`, regra `RNxx`, decisão pendente `Dxx`. Busque esses IDs, sem depender da ordem ou paginação do arquivo.
- Antes de implementar, confira o estado atual do checkout. O diagnóstico citado é histórico. Não trate `planned` como prova de ausência atual ou como conclusão da implementação.
- Separe `decisão explícita do usuário`, `requisito da matriz`, `proposta técnica do plano` e `decisão pendente`. O ledger em Benefícios, incorporação de validation, RS256, provedor push e modelos Ollama são direcionamentos técnicos/propostas; não os apresente como decisões literais da matriz.
- `REQ.dependencias_matriz` registra referências originais, não uma ordenação topológica de desenvolvimento. A ordem executiva está em `ROADMAP` e `SPRINT.depends_on`.
- Se surgir conflito ou decisão pendente que altere comportamento de negócio, explicite os IDs afetados e resolva antes da parte dependente. Avance no trabalho independente já autorizado.
- Ao concluir uma tarefa, registre commit/arquivos, testes executados, resultado, limitações e evidência de aceite. Não marque sprint/requisito aceito apenas por existir endpoint, teste unitário ou percentual de cobertura.
- Atualize status apenas com evidência verificada. Preserve os critérios originais e registre mudanças aprovadas com versão, data, motivo e impacto. Não promova requisito pós-MVP sem autorização.
- Uma implementação de backend não comprova os aceites dependentes de React, Android, dispositivo push, infraestrutura real ou teste com usuários.

## RETRIEVAL_INDEX — mapa de consulta

- `AUTHORITY`: fonte da verdade, alterações explícitas e escopo.
- `ROADMAP`: ordem, marcos e papéis de execução.
- `ARCHITECTURE`: serviços, schemas e propostas de ownership.
- `DATA_MODEL`: entidades, atributos, permissões e migrations.
- `CONSISTENCY`: transações, eventos, outbox/inbox e migração do legado.
- `SPRINT S1` a `SPRINT S8`: tarefas, dependências e aceites identificáveis.
- `API_RBAC`: capacidades, personas e contratos propostos.
- `DEFINITION_OF_DONE`: gates comuns e releases M1/M2/M3.
- `DECISIONS`: pendências D01–D10 e momento de resolução.
- `REQ RFxx` e `REQ RNFxx`: catálogo completo com escopo, origem, dependências e aceite.
- `RULE RNxx`: todas as regras, sua origem e sprint.
- `POST_MVP`: backlog sem promoção indevida de escopo.
- `PROVENANCE`: origem, limites do diagnóstico e referências técnicas.

## AUTHORITY

**Objetivo:** adaptar o passanorte-backend existente para entregar o MVP da matriz 2.0, preservando componentes úteis e substituindo o modelo de brindes pelo fluxo de guaranás e cupons. Este documento orienta implementação, revisão e aceite; não declara as tarefas concluídas.

**Ordem de precedência:** decisões explícitas deste planejamento → matriz de rastreabilidade 2.0 de 17/11/2026, incluindo regras e cadastros → decisões técnicas registradas neste plano → código e documentação anteriores. O código deve mudar quando divergir da matriz. A matriz permanece a fonte principal dos requisitos; as alterações de escopo abaixo devem ser incorporadas à sua próxima revisão.

- **Microsserviços distribuídos e modulares**
  - Consequência no projeto: Cada domínio tem aplicação, container, contrato, credencial e migrations próprios. Comunicação em rede por API e RabbitMQ. O banco compartilhado não autoriza acesso irrestrito entre domínios.
- **RBAC com Administrador, Fornecedor e Turista**
  - Consequência no projeto: Roles técnicas admin, supplier e tourist. employee deixa de existir no contrato, nos tokens, no código ativo e na documentação.
- **Sem brinde físico**
  - Consequência no projeto: Remover Prize, estoque de brindes e emissão de código por conclusão. Conclusão gera guaranás; código nasce do resgate de cupom.
- **Chatbot por último**
  - Consequência no projeto: Só iniciar sua implementação após aceite do sistema principal, incluindo notificações. RF40–RF42 continuam no MVP final.
- **Notificações no MVP**
  - Consequência no projeto: RF39 passa de Pós-MVP para MVP. RabbitMQ permanece como barramento; entrega push ao dispositivo integra o aceite, não apenas uma inbox.
- **Um database com schemas e ownership**
  - Consequência no projeto: Database lógico passanorte. Schemas e usuários por domínio, com privilégios mínimos e separação entre migração e execução.

Escopo resultante: **36 RF e 17 RNF no MVP, total de 53 requisitos**. Permanecem no pós-MVP 7 RF e 1 RNF. As 28 regras continuam rastreadas. As propostas já assinaladas na matriz não são promovidas silenciosamente a decisões da equipe: a seção de decisões pendentes indica como encerrá-las antes da implementação dependente.

A mudança de escopo não autoriza reescrita integral. Reaproveitar FastAPI/Pydantic, organização api/core/models/schemas, SQLAlchemy/Alembic, tratamento de erros, observabilidade e testes úteis. Acrescentar camada de casos de uso para transações; evitar regra de negócio extensa nos routers.

## ROADMAP

A sequência contém oito sprints, agrupadas nas três etapas solicitadas. A sprint é uma unidade de entrega verificável, sem prazo calendário imposto. Sugestão inicial de cadência: uma a duas semanas, recalibrada após S1 conforme equipe, capacidade e tamanho das histórias. Dividir uma sprint se necessário, preservando dependências e critérios de saída.

- **1 Correção**
  - Sprints: S1 e S2
  - Marco de saída: M1 Base reproduzível, segura, documentada e migrável com banco único.
- **2 Serviços e adequações**
  - Sprints: S3 a S6
  - Marco de saída: M2 Sistema principal homologado, incluindo guaranás, cupons, notificações, painel e app. Ainda não é aceite integral do MVP.
- **3 Chatbot**
  - Sprints: S7 e S8
  - Marco de saída: M3 MVP completo com RAG e Ollama, depois da aprovação de M2.

Dependência principal: S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8. O trabalho atual prioriza backend e infraestrutura. Os aceites dessa etapa usam evidências de API e serviços integrados. A implementação, a integração e a homologação de React e Android ficam pendentes no item P4.

- Responsável de produto: esclarecer ambiguidades e aceitar o comportamento por RF/RN. Liderança técnica: arquitetura, contratos, migração e revisão. Backend/infra: implementação e operação. Clientes: React e Android. QA: regressão, concorrência e evidências. Os nomes serão atribuídos no início de cada sprint.
- Cada tarefa deve registrar ID, RF/RNF/RN relacionados, serviço, dependência, responsável, critérios de aceite, teste, migration/rollback quando aplicável e evidência do commit. Estados sugeridos: planejada, em andamento, em revisão, bloqueada e aceita.
- Não marcar requisito como concluído pela existência de rota ou por teste unitário isolado. A rastreabilidade deve apontar implementação, contrato OpenAPI e teste de aceite, incluindo falhas e permissões.
- Versionar este plano e a matriz revisada no repositório durante S1. Criar registros de decisões arquiteturais em docs/architecture e registrar alterações de escopo com versão, motivo, impacto e aceite do responsável de produto. O presente documento é a versão 1.0, com todas as sprints planejadas.

## ARCHITECTURE

Painel React e app Kotlin/Jetpack Compose consomem a API pelo Kong. Serviços publicam e consomem eventos pelo RabbitMQ. PostgreSQL hospeda somente o database passanorte. Ollama entra na etapa 3 em rede interna. Kong deve iniciar e manter login, check-in, resgate e validação operacionais mesmo sem chatbot/Ollama.

- **Identidade / auth**
  - Responsabilidade e ownership: Usuários, perfis, fornecedor→parceiro por ID, interesses, consentimento, sessões e acessos autenticados.
  - Adaptação do código atual: Evoluir auth; eliminar employee e suas permissões antigas.
- **Catálogo / catalog**
  - Responsabilidade e ownership: Categorias, pontos, horários, eventos e definição das rotas, seus pontos, temas e recompensa configurada.
  - Adaptação do código atual: Evoluir catalog e mover o cadastro de rotas de gamification para catalog.
- **Gamificação / gamification**
  - Responsabilidade e ownership: Visitas, inscrições/desistências, progresso derivado, conclusão e apuração das recompensas de visita/rota.
  - Adaptação do código atual: Incorporar validation, reaproveitando Haversine e constraints. validation deixa de ser deploy separado após migração.
- **Benefícios / benefits**
  - Responsabilidade e ownership: Parceiros, cupons, resgates, validações, carteiras e lançamentos de guaranás. Autoridade sobre crédito/débito e saldo.
  - Adaptação do código atual: Novo serviço. Substitui o mecanismo de Prize/Badge/redeem-code de brinde.
- **Analytics / insights**
  - Responsabilidade e ownership: Projeções de cadastro, login, visita, crédito e débito; totais e distribuições por período.
  - Adaptação do código atual: Corrigir eventos incompletos, deduplicação e fórmulas.
- **Notificações / notifications**
  - Responsabilidade e ownership: Preferências de entrega, inbox, dispositivos e entrega push a partir de eventos de domínio.
  - Adaptação do código atual: Preservar serviço e RabbitMQ; completar o push e a sincronização de interesses.
- **Chatbot / chatbot**
  - Responsabilidade e ownership: Conversas, conteúdo indexado, embeddings e recuperação. Geração pelo Ollama privado.
  - Adaptação do código atual: Adequar apenas em S7/S8; retirar stub como comportamento de produção.


### Decisão técnica proposta para guaranás

O lançamento econômico reside em Benefícios, junto ao cupom e ao resgate, para que **débito, disponibilidade e emissão do código sejam uma única transação local**. Gamificação decide quando e quanto recompensar e envia comandos/eventos idempotentes de crédito. Benefícios não recalcula progresso. Essa distribuição refina a coluna “Serviço proposto” da matriz, preservando RF33/RF34, RN03 e RN15. Registrar a decisão em S2 antes de criar as tabelas. Não conceder escrita cruzada entre schemas como atalho.

A incorporação de validation em Gamificação evita separar visita e progresso em dois domínios artificiais; o sistema continua com sete microsserviços de negócio. Se a equipe optar por manter validation separado, deve demonstrar a mesma consistência e registrar a decisão sem mudar os aceites. O plano de referência usa sete serviços, incluindo Benefícios e Notificações.

A biblioteca shared deve conter infraestrutura e contratos técnicos pequenos, não um ORM global que importe todos os modelos de todos os domínios. Cada serviço tem metadata e Alembic próprios; não importa modelos internos de outro serviço. IDs entre domínios são referências validadas por API/evento, sem joins operacionais que burlem o ownership.

## DATA_MODEL


### Isolamento e migrations

- Criar um owner NOLOGIN por schema, um usuário de migration autorizado a assumir o owner e um usuário de runtime com LOGIN e privilégios mínimos. Runtime não é owner, superuser, criador de roles ou de databases; não recebe DDL.
- Revogar CREATE em public e permissões públicas indevidas. Configurar search_path seguro e qualificar schema nos modelos/migrations. Um schema por domínio e tabela alembic_version dentro do schema correspondente. Testar permissões negativas de leitura/escrita/DDL entre usuários.
- Conceder apenas USAGE e operações necessárias nas tabelas do domínio; ledger e audit_logs têm INSERT/SELECT, sem UPDATE/DELETE para runtime. Usar usuário separado para manutenção. Visões de leitura entre domínios somente com contrato, motivo e grant explícitos.
- Cada serviço mantém outbox e inbox no próprio schema, na mesma transação de seus dados. Extensões são provisionadas por conta de implantação; runtime não instala extensões.
- Pooling e engine por processo; sessão por requisição/consumo. Limites de conexões por serviço evitam que um serviço esgote o database compartilhado. Banco único é um ponto comum de falha: prever backup, restauração e limites de recursos.


### Entidades e atributos obrigatórios

- **Turista**
  - Campos e relações essenciais: Nome, sobrenome, e-mail único, telefone com país, CPF válido ou passaporte único cifrado, hash de unicidade normalizado, país, senha em hash, aceite com versão/data/hora. Interesses e idioma preferido opcionais.
- **Usuário do painel**
  - Campos e relações essenciais: Nome, e-mail único, senha em hash, role admin/supplier, ativo. supplier exige partner_id válido. Não há role employee.
- **Parceiro**
  - Campos e relações essenciais: Nome, CNPJ validado e único, contato conforme decisão de obrigatoriedade, ativo. Desativação lógica; vínculos históricos preservados.
- **Categoria e ponto**
  - Campos e relações essenciais: Categorias pré-carregadas. Ponto: nome, descrição, endereço, latitude/longitude válidas, ao menos uma categoria, status e cronograma semanal com intervalos ou 24h. Raio, imagem e duração opcionais. Remoção lógica.
- **Evento**
  - Campos e relações essenciais: Ponto, título, descrição, início obrigatório, fim opcional posterior ao início, preço decimal não negativo. Sem venda de ingresso. Regras de encerramento aplicadas em API e RAG.
- **Rota**
  - Campos e relações essenciais: Nome, descrição, ao menos dois pontos distintos, ao menos uma categoria, recompensa inteira ≥ 0, ativa/inativa e imagem opcional. Sem brinde; ordem de visita livre.
- **Visita e inscrição**
  - Campos e relações essenciais: Visita única por turista/ponto com data/hora, distância e precisão; sem coordenadas do turista. Inscrição única por turista/rota, data, situação em andamento/desistiu/concluída e conclusão.
- **Carteira e lançamento**
  - Campos e relações essenciais: Carteira do turista e saldo conciliável. Lançamento imutável: turista, tipo, valor inteiro, referência e instante; unicidade da origem. Referência de recompensa de rota inclui turista+rota. Débitos referenciam resgate.
- **Cupom e resgate**
  - Campos e relações essenciais: Cupom: parceiro ativo, título, benefício, condições, custo ≥ 1, limite inicial ≥ 1 e ativo. Disponibilidade pode chegar a zero. Resgate único por turista/cupom, código não sequencial único, QR, data, situação, data de uso e validado_por. Guardar condições/custo da emissão para preservar histórico.
- **Acesso e auditoria**
  - Campos e relações essenciais: Login do turista com instante/event_id; auditoria append-only com ator, ação, entidade, antes/depois e instante. Não registrar senha, token ou documento em claro.
- **Notificação e índice RAG**
  - Campos e relações essenciais: Notificação por usuário/evento, situação de entrega/leitura, preferências e dispositivos. Índice com origem, versão, exclusão, metadados, embedding/modelo/dimensão; sem documento/telefone/e-mail do turista.

A tabela resume a aba Cadastros. As validações e relações completas continuam subordinadas à matriz. Campos técnicos adicionais, como event_id, version e idempotency_key, sustentam a confiabilidade sem alterar a regra de negócio.

## CONSISTENCY


### Check-in progresso e crédito

Na transação de Gamificação, gravar a visita única e a intenção persistente de recompensa. Reavaliar inscrições afetadas por essa visita; registrar conclusão única quando todos os pontos válidos tiverem sido visitados. Progresso e concessão são operações distintas. Criação de inscrição também considera visitas anteriores. Remoção/fechamento de ponto exige evento e recálculo das rotas afetadas; GET de progresso não cria recompensa.

Benefícios processa a concessão com chave idempotente de visita ou de turista/rota e confirma o lançamento. O fluxo normal deve retornar o saldo confirmado após o check-in. Em falha de rede entre serviços, retornar operação pendente identificável, nunca sucesso econômico fictício: retry/outbox conclui o mesmo crédito e o cliente acompanha até a confirmação. Formalizar esse contrato de recuperação em S4 e medir convergência. Não conceder duas vezes nem perder o crédito; não exigir que uma transação SQL atravesse duas APIs.


### Resgate e validação

Benefícios bloqueia a carteira e a disponibilidade do cupom em ordem determinística; verifica ativo, saldo, limite e unicidade por turista/cupom. Uma transação grava débito, reduz disponibilidade, gera código/QR e registra resgate, auditoria e outbox. Qualquer falha desfaz tudo. Uma segunda transação de validação altera disponível→utilizado condicionalmente, confirma o parceiro do fornecedor e grava ator/data. Administrador pode validar qualquer parceiro. Reenvio com a mesma chave recupera o resultado original; colisão de regra retorna conflito legível.


### RabbitMQ e contratos

Usar entrega at-least-once, publisher confirms, mensagens persistentes, filas duráveis, retry com atraso, DLQ e reprocessamento auditável. A proteção contra duplicidade está no banco do consumidor, por event_id e chave de negócio. Outbox elimina a janela de perda entre commit e publicação. Não prometer entrega exatamente uma vez pelo broker.

- **tourist.registered e tourist.logged_in**
  - Consumidores e exigências: Analytics; contabilizar apenas turista e o instante original, nunca ingestão/retry.
- **catalog.spot.changed/deleted, event.changed/deleted, route.changed/deleted**
  - Consumidores e exigências: Gamificação, Notificações e, a partir de S7, Chatbot. Carregar ID, versão, campos permitidos e indicação de exclusão.
- **tourist.interests.changed**
  - Consumidores e exigências: Notificações e projeções autorizadas; interesses são as mesmas categorias de pontos/rotas.
- **visit.recorded e route.completed**
  - Consumidores e exigências: Benefícios recebe intenção de crédito idempotente; Analytics recebe dimensão mínima necessária. Nunca incluir GPS do turista.
- **guarana.credited/debited e coupon.redeemed/validated**
  - Consumidores e exigências: Analytics e notificações transacionais se previstas no produto. Deduplicar sem alterar saldo por replay.
- **notification.requested**
  - Consumidores e exigências: Worker de entrega push/inbox. Falha do provider não invalida ação de negócio.

Envelope obrigatório: event_id, event_type, schema_version, occurred_at UTC, correlation_id, producer, aggregate_id/version e payload tipado. Validar compatibilidade produtor/consumidor na CI; dados de país/interesses e coordenadas do ponto precisam de origem real, não somente fixtures preenchidas.


### Transição do legado

- S2 entrega ferramenta repetível de migração dos sete databases para schemas do database único, preservando IDs e timestamps. Executar em cópia, comparar contagens, unicidades e vínculos e testar restauração antes do corte.
- Migração de employee: só converter para supplier quando houver parceiro identificado e validado; contas sem vínculo ficam desativadas até regularização. Revogar sessões antigas. Nenhuma migração deve conceder admin por conveniência.
- Preservar registros históricos de brindes em arquivo/área legada com acesso restrito, fora das APIs ativas. Não converter estoque, insígnia ou código antigo em saldo/cupom sem regra de negócio expressa. Criar relatório de pendências de transição.
- Não recriar guaranás por visitas legadas automaticamente. Decidir política de créditos retroativos e executar, se aprovada, carga idempotente com origem rastreável. Nunca recalcular saldo histórico a partir de prêmio físico.
- No corte, suspender escritas, fazer backup final, migrar/reconciliar, trocar configuração e executar smoke tests. Não apagar bancos antigos nessa etapa. Depois de novas escritas, rollback exige reconciliação/replay; restaurar backup antigo cegamente pode duplicar ou apagar resgates.

## SPRINTS — plano executável

Todos os status abaixo são o estado de planejamento preservado, não o estado comprovado do checkout.

## SPRINT S1 — Build configuração e segurança

- status: implemented_pending_e2e_acceptance
- etapa: Etapa 1 Correção
- depends_on: baseline
- condicao_de_entrada: Entrada: matriz e diagnóstico disponíveis. Não depende de mudança de regra de negócio.
- rastreabilidade: RF01, RF02, RF17; RNF05, RNF06, RNF07, RNF10, RNF17.
- objetivo: Fazer uma cópia limpa construir e iniciar com configuração explícita, credenciais seguras e falhas previsíveis.

### Tarefas

#### TASK S1.1

- status: implemented
- acao: Versionar uv.lock, fixar versões de runtime/imagens de forma reproduzível, corrigir Dockerfile e .dockerignore e retirar uv.lock do ignore. Separar imagem de runtime das ferramentas de desenvolvimento; runtime sem root.

#### TASK S1.2

- status: implemented
- acao: Centralizar Settings tipadas por serviço. Corrigir nomes e injeção das variáveis no Compose, distinguir interpolação de .env e ambiente do container e falhar cedo quando faltar segredo/configuração. Não cair silenciosamente em SQLite ou gerar chave PII efêmera em produção.

#### TASK S1.3

- status: implemented
- acao: Retirar segredos padrão e senha gerada dos logs. Separar chaves JWT, cifra de documento e HMAC de unicidade. Ler segredos por arquivos montados/secret manager; manter .env.example sem valores reais. Definir backup e rotação das chaves de PII, incluindo unicidade após rotação.

#### TASK S1.4

- status: implemented
- acao: Propor RS256: somente Identidade possui chave privada; Kong e serviços verificam com chave pública. Exigir algoritmo permitido, assinatura, exp, sub, iss, aud e tipo de token. Definir kid/identificador de credencial consistente no Kong, rotação com sobreposição e remoção da chave antiga após a janela dos tokens.

#### TASK S1.5

- status: implemented
- acao: Refresh com sessão rastreável, rotação/revogação e rejeição de usuário desativado. Bootstrap admin idempotente com senha fornecida por meio seguro. Corrigir tipagem/lint e limites de senha compatíveis com o hash.

#### TASK S1.6

- status: implemented
- acao: Reescrever README inicial: fonte de verdade, setup, geração de secrets, variáveis por serviço, portas, comandos reais, endpoints, testes, limitações e links. Atualizar a cada sprint, sem anunciar como pronta a funcionalidade futura.

### Critérios de aceite da sprint

- **S1.AC1**: Build limpo usa o lock versionado; ausência de configuração obrigatória encerra o serviço com mensagem sem segredo. Nenhum secret aparece na imagem, Git ou logs.
- **S1.AC2**: Token expirado, adulterado, de tipo/issuer/audience errado ou sem claims obrigatórios é recusado. Rotação mantém tokens autorizados durante a janela definida e rejeita a chave retirada.
- **S1.AC3**: Admin criado uma vez sem sobrescrever; usuário desativado não renova sessão. CI de lint, tipagem, unitários e varredura de segredos passa.

### Evidências de conclusão

Commit do lock/configuração, log sanitizado de build, testes de autenticação/rotação e README executado a partir de checkout limpo.


### Atualiza??o de execu??o ? 2026-11-23

- evidencia: [Registro S1](../implementation/S1.md).
- verificado: 134 testes; lint; mypy; lock; build; migra??es; stack Docker saud?vel.
- pendente: smoke HTTP/Kong e concorr?ncia de refresh em PostgreSQL (execu??o n?o autorizada), inspe??o final do runtime e CI remota.
- aceite: n?o declarar integral enquanto as valida??es pendentes n?o forem executadas. Os crit?rios originais foram preservados.

## SPRINT S2 — Banco único microsserviços Kong e Swagger

- status: planned
- etapa: Etapa 1 Correção
- depends_on: S1
- condicao_de_entrada: Depende de S1. Encerra o marco M1.
- rastreabilidade: RNF01, RNF02, RNF08, RNF10, RNF14, RNF16, RNF17; RN23.
- objetivo: Consolidar a fundação operacional e a migração sem misturar ownership ou bloquear a borda pelo chatbot.

### Tarefas

#### TASK S2.1

- status: planned
- acao: Registrar decisões de limites: sete serviços, incorporação de validation em Gamificação, rotas no Catálogo e ledger econômico em Benefícios. Criar scaffolds faltantes no padrão atual com casos de uso, schemas e metadata próprios.

#### TASK S2.2

- status: planned
- acao: Provisionar database único, schemas, owners, runtime/migrator e grants mínimos. Adaptar SQLAlchemy/Alembic para schemas e version_table_schema; corrigir engine por processo. Criar ensaio de migração e relatórios de reconciliação.

#### TASK S2.3

- status: planned
- acao: Orquestrar Postgres, RabbitMQ, serviços e Kong com health/readiness, restart para permanentes, migrations/seed one-shot, redes e limites. Remover exposição externa de bancos e APIs internas; ferramentas de debug somente em perfil de desenvolvimento.

#### TASK S2.4

- status: planned
- acao: Configurar TLS na borda, CORS explícito, rate limit, timeouts e correlation ID. Manter Kong independente do boot do chatbot. Autenticar chamadas internas e retirar rotas de seed do runtime produtivo.

#### TASK S2.5

- status: planned
- acao: Publicar Swagger por serviço em /docs/{service} e OpenAPI correspondente em ambiente de teste, com servers apontando para a borda. Em produção, restringir documentação administrativa. Ajustar precedência das rotas para /me/balance e /me/coupons não caírem no auth.

#### TASK S2.6

- status: planned
- acao: Implantar outbox/inbox, envelopes versionados, retries/DLQ e auditoria append-only como infraestrutura reutilizável. README completo da etapa 1 inclui diagrama, Compose, Swagger Try it out, migração, backup/restore e troubleshooting.

### Critérios de aceite da sprint

- **S2.AC1**: Com pré-requisitos e secrets provisionados, docker compose up --build aplica migrations e deixa serviços prontos. Reiniciar processo permanente comprova recuperação automática; readiness detecta indisponibilidade relevante.
- **S2.AC2**: Cada runtime consegue operar somente suas tabelas; DDL, leitura/escrita cruzada indevida e edição de audit/ledger são negados em testes SQL.
- **S2.AC3**: Chamadas de smoke test pelo Kong e Swagger funcionam para públicos/autenticados. Rotas internas não são públicas. Chatbot/Ollama desligados não bloqueiam a borda.
- **S2.AC4**: Migração em cópia preserva IDs/contagens/vínculos e restauração ensaiada funciona. Falha do broker entre commit e envio não perde a intenção persistente.

### Evidências de conclusão

Compose validado e executado, relatório de privilégios, OpenAPI por serviço, testes pelo Kong, ensaio de migração/restore e decisão arquitetural versionada.

## SPRINT S3 — Identidade parceiros fornecedores e catálogo

- status: planned
- etapa: Etapa 2 Implementar serviços faltantes
- depends_on: S2
- condicao_de_entrada: Depende de S2. Parceiro deve existir antes de ativar fornecedor ou criar cupom.
- rastreabilidade: RF01–RF08, RF16–RF18, RF22–RF24; RNF03–RNF07, RNF13–RNF16; RN18–RN20, RN22, RN24, RN26.
- objetivo: Adequar personas, cadastros e descoberta à matriz e eliminar o contrato employee.

### Tarefas

#### TASK S3.1

- status: planned
- acao: Implementar parceiro com CNPJ validado/normalizado/único e desativação lógica. Adaptar usuários do painel para admin/supplier, parceiro obrigatório de supplier e gestão por admin. Regra de vínculo é verificada no servidor.

#### TASK S3.2

- status: planned
- acao: Migrar contas employee com relatório das sem parceiro; invalidar tokens antigos. Remover role e endpoints legados do contrato ativo. Preservar histórico de validações e identidade dos atores.

#### TASK S3.3

- status: planned
- acao: Completar turista: CPF com verificadores, documento normalizado/cifrado/hash, e-mail/documento únicos, país/telefone, aceite versionado e interesses múltiplos validados contra categorias. Registrar login de turista como evento durável distinto de acesso ao catálogo.

#### TASK S3.4

- status: planned
- acao: Completar pontos: endereço, categoria mínima, imagem/duração opcionais, raio configurável, status e remoção lógica. Agenda tipada aceita múltiplos intervalos/24h, com PUT idempotente. Fuso via configuração, padrão America/Manaus.

#### TASK S3.5

- status: planned
- acao: Completar eventos com início/fim/preço; ocultar encerrados conforme decisão registrada. Emissão de eventos cobre criação, alteração, status, agenda e exclusão. Seed de categorias usa lista oficial idempotente; gestão livre de categorias não é requisito MVP.

#### TASK S3.6

- status: planned
- acao: Implementar relevância por interesses e proximidade e fallback por nome, ocultar permanentemente fechados, expor dados completos e link Maps. A atualização das telas está pendente em P4.

### Critérios de aceite da sprint

- **S3.AC1**: Admin acessa todas as funções administrativas; supplier não acessa CRUD/dashboard e não é salvo sem parceiro. tourist não acessa painel. API aplica 401/403 independentemente dos menus.
- **S3.AC2**: CPF inválido, duplicidade normalizada ou ausência de aceite são recusados. Documento/senha não aparecem em respostas ou logs.
- **S3.AC3**: Ponto sem categoria/coordenada válida não é salvo; agenda reenviada mantém sucesso; eventos encerrados não aparecem. Interesses/proximidade/fallback têm testes de ordenação.
- **S3.AC4**: Testes de API comprovam os fluxos de cadastro, login e descoberta e a gestão administrativa de usuários, parceiros, pontos e eventos. A validação ponta a ponta no Android e no React está no item P4.

### Evidências de conclusão

Testes RBAC e validações, migrations de personas, contrato de catálogo e testes de ordenação e de fluxo pela API.

## SPRINT S4 — Rotas check-in progresso e guaranás

- status: planned
- etapa: Etapa 2 Implementar serviços faltantes
- depends_on: S3
- condicao_de_entrada: Depende de S3. Ledger e carteira ficam prontos antes do resgate de S5.
- rastreabilidade: RF09, RF25, RF28–RF34; RNF07–RNF09, RNF14, RNF16, RNF17; RN01–RN12, RN20, RN27, RN28.
- objetivo: Entregar o passaporte e as recompensas virtuais com idempotência e histórico econômico.

### Tarefas

#### TASK S4.1

- status: planned
- acao: Mover definição de rotas para Catálogo: pontos distintos ≥ 2, temas ≥ 1, recompensa ≥ 0 e ativa/inativa. Criar GET de detalhe. Remover dependência de Prize/Badge e não emitir código na conclusão.

#### TASK S4.2

- status: planned
- acao: Implementar inscrição, desistência e reinscrição. Histórico anterior conta, visita serve para todas as rotas e progresso é a interseção com pontos válidos. Excluir removidos/permanentemente fechados do cálculo e descartar progresso de rota removida sem apagar créditos.

#### TASK S4.3

- status: planned
- acao: Check-in recebe lat/lon/precisão, valida faixa, ponto aberto e Haversine contra limiar definido. Persistir apenas resultado, distância e precisão. Índice único turista/ponto com tratamento de colisões retorna já visitado sem efeito duplicado.

#### TASK S4.4

- status: planned
- acao: Registrar conclusão única por turista/rota em comando de domínio, acionado por visita, inscrição e alteração relevante do catálogo. GET não altera dados. Separar conclusão de concessão econômica.

#### TASK S4.5

- status: planned
- acao: Implementar carteira e ledger em Benefícios: 1 guaraná por visita por padrão configurável, recompensa de rota configurada, referência única e saldo conciliável. Crédito por origem somente de produtor autenticado; turista não escolhe valor. Lançamentos são imutáveis.

#### TASK S4.6

- status: planned
- acao: Garantir outbox, retry e confirmação do crédito no fluxo de check-in; expor pela API saldo, progresso, visitas e estado da operação. As telas de progresso e gestão de rotas estão pendentes em P4.

### Critérios de aceite da sprint

- **S4.AC1**: Vinte check-ins simultâneos no mesmo ponto produzem uma visita e um crédito; reenvio após falha de rede não duplica nem perde crédito.
- **S4.AC2**: Visita anterior conta na inscrição; uma visita atualiza duas rotas. Desistir/reinscrever não repete recompensa. Fechamento/remoção recalcula progresso segundo regra aprovada.
- **S4.AC3**: Ponto fechado e fora do raio são recusados; GPS bruto não fica no banco/log. Remover rota/ponto não reduz saldo já creditado.
- **S4.AC4**: Saldo coincide com lançamentos; conclusão e crédito permanecem separados e auditáveis. Nenhum fluxo ativo exige brinde físico.

### Evidências de conclusão

Testes de domínio/concorrência em PostgreSQL, falhas do broker/retry, conciliação do ledger, contratos e jornada check-in→saldo.

## SPRINT S5 — Cupons resgate e validação por parceiro

- status: planned
- etapa: Etapa 2 Implementar serviços faltantes
- depends_on: S4
- condicao_de_entrada: Depende de S4 e do vínculo fornecedor→parceiro de S3.
- rastreabilidade: RF10, RF11, RF34, RF36–RF38; RNF03, RNF05, RNF08, RNF16, RNF17; RN13–RN19, RN27.
- objetivo: Permitir a troca atômica de guaranás por cupom e sua validação segura no painel.

### Tarefas

#### TASK S5.1

- status: planned
- acao: Implementar CRUD/desativação de cupons: parceiro ativo, CNPJ associado, título, benefício, condições, custo inteiro ≥ 1 e disponibilidade inicial ≥ 1. Preservar custo/condições dos já emitidos ao editar o catálogo.

#### TASK S5.2

- status: planned
- acao: Implementar catálogo para turista e meus cupons, indicando já resgatado, disponibilidade, QR/código textual, situação e data de uso. Cupom inativo/esgotado não pode ser resgatado.

#### TASK S5.3

- status: planned
- acao: Implementar resgate transacional com bloqueios, unique(turista,cupom), código aleatório verificável e chave de idempotência. Débito, limite, código, auditoria e outbox confirmam juntos; falha não produz efeito parcial.

#### TASK S5.4

- status: planned
- acao: Validação exige admin ou supplier do parceiro. Consultar vínculo vigente, não confiar em partner_id fornecido pelo cliente. Garantir transição única para utilizado e registrar ator/data. Código inválido, utilizado ou de outro parceiro recebe motivo adequado.

#### TASK S5.5

- status: planned
- acao: Remover /prizes e contratos de brindes, com migração e aviso de mudança de contrato. As telas de validação web e cupons no app estão pendentes em P4.

### Critérios de aceite da sprint

- **S5.AC1**: Vinte requisições para última unidade dão um sucesso, um débito e um código; saldo e disponibilidade nunca negativos.
- **S5.AC2**: Saldo insuficiente, resgate duplicado ou cupom inativo falham sem débito. Retry da mesma operação recupera resultado sem novo efeito.
- **S5.AC3**: Duas validações concorrentes dão um uso registrado; supplier de outro parceiro recebe recusa; admin valida qualquer parceiro.
- **S5.AC4**: Teste integrado pelo Kong comprova check-in→guaranás→resgate→uso. O aceite de câmera/QR e digitação nos clientes está em P4.

### Evidências de conclusão

Relatório de concorrência PostgreSQL, trilha de auditoria protegida, testes negativos RBAC e jornada integrada pelo Kong.

## SPRINT S6 — Notificações analytics e aceite do sistema principal

- status: planned
- etapa: Etapa 2 Implementar serviços faltantes
- depends_on: S5
- condicao_de_entrada: Depende de S5. M2 é pré-condição para iniciar o chatbot.
- rastreabilidade: RF12–RF15, RF17, RF18, RF39 promovido ao MVP; RNF03, RNF04, RNF08–RNF10, RNF12–RNF17; RN20, RN24–RN26.
- objetivo: Fechar as lacunas do sistema principal e comprovar operação integrada antes de investir no chatbot.

### Tarefas

#### TASK S6.1

- status: planned
- acao: Preservar RabbitMQ e completar notificações por novos pontos, rotas e eventos de interesse. Sincronizar seleção de interesses, opt-out e tokens de dispositivo. Implementar inbox e adaptador push Android; definir provedor compatível com baixo custo, como FCM, sem tratá-lo como substituto do broker.

#### TASK S6.2

- status: planned
- acao: Worker consome fila, persiste entrega e deduplica usuário/evento; retry/backoff, token inválido, DLQ e reprocessamento observáveis. Tolerar duplicata de push no cliente pelo ID da notificação; não prometer exactly-once do provedor externo.

#### TASK S6.3

- status: planned
- acao: Corrigir fatos analíticos: cadastros, logins somente de turistas, visitas, créditos e débitos com instante original. Enriquecer país/interesses e coordenadas do ponto por contratos permitidos; nunca usar coordenadas contínuas do turista.

#### TASK S6.4

- status: planned
- acao: Dashboard com período configurável, totais conciliados, ranking com desempate estável, heatmap OSM/Leaflet e distribuições de turistas distintos. País soma 100%; múltiplos interesses podem somar mais de 100%. Retirar contagem de listagem como login.

#### TASK S6.5

- status: planned
- acao: Verificar JWT/RBAC pela API e a inicialização integrada dos serviços de backend pelo Compose. A integração do painel ao Compose e a homologação dos clientes estão pendentes em P4.

#### TASK S6.6

- status: planned
- acao: Executar carga, falhas, backup/restore e auditoria; medir p95 de consultas com 50 usuários simultâneos. Reconciliar todos os RF/RNF do núcleo, atualizar README e registrar aceite M2.

### Critérios de aceite da sprint

- **S6.AC1**: Só interessados habilitados recebem push de conteúdo novo; opt-out é respeitado. Queda do broker/provider não perde a intenção, nem cria duplicidade de inbox.
- **S6.AC2**: Totais por período conferem com origem; reprocessar eventos não altera totais. Heatmap tem coordenadas dos pontos e distribuição usa turistas, não número de visitas.
- **S6.AC3**: Meta inicial p95 ≤ 500 ms para consultas simples com 50 usuários simultâneos; relatório descreve ambiente/dados. O teste com usuários está em P4.
- **S6.AC4**: Sistema principal roda com um comando após preparação documentada; chatbot desligado não afeta jornadas. Todos os aceites M2 têm evidência, sem defeito crítico/alto pendente.

### Evidências de conclusão

Evidência de processamento e envio pelo provedor push, conciliação analytics, teste de carga e relatório de homologação do backend M2. A confirmação em aparelho está em P4.

## SPRINT S7 — Base de conhecimento e recuperação RAG

- status: planned
- etapa: Etapa 3 Chatbot
- depends_on: S6
- condicao_de_entrada: Depende do aceite de M2 em S6. Nenhuma implementação de geração precede esse marco.
- rastreabilidade: RF40, RF42; RNF01, RNF07, RNF09, RNF15, RNF17, RNF18; RN21.
- objetivo: Disponibilizar uma base atualizada e uma recuperação verificável antes da geração de respostas.

### Tarefas

#### TASK S7.1

- status: planned
- acao: Preparar Ollama interno com volume de modelos, limites e healthcheck independente. Selecionar modelo de embeddings aberto/multilíngue de baixo porte; candidato inicial qwen3-embedding:0.6b. Fixar licença, versão/digest e dimensão observada.

#### TASK S7.2

- status: planned
- acao: Usar pgvector no schema chatbot e recuperação no banco, com índice apropriado ao volume. Declarar pacote/extensão/modelo e impedir fallback silencioso para stub ou dimensão incompatível. Separar embedder do modelo gerador.

#### TASK S7.3

- status: planned
- acao: Indexar somente catálogo autorizado: texto, localização do ponto, categorias, status, horários, eventos/datas/preços, IDs e versões. Fazer carga inicial e consumo incremental de criação/edição/status/agenda/exclusão com tombstones e ordenação por versão.

#### TASK S7.4

- status: planned
- acao: Garantir retry/DLQ e reconciliação periódica completa. Trocar modelo/dimensão exige reindexação versionada e corte controlado, não misturar vetores no mesmo índice.

#### TASK S7.5

- status: planned
- acao: Construir conjunto de perguntas pt-BR/en, sem resposta, desatualização e remoção. Validar recuperação e referências. Filtrar disponibilidade/encerramento por regras e revalidar itens atuais antes de responder.

### Critérios de aceite da sprint

- **S7.AC1**: Alterações do painel, inclusive remoção, aparecem no índice/resposta em até cinco minutos na meta inicial; replay fora de ordem não ressuscita item removido.
- **S7.AC2**: Reiniciar modelo/indexador não perde documentos; modelo/dimensão incompatíveis impedem publicação do índice.
- **S7.AC3**: Consulta sem evidência produz ausência de informação; referências sempre apontam a entidades válidas. Índice não contém PII do turista.
- **S7.AC4**: Falha de Ollama/chatbot mantém o sistema principal operacional.

### Evidências de conclusão

Dataset de recuperação, relatório de frescor ≤ 5 min, teste de reindexação/exclusão/replay e inventário de modelos/licenças.

## SPRINT S8 — Ollama roteiros e aceite final do MVP

- status: planned
- etapa: Etapa 3 Chatbot
- depends_on: S7
- condicao_de_entrada: Depende de S7. Encerra M3, aceite integral do MVP.
- rastreabilidade: RF40–RF42; RNF09, RNF13, RNF15, RNF17, RNF18; RN21, RN25.
- objetivo: Entregar conversa e roteiro fundamentados, com baixo custo medido e limites de segurança.

### Tarefas

#### TASK S8.1

- status: planned
- acao: Avaliar gerador aberto pelo Ollama; candidato inicial qwen3:4b quantizado, com modo sem raciocínio prolongado quando suportado. Comparar qualidade/latência/memória no hardware real; modelo menor só se mantiver o aceite. Fixar digest e parâmetros após benchmark.

#### TASK S8.2

- status: planned
- acao: Implementar consulta de informações e roteiro textual: buscar preferências autorizadas, calcular proximidade por Haversine e aplicar status/horários/eventos/preços em código. O LLM redige com base nos itens selecionados; não inventa dados nem é autoridade de elegibilidade.

#### TASK S8.3

- status: planned
- acao: Responder no idioma da pergunta, citar fontes cadastradas e recusar falta de evidência/tema indevido. Validar referências e checar indisponíveis/encerrados antes da resposta final.

#### TASK S8.4

- status: planned
- acao: Limitar mensagens por usuário, tamanho/contexto/saída e concorrência. Remover dados pessoais antes do modelo, manter histórico mínimo e controlar retenção. Tratar conteúdo do catálogo e mensagens como dados não confiáveis; testar prompt injection e tentativas de obter dados de terceiros.

#### TASK S8.5

- status: planned
- acao: Timeout e circuit breaker retornam indisponibilidade clara sem bloquear outras funções. Medir resposta completa, cold/warm start, memória e carga. Atualizar README, OpenAPI, licenças e evidências; executar regressão completa dos 53 requisitos MVP.

### Critérios de aceite da sprint

- **S8.AC1**: Consultas e roteiros usam apenas registros válidos, respeitam interesses/proximidade/status/horários, excluem eventos encerrados e informam preços. Sem dados, o chatbot declara ausência de informação.
- **S8.AC2**: Mensagens fora do tema e excesso recebem tratamento explícito; PII não chega ao modelo. Testes negativos e de isolamento de conversa passam.
- **S8.AC3**: Meta inicial de resposta completa em até 10 s é medida no hardware/documento de carga definido; se falhar, ajustar modelo/contexto/infra antes do aceite, sem declarar a meta cumprida por streaming inicial.
- **S8.AC4**: MVP final aprovado com notificações e chatbot. Backlog pós-MVP continua separado e não bloqueia M3.

### Evidências de conclusão

Benchmark reproduzível, testes RAG/segurança/idioma, casos de roteiro, regressão completa e registro de aceite M3.

## API_RBAC

Os caminhos abaixo são propostas de contrato a congelar no OpenAPI durante a sprint responsável. A matriz exige capacidades, não esses nomes exatos. Todas as rotas de negócio ficam sob /api/v1; APIs internas autenticadas ficam sem rota pública no Kong.

- **/session, /session/refresh, /tourists**
  - Serviço: auth
  - Permissão de negócio: Login/refresh/cadastro públicos com validação e rate limit.
- **/panel-users, /panel-users/{id}**
  - Serviço: auth
  - Permissão de negócio: Administrador gerencia administradores e fornecedores.
- **/me, /me/interests**
  - Serviço: auth
  - Permissão de negócio: Autenticado, limitado aos próprios dados e capacidades do seu papel.
- **/partners**
  - Serviço: benefits
  - Permissão de negócio: Administrador. Fornecedor não tem CRUD de parceiro.
- **/tourist-spots, /events, /categories, /routes**
  - Serviço: catalog
  - Permissão de negócio: Leitura conforme contrato; escrita somente Administrador. Categorias pré-carregadas no MVP.
- **/visits, /routes/{id}/enrollments, /enrollments**
  - Serviço: gamification
  - Permissão de negócio: Turista registra própria visita e administra próprias inscrições.
- **/me/balance**
  - Serviço: benefits
  - Permissão de negócio: Turista consulta o próprio saldo. Créditos só por chamadas/eventos internos autorizados.
- **/coupons, /coupons/{id}/redemptions, /me/coupons**
  - Serviço: benefits
  - Permissão de negócio: Admin gere catálogo; turista consulta e resgata para si.
- **/coupon-validations**
  - Serviço: benefits
  - Permissão de negócio: Admin para todos os parceiros; supplier somente parceiro vinculado.
- **/dashboard/***
  - Serviço: insights
  - Permissão de negócio: Administrador.
- **/notification-preferences, /devices, /notifications**
  - Serviço: notifications
  - Permissão de negócio: Turista gere suas preferências/dispositivos e consulta suas notificações.
- **/conversations e /conversations/{id}/messages**
  - Serviço: chatbot
  - Permissão de negócio: Turista autenticado e proprietário da conversa, com limite por usuário.

Administrador tem todas as features do painel, inclusive validação de cupons; isso não exige simular ações privadas de um turista. Fornecedor tem somente a validação como função de negócio do painel, além do acesso necessário à própria sessão. Não aceitar employee como alias transitório em produção. Autorizações verificam papel, propriedade e parceiro no serviço, mesmo com JWT validado pelo Kong.

Swagger descreve modelos Pydantic completos, exemplos, erros, status e segurança por operação. Público é marcado como público. Try it out deve atravessar o mesmo Kong que os clientes; documentar obtenção do token e servidor por ambiente. Não publicar endpoints internos nem chaves na documentação externa.

## DEFINITION_OF_DONE

- Requisito, regra e aceite vinculados à tarefa; código revisado; lint/tipagem e testes relevantes passam. READMEs e OpenAPI refletem o comportamento entregue, sem referências normativas antigas.
- Testes unitários para domínio; integração com PostgreSQL real para constraints/locks; contratos entre serviços; jornadas pelo Kong; RabbitMQ real para falhas/replay; teste de cliente quando o aceite depende da UI.
- Operações críticas comprovam concorrência, idempotência, ausência de saldo/limite negativos e recuperação após timeout. Mensagens não publicadas são recuperadas pela outbox. Nenhum requisito é aprovado apenas pelo percentual de cobertura.
- Migration aplicada em banco vazio e cópia do legado, com integridade verificada e procedimento de recuperação. Nenhuma exclusão destrutiva automática de dado legado sem inventário e política aprovada.
- Privilégios do banco, API e tokens testados negativamente. Secrets ausentes/padrão impedem deploy. Auditoria não é alterável pelo runtime; logs não contêm credenciais, documento ou GPS do turista.
- Health/readiness, métricas e logs têm correlation_id. Monitorar erro/latência por serviço, backlog de outbox/filas/DLQ, atraso de projeções, falhas push e frescor do RAG.
- M1 exige infraestrutura real e ensaio de migração; M2 exige jornada sem chatbot incluindo notificações; M3 exige todos os requisitos MVP. Pendência crítica/alta impede release. Responsável de produto registra aceite, evidências e eventuais exceções de escopo formalizadas.

Os 106 testes/81% de cobertura do diagnóstico são uma referência histórica, não o critério de conclusão deste plano. A suíte precisa ser reescrita onde perpetua brindes, employee, coordenadas persistidas ou fatos analíticos artificialmente completos.

## DECISIONS

Estas decisões não impedem planejar o projeto. Devem ser fechadas pelo responsável de produto e pela liderança técnica no prazo indicado, antes de codificar o comportamento dependente. Nenhuma delas autoriza ignorar requisito explícito.

- **D01**
  - Tema: Raio e tolerância do check-in
  - Decisão a registrar: RF30 fala em raio mais tolerância; Cadastros trata o raio como limiar. Proposta: documentar raio base e tolerância separadamente, fallback global/override por ponto e limite efetivo explícito. Precisão não deve inflar o limite sem regra antifraude.
  - Momento: Antes de S4
- **D02**
  - Tema: Eventos sem data de fim
  - Decisão a registrar: Definir quando encerram para listagem e RAG. Proposta: considerar encerrado no final do dia local do início quando fim ausente.
  - Momento: Antes de S3
- **D03**
  - Tema: Rota sem pontos válidos e alterações
  - Decisão a registrar: Definir caso de todos os pontos removidos/fechados, alteração de recompensa/pontos e créditos retroativos. Proposta: zero pontos não gera conclusão automática; manter snapshot do valor concedido e nunca repetir crédito.
  - Momento: Antes de S4
- **D04**
  - Tema: Desativação de parceiro e cupom já resgatado
  - Decisão a registrar: Matriz bloqueia novo cupom para parceiro inativo, mas não define uso de cupom já emitido. Proposta: preservar direito emitido e permitir validação administrativa; bloquear emissão nova. Decidir fornecedor inativo e uso após desativação do cupom.
  - Momento: Antes de S5
- **D05**
  - Tema: Contato do parceiro
  - Decisão a registrar: RF05 menciona contato; Cadastros o marca opcional. Proposta: opcional, com validação quando informado.
  - Momento: Antes de S3
- **D06**
  - Tema: Propostas da matriz
  - Decisão a registrar: Registrar aceite de RN08, RN11, RN12, RN26, RN27 e RN28. Plano usa seu comportamento esperado sem reclassificar origem: aberto no check-in, progresso derivado, crédito único, fuso configurável, guaranás sem expiração/transferência/valor monetário e sem GPS persistido.
  - Momento: Na abertura das sprints afetadas
- **D07**
  - Tema: Push e dispositivos
  - Decisão a registrar: Escolher adaptador Android de baixo custo, credenciais, retenção de tokens e estratégia de retry. RabbitMQ continua obrigatório. FCM é candidato, não componente já instalado nem garantia permanente de preço.
  - Momento: Antes de S6
- **D08**
  - Tema: Hardware e metas do LLM
  - Decisão a registrar: Definir CPU/GPU/RAM disponíveis, volume e perguntas de avaliação. Validar modelo/digest/licença e metas de 10 s/5 min no ambiente real. Não prometer desempenho por tamanho do arquivo.
  - Momento: Antes de S7
- **D09**
  - Tema: Dados existentes e corte
  - Decisão a registrar: Inventariar se há usuários/visitas reais, resolver suppliers sem parceiro e política de saldos retroativos. Planejar janela e recuperação conforme dados reais.
  - Momento: S2, antes de qualquer corte
- **D10**
  - Tema: Prazo de convergência entre serviços
  - Decisão a registrar: Confirmar contrato de operação pendente em falha de crédito e atraso máximo de progresso/saldo. Não relaxar unicidade nem atomicidade do resgate. Registrar timeout e experiência do app.
  - Momento: Antes do aceite de S4

Principais riscos: migração de identidades e dados antigos; fronteira entre progresso e crédito; provisão de push e aparelhos para teste; capacidade do hardware de inferência; e dependências dos repositórios React/Android. Mitigar com ensaio de migração em S2, teste de falhas em S4/S5, decisão de push antes de S6 e benchmark antes de fixar o LLM. Não alocar o chatbot antes de M2 para compensar atraso no núcleo.

## REQUIREMENTS — catálogo integral

Campos da matriz mantêm sua origem. `escopo_plano` contém a promoção aprovada de RF39. `servico_proposto_matriz` não substitui a decisão de arquitetura descrita em `ARCHITECTURE`.

### REQ RF01 — Provisionamento do primeiro administrador

- status: planned
- escopo_plano: MVP
- sprints: S1/S3
- entrega_planejada: Bootstrap seguro e idempotente
- escopo_matriz: MVP
- id_anterior: RF01
- persona_matriz: Administrador
- modulo: Autenticação e Acesso
- servico_proposto_matriz: Identidade
- objetivo_matriz: O6
- complexidade_matriz: Baixa
- dependencias_matriz: —
- regras_relacionadas: RN19

**Descrição original:** Script executado na implantação que cria o primeiro administrador do painel. Os demais usuários do painel são cadastrados pelo próprio painel (RF04).

**Critério de aceite original:** Executar o script cria o administrador com senha em hash; executar de novo não duplica nem sobrescreve.

### REQ RF02 — Login no painel

- status: planned
- escopo_plano: MVP
- sprints: S1/S3
- entrega_planejada: Login de painel e usuário ativo
- escopo_matriz: MVP
- id_anterior: RF02
- persona_matriz: Administrador / Fornecedor
- modulo: Autenticação e Acesso
- servico_proposto_matriz: Identidade
- objetivo_matriz: O6
- complexidade_matriz: Baixa
- dependencias_matriz: RF01, RNF05
- regras_relacionadas: RN19

**Descrição original:** Administradores e fornecedores se autenticam no painel web com e-mail e senha; o sistema emite um token JWT.

**Critério de aceite original:** Credenciais válidas de usuário ativo abrem a sessão; credenciais inválidas ou de usuário desativado são recusadas com mensagem genérica.

### REQ RF03 — Controle de acesso por perfil (RBAC)

- status: planned
- escopo_plano: MVP
- sprints: S3/S5
- entrega_planejada: RBAC e validação por admin/fornecedor
- escopo_matriz: MVP
- id_anterior: RF03
- persona_matriz: Administrador / Fornecedor
- modulo: Autenticação e Acesso
- servico_proposto_matriz: Identidade
- objetivo_matriz: O6
- complexidade_matriz: Média
- dependencias_matriz: RF02
- regras_relacionadas: RN19

**Descrição original:** Administrador acessa todas as funções; fornecedor acessa somente a tela de validação de códigos (RF11). A restrição vale na API, não só na interface.

**Critério de aceite original:** Fornecedor que chama um endpoint administrativo recebe 403; os menus administrativos não aparecem para ele.

### REQ RF04 — Gestão de funcionários

- status: planned
- escopo_plano: MVP
- sprints: S3
- entrega_planejada: Usuários do painel e vínculo de fornecedor
- escopo_matriz: MVP
- id_anterior: RF04, RF05
- persona_matriz: Administrador
- modulo: Funcionários e Parceiros
- servico_proposto_matriz: Identidade
- objetivo_matriz: O6
- complexidade_matriz: Baixa
- dependencias_matriz: RF03, RF05
- regras_relacionadas: RN18, RN19

**Descrição original:** O administrador cadastra, edita e desativa usuários do painel, escolhendo o perfil: Administrador ou Fornecedor. O fornecedor é vinculado a um parceiro (RF05). A desativação é lógica e preserva o histórico de validações.

**Critério de aceite original:** Fornecedor não é salvo sem parceiro; usuário desativado perde o acesso no máximo até o token expirar (RNF05); o histórico de validações permanece.

### REQ RF05 — Gestão de parceiros

- status: planned
- escopo_plano: MVP
- sprints: S3
- entrega_planejada: CRUD parceiro e CNPJ
- escopo_matriz: MVP
- id_anterior: RF20 (parte)
- persona_matriz: Administrador
- modulo: Funcionários e Parceiros
- servico_proposto_matriz: Benefícios
- objetivo_matriz: O3
- complexidade_matriz: Baixa
- dependencias_matriz: RF03
- regras_relacionadas: RN16, RN18

**Descrição original:** O administrador cadastra, edita e desativa empresas parceiras (nome, CNPJ, contato). O parceiro é a base do vínculo com fornecedores (RF04) e com cupons (RF10). A parceria em si é gerenciada fora do sistema.

**Critério de aceite original:** O CNPJ é validado (dígitos verificadores) e único; parceiro desativado não aparece como opção em novos cupons.

### REQ RF06 — Gestão de pontos turísticos

- status: planned
- escopo_plano: MVP
- sprints: S3
- entrega_planejada: Pontos e remoção lógica
- escopo_matriz: MVP
- id_anterior: RF11, RF12, RF13
- persona_matriz: Administrador
- modulo: Pontos e Eventos
- servico_proposto_matriz: Catálogo
- objetivo_matriz: O1
- complexidade_matriz: Média
- dependencias_matriz: RF03
- regras_relacionadas: RN09, RN20

**Descrição original:** O administrador cadastra, edita e remove pontos com nome, descrição, endereço, latitude/longitude e categorias (uma ou mais, da lista pré-definida). Opcionais: raio de check-in, imagem (URL) e duração estimada da visita. A remoção é lógica.

**Critério de aceite original:** O ponto exige ao menos 1 categoria e coordenadas válidas; ponto removido some do app e das rotas, sem apagar as visitas já registradas.

### REQ RF07 — Cronograma e status de funcionamento

- status: planned
- escopo_plano: MVP
- sprints: S3/S4
- entrega_planejada: Cronograma/status e efeitos no progresso
- escopo_matriz: MVP
- id_anterior: RF14, RF15
- persona_matriz: Administrador
- modulo: Pontos e Eventos
- servico_proposto_matriz: Catálogo
- objetivo_matriz: O1
- complexidade_matriz: Baixa
- dependencias_matriz: RF06
- regras_relacionadas: RN07, RN08, RN26

**Descrição original:** Cada ponto tem cronograma semanal (um ou mais intervalos por dia, ou 24h) e status: aberto, temporariamente fechado ou fechado permanentemente.

**Critério de aceite original:** Mudar o status reflete de imediato no app; ponto fechado permanentemente sai do cálculo de progresso das rotas; check-in só é aceito com status “aberto”.

### REQ RF08 — Gestão de eventos

- status: planned
- escopo_plano: MVP
- sprints: S3
- entrega_planejada: Eventos e encerramento
- escopo_matriz: MVP
- id_anterior: RF16, RF17
- persona_matriz: Administrador
- modulo: Pontos e Eventos
- servico_proposto_matriz: Catálogo
- objetivo_matriz: O1
- complexidade_matriz: Média
- dependencias_matriz: RF06
- regras_relacionadas: RN22

**Descrição original:** O administrador cadastra, edita e remove eventos de um ponto: título, descrição, data/hora de início, fim (opcional) e preço do ingresso (0 = gratuito; informativo, o sistema não vende ingressos). Eventos encerrados deixam de ser exibidos.

**Critério de aceite original:** O evento exige ponto e data de início; evento encerrado não aparece no app nem nas respostas do chatbot.

### REQ RF09 — Gestão de rotas

- status: planned
- escopo_plano: MVP
- sprints: S4
- entrega_planejada: Rotas sem brinde e com guaranás
- escopo_matriz: MVP
- id_anterior: RF18, RF19
- persona_matriz: Administrador
- modulo: Rotas (gestão)
- servico_proposto_matriz: Catálogo
- objetivo_matriz: O1
- complexidade_matriz: Média
- dependencias_matriz: RF06
- regras_relacionadas: RN02, RN06, RN09, RN20

**Descrição original:** O administrador cadastra, edita e remove rotas: nome, descrição, pontos (mínimo 2), categorias (temas), guaranás de recompensa pela conclusão e status ativa/inativa. Sem brindes físicos.

**Critério de aceite original:** A rota exige no mínimo 2 pontos, 1 categoria e recompensa maior ou igual a 0; remover a rota descarta o progresso dos inscritos e preserva os guaranás já creditados.

### REQ RF10 — Gestão de cupons

- status: planned
- escopo_plano: MVP
- sprints: S5
- entrega_planejada: Gestão de cupons
- escopo_matriz: MVP
- id_anterior: RF20, RF35 (parte)
- persona_matriz: Administrador
- modulo: Cupons (gestão)
- servico_proposto_matriz: Benefícios
- objetivo_matriz: O3
- complexidade_matriz: Média
- dependencias_matriz: RF05
- regras_relacionadas: RN14, RN16

**Descrição original:** O administrador cadastra, edita e desativa cupons: parceiro (CNPJ), custo em guaranás, limite disponível, condições de utilização e descrição do benefício.

**Critério de aceite original:** Todos os campos são obrigatórios, com custo ≥ 1 e limite ≥ 1; cupom desativado some do catálogo e não pode ser resgatado.

### REQ RF11 — Validação de código de resgate

- status: planned
- escopo_plano: MVP
- sprints: S5
- entrega_planejada: Validação concorrente e por parceiro
- escopo_matriz: MVP
- id_anterior: RF21
- persona_matriz: Fornecedor / Administrador
- modulo: Cupons (validação)
- servico_proposto_matriz: Benefícios
- objetivo_matriz: O3
- complexidade_matriz: Alta
- dependencias_matriz: RF03, RF37, RNF08
- regras_relacionadas: RN17, RN18

**Descrição original:** O fornecedor (ou o administrador) valida um código lido por QR Code (câmera do navegador) ou digitado. O sistema confirma que o código existe, pertence a cupom do parceiro do fornecedor e ainda não foi usado; então o marca como utilizado, registrando quem validou e quando.

**Critério de aceite original:** Dois fornecedores validando o mesmo código ao mesmo tempo: só um tem sucesso; código inexistente, já usado ou de cupom de outro parceiro é recusado com o motivo.

### REQ RF12 — Indicadores gerais

- status: planned
- escopo_plano: MVP
- sprints: S6
- entrega_planejada: Indicadores conciliados
- escopo_matriz: MVP
- id_anterior: RF07
- persona_matriz: Administrador
- modulo: Dashboard
- servico_proposto_matriz: Analytics
- objetivo_matriz: O5
- complexidade_matriz: Baixa
- dependencias_matriz: RF17, RF31, RF33, RF37
- regras_relacionadas: —

**Descrição original:** O dashboard mostra, para um período configurável: turistas cadastrados, acessos (logins de turistas), visitas validadas, guaranás emitidos e guaranás gastos.

**Critério de aceite original:** Os valores batem com a consulta direta ao banco no mesmo período; trocar o período altera os totais.

### REQ RF13 — Ranking de pontos mais visitados

- status: planned
- escopo_plano: MVP
- sprints: S6
- entrega_planejada: Ranking por período e desempate
- escopo_matriz: MVP
- id_anterior: RF08
- persona_matriz: Administrador
- modulo: Dashboard
- servico_proposto_matriz: Analytics
- objetivo_matriz: O5
- complexidade_matriz: Média
- dependencias_matriz: RF31
- regras_relacionadas: —

**Descrição original:** Ranking por número de visitas validadas, filtrável por dia, mês e ano.

**Critério de aceite original:** O ranking vem ordenado por visitas, com desempate estável; o filtro de período muda o resultado.

### REQ RF14 — Mapa de calor de visitas

- status: planned
- escopo_plano: MVP
- sprints: S6
- entrega_planejada: Heatmap por ponto com OSM
- escopo_matriz: MVP
- id_anterior: RF06, RNF18 (parte)
- persona_matriz: Administrador
- modulo: Dashboard
- servico_proposto_matriz: Analytics
- objetivo_matriz: O5
- complexidade_matriz: Média
- dependencias_matriz: RF06, RF31
- regras_relacionadas: —

**Descrição original:** Mapa da cidade (OpenStreetMap) com intensidade proporcional às visitas validadas de cada ponto no período escolhido. É um mapa por ponto cadastrado: não rastreia a posição contínua dos turistas.

**Critério de aceite original:** Pontos com mais visitas aparecem com maior intensidade; ponto sem visitas no período não aparece; não usa API paga.

### REQ RF15 — Distribuição de turistas por país e interesses

- status: planned
- escopo_plano: MVP
- sprints: S6
- entrega_planejada: Turistas distintos por país/interesses
- escopo_matriz: MVP
- id_anterior: RF09, RF10
- persona_matriz: Administrador
- modulo: Dashboard
- servico_proposto_matriz: Analytics
- objetivo_matriz: O5
- complexidade_matriz: Baixa
- dependencias_matriz: RF16, RF18, RF31
- regras_relacionadas: —

**Descrição original:** Gráficos com a proporção de turistas com visita validada por país de origem e por categoria de interesse, no período escolhido.

**Critério de aceite original:** A proporção por país soma 100%; por interesse pode passar de 100% (seleção múltipla) e o gráfico indica isso.

### REQ RF16 — Cadastro do turista

- status: planned
- escopo_plano: MVP
- sprints: S3
- entrega_planejada: Cadastro validado e consentimento
- escopo_matriz: MVP
- id_anterior: RF22
- persona_matriz: Turista
- modulo: Perfil do Turista
- servico_proposto_matriz: Identidade
- objetivo_matriz: O6
- complexidade_matriz: Baixa
- dependencias_matriz: RNF06, RNF07
- regras_relacionadas: —

**Descrição original:** O turista se cadastra no app com nome, sobrenome, e-mail, telefone, CPF ou número de passaporte, país de origem e senha, aceitando os termos de uso e a política de privacidade.

**Critério de aceite original:** E-mail e documento são únicos; CPF é validado quando informado; sem aceite dos termos não há cadastro; a senha é guardada só em hash.

### REQ RF17 — Login do turista

- status: planned
- escopo_plano: MVP
- sprints: S1/S3/S6
- entrega_planejada: Login e acesso durável do turista
- escopo_matriz: MVP
- id_anterior: RF23
- persona_matriz: Turista
- modulo: Perfil do Turista
- servico_proposto_matriz: Identidade
- objetivo_matriz: O6
- complexidade_matriz: Baixa
- dependencias_matriz: RF16, RNF05
- regras_relacionadas: —

**Descrição original:** Autenticação no app por e-mail e senha, com token JWT; cada login gera um registro de acesso.

**Critério de aceite original:** Credenciais válidas abrem a sessão; cada login grava data/hora, usada nos acessos do dashboard (RF12).

### REQ RF18 — Seleção de interesses

- status: planned
- escopo_plano: MVP
- sprints: S3/S6
- entrega_planejada: Interesses e consumo nas features
- escopo_matriz: MVP
- id_anterior: RF25
- persona_matriz: Turista
- modulo: Perfil do Turista
- servico_proposto_matriz: Identidade
- objetivo_matriz: O1
- complexidade_matriz: Baixa
- dependencias_matriz: RF16
- regras_relacionadas: RN20

**Descrição original:** O turista escolhe as categorias de seu interesse (lazer, cultura, gastronomia etc., as mesmas dos pontos e rotas) e pode alterá-las a qualquer momento. Elas alimentam a ordenação da home (RF22), o chatbot (RF41) e as notificações (RF39).

**Critério de aceite original:** Seleção múltipla; a alteração vale na próxima abertura da home.

### REQ RF19 — Edição de perfil

- status: planned
- escopo_plano: Pós-MVP
- sprints: P1
- entrega_planejada: Edição completa de perfil
- escopo_matriz: Pós-MVP
- id_anterior: RF24
- persona_matriz: Turista
- modulo: Perfil do Turista
- servico_proposto_matriz: Identidade
- objetivo_matriz: O6
- complexidade_matriz: Baixa
- dependencias_matriz: RF16
- regras_relacionadas: —

**Descrição original:** O turista visualiza e edita seus dados cadastrais (exceto o documento).

**Critério de aceite original:** As alterações seguem as mesmas validações do cadastro.

### REQ RF20 — Recuperação de senha

- status: planned
- escopo_plano: Pós-MVP
- sprints: P1
- entrega_planejada: Recuperação de senha
- escopo_matriz: Pós-MVP
- id_anterior: novo
- persona_matriz: Turista / Administrador / Fornecedor
- modulo: Autenticação e Acesso
- servico_proposto_matriz: Identidade
- objetivo_matriz: O6
- complexidade_matriz: Baixa
- dependencias_matriz: RF02, RF16
- regras_relacionadas: —

**Descrição original:** Turista e usuários do painel redefinem a senha por link enviado ao e-mail cadastrado.

**Critério de aceite original:** O link é de uso único e tem validade curta.

### REQ RF21 — Exclusão de conta (LGPD)

- status: planned
- escopo_plano: Pós-MVP
- sprints: P1
- entrega_planejada: Exclusão e anonimização da conta
- escopo_matriz: Pós-MVP
- id_anterior: novo
- persona_matriz: Turista
- modulo: Perfil do Turista
- servico_proposto_matriz: Identidade
- objetivo_matriz: O6
- complexidade_matriz: Média
- dependencias_matriz: RF16
- regras_relacionadas: —

**Descrição original:** O turista solicita a exclusão da conta e dos dados pessoais; visitas e guaranás ficam anonimizados para manter as estatísticas.

**Critério de aceite original:** Após a exclusão o turista não consegue entrar e os dados pessoais são removidos ou anonimizados.

### REQ RF22 — Listagem de pontos por relevância

- status: planned
- escopo_plano: MVP
- sprints: S3
- entrega_planejada: Relevância e fallback
- escopo_matriz: MVP
- id_anterior: RF26
- persona_matriz: Turista
- modulo: Descoberta
- servico_proposto_matriz: Catálogo
- objetivo_matriz: O1
- complexidade_matriz: Média
- dependencias_matriz: RF06, RF18
- regras_relacionadas: —

**Descrição original:** A home lista os pontos ordenados por afinidade com os interesses do turista e, quando há localização, por proximidade em linha reta (Haversine). Sem interesses ou sem localização, ordena por nome. Pontos fechados permanentemente não são listados.

**Critério de aceite original:** Ponto de categoria de interesse aparece antes de um sem afinidade; entre iguais, o mais próximo vem primeiro; o app funciona se o turista negar a localização.

### REQ RF23 — Detalhes do ponto turístico

- status: planned
- escopo_plano: MVP
- sprints: S3/S4
- entrega_planejada: Detalhes e já visitado
- escopo_matriz: MVP
- id_anterior: RF27
- persona_matriz: Turista
- modulo: Descoberta
- servico_proposto_matriz: Catálogo
- objetivo_matriz: O1
- complexidade_matriz: Baixa
- dependencias_matriz: RF06, RF07, RF08
- regras_relacionadas: —

**Descrição original:** Tela com descrição, endereço, categorias, horários, status, eventos futuros, indicação de “já visitado” e acesso a “Como chegar” e “Marcar visitação”.

**Critério de aceite original:** Mostra só eventos futuros ou em andamento; ponto já visitado exibe o selo e não oferece nova marcação.

### REQ RF24 — Como chegar (Google Maps)

- status: planned
- escopo_plano: MVP
- sprints: S3
- entrega_planejada: Link Google Maps
- escopo_matriz: MVP
- id_anterior: RF28 (parte), RNF18 (parte)
- persona_matriz: Turista
- modulo: Descoberta
- servico_proposto_matriz: App (cliente)
- objetivo_matriz: O1
- complexidade_matriz: Baixa
- dependencias_matriz: RF23
- regras_relacionadas: RN24

**Descrição original:** Componente clicável que abre o Google Maps na localização do ponto. Não usa a API paga.

**Critério de aceite original:** O toque abre o Google Maps (aplicativo ou navegador) com a latitude/longitude do ponto.

### REQ RF25 — Listagem e detalhes de rotas

- status: planned
- escopo_plano: MVP
- sprints: S4
- entrega_planejada: Lista/detalhe de rota e inscrição
- escopo_matriz: MVP
- id_anterior: novo
- persona_matriz: Turista
- modulo: Descoberta
- servico_proposto_matriz: Catálogo
- objetivo_matriz: O1
- complexidade_matriz: Baixa
- dependencias_matriz: RF09
- regras_relacionadas: RN02

**Descrição original:** O turista vê as rotas ativas e, em cada uma, os pontos, as categorias, a recompensa em guaranás e, se inscrito, o progresso.

**Critério de aceite original:** Rotas inativas não aparecem; o detalhe indica se o turista está inscrito.

### REQ RF26 — Busca e filtro de pontos

- status: planned
- escopo_plano: Pós-MVP
- sprints: P2
- entrega_planejada: Busca e filtro combinados
- escopo_matriz: Pós-MVP
- id_anterior: novo
- persona_matriz: Turista
- modulo: Descoberta
- servico_proposto_matriz: Catálogo
- objetivo_matriz: O1
- complexidade_matriz: Baixa
- dependencias_matriz: RF22
- regras_relacionadas: —

**Descrição original:** Busca por nome e filtro por categoria na lista de pontos.

**Critério de aceite original:** Busca e filtro podem ser combinados e respeitam a ordenação por relevância.

### REQ RF27 — Atalhos para Uber e 99

- status: planned
- escopo_plano: Pós-MVP
- sprints: P2
- entrega_planejada: Atalhos Uber/99 no app
- escopo_matriz: Pós-MVP
- id_anterior: RF28 (parte)
- persona_matriz: Turista
- modulo: Descoberta
- servico_proposto_matriz: App (cliente)
- objetivo_matriz: O1
- complexidade_matriz: Baixa
- dependencias_matriz: RF23
- regras_relacionadas: —

**Descrição original:** Links que abrem o Uber e o 99 com o ponto como destino.

**Critério de aceite original:** O toque abre o aplicativo (ou a loja) com o destino preenchido, quando o aplicativo suportar.

### REQ RF28 — Inscrição e desistência de rota

- status: planned
- escopo_plano: MVP
- sprints: S4
- entrega_planejada: Inscrição/desistência/reinscrição
- escopo_matriz: MVP
- id_anterior: RF29
- persona_matriz: Turista
- modulo: Rotas (turista)
- servico_proposto_matriz: Gamificação
- objetivo_matriz: O2
- complexidade_matriz: Média
- dependencias_matriz: RF09, RF31
- regras_relacionadas: RN05, RN06, RN12

**Descrição original:** O turista se inscreve em rotas ativas, em várias ao mesmo tempo, e pode desistir. Visitas feitas antes da inscrição contam para o progresso.

**Critério de aceite original:** A inscrição já mostra o progresso com as visitas anteriores; desistir mantém visitas e guaranás; reinscrever retoma o progresso a partir das visitas.

### REQ RF29 — Acompanhamento de progresso da rota

- status: planned
- escopo_plano: MVP
- sprints: S4
- entrega_planejada: Progresso derivado
- escopo_matriz: MVP
- id_anterior: RF30
- persona_matriz: Turista
- modulo: Rotas (turista)
- servico_proposto_matriz: Gamificação
- objetivo_matriz: O2
- complexidade_matriz: Baixa
- dependencias_matriz: RF28, RF32
- regras_relacionadas: RN07, RN11

**Descrição original:** Mostra pontos visitados e pendentes e uma barra de progresso. Pontos fechados permanentemente aparecem como indisponíveis e ficam fora do cálculo.

**Critério de aceite original:** Progresso = pontos visitados ÷ pontos válidos da rota; fechar um ponto recalcula o percentual.

### REQ RF30 — Check-in com validação de presença

- status: planned
- escopo_plano: MVP
- sprints: S4
- entrega_planejada: Check-in e Haversine
- escopo_matriz: MVP
- id_anterior: RF31, RF32, RNF14
- persona_matriz: Turista
- modulo: Check-in e Visitas
- servico_proposto_matriz: Gamificação
- objetivo_matriz: O2
- complexidade_matriz: Média
- dependencias_matriz: RF06, RF07, RNF08
- regras_relacionadas: RN08, RN10, RN28

**Descrição original:** Ao acionar “Marcar visitação” em um ponto, o app envia a posição (latitude, longitude e precisão). O servidor calcula a distância em linha reta (Haversine) até o ponto e aceita o check-in se ela estiver dentro do raio do ponto mais o limiar de tolerância (padrão global, ajustável por ponto).

**Critério de aceite original:** Dentro do limiar: aceito. Fora: recusado, informando a distância aproximada. Ponto não “aberto”: recusado. Permissão de localização negada: o app orienta o turista.

### REQ RF31 — Registro de visita única

- status: planned
- escopo_plano: MVP
- sprints: S4
- entrega_planejada: Visita única e precisão
- escopo_matriz: MVP
- id_anterior: RF33
- persona_matriz: Turista
- modulo: Check-in e Visitas
- servico_proposto_matriz: Gamificação
- objetivo_matriz: O2
- complexidade_matriz: Média
- dependencias_matriz: RF30, RNF08
- regras_relacionadas: RN04

**Descrição original:** O check-in aceito grava a visita (turista, ponto, data/hora, distância, precisão) uma única vez por turista e ponto; repetir não gera novo registro nem novos guaranás.

**Critério de aceite original:** Um segundo check-in no mesmo ponto retorna “já visitado” sem efeito; reenvio ou duplo toque não duplica a visita.

### REQ RF32 — Atualização de progresso e conclusão de rotas

- status: planned
- escopo_plano: MVP
- sprints: S4
- entrega_planejada: Conclusão de todas as rotas afetadas
- escopo_matriz: MVP
- id_anterior: RF34 (parte)
- persona_matriz: Turista
- modulo: Check-in e Visitas
- servico_proposto_matriz: Gamificação
- objetivo_matriz: O2
- complexidade_matriz: Média
- dependencias_matriz: RF28, RF31
- regras_relacionadas: RN03, RN04, RN07, RN11

**Descrição original:** A cada visita registrada, o sistema reavalia as rotas em que o turista está inscrito e que contêm o ponto. A rota é concluída quando todos os pontos válidos foram visitados. A visita vale para todas as rotas que incluem o ponto.

**Critério de aceite original:** Uma visita em ponto que está em 2 rotas atualiza as duas; a rota concluída é marcada uma única vez.

### REQ RF33 — Concessão de guaranás

- status: planned
- escopo_plano: MVP
- sprints: S4
- entrega_planejada: Crédito de guaranás único
- escopo_matriz: MVP
- id_anterior: RF34 (parte), RF35 (parte)
- persona_matriz: Turista
- modulo: Guaranás
- servico_proposto_matriz: Gamificação
- objetivo_matriz: O2
- complexidade_matriz: Média
- dependencias_matriz: RF31, RF32, RNF08
- regras_relacionadas: RN01, RN02, RN03, RN09, RN12, RN27

**Descrição original:** Crédito feito em evento separado do progresso: (a) 1 guaraná por visita registrada; (b) o valor definido na rota quando ela é concluída, uma vez por turista e rota. Cada crédito gera um lançamento no histórico do turista.

**Critério de aceite original:** Visita nova credita 1; conclusão credita o valor da rota uma vez; reenvio ou reinscrição não creditam de novo; guaranás permanecem se rota ou ponto forem removidos.

### REQ RF34 — Saldo de guaranás

- status: planned
- escopo_plano: MVP
- sprints: S4/S5
- entrega_planejada: Saldo após crédito e resgate
- escopo_matriz: MVP
- id_anterior: RF35 (parte)
- persona_matriz: Turista
- modulo: Guaranás
- servico_proposto_matriz: Gamificação
- objetivo_matriz: O2
- complexidade_matriz: Baixa
- dependencias_matriz: RF33, RF37
- regras_relacionadas: RN27

**Descrição original:** O turista vê no app o saldo atualizado de guaranás.

**Critério de aceite original:** Saldo = créditos − débitos do histórico; atualiza após check-in e após resgate.

### REQ RF35 — Extrato de guaranás

- status: planned
- escopo_plano: Pós-MVP
- sprints: P2
- entrega_planejada: Extrato visível no app
- escopo_matriz: Pós-MVP
- id_anterior: novo
- persona_matriz: Turista
- modulo: Guaranás
- servico_proposto_matriz: Gamificação
- objetivo_matriz: O2
- complexidade_matriz: Baixa
- dependencias_matriz: RF33
- regras_relacionadas: —

**Descrição original:** Lista dos lançamentos (crédito por visita, crédito por rota, débito por resgate) com data e origem.

**Critério de aceite original:** Cada lançamento mostra tipo, valor, origem e data, do mais recente ao mais antigo.

### REQ RF36 — Catálogo de cupons

- status: planned
- escopo_plano: MVP
- sprints: S5
- entrega_planejada: Catálogo de cupons
- escopo_matriz: MVP
- id_anterior: novo
- persona_matriz: Turista
- modulo: Cupons (turista)
- servico_proposto_matriz: Benefícios
- objetivo_matriz: O3
- complexidade_matriz: Baixa
- dependencias_matriz: RF10
- regras_relacionadas: RN13, RN14

**Descrição original:** O turista vê os cupons ativos com parceiro, descrição, condições, custo em guaranás e disponibilidade, e quais já resgatou.

**Critério de aceite original:** Cupom desativado ou sem limite disponível não é resgatável; cupom já resgatado pelo turista aparece como tal.

### REQ RF37 — Resgate de cupom e geração do código

- status: planned
- escopo_plano: MVP
- sprints: S5
- entrega_planejada: Resgate atômico
- escopo_matriz: MVP
- id_anterior: RF35 (parte), RF36
- persona_matriz: Turista
- modulo: Cupons (turista)
- servico_proposto_matriz: Benefícios
- objetivo_matriz: O3
- complexidade_matriz: Alta
- dependencias_matriz: RF34, RF36, RNF08
- regras_relacionadas: RN13, RN15, RN17

**Descrição original:** O turista com saldo suficiente resgata um cupom: o sistema debita o custo, reduz o limite disponível e gera o código de resgate (QR Code + código alfanumérico verificável). Cada cupom só pode ser resgatado uma vez por turista.

**Critério de aceite original:** Saldo insuficiente, cupom já resgatado ou limite esgotado: recusa sem débito. Resgates simultâneos do último cupom disponível: só um tem sucesso. O código não é sequencial e o servidor consegue verificá-lo.

### REQ RF38 — Meus cupons

- status: planned
- escopo_plano: MVP
- sprints: S5
- entrega_planejada: Meus cupons com QR/situação
- escopo_matriz: MVP
- id_anterior: novo
- persona_matriz: Turista
- modulo: Cupons (turista)
- servico_proposto_matriz: Benefícios
- objetivo_matriz: O3
- complexidade_matriz: Baixa
- dependencias_matriz: RF37
- regras_relacionadas: RN17

**Descrição original:** O turista vê os cupons resgatados, com QR Code, código textual, condições e situação (disponível ou utilizado).

**Critério de aceite original:** Cupom utilizado aparece como “utilizado”, com a data de uso.

### REQ RF39 — Notificações por interesse

- status: planned
- escopo_plano: MVP por decisão deste plano
- sprints: S6
- entrega_planejada: Push por interesse com RabbitMQ
- escopo_matriz: Pós-MVP
- id_anterior: RF37
- persona_matriz: Turista
- modulo: Notificações
- servico_proposto_matriz: Notificações
- objetivo_matriz: O1
- complexidade_matriz: Média
- dependencias_matriz: RF06, RF08, RF09, RF18
- regras_relacionadas: RN20

**Descrição original:** O turista recebe notificações push sobre novos pontos, rotas e eventos ligados às categorias que escolheu.

**Critério de aceite original:** Conteúdo novo de uma categoria de interesse notifica só quem a escolheu; o turista pode desativar as notificações.

### REQ RF40 — Consulta de informações no chatbot

- status: planned
- escopo_plano: MVP
- sprints: S7/S8
- entrega_planejada: RAG de informações
- escopo_matriz: MVP
- id_anterior: RF38
- persona_matriz: Turista
- modulo: Chatbot
- servico_proposto_matriz: Chatbot
- objetivo_matriz: O4
- complexidade_matriz: Alta
- dependencias_matriz: RF06, RF07, RF08, RF42
- regras_relacionadas: RN21

**Descrição original:** O turista conversa em linguagem natural e obtém informações sobre pontos (descrição, localização, disponibilidade) e eventos, usando RAG sobre os dados cadastrados.

**Critério de aceite original:** A resposta cita só pontos e eventos cadastrados; pergunta sem dado correspondente recebe aviso de que não há informação.

### REQ RF41 — Roteiro personalizado no chatbot

- status: planned
- escopo_plano: MVP
- sprints: S8
- entrega_planejada: Roteiro personalizado
- escopo_matriz: MVP
- id_anterior: RF38, RF39
- persona_matriz: Turista
- modulo: Chatbot
- servico_proposto_matriz: Chatbot
- objetivo_matriz: O4
- complexidade_matriz: Alta
- dependencias_matriz: RF18, RF40
- regras_relacionadas: RN21

**Descrição original:** A pedido do turista, o chatbot sugere um roteiro considerando interesses, proximidade entre pontos (Haversine), disponibilidade (status e horários) e eventos (data e preço do ingresso). A sugestão é texto na conversa.

**Critério de aceite original:** O roteiro não inclui ponto fechado nem evento encerrado, respeita os interesses do turista e informa o preço dos eventos incluídos.

### REQ RF42 — Sincronização da base do chatbot

- status: planned
- escopo_plano: MVP
- sprints: S7
- entrega_planejada: Atualização integral da base
- escopo_matriz: MVP
- id_anterior: novo
- persona_matriz: Sistema
- modulo: Chatbot
- servico_proposto_matriz: Chatbot
- objetivo_matriz: O4
- complexidade_matriz: Média
- dependencias_matriz: RF06, RF07, RF08
- regras_relacionadas: RN21

**Descrição original:** Alterações em pontos, status, cronogramas e eventos são refletidas na base de conhecimento do chatbot.

**Critério de aceite original:** Uma alteração feita no painel aparece nas respostas em até 5 minutos (meta do MVP, ajustável); ponto removido deixa de ser citado.

### REQ RF43 — Salvar roteiro sugerido

- status: planned
- escopo_plano: Pós-MVP
- sprints: P3
- entrega_planejada: Salvar roteiro/rota pessoal
- escopo_matriz: Pós-MVP
- id_anterior: novo
- persona_matriz: Turista
- modulo: Chatbot
- servico_proposto_matriz: Chatbot
- objetivo_matriz: O4
- complexidade_matriz: Média
- dependencias_matriz: RF41
- regras_relacionadas: —

**Descrição original:** O turista salva o roteiro sugerido pelo chatbot e o consulta depois, ou o transforma em rota pessoal.

**Critério de aceite original:** O roteiro salvo aparece listado no perfil do turista.

### REQ RNF01 — Arquitetura distribuída com microsserviços

- status: planned
- escopo_plano: MVP
- sprints: S2
- entrega_planejada: Containers/domínios e banco único
- escopo_matriz: MVP
- id_anterior: RNF01, RNF02, RNF17
- persona_matriz: —
- modulo: Arquitetura
- servico_proposto_matriz: Transversal
- objetivo_matriz: O6
- complexidade_matriz: Alta
- dependencias_matriz: —
- regras_relacionadas: RN23

**Descrição original:** Backend em microsserviços independentes por domínio (Identidade, Catálogo, Gamificação, Benefícios, Chatbot, Analytics e, no pós-MVP, Notificações), comunicando-se em rede, com banco de dados único. Convenção proposta: cada serviço é dono de suas tabelas e só acessa dados de outro domínio por API ou visão somente leitura. Serviços sem estado local.

**Critério de aceite original:** Cada serviço sobe em contêiner próprio; derrubar o Chatbot não impede login, check-in, resgate nem validação.

### REQ RNF02 — API REST em Python

- status: planned
- escopo_plano: MVP
- sprints: S2 e contínuo
- entrega_planejada: FastAPI/Pydantic/OpenAPI e Kong
- escopo_matriz: MVP
- id_anterior: RNF03
- persona_matriz: —
- modulo: Arquitetura
- servico_proposto_matriz: Transversal
- objetivo_matriz: O6
- complexidade_matriz: Média
- dependencias_matriz: RNF01
- regras_relacionadas: —

**Descrição original:** Painel e app consomem a mesma API RESTful, feita com FastAPI e Pydantic, com autorização por perfil e documentação OpenAPI gerada.

**Critério de aceite original:** Todo endpoint tem esquema Pydantic e aparece na documentação OpenAPI.

### REQ RNF03 — Painel web em React

- status: planned
- escopo_plano: MVP
- sprints: S3/S5/S6
- entrega_planejada: Painel React e QR web
- escopo_matriz: MVP
- id_anterior: RNF04
- persona_matriz: —
- modulo: Arquitetura
- servico_proposto_matriz: Painel
- objetivo_matriz: O6
- complexidade_matriz: Média
- dependencias_matriz: RNF02
- regras_relacionadas: —

**Descrição original:** Painel administrativo em React (JavaScript), em português, com leitura de QR Code pela câmera do navegador na tela de validação.

**Critério de aceite original:** O painel funciona nas versões atuais do Chrome e do Firefox; a validação por QR funciona em navegador de celular (HTTPS).

### REQ RNF04 — App Android em Kotlin

- status: planned
- escopo_plano: MVP
- sprints: S3–S6
- entrega_planejada: App Kotlin/Compose e jornada
- escopo_matriz: MVP
- id_anterior: RNF05
- persona_matriz: —
- modulo: Arquitetura
- servico_proposto_matriz: App (cliente)
- objetivo_matriz: O6
- complexidade_matriz: Média
- dependencias_matriz: RNF02
- regras_relacionadas: —

**Descrição original:** Aplicativo Passaporte em Kotlin com Jetpack Compose, consumindo a API (RNF02). Plataforma-alvo do MVP: Android (ver P01).

**Critério de aceite original:** O app é instalável em Android a partir da versão mínima definida no projeto; o fluxo cadastro → check-in → resgate roda de ponta a ponta.

### REQ RNF05 — Autenticação por token (JWT)

- status: planned
- escopo_plano: MVP
- sprints: S1/S3
- entrega_planejada: JWT/refresh e desativação
- escopo_matriz: MVP
- id_anterior: RNF09
- persona_matriz: —
- modulo: Segurança
- servico_proposto_matriz: Identidade
- objetivo_matriz: O6
- complexidade_matriz: Média
- dependencias_matriz: —
- regras_relacionadas: —

**Descrição original:** Acesso à API por JWT de curta duração, com renovação controlada. Usuário do painel desativado perde o acesso no máximo no tempo de vida do token.

**Critério de aceite original:** Token expirado ou adulterado é recusado; a renovação exige token de renovação válido; desativar um funcionário impede a renovação.

### REQ RNF06 — Armazenamento seguro de senhas

- status: planned
- escopo_plano: MVP
- sprints: S1/S3
- entrega_planejada: Hash e ausência de senha em logs
- escopo_matriz: MVP
- id_anterior: RNF10
- persona_matriz: —
- modulo: Segurança
- servico_proposto_matriz: Identidade
- objetivo_matriz: O6
- complexidade_matriz: Baixa
- dependencias_matriz: —
- regras_relacionadas: —

**Descrição original:** Senhas de turistas, administradores e fornecedores guardadas com hash forte (bcrypt ou argon2), nunca em texto.

**Critério de aceite original:** Nenhuma senha aparece em texto no banco, nos logs nem nas respostas da API.

### REQ RNF07 — Proteção de dados pessoais (LGPD)

- status: planned
- escopo_plano: MVP
- sprints: S1/S3/S4
- entrega_planejada: Cifra/HTTPS/consentimento/sem GPS
- escopo_matriz: MVP
- id_anterior: RNF08
- persona_matriz: —
- modulo: Segurança
- servico_proposto_matriz: Identidade
- objetivo_matriz: O6
- complexidade_matriz: Média
- dependencias_matriz: RF16
- regras_relacionadas: RN28

**Descrição original:** Documento (CPF ou passaporte) cifrado em repouso, com hash separado para checar unicidade; tráfego só por HTTPS; aceite dos termos registrado; o sistema não guarda trilha de localização, só o resultado do check-in.

**Critério de aceite original:** O documento não aparece em texto no banco nem nos logs; o cadastro registra o aceite com data/hora; a tabela de visitas não contém coordenadas do turista.

### REQ RNF08 — Consistência e concorrência nas operações críticas

- status: planned
- escopo_plano: MVP
- sprints: S2/S4/S5
- entrega_planejada: Atomicidade e concorrência
- escopo_matriz: MVP
- id_anterior: novo
- persona_matriz: —
- modulo: Confiabilidade
- servico_proposto_matriz: Transversal
- objetivo_matriz: O6
- complexidade_matriz: Alta
- dependencias_matriz: —
- regras_relacionadas: RN04, RN12, RN15, RN17

**Descrição original:** Check-in, concessão de guaranás, resgate de cupom e validação de código são operações atômicas e idempotentes, com transações e restrições de unicidade no banco.

**Critério de aceite original:** Teste de concorrência (ex.: 20 requisições simultâneas) resulta em um único resgate do último cupom, uma única validação por código e nenhum crédito duplicado.

### REQ RNF09 — Desempenho

- status: planned
- escopo_plano: MVP
- sprints: S6/S8
- entrega_planejada: Carga e latência do chatbot
- escopo_matriz: MVP
- id_anterior: RNF12
- persona_matriz: —
- modulo: Desempenho
- servico_proposto_matriz: Transversal
- objetivo_matriz: O6
- complexidade_matriz: Média
- dependencias_matriz: RNF01
- regras_relacionadas: —

**Descrição original:** Metas propostas para o MVP: consultas simples (listagem de pontos e rotas, saldo) com p95 ≤ 500 ms para 50 usuários simultâneos; resposta do chatbot em até 10 s.

**Critério de aceite original:** Teste de carga (ex.: k6 ou Locust) comprova as metas e o relatório fica anexado ao projeto.

### REQ RNF10 — Implantação e disponibilidade

- status: planned
- escopo_plano: MVP
- sprints: S1/S2/S6
- entrega_planejada: Compose completo e reinício
- escopo_matriz: MVP
- id_anterior: RNF11
- persona_matriz: —
- modulo: Confiabilidade
- servico_proposto_matriz: Transversal
- objetivo_matriz: O6
- complexidade_matriz: Baixa
- dependencias_matriz: RNF01
- regras_relacionadas: —

**Descrição original:** Todo o sistema (serviços, banco e painel) sobe com um único comando (Docker Compose), com health check, reinício automático e logs por serviço.

**Critério de aceite original:** “docker compose up” deixa o sistema funcional; um serviço derrubado volta sozinho e o health check reflete o estado.

### REQ RNF11 — Escalabilidade horizontal

- status: planned
- escopo_plano: Pós-MVP
- sprints: P3
- entrega_planejada: Réplicas e balanceamento
- escopo_matriz: Pós-MVP
- id_anterior: RNF07
- persona_matriz: —
- modulo: Desempenho
- servico_proposto_matriz: Transversal
- objetivo_matriz: O6
- complexidade_matriz: Alta
- dependencias_matriz: RNF01, RNF10
- regras_relacionadas: —

**Descrição original:** Serviços podem rodar com várias réplicas atrás de balanceador, escalados de forma independente.

**Critério de aceite original:** Catálogo e check-in operam com 2 ou mais réplicas sem perda de dados nem duplicidade.

### REQ RNF12 — Usabilidade e acessibilidade

- status: planned
- escopo_plano: MVP
- sprints: S6
- entrega_planejada: Usabilidade e acessibilidade
- escopo_matriz: MVP
- id_anterior: RNF13
- persona_matriz: —
- modulo: Usabilidade
- servico_proposto_matriz: App (cliente)
- objetivo_matriz: O1
- complexidade_matriz: Média
- dependencias_matriz: —
- regras_relacionadas: —

**Descrição original:** Navegação simples para turistas de diferentes perfis; textos legíveis, contraste adequado e descrição de acessibilidade nos controles do app.

**Critério de aceite original:** Em teste com 5 pessoas, ao menos 4 concluem cadastro → check-in sem ajuda; os controles principais têm descrição para leitor de tela.

### REQ RNF13 — Internacionalização (i18n)

- status: planned
- escopo_plano: MVP
- sprints: S3/S6/S8
- entrega_planejada: App pt-BR/en e idioma da conversa
- escopo_matriz: MVP
- id_anterior: RNF16
- persona_matriz: —
- modulo: Usabilidade
- servico_proposto_matriz: App (cliente)
- objetivo_matriz: O1
- complexidade_matriz: Média
- dependencias_matriz: —
- regras_relacionadas: RN25

**Descrição original:** Textos do app externalizados, com português (pt-BR) e inglês no MVP; datas, horas e valores formatados conforme o idioma; o chatbot responde no idioma da pergunta. O conteúdo cadastrado (pontos, eventos) fica em português no MVP, e o painel é só em pt-BR.

**Critério de aceite original:** Trocar o idioma do dispositivo (pt-BR ou inglês) muda toda a interface sem recompilar; não há texto fixo no código das telas.

### REQ RNF14 — Portabilidade para outras localidades

- status: planned
- escopo_plano: MVP
- sprints: S2/S3/S6
- entrega_planejada: Cidade e fuso configuráveis
- escopo_matriz: MVP
- id_anterior: RNF06
- persona_matriz: —
- modulo: Arquitetura
- servico_proposto_matriz: Transversal
- objetivo_matriz: O6
- complexidade_matriz: Média
- dependencias_matriz: —
- regras_relacionadas: RN26

**Descrição original:** Nenhuma regra ou constante de Manaus fica fixa no código: fuso, idioma padrão e centro do mapa vêm de configuração, e a carga de pontos, rotas e cupons de outra cidade é só de dados. Várias cidades na mesma instalação ficam para o pós-MVP.

**Critério de aceite original:** Trocar a configuração e carregar dados de outra cidade em ambiente de teste funciona sem mudar código.

### REQ RNF15 — Baixo custo

- status: planned
- escopo_plano: MVP
- sprints: S1/S6/S8
- entrega_planejada: Baixo custo e licenças
- escopo_matriz: MVP
- id_anterior: RNF15
- persona_matriz: —
- modulo: Infraestrutura
- servico_proposto_matriz: Transversal
- objetivo_matriz: O6
- complexidade_matriz: Baixa
- dependencias_matriz: —
- regras_relacionadas: RN24

**Descrição original:** Preferir ferramentas gratuitas ou de código aberto: OpenStreetMap/Leaflet no dashboard, Google Maps só por link, modelo de linguagem aberto ou em camada gratuita.

**Critério de aceite original:** Nenhum serviço pago é necessário para executar o MVP; as dependências e licenças estão listadas no README.

### REQ RNF16 — Auditoria

- status: planned
- escopo_plano: MVP
- sprints: S2–S6
- entrega_planejada: Auditoria transacional protegida
- escopo_matriz: MVP
- id_anterior: RNF19
- persona_matriz: —
- modulo: Segurança
- servico_proposto_matriz: Transversal
- objetivo_matriz: O6
- complexidade_matriz: Baixa
- dependencias_matriz: RF03
- regras_relacionadas: —

**Descrição original:** Registrar quem, quando e o quê (antes e depois) nas ações administrativas: pontos, eventos, rotas, parceiros, cupons, funcionários, desativação de cupom e cada validação de código (com o fornecedor).

**Critério de aceite original:** Toda escrita feita pelo painel gera registro persistido que a aplicação não consegue editar.

### REQ RNF17 — Qualidade e testes

- status: planned
- escopo_plano: MVP
- sprints: Todas
- entrega_planejada: Qualidade e testes por serviço
- escopo_matriz: MVP
- id_anterior: RNF20
- persona_matriz: —
- modulo: Qualidade
- servico_proposto_matriz: Transversal
- objetivo_matriz: O6
- complexidade_matriz: Média
- dependencias_matriz: —
- regras_relacionadas: —

**Descrição original:** Código organizado por serviço, com README, e testes automatizados cobrindo os fluxos críticos: check-in, concessão de guaranás, resgate e validação.

**Critério de aceite original:** A suíte de testes roda com um comando e passa; cada serviço tem README explicando como executar.

### REQ RNF18 — Segurança e limites do chatbot

- status: planned
- escopo_plano: MVP
- sprints: S7/S8
- entrega_planejada: Tema/PII/limites/falhas do LLM
- escopo_matriz: MVP
- id_anterior: novo
- persona_matriz: —
- modulo: Segurança
- servico_proposto_matriz: Chatbot
- objetivo_matriz: O4
- complexidade_matriz: Média
- dependencias_matriz: RF40, RF41
- regras_relacionadas: RN21

**Descrição original:** O chatbot responde só sobre turismo e a partir dos dados cadastrados, limita mensagens por usuário, não envia dados pessoais ao modelo de linguagem e, se o modelo estiver indisponível, avisa sem afetar o resto do app.

**Critério de aceite original:** Mensagem fora do tema é recusada; excesso de mensagens recebe limite; com o modelo fora do ar o app continua funcional.

## BUSINESS_RULES — regras completas

### RULE RN01

- origem: Planilha original
- sprints: S4
- regra: Cada visita registrada concede 1 guaraná (valor global configurável).

### RULE RN02

- origem: Decisão da equipe
- sprints: S4
- regra: A conclusão de uma rota concede guaranás, no valor definido no cadastro da rota. Não há brindes físicos.

### RULE RN03

- origem: Decisão da equipe
- sprints: S4
- regra: Atualizar o progresso das rotas e creditar guaranás são operações distintas.

### RULE RN04

- origem: Decisão da equipe
- sprints: S4
- regra: O turista registra a visita a um ponto uma única vez; essa visita vale para todas as rotas que incluem o ponto.

### RULE RN05

- origem: Decisão da equipe
- sprints: S4
- regra: Visitas feitas antes da inscrição na rota contam para o progresso.

### RULE RN06

- origem: Decisão da equipe
- sprints: S4
- regra: Os pontos de uma rota podem ser visitados em qualquer ordem; o turista pode estar inscrito em várias rotas ao mesmo tempo e pode desistir.

### RULE RN07

- origem: Decisão da equipe
- sprints: S3/S4
- regra: Ponto com status “fechado permanentemente” deixa de contar no progresso das rotas.

### RULE RN08

- origem: Proposta (validar)
- sprints: S4
- regra: O check-in só é aceito com o ponto em status “aberto”; o horário de funcionamento é informativo.

### RULE RN09

- origem: Decisão da equipe
- sprints: S4
- regra: Se uma rota ou ponto for removido, o turista mantém os guaranás já recebidos e o registro das visitas a pontos que continuam no sistema; o progresso da rota removida é descartado.

### RULE RN10

- origem: Decisão da equipe
- sprints: S4
- regra: O check-in compara a distância em linha reta (Haversine) entre o turista e o ponto, com limiar de tolerância configurável (padrão global, ajustável por ponto).

### RULE RN11

- origem: Proposta (validar)
- sprints: S4
- regra: O progresso de uma rota é calculado a partir do histórico de visitas (visitas ∩ pontos válidos da rota), sem contador próprio.

### RULE RN12

- origem: Proposta (validar)
- sprints: S4
- regra: A recompensa de conclusão de rota é paga uma única vez por turista e rota; desistir e reinscrever-se não repete o pagamento.

### RULE RN13

- origem: Decisão da equipe
- sprints: S5
- regra: Cada cupom pode ser resgatado uma única vez por turista.

### RULE RN14

- origem: Decisão da equipe
- sprints: S5
- regra: O administrador pode desativar cupons; cupom desativado sai do catálogo e não pode mais ser resgatado.

### RULE RN15

- origem: Decisão da equipe
- sprints: S5
- regra: O resgate debita o custo em guaranás, reduz o limite disponível e gera o código em uma única operação; sem saldo ou sem limite, falha sem efeitos.

### RULE RN16

- origem: Decisão da equipe
- sprints: S3/S5
- regra: O cadastro de cupom exige o CNPJ do parceiro, o custo em guaranás, o limite disponível, as condições de utilização e a descrição do benefício.

### RULE RN17

- origem: Decisão da equipe
- sprints: S5
- regra: O código de resgate tem QR Code associado a um código alfanumérico verificável; cada código é validado uma única vez, com controle de condições de corrida.

### RULE RN18

- origem: Decisão da equipe
- sprints: S3/S5
- regra: O fornecedor só valida códigos de cupons do parceiro ao qual está vinculado.

### RULE RN19

- origem: Decisão da equipe
- sprints: S1/S3/S5
- regra: Perfis do painel: Administrador (acesso total) e Fornecedor (somente validação de códigos, por QR Code ou código digitado). O primeiro administrador é criado por script.

### RULE RN20

- origem: Decisão da equipe
- sprints: S3/S4/S6
- regra: Interesses são as mesmas categorias dos pontos e rotas (lazer, cultura, gastronomia…); as notificações são vinculadas aos pontos e rotas do tema escolhido.

### RULE RN21

- origem: Decisão da equipe
- sprints: S7/S8
- regra: O chatbot responde apenas com base nos dados cadastrados (pontos, localização, descrição, disponibilidade e eventos); sem dado, informa que não sabe.

### RULE RN22

- origem: Decisão da equipe
- sprints: S3
- regra: Eventos são cadastrados no sistema e pertencem a um ponto turístico.

### RULE RN23

- origem: Decisão da equipe
- sprints: S2
- regra: O banco de dados é único para todos os serviços.

### RULE RN24

- origem: Decisão da equipe
- sprints: S3/S6
- regra: O Google Maps é usado apenas como link que abre a localização do ponto; sem API paga.

### RULE RN25

- origem: Decisão da equipe
- sprints: S6/S8
- regra: A internacionalização (i18n) é requisito não funcional.

### RULE RN26

- origem: Proposta (validar)
- sprints: S2/S3/S6
- regra: Os horários de funcionamento usam o fuso America/Manaus no MVP, definido em configuração.

### RULE RN27

- origem: Proposta (validar)
- sprints: S4/S5
- regra: Guaranás não expiram, não são transferíveis e não têm valor monetário.

### RULE RN28

- origem: Proposta (validar)
- sprints: S4
- regra: O sistema não armazena as coordenadas do turista; guarda só o resultado do check-in (distância e precisão).

## POST_MVP

- **P1 Conta e autosserviço**
  - Requisitos: RF19, RF20, RF21
  - Direcionamento: Completar edição de dados, recuperação segura de senha e exclusão/anonimização. Definir retenção e preservação das estatísticas. Não confundir com validações obrigatórias do cadastro já entregues no MVP.
- **P2 Conveniência e consulta**
  - Requisitos: RF26, RF27, RF35
  - Direcionamento: Busca/filtro combinados, links Uber/99 e extrato visível de guaranás. Ledger interno é obrigatório já em S4; só a tela/consulta de extrato fica depois.
- **P3 Evolução de roteiro e escala**
  - Requisitos: RF43, RNF11
  - Direcionamento: Salvar roteiro/rota pessoal e comprovar duas ou mais réplicas independentes com balanceamento, sem duplicidade de crédito/resgate.
- **P4 Implementação e validação de Android e React**
  - Status: pendente. Depende dos contratos e do backend das sprints correspondentes.
  - S3: acesso, cadastro, descoberta e perfis do painel. Demonstrar a gestão de usuários, parceiros, pontos e eventos.
  - S4: progresso, visitas e saldo no app, com gestão de rotas no painel.
  - S5: catálogo, resgate e cupons no app. Validação web por câmera/QR e entrada manual em HTTPS no Chrome, Firefox e navegador móvel, com interface de fornecedor limitada à validação.
  - S6: integração do painel ao Compose, recepção de push no Android, JWT/RBAC nos clientes, textos pt-BR/en, leitor de tela e navegação. Pelo menos 4 de 5 pessoas concluem cadastro→check-in sem ajuda.
  - Evidência: demonstração e registro dos testes ponta a ponta nos dois clientes.

Notificações não fazem parte deste backlog: foram promovidas para S6. Chatbot também não é pós-MVP neste plano; é a última etapa do MVP. APIs antecipadas do legado podem ser preservadas apenas se seguras e coerentes, sem consumir prioridade nem ampliar o aceite obrigatório.

## PROVENANCE

**Revisão 1.2 · 23/11/2026.** A etapa atual prioriza backend e infraestrutura. As implementações, integrações e validações de Android e React permanecem pendentes em P4; os testes de API e serviços integrados orientam o aceite do backend.

**Revisão 1.1 · 23/11/2026.** Por decisão de escopo, a homologação dos fluxos da S3 no Android e no React passa para o pós-MVP. O aceite da S3 usa evidências da API e das migrações. O escopo de implementação das telas previsto em S3.6 permanece registrado.

**Versão 1.0 · 22/11/2026.** Destinatários: equipe de produto, backend, infraestrutura, painel, Android e QA. Próxima revisão: abertura de S1 e a cada marco M1/M2/M3. Atualizar matriz/planilha em revisão identificada; preservar a versão 2.0 original para comparação.

- Fonte principal: PassaNorte_Matriz_de_Rastreabilidade_MVP.xlsx, versão 2.0 de 17/11/2026. RF em Matriz linhas 5–47; RNF em linhas 48–65; regras em Regras de Negócio linhas 5–32; atributos na aba Cadastros.
- Diagnóstico de referência: relatório técnico de 22/11/2026, checkout 2145274e901a5ad28c531640959cb4360206cdb0. Os achados são linha de base, não uma nova execução de testes neste plano.
- Decisões de escopo: solicitação que aprovou continuidade do projeto, banco único, personas sem employee, ausência de brindes, notificações no MVP e chatbot na última etapa.


### Referências técnicas consultadas

- [Firebase Cloud Messaging](https://firebase.google.com/docs/cloud-messaging). Candidato para o transporte push ao Android; requer integração de servidor e cliente e não substitui RabbitMQ.
- [PostgreSQL 16 sobre schemas e privilégios](https://www.postgresql.org/docs/16/ddl-schemas.html). Schemas organizam objetos; a separação efetiva depende de permissões e search_path.
- [Kong JWT](https://developer.konghq.com/plugins/jwt/) e [referência de configuração](https://developer.konghq.com/plugins/jwt/reference/). Suporte a RS256/chave pública e identificação da credencial; validar comportamento na versão fixada do projeto.
- [Ollama Qwen3 4B](https://ollama.com/library/qwen3:4b). Candidato aberto com licença Apache 2.0 e variante quantizada. A escolha final depende de benchmark, não de alegação de desempenho genérica.
- [Ollama Qwen3 Embedding 0.6B](https://ollama.com/library/qwen3-embedding:0.6b) e [API de embeddings do Ollama](https://docs.ollama.com/api/embed). Fixar modelo, licença, dimensão e versão em S7.

Modelos citados são candidatos de implementação, não instalação realizada. Nenhum prazo ou responsável nominal foi assumido. Este plano não implementa mudanças no backend; ele define a ordem, os contratos esperados e os testes que permitirão aceitá-las.

### Registro desta conversão

- Data: 2026-11-23. Versão do plano preservada: 1.0 de 2026-11-22.
- Origem: `outputs/passanorte-plano/PassaNorte_Plano_de_Implementacao.html` e `outputs/passanorte-plano/plano-rastreabilidade.json`, relativos à raiz do workspace original.
- SHA-256 do HTML de origem: `ae68372ae1eaa4b41faa5a2cdffa8850d5976eda2a157b74c586e6b314dee21e`.
- Removidos somente elementos de apresentação/interação: CSS, JavaScript, botões, filtro visual, links de retorno e paginação. Tabelas foram convertidas em registros com campos explícitos.
- Acrescentados protocolo de consulta, metadados de origem/status e IDs estáveis para aceites. Descrições completas dos requisitos foram recuperadas do JSON associado ao mesmo plano.
- Nenhum teste de backend foi reexecutado nesta conversão. O planejamento não foi aplicado ao código.
