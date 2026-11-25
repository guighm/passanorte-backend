# ADR-001 — Configuração, chaves e sessões na S1

- data: 2026-11-23
- status: implementado; evidências em ../implementation/S1.md
- origem: plano S1.1–S1.6; RF01, RF02, RF17; RNF05, RNF06, RNF07, RNF10, RNF17
- escopo: fundação operacional; sem antecipar alteração de domínio das sprints seguintes

## Decisões

1. Build em duas etapas, Python/uv e imagens de infraestrutura fixados por versão e digest. Lock obrigatório, sincronização frozen. Runtime UID 10001, somente dependências de produção; contexto de build por allowlist.
2. Settings tipadas compartilhadas, validadas conforme o serviço no lifespan. Sem .env implícito, SQLite automático, chave PII efêmera ou segredo JWT padrão.
3. Arquivos de segredo montados somente nos consumidores necessários. Só auth recebe privada RSA e PII. Migrate recebe URLs de bancos, seed recebe URL auth e senha admin. Kong recebe exclusivamente chaves públicas.
4. RS256 com RSA >=2048 bits (gerador local usa 3072), kid no header igual ao nome do PEM. Algoritmo fixo, issuer/audience obrigatórios; JWT de acesso e refresh têm tipos separados. Tokens HS256 anteriores são invalidados nesta transição.
5. Refresh persistido por hash SHA-256 do jti aleatório, família, usuário, expiração e revogação. Atualização condicional e bloqueio da linha do usuário serializam renovação/logout. Reutilização revoga a família. Expiração de refresh é renovada por 7 dias por padrão a cada rotação.
6. Criptografia existente é Fernet (AES-128-CBC autenticado com HMAC-SHA256), não AES-GCM. HMAC de unicidade usa chave independente. Mudar a cifra não faz parte desta sprint.
7. Senha não é aceita como argumento do CLI nem impressa; bootstrap idempotente não sobrescreve credenciais. Senhas além de 72 bytes são recusadas antes de bcrypt.
8. Preservar a versão principal do RabbitMQ 3.13 para compatibilidade com volumes existentes; atualização para linha suportada requer teste de migração/backup em atividade própria. Fixar digest não constitui auditoria de vulnerabilidades da imagem.

## Rotação JWT com sobreposição

1. Gerar novo par RSA em ambiente seguro; escolher kid novo (letras, números, hífen ou underscore).
2. Distribuir o novo PEM público para Kong e todos os serviços, mantendo o antigo. Reiniciar/recarregar Kong (a configuração declarativa é produzida no boot). Conferir aceitação das duas credenciais.
3. Montar a nova privada somente em auth, atualizar JWT_ACTIVE_KID e reiniciar auth. Confirmar emissão com novo kid.
4. Manter a pública antiga pelo maior TTL configurado na emissão antiga: refresh padrão 7 dias, máximo aceito 30 dias; contar da **última emissão** antiga. Monitorar relógios; não existe leeway configurado.
5. Retirar a pública antiga dos verificadores e reiniciar Kong. Tokens assinados por ela são recusados. Nunca reutilizar kid para outra chave.
6. Em comprometimento, retirar imediatamente e aceitar reautenticação forçada. Sessões podem ser revogadas por usuário/família no banco auth durante operação controlada.

O código lê chaves a cada operação; atualização de arquivos deve ser atômica, e o conjunto ativo precisa estar completo. A mudança dos arquivos não recarrega automaticamente o Kong.

Kong valida assinatura/expiração; issuer, audience e tipo são validados no serviço. Credenciais RSA do plugin incluem um campo secret sintático sem função criptográfica. Referência: [JWT Kong](https://developer.konghq.com/plugins/jwt/) e [configuração](https://developer.konghq.com/plugins/jwt/reference/).

## Backup e rotação PII

Fazer backup cifrado do banco **e das versões das chaves**, armazenados separadamente com acesso restrito; testar restauração antes de aposentar chaves. Um backup de banco sem suas chaves não permite recuperar os documentos.

Rotação da cifra:
1. Suspender escritas em auth e tirar snapshot restaurável.
2. Disponibilizar PII_ENCRYPTION_KEY_FILE com nova,antiga (separadas por vírgula), mantendo **a mesma PII_HMAC_KEY**.
3. Em processo de manutenção com PYTHONPATH=src e configuração própria, executar `python scripts/rotate_pii.py`. Todas as linhas são recriptografadas em uma transação.
4. Conferir leitura e cadastros duplicados em ambiente restaurado. Remover a chave antiga da configuração ativa somente após essa validação; conservá-la no cofre para os backups antigos. Reiniciar auth.
5. Em falha, rollback da transação; em falha de implantação posterior, restaurar banco e conjunto de chaves compatíveis.

Rotação HMAC ou migração do HMAC legado:
1. Não trocar a chave enquanto houver escritas: hashes antigos e novos não são comparáveis e a unicidade seria perdida.
2. Parar auth/seed e qualquer escritor; fazer backup.
3. Configurar a cifra capaz de ler os dados antigos e a **nova chave HMAC independente**. Executar `python scripts/rotate_pii.py --rehash`.
4. O script reprocessa CPF/passaporte, verifica duplicações entre ambos os tipos e atualiza índices na mesma transação. Colisão/erro cancela tudo; não há saída de dados pessoais.
5. Só depois do commit iniciar todas as instâncias com a chave HMAC nova. Validar duplicação antes de liberar tráfego.
6. Migração envolve toda a tabela em memória e exige janela de manutenção; para bases grandes, planejar migração em lotes com índices paralelos em atividade específica.

Na versão anterior, o HMAC derivava diretamente da chave Fernet. Para banco já existente, executar obrigatoriamente o procedimento de rehash antes de abrir cadastros. Se a chave antiga era efêmera e foi perdida, os dados cifrados não são recuperáveis: restaurar backup compatível, sem fingir que uma nova chave recuperará os dados.

## Volumes existentes e rollout

Não use o gerador local sobre dados existentes. Recupere as credenciais efetivas do PostgreSQL/RabbitMQ e a chave PII original; provisione os novos arquivos de URL coerentes com elas. Alterar POSTGRES_PASSWORD_FILE/RABBITMQ_DEFAULT_PASS não altera automaticamente usuários já persistidos.

Aplicar migração auth 20261123_refresh e rehash PII antes do tráfego. Tokens antigos são invalidados e clientes precisam efetuar login. Atualizar cliente para substituir refresh e enviar corpo no DELETE /session. Não remover volumes para contornar falhas.

S2 ainda deve reduzir para um database com schemas, ownership e usuários por domínio. Os usuários de banco atuais são compartilhados e privilegiados; esta decisão transitória não satisfaz a arquitetura final.

## Limites explícitos

- Logout e replay revogam refresh; access permanece válido até exp. Serviços não consultam auth em cada requisição.
- HTTP sem TLS no Compose é para desenvolvimento; publicação exige terminação TLS.
- /health é liveness. RabbitMQ existente ainda usa entrega best-effort em alguns fluxos; outbox/robustez integral pertence às sprints de notificações.
- Dados de teste e segredos de desenvolvimento não entram no Git nem na imagem.
- A pasta docs/planning já estava ignorada pelo usuário. Essa configuração foi preservada; o plano referenciado pode não estar presente em checkout remoto. Versionar a fonte canônica continua pendência documental de acompanhamento.
- Referência de build: [guia oficial uv/Docker](https://docs.astral.sh/uv/guides/integration/docker/).
