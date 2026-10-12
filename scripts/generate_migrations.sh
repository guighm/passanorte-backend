#!/usr/bin/env bash
# Gera migrações Alembic (revision --autogenerate) para cada microsserviço (Princípio I).
#
# Uso (a partir da raiz do repositório):
#   scripts/generate_migrations.sh                          # todos os 7 serviços
#   scripts/generate_migrations.sh auth catalog             # só serviços específicos
#   scripts/generate_migrations.sh -m "initial schema"      # mensagem customizada
#   scripts/generate_migrations.sh --database-url POSTGRES_...  # dif contra banco real
#
# Alvo do autogenerate:
#   - Por padrão, compara os modelos contra um banco SQLite vazio temporário
#     (o fallback de dev do env.py) e apaga o arquivo ao final. Antes do diff,
#     `upgrade head` sobe a cadeia de migrações existente no banco temporário —
#     assim o autogenerate vê as tabelas já cobertas pelas migrações e saída é
#     sempre incremental (rodar duas vezes gera arquivo vazio, não duplica o
#     schema). As migrações escritas são portáveis entre sqlite e Postgres.
#   - Com --database-url, compara contra o banco indicado (útil para migrações
#     incrementais); `{svc}` no template é trocado pelo nome do serviço.
#     Ex.: postgresql://passanorte:passanorte@localhost:5432/passanorte_{svc}
#     Nesse caso um `upgrade head` é executado antes (exigência do Alembic).
set -euo pipefail

cd "$(dirname "$0")/.."

ALL_SERVICES=(auth catalog chatbot gamification insights notifications validation)
MESSAGE="create initial schema"
DATABASE_URL_TEMPLATE="${DATABASE_URL:-}"

usage() {
  sed -n '2,15p' "$0" | sed 's/^# \{0,2\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--message)     MESSAGE="$2"; shift 2 ;;
    --database-url)   DATABASE_URL_TEMPLATE="$2"; shift 2 ;;
    -h|--help)        usage ;;
    -*)               echo "Opção desconhecida: $1 (use --help)" >&2; exit 1 ;;
    *)                break ;;
  esac
done

SERVICES=("$@")
if [[ ${#SERVICES[@]} -eq 0 ]]; then
  SERVICES=("${ALL_SERVICES[@]}")
fi
for svc in "${SERVICES[@]}"; do
  is_known=false
  for known in "${ALL_SERVICES[@]}"; do
    [[ "$svc" == "$known" ]] && is_known=true
  done
  if ! $is_known; then
    echo "Serviço desconhecido: $svc (conhecidos: ${ALL_SERVICES[*]})" >&2
    exit 1
  fi
done

# Banco vazio temporário por serviço, a menos que a URL tenha sido explicitada.
TMPDIR_DB=""
DATABASE_URL="$DATABASE_URL_TEMPLATE"
if [[ -z "$DATABASE_URL" ]]; then
  TMPDIR_DB="$(mktemp -d)"
  trap 'rm -rf "$TMPDIR_DB"' EXIT
fi

for svc in "${SERVICES[@]}"; do
  if [[ -n "$TMPDIR_DB" ]]; then
    url="sqlite:///$TMPDIR_DB/$svc.db"
  elif [[ "$DATABASE_URL" == *'{svc}'* ]]; then
    url="${DATABASE_URL//\{svc\}/$svc}"
  else
    url="$DATABASE_URL"
  fi

  echo "==> $svc ($url)"
  # sobe a cadeia de migrações existente no banco alvo (vazio na primeira vez,
  # já migrado nas seguintes) antes do diff. Em banco real isso é um upgrade
  # direto; em banco temporário valida também que as migrações são portáveis.
  DATABASE_URL="$url" uv run alembic -c "src/services/$svc/alembic.ini" upgrade head
  DATABASE_URL="$url" uv run alembic \
    -c "src/services/$svc/alembic.ini" \
    revision --autogenerate -m "$MESSAGE"
done

echo
echo "Concluído. Revisões geradas:"
for svc in "${SERVICES[@]}"; do
  ls "src/services/$svc/alembic/versions/"*.py 2>/dev/null || echo "  $svc: (nenhuma)"
done