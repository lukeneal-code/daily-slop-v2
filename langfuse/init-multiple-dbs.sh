#!/usr/bin/env bash
# Postgres init hook: creates additional databases listed in $POSTGRES_MULTIPLE_DATABASES
# (comma-separated). Used so the docker-compose Postgres can host both `slop` and `langfuse`.
set -euo pipefail

if [[ -z "${POSTGRES_MULTIPLE_DATABASES:-}" ]]; then
  exit 0
fi

IFS=',' read -ra DBS <<< "${POSTGRES_MULTIPLE_DATABASES}"
for db in "${DBS[@]}"; do
  db="$(echo "$db" | xargs)"
  [[ -n "$db" ]] || continue
  echo "[init] creating database: ${db}"
  psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<-SQL
    SELECT 'CREATE DATABASE "${db}"'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${db}')
    \\gexec
SQL
done
