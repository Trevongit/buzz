#!/usr/bin/env bash
# Post a COLLAB v0 envelope. OPEN/DONE stay in the agent loop; BLOCKED+need-prime is escalate.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/lib.sh"

ACTION=""
ROOM=""
SEAT="$(visitor_resolve_seat)"
FROM_ROLE="${VISITOR_ROLE:-}"
TO_ROLE=""
TASK=""
NEED_PRIME="false"
DRY=0
HOME_AGENTS="${VISITOR_AGENTS_HOME:-$HOME/.buzz-dev/agents}"
ROLE_SEATS="${VISITOR_ROLE_SEATS:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    open|done|blocked) ACTION="$1"; shift ;;
    --room) ROOM="$2"; shift 2 ;;
    --seat) SEAT="$2"; shift 2 ;;
    --from) FROM_ROLE="$2"; shift 2 ;;
    --to) TO_ROLE="$2"; shift 2 ;;
    --task) TASK="$2"; shift 2 ;;
    --need-prime) NEED_PRIME="$2"; shift 2 ;;
    --home) HOME_AGENTS="$2"; shift 2 ;;
    --role-seats) ROLE_SEATS="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help)
      echo "Usage: collab.sh open|done|blocked --from ROLE --to ROLE --task TEXT [--room ID] [--dry-run]"
      echo "  BLOCKED with --need-prime true goes through escalate.sh (once-then-stop)."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$FROM_ROLE" ]]; then
  FROM_ROLE="$(visitor_default_role "$SEAT")"
fi
if [[ -z "$ACTION" || -z "$FROM_ROLE" || -z "$TO_ROLE" || -z "$TASK" ]]; then
  echo "error: open|done|blocked and --from --to --task required" >&2
  exit 1
fi

STATUS="OPEN"
case "$ACTION" in
  open) STATUS="OPEN" ;;
  done) STATUS="DONE" ;;
  blocked) STATUS="BLOCKED" ;;
esac

need="$(printf '%s' "$NEED_PRIME" | tr '[:upper:]' '[:lower:]')"
if [[ "$STATUS" == "BLOCKED" && "$need" =~ ^(1|true|yes)$ ]]; then
  esc=(--from "$FROM_ROLE" --to "$TO_ROLE" --task "$TASK" --seat "$SEAT")
  if [[ -n "$ROOM" ]]; then
    esc+=(--room "$ROOM")
  fi
  if [[ "$DRY" == "1" ]]; then
    esc+=(--dry-run)
  fi
  exec bash "${ROOT}/escalate.sh" "${esc[@]}"
fi

args=(--seat "$SEAT" --from "$FROM_ROLE" --to "$TO_ROLE" --task "$TASK" --status "$STATUS" --need-prime false --home "$HOME_AGENTS")
if [[ -n "$ROOM" ]]; then
  args+=(--room "$ROOM")
fi
if [[ -n "$ROLE_SEATS" ]]; then
  args+=(--role-seats "$ROLE_SEATS")
fi
if [[ "$DRY" == "1" ]]; then
  args+=(--dry-run)
fi
exec bash "${ROOT}/post.sh" "${args[@]}"
