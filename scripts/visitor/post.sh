#!/usr/bin/env bash
# Post a visitor message or a COLLAB v0 envelope. Key via env only.
set -euo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ROOM=""
CONTENT=""
FILE=""
REPLY_TO=""
SEAT="$(visitor_resolve_seat)"
FROM_ROLE="${VISITOR_ROLE:-}"
TO_ROLE=""
TASK=""
STATUS="OPEN"
NEED_PRIME="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --room) ROOM="$2"; shift 2 ;;
    --content) CONTENT="$2"; shift 2 ;;
    --file) FILE="$2"; shift 2 ;;
    --reply-to|--reply) REPLY_TO="$2"; shift 2 ;;
    --seat) SEAT="$2"; shift 2 ;;
    --from) FROM_ROLE="$2"; shift 2 ;;
    --to) TO_ROLE="$2"; shift 2 ;;
    --task) TASK="$2"; shift 2 ;;
    --status) STATUS="$2"; shift 2 ;;
    --need-prime) NEED_PRIME="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: post.sh --room <id|name> (--content TEXT | --file PATH | --envelope via --to --task)"
      echo "  COLLAB: --from grok|codex|agy --to grok|codex|agy|all --task '…' [--status OPEN|DONE|BLOCKED] [--need-prime false]"
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

visitor_load_seat_env "$SEAT"
DIR="$(visitor_seat_dir "$SEAT")"
if [[ -z "$ROOM" && -f "${DIR}/last-room.json" ]]; then
  ROOM="$(python3 -c 'import json; print(json.load(open("'"$DIR"'/last-room.json"))["channel_id"])')"
fi
if [[ -z "$ROOM" ]]; then
  echo "error: --room required" >&2
  exit 1
fi
CID="$(visitor_resolve_room "$ROOM")"

if [[ -n "$TO_ROLE" && -n "$TASK" ]]; then
  if [[ -z "$FROM_ROLE" ]]; then
    echo "error: --from required with --to/--task" >&2
    exit 1
  fi
  CONTENT="$(python3 "${VISITOR_ROOT}/gate.py" render --from "$FROM_ROLE" --to "$TO_ROLE" --task "$TASK" --status "$STATUS" --need-prime "$NEED_PRIME")"
fi
if [[ -n "$FILE" ]]; then
  CONTENT="$(cat "$FILE")"
fi
if [[ -z "$CONTENT" ]]; then
  echo "error: --content, --file, or --to/--task required" >&2
  exit 1
fi

args=(messages send --channel "$CID" --content "$CONTENT")
if [[ -n "$REPLY_TO" ]]; then
  args+=(--reply-to "$REPLY_TO")
fi
visitor_run "${args[@]}"
