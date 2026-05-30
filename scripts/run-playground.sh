#!/usr/bin/env bash
# Boot the vendored memory-graph-playground wired to the local Company Brain API.
#
# Usage:
#   ./scripts/run-playground.sh
#
# Env:
#   COMPANY_BRAIN_URL   override the brain API base URL (default http://localhost:8088)
#   PORT                playground port (default 3004)

set -euo pipefail

cd "$(dirname "$0")/.."

./scripts/apply-vendor-patches.sh

cd vendor/supermemory
bun install --frozen-lockfile 2>/dev/null || bun install

cd apps/memory-graph-playground
COMPANY_BRAIN_URL="${COMPANY_BRAIN_URL:-http://localhost:8088}" \
  PORT="${PORT:-3004}" \
  bun run dev:app
