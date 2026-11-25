#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

legacy_revision=b1096a8
git cat-file -e "$legacy_revision^{commit}"
scratch=$(mktemp -d)
project="passanorte-s2-rehearsal-$(basename "$scratch" | tr -cd '[:alnum:]' | tr '[:upper:]' '[:lower:]')"
compose=(docker compose --env-file .env.example -p "$project")
cleanup() {
  "${compose[@]}" down --volumes || true
  rm -rf -- "$scratch"
}
trap cleanup EXIT

git archive "$legacy_revision" src | tar -xf - -C "$scratch"
cp scripts/verify_s2_migration.py "$scratch/"
"${compose[@]}" up -d --wait --wait-timeout 90 db
"${compose[@]}" build provision migrate
"${compose[@]}" run --rm --no-deps -T provision
"${compose[@]}" run --rm --no-deps -T migrate bash scripts/apply_migrations.sh --s2
tar -cf - -C "$scratch" src verify_s2_migration.py |
  "${compose[@]}" run --rm --no-deps -T provision bash -ec '
    legacy=$(mktemp -d)
    tar -xf - -C "$legacy"
    PYTHONPATH=/app/scripts python "$legacy/verify_s2_migration.py"
  '
"${compose[@]}" run --rm --no-deps -T migrate
"${compose[@]}" exec -T db psql -X -v ON_ERROR_STOP=1 -U passanorte -d passanorte < scripts/verify_s3_migration.sql
echo "S3 legacy identities, actor history and category seed checks passed."
