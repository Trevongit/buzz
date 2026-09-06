#!/usr/bin/env bash
# Post BLOCKED + need_prime once per task fingerprint. Never retry-spam Prime.
# Fail-closed when grok/Prime is on another PUBLIC.txt host (silent empty room).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/lib.sh"

ROOM=""
SEAT="$(visitor_resolve_seat)"
FROM_ROLE="${VISITOR_ROLE:-}"
TO_ROLE="grok"
TASK=""
DRY=0
HOME_AGENTS="${VISITOR_AGENTS_HOME:-$HOME/.buzz-dev/agents}"
ROLE_SEATS="${VISITOR_ROLE_SEATS:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --room) ROOM="$2"; shift 2 ;;
    --seat) SEAT="$2"; shift 2 ;;
    --from) FROM_ROLE="$2"; shift 2 ;;
    --to) TO_ROLE="$2"; shift 2 ;;
    --task) TASK="$2"; shift 2 ;;
    --home) HOME_AGENTS="$2"; shift 2 ;;
    --role-seats) ROLE_SEATS="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help)
      echo "Usage: escalate.sh --task TEXT [--from ROLE] [--to grok] [--room ID] [--seat ID] [--dry-run]"
      echo "  Same-bus only. Mixed Groundfeed/Tailscale does not ping Prime."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done
export VISITOR_AGENTS_HOME="$HOME_AGENTS"

if [[ -z "$FROM_ROLE" ]]; then
  FROM_ROLE="$(visitor_default_role "$SEAT")"
fi
if [[ -z "$FROM_ROLE" || -z "$TASK" ]]; then
  echo "error: --task required (and --from, or a mapped --seat)" >&2
  exit 1
fi

render_blocked() {
  python3 "${ROOT}/gate.py" render --from "$FROM_ROLE" --to "$TO_ROLE" --task "$TASK" --status BLOCKED --need-prime true
}

bus=(same-bus --from "$FROM_ROLE" --to "$TO_ROLE" --home "$HOME_AGENTS")
if [[ -n "$ROLE_SEATS" ]]; then
  bus+=(--role-seats "$ROLE_SEATS")
fi
if ! python3 "${ROOT}/gate.py" "${bus[@]}" >/dev/null; then
  echo "error: escalate to=$TO_ROLE is not on the same relay as from=$FROM_ROLE" >&2
  echo "VISITOR_ESCALATE skip reason=prime-other-bus" >&2
  if [[ "$DRY" == "1" ]]; then
    render_blocked
    echo "DRY-RUN not posted (Prime not pinged)"
  fi
  exit 3
fi

if [[ "$DRY" == "1" ]]; then
  render_blocked
  echo "DRY-RUN not posted (Prime not pinged)"
  exit 0
fi

visitor_load_seat_env "$SEAT"
DIR="$(visitor_seat_dir "$SEAT")"
JOURNAL="${DIR}/prime-escalation.json"
mkdir -p "$DIR"

check="$(python3 "${ROOT}/gate.py" escalate-check --journal "$JOURNAL" --task "$TASK" || true)"
allow="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("allow"))' "$check")"
reason="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("reason"))' "$check")"
if [[ "$allow" != "True" ]]; then
  echo "VISITOR_ESCALATE skip reason=${reason}" >&2
  exit 0
fi

if [[ -z "$ROOM" && -f "${DIR}/last-room.json" ]]; then
  ROOM="$(python3 -c 'import json; print(json.load(open("'"$DIR"'/last-room.json"))["channel_id"])')"
fi
if [[ -z "$ROOM" ]]; then
  echo "error: --room required" >&2
  exit 1
fi

# Post first; record only after success so a failed send can retry once.
# A second successful post of the same fingerprint is refused.
post=(--seat "$SEAT" --room "$ROOM" --from "$FROM_ROLE" --to "$TO_ROLE" --task "$TASK" --status BLOCKED --need-prime true --home "$HOME_AGENTS")
if [[ -n "$ROLE_SEATS" ]]; then
  post+=(--role-seats "$ROLE_SEATS")
fi
bash "${ROOT}/post.sh" "${post[@]}"
python3 "${ROOT}/gate.py" escalate-record --journal "$JOURNAL" --task "$TASK" >/dev/null
fp="$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); from gate import task_fingerprint; print(task_fingerprint(sys.argv[2]))' "$ROOT" "$TASK")"
echo "VISITOR_ESCALATE posted seat=$SEAT task_fp=$fp" >&2
