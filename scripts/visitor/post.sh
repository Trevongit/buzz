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
DRY=0
FROM_ESCALATE=0
HOME_AGENTS="${VISITOR_AGENTS_HOME:-$HOME/.buzz-dev/agents}"
ROLE_SEATS="${VISITOR_ROLE_SEATS:-}"

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
    --home) HOME_AGENTS="$2"; shift 2 ;;
    --role-seats) ROLE_SEATS="$2"; shift 2 ;;
    --from-escalate) FROM_ESCALATE=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help)
      echo "Usage: post.sh --room <id|name> (--content TEXT | --file PATH | --envelope via --to --task)"
      echo "  COLLAB: --from grok|codex|agy --to grok|codex|agy|all --task '…' [--status OPEN|DONE|BLOCKED] [--need-prime false]"
      echo "  --dry-run prints the body and does not load keys or send."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

export VISITOR_AGENTS_HOME="$HOME_AGENTS"

need="$(printf '%s' "$NEED_PRIME" | tr '[:upper:]' '[:lower:]')"
st="$(printf '%s' "$STATUS" | tr '[:upper:]' '[:lower:]')"
# BLOCKED+need_prime must journal via escalate.sh (once-then-stop). Do not
# let a raw post.sh call ping Prime without that fence. escalate.sh re-enters
# with --from-escalate so this cannot recurse.
if [[ "$FROM_ESCALATE" != "1" && -n "$TO_ROLE" && -n "$TASK" && "$st" == "blocked" && "$need" =~ ^(1|true|yes)$ ]]; then
  if [[ -z "$FROM_ROLE" ]]; then
    FROM_ROLE="$(visitor_default_role "$SEAT")"
  fi
  esc=(--from "$FROM_ROLE" --to "$TO_ROLE" --task "$TASK" --seat "$SEAT" --home "$HOME_AGENTS")
  if [[ -n "$ROOM" ]]; then
    esc+=(--room "$ROOM")
  fi
  if [[ -n "$ROLE_SEATS" ]]; then
    esc+=(--role-seats "$ROLE_SEATS")
  fi
  if [[ "$DRY" == "1" ]]; then
    esc+=(--dry-run)
  fi
  exec bash "${VISITOR_ROOT}/escalate.sh" "${esc[@]}"
fi

if [[ -n "$TO_ROLE" && -n "$TASK" ]]; then
  if [[ -z "$FROM_ROLE" ]]; then
    FROM_ROLE="$(visitor_default_role "$SEAT")"
  fi
  if [[ -z "$FROM_ROLE" ]]; then
    echo "error: --from required with --to/--task (or a mapped --seat)" >&2
    exit 1
  fi
  bus=(same-bus --from "$FROM_ROLE" --to "$TO_ROLE" --home "$HOME_AGENTS")
  if [[ -n "$ROLE_SEATS" ]]; then
    bus+=(--role-seats "$ROLE_SEATS")
  fi
  bus_json="$(python3 "${VISITOR_ROOT}/gate.py" "${bus[@]}" || true)"
  if ! python3 -c 'import json,sys; raise SystemExit(0 if json.loads(sys.argv[1] or "{}").get("ok") else 3)' "$bus_json"; then
    reason="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1] or "{}").get("reason") or "mixed-or-missing")' "$bus_json" 2>/dev/null || echo mixed-or-missing)"
    echo "error: COLLAB to=$TO_ROLE is not on the same relay bus as from=$FROM_ROLE" >&2
    echo "VISITOR_COLLAB skip reason=${reason}" >&2
    if [[ "$DRY" == "1" ]]; then
      python3 "${VISITOR_ROOT}/gate.py" render --from "$FROM_ROLE" --to "$TO_ROLE" --task "$TASK" --status "$STATUS" --need-prime "$NEED_PRIME" || true
      echo "DRY-RUN not posted"
    fi
    exit 3
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

if [[ "$DRY" == "1" ]]; then
  printf '%s' "$CONTENT"
  echo
  echo "DRY-RUN not posted"
  exit 0
fi

visitor_load_seat_env "$SEAT"
DIR="$(visitor_seat_dir "$SEAT")"
if [[ -z "$ROOM" ]]; then
  ROOM="$(visitor_last_room "$DIR" || true)"
fi
if [[ -z "$ROOM" ]]; then
  echo "error: --room required" >&2
  exit 1
fi
CID="$(visitor_resolve_room "$ROOM")"

args=(messages send --channel "$CID" --content "$CONTENT")
if [[ -n "$REPLY_TO" ]]; then
  args+=(--reply-to "$REPLY_TO")
fi
visitor_run "${args[@]}"
