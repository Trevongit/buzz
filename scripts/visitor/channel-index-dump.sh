#!/usr/bin/env bash
# Write ~/.buzz-dev/channel-index.json. Bounded. extras owns this file.
set -euo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

SEAT="$(visitor_resolve_seat)"
ROOMS=()
ALL=0
LIMIT=20
OUT="${HOME}/.buzz-dev/channel-index.json"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --seat) SEAT="$2"; shift 2 ;;
    --room) ROOMS+=("$2"); shift 2 ;;
    --all) ALL=1; shift ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: channel-index-dump.sh (--all | --room <uuid>) [--limit N] [--seat ID] [--out PATH]"
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done
if [[ ${#ROOMS[@]} -eq 0 && "$ALL" -ne 1 ]]; then
  echo "error: --room or --all required" >&2
  exit 1
fi
visitor_load_seat_env "$SEAT"
PY_ARGS=()
if [[ "$ALL" -eq 1 ]]; then
  PY_ARGS+=(--all)
fi
for room in "${ROOMS[@]}"; do
  PY_ARGS+=(--room "$room")
done
python3 "${VISITOR_ROOT}/channel_index.py" "${PY_ARGS[@]}" --limit "$LIMIT" --out "$OUT"
