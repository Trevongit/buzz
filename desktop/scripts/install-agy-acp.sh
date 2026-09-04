#!/usr/bin/env bash
# Install the extras Antigravity ACP shim onto PATH for Desktop discovery.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="$ROOT/desktop/scripts/agy-acp"
DEST="${HOME}/.local/bin/agy-acp"
if [[ ! -f "$SRC" ]]; then
  echo "missing $SRC" >&2
  exit 1
fi
mkdir -p "$(dirname "$DEST")"
install -m 755 "$SRC" "$DEST"
echo "installed $DEST"
command -v agy >/dev/null && echo "agy: $(command -v agy)" || echo "agy: not on PATH (Adapter missing until agy is installed)"
command -v agy-acp
