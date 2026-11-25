# ADR 002 — Limites dos serviços e persistência da S2

Adotado na S2 conforme o [plano de implementação](../planning/PASSANORTE_IMPLEMENTATION_PLAN.md).

| Serviço e schema | Responsabilidade |
| --- | --- |
| `auth` | Identidade, perfis e sessões |
| `catalog` | Pontos, categorias, eventos e definição das rotas |
| `gamification` | Validação das visitas, progresso e decisão de recompensa |
| `benefits` | Ledger econômico e base para o futuro resgate transacional |
| `insights` | Projeções e métricas |
| `notifications` | Preferências e entrega de notificações |
| `chatbot` | Conversas e índice do assistente, com execução opcional |

A API de visitas roda no processo de Gamificação e usa suas sessões. Catálogo mantém os dados das rotas e os fornece por HTTP interno. Referências entre domínios são IDs validados pela aplicação e reconciliados na importação. Os prêmios legados permanecem em Gamificação. Benefícios recebe a fundação do ledger. As regras econômicas e APIs de saldo, cupons e resgate seguem as sprints previstas.

Cada schema tem um owner sem login, um migrator que pode assumir o owner e um runtime com permissões de operação no próprio schema. Auditoria e ledger permitem leitura e inserção pelo runtime. A tabela de versões do Alembic é administrada pelo migrator. A conta de implantação provisiona papéis e extensões.

Os produtores registram eventos na outbox na transação de negócio. O relay aguarda a confirmação do RabbitMQ antes de apagar a linha. Consumidores transacionais registram o ID na inbox junto de seus efeitos no banco. Falhas podem gerar nova entrega. A fila de mensagens mortas preserva eventos rejeitados após o retry.

Kong termina TLS e encaminha somente rotas externas. O boot da borda depende dos serviços permanentes. O Chatbot fica em perfil opcional. APIs privadas exigem credencial interna, e Swagger fica disponível nos ambientes de desenvolvimento e teste.
