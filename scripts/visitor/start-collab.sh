#!/usr/bin/env bash
# Fail-closed gate for unsupervised visitor collab. Does not ping Prime.
# Does not mint seats. Does not post. PUBLIC.txt roster only.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEATS="${VISITOR_SEATS:-codex-buzz,agy-buzz}"
HOME_AGENTS="${VISITOR_AGENTS_HOME:-$HOME/.buzz-dev/agents}"
ROOM=""
DRY=0
FROM_ROLE="${VISITOR_ROLE:-codex}"
TO_ROLE="agy"
TASK="collab dry-run"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --seats) SEATS="$2"; shift 2 ;;
    --home) HOME_AGENTS="$2"; shift 2 ;;
    --room) ROOM="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --from) FROM_ROLE="$2"; shift 2 ;;
    --to) TO_ROLE="$2"; shift 2 ;;
    --task) TASK="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: start-collab.sh [--seats a,b] [--room name|uuid] [--home DIR] [--dry-run]"
      echo "  Default seats: codex-buzz,agy-buzz (same Tailscale bus on this host)."
      echo "  Exit 0 ready; 3 mixed/missing. Does not send messages."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done
if ! bash "${ROOT}/roster.sh" --seats "$SEATS" --home "$HOME_AGENTS"; then
  echo "start-collab: not ready — pick --seats on one bus" >&2
  exit 3
fi
echo "collab-ready seats=$SEATS"
if [[ -n "$ROOM" ]]; then
  echo "room=$ROOM  next: each visitor wake.sh --once and collab.sh open --to <peer>"
fi
if [[ "$DRY" == "1" ]]; then
  echo "DRY-RUN envelope (not posted):"
  python3 "${ROOT}/gate.py" render --from "$FROM_ROLE" --to "$TO_ROLE" --task "$TASK" --status OPEN --need-prime false
  echo "DRY-RUN end"
fi
echo "prime: only collab.sh blocked --need-prime true (once per task)"
