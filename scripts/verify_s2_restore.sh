#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

compose=(docker compose)
if [[ $# -gt 0 ]]; then
  compose+=(--env-file "$1")
fi
database=passanorte
restore="passanorte_restore_$$"
scratch=$(mktemp -d)
chmod 700 "$scratch"
pg() { "${compose[@]}" exec -T db "$@"; }
cleanup() {
  pg dropdb -U passanorte --if-exists "$restore"
  rm -f -- "$scratch/backup.dump" "$scratch/expected" "$scratch/actual"
  rmdir -- "$scratch"
}
trap cleanup EXIT

pg pg_dump -U passanorte -d "$database" -Fc > "$scratch/backup.dump"
pg createdb -U passanorte -T template0 "$restore"
# Database-level policies belong to provisioning, outside the per-database archive.
pg psql -X -v ON_ERROR_STOP=1 -U passanorte -d "$restore" -v "restore=$restore" <<'SQL'
REVOKE ALL ON DATABASE :"restore" FROM PUBLIC;
SQL
pg pg_restore -U passanorte -d "$restore" --exit-on-error --single-transaction < "$scratch/backup.dump"

# Compare the same captured snapshot, including data, ownership and grants.
# pg_restore emits independent psql restrict keys when generating SQL.
pg pg_restore --file=- < "$scratch/backup.dump" |
  sed -E '/^\\(un)?restrict /d' > "$scratch/expected"
pg pg_dump -U passanorte -d "$restore" -Fp |
  sed -E '/^\\(un)?restrict /d' > "$scratch/actual"
cmp "$scratch/expected" "$scratch/actual"
pg psql -X -v ON_ERROR_STOP=1 -U passanorte -d "$restore" < scripts/verify_s2_privileges.sql
echo "S2 backup restored and compared successfully."
