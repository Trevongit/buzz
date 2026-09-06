#!/usr/bin/env bash
# Fail-closed gate for unsupervised visitor collab. Does not ping Prime.
# Does not mint seats. Does not post. PUBLIC.txt roster only.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEATS="${VISITOR_SEATS:-codex-buzz,agy-buzz}"
HOME_AGENTS="${VISITOR_AGENTS_HOME:-$HOME/.buzz-dev/agents}"
ROOM=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --seats) SEATS="$2"; shift 2 ;;
    --home) HOME_AGENTS="$2"; shift 2 ;;
    --room) ROOM="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: start-collab.sh [--seats a,b] [--room name|uuid] [--home DIR]"
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
echo "prime: only collab.sh blocked --need-prime true (once per task)"
