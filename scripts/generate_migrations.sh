#!/usr/bin/env bash
# Run against a provisioned local S2 PostgreSQL database.
set -euo pipefail
cd "$(dirname "$0")/.."
message="${1:?Usage: generate_migrations.sh MESSAGE SERVICE}"
service="${2:?Specify a service}"
case "$service" in auth|catalog|gamification|benefits|insights|notifications|chatbot) ;; *) exit 2 ;; esac
export DATABASE_URL_FILE="${DB_CREDENTIAL_DIR:?Set DB_CREDENTIAL_DIR}/database-${service}_migrator"
uv run --frozen alembic -c "src/services/$service/alembic.ini" revision --autogenerate -m "$message"
