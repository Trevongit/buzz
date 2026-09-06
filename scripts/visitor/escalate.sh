#!/usr/bin/env bash
# Post BLOCKED + need_prime once per task fingerprint. Never retry-spam Prime.
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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --room) ROOM="$2"; shift 2 ;;
    --seat) SEAT="$2"; shift 2 ;;
    --from) FROM_ROLE="$2"; shift 2 ;;
    --to) TO_ROLE="$2"; shift 2 ;;
    --task) TASK="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help)
      echo "Usage: escalate.sh --from ROLE --task TEXT [--to grok] [--room ID] [--seat ID] [--dry-run]"
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$FROM_ROLE" || -z "$TASK" ]]; then
  echo "error: --from and --task required" >&2
  exit 1
fi

if [[ "$DRY" == "1" ]]; then
  python3 "${ROOT}/gate.py" render --from "$FROM_ROLE" --to "$TO_ROLE" --task "$TASK" --status BLOCKED --need-prime true
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
bash "${ROOT}/post.sh" --seat "$SEAT" --room "$ROOM" --from "$FROM_ROLE" --to "$TO_ROLE" \
  --task "$TASK" --status BLOCKED --need-prime true
python3 "${ROOT}/gate.py" escalate-record --journal "$JOURNAL" --task "$TASK" >/dev/null
fp="$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); from gate import task_fingerprint; print(task_fingerprint(sys.argv[2]))' "$ROOT" "$TASK")"
echo "VISITOR_ESCALATE posted seat=$SEAT task_fp=$fp" >&2
