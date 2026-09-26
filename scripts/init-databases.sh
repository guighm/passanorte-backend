#!/bin/bash
# Cria um database por microsserviço (Princípio I da Constituição)
set -euo pipefail

for db in passanorte_auth passanorte_catalog passanorte_validation \
          passanorte_gamification passanorte_insights passanorte_notifications \
          passanorte_chatbot; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE $db'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
done

# pgvector para o serviço de chatbot (D-08)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname passanorte_chatbot <<-EOSQL
  CREATE EXTENSION IF NOT EXISTS vector;
EOSQL