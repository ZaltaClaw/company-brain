#!/usr/bin/env bash
# Run all three connectors in sequence.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run company-brain ingest fabric  || echo "! fabric ingest failed (continuing)"
uv run company-brain ingest work    || echo "! work ingest failed (continuing)"
uv run company-brain ingest foundry || echo "! foundry ingest failed (continuing)"

uv run company-brain status
