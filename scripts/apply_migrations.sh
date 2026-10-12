#!/usr/bin/env bash
# Aplica as migrações Alembic (upgrade head) de cada microsserviço no respectivo
# database (Princípio I). Idempotente: revisões já aplicadas são puladas via
# tabela alembic_version.
#
# Uso (a partir da raiz do repositório):
#   scripts/apply_migrations.sh                       # template padrão (host "db" do compose)
#   scripts/apply_migrations.sh 'postgresql://passanorte:passanorte@localhost:5432/passanorte_{svc}'
#
# `{svc}` no template é trocado pelo nome do serviço. O template pode vir da
# variável DATABASE_URL_TEMPLATE (usada pelo serviço one-shot "migrate" do compose).
set -euo pipefail

cd "$(dirname "$0")/.."

ALL_SERVICES=(auth catalog chatbot gamification insights notifications validation)
# `{svc}` via variável: um literal `}` dentro de ${1:-...} fecha a expansão cedo
SVC='{svc}'
URL_TEMPLATE="${1:-${DATABASE_URL_TEMPLATE:-postgresql://passanorte:passanorte@db:5432/passanorte_${SVC}}}"

if [[ "$URL_TEMPLATE" != *'{svc}'* ]]; then
  echo "Template de URL precisa conter {svc} (ex.: postgresql://user:pass@host:5432/passanorte_{svc})" >&2
  exit 1
fi

for svc in "${ALL_SERVICES[@]}"; do
  url="${URL_TEMPLATE/'{svc}'/$svc}"
  echo "==> $svc ($url)"
  DATABASE_URL="$url" uv run alembic -c "src/services/$svc/alembic.ini" upgrade head
done