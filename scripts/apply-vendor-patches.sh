#!/usr/bin/env bash
# Apply local runtime patches to the vendored supermemory submodule.
#
# We deliberately do NOT commit changes inside vendor/supermemory (that would
# move the submodule pointer). Instead, the diffs live under vendor-patches/
# in this repo and are applied at runtime.
#
# Idempotent: if the patch already applies cleanly in reverse, we skip.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SUBMODULE="$ROOT/vendor/supermemory"
PATCH_DIR="$ROOT/vendor-patches"

if [ ! -d "$SUBMODULE/.git" ] && [ ! -f "$SUBMODULE/.git" ]; then
  echo "vendor/supermemory submodule is missing — run: git submodule update --init --recursive" >&2
  exit 1
fi

shopt -s nullglob
patches=("$PATCH_DIR"/*.patch)
if [ "${#patches[@]}" -eq 0 ]; then
  echo "no patches in $PATCH_DIR — nothing to do"
  exit 0
fi

cd "$SUBMODULE"
for p in "${patches[@]}"; do
  name="$(basename "$p")"
  if git apply --reverse --check "$p" >/dev/null 2>&1; then
    echo "✓ $name already applied — skipping"
    continue
  fi
  if git apply --check "$p" >/dev/null 2>&1; then
    git apply "$p"
    echo "✓ applied $name"
  else
    echo "✗ $name does not apply cleanly to current submodule HEAD" >&2
    exit 1
  fi
done
