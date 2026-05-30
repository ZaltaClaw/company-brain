#!/usr/bin/env bash
# Boot Postgres+pgvector and apply schema.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "✗ docker not found — install Docker Desktop first" >&2
  exit 1
fi

echo "→ docker compose up -d postgres"
docker compose up -d postgres

echo "→ waiting for postgres to be healthy..."
for i in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U brain -d company_brain >/dev/null 2>&1; then
    echo "✓ postgres ready"
    break
  fi
  sleep 1
done

echo "→ applying schema"
uv run company-brain init-db
echo "✓ done"
