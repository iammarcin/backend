#!/bin/bash
# Run batch_jobs table migration

set -euo pipefail

MIGRATION_FILE="001_add_batch_jobs_table.sql"

echo "Running migration: $MIGRATION_FILE"

mysql -h "${MAIN_DB_HOST}" \
      -u "${MAIN_DB_USER}" \
      -p"${MAIN_DB_PASSWORD}" \
      "${MAIN_DB_NAME}" < "${MIGRATION_FILE}"

echo "✅ Migration completed successfully"
