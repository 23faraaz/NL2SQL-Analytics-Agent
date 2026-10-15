#!/usr/bin/env bash
set -euo pipefail

project_name="nl2sql-compose-regression"
compose_files=(
  -f docker-compose.yml
  -f tests/integration/compose-repeated-up.override.yml
)

cleanup() {
  docker compose -p "${project_name}" "${compose_files[@]}" down --volumes --remove-orphans
}
trap cleanup EXIT

run_initialization() {
  docker compose -p "${project_name}" "${compose_files[@]}" up \
    --build \
    --force-recreate \
    --abort-on-container-exit \
    --exit-code-from db-init \
    db-init
}

run_initialization
run_initialization

row_count="$(docker compose -p "${project_name}" "${compose_files[@]}" exec -T db \
  psql -U "${DB_USER}" -d "${DB_NAME}" -Atc \
  'SELECT COUNT(*) FROM commerce.categories;')"
test "${row_count}" = "1"
