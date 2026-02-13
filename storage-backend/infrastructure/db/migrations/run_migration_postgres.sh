#!/bin/bash
# Run batch_jobs table migration for PostgreSQL/Supabase

set -euo pipefail

MIGRATION_FILE="001_add_batch_jobs_table_postgres.sql"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Running PostgreSQL migration: $MIGRATION_FILE"

# Database connection from environment (same pattern as storage-backend/config/database/urls.py)
DB_HOST="${SUPABASE_HOST:-${SUPABASE_DB_HOST:-}}"
DB_PORT="${SUPABASE_DB_PORT:-5432}"
DB_USER="${SUPABASE_DB_USER:-postgres}"
DB_PASS="${SUPABASE_DB_PASSWORD:-${SUPABASE_DB_PASS:-}}"
DB_NAME="${SUPABASE_DB_NAME:-postgres}"

if [ -z "$DB_HOST" ]; then
    echo "Error: SUPABASE_HOST or SUPABASE_DB_HOST environment variable is required"
    exit 1
fi

if [ -z "$DB_PASS" ]; then
    echo "Error: SUPABASE_DB_PASSWORD or SUPABASE_DB_PASS environment variable is required"
    exit 1
fi

# Set search_path for Supabase schema (default to aiapp)
SCHEMA="${SUPABASE_SCHEMA:-aiapp}"

echo "Connecting to: ${DB_HOST}:${DB_PORT}/${DB_NAME} (schema: ${SCHEMA})"

PGPASSWORD="${DB_PASS}" psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -v ON_ERROR_STOP=1 \
    -c "SET search_path TO ${SCHEMA};" \
    -f "${SCRIPT_DIR}/${MIGRATION_FILE}"

echo "Migration completed successfully"
