#!/usr/bin/env bash
# Print row counts per container_tag.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run company-brain status
