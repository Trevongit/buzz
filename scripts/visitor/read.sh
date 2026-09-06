#!/usr/bin/env bash
# Bounded read. Default 20 events. No cortex.
set -euo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ROOM=""
LIMIT="${VISITOR_READ_LIMIT:-20}"
SEAT="$(visitor_resolve_seat)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --room) ROOM="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --seat) SEAT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: read.sh --room <name|uuid> [--limit N] [--seat ID]"
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done
visitor_load_seat_env "$SEAT"
DIR="$(visitor_seat_dir "$SEAT")"
if [[ -z "$ROOM" && -f "${DIR}/last-room.json" ]]; then
  ROOM="$(python3 -c 'import json; print(json.load(open("'"$DIR"'/last-room.json")).get("channel_id") or "")')"
fi
if [[ -z "$ROOM" ]]; then
  echo "error: --room required" >&2
  exit 1
fi
CID="$(visitor_resolve_room "$ROOM")"
visitor_run messages get --channel "$CID" --limit "$LIMIT"
