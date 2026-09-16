#!/usr/bin/env bash
# Kind 20001 online heartbeat for visitor seats (phone/desktop green light).
# Ephemeral: WebSocket only. HTTP POST /events is rejected. Idle tokens = 0.
# One flock per seat. Do not mint. Do not rewrite agent.env.
set -euo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

SEAT="$(visitor_resolve_seat)"
TICK="${VISITOR_PRESENCE_SECS:-60}"
ONCE=0
STATUS="online"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seat) SEAT="$2"; shift 2 ;;
    --secs) TICK="$2"; shift 2 ;;
    --once) ONCE=1; shift ;;
    --status) STATUS="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: visitor-presence.sh [--seat ID] [--once] [--secs 60] [--status online|away|offline]"
      echo "  Heartbeat kind:20001 via buzz users set-presence (WebSocket)."
      echo "  Sit beside buzz-inbox.sh / hands_listen / auto-reply. Not extra_channels."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

if [[ "$SEAT" == "buzz-control" ]]; then
  echo "REFUSE steward" >&2
  exit 2
fi
case "$STATUS" in
  online|away|offline) ;;
  *) echo "status must be online|away|offline" >&2; exit 1 ;;
esac

visitor_load_seat_env "$SEAT"
TICK="$(visitor_bound_limit "$TICK" 180)"
DIR="$(visitor_seat_dir "$SEAT")"
LOCK="${DIR}/visitor-presence.lock"
mkdir -p "$DIR"

publish() {
  local st="$1"
  visitor_run users set-presence --status "$st"
  echo "VISITOR_PRESENCE seat=${SEAT} status=${st}"
}

if [[ "$ONCE" == "1" ]]; then
  publish "$STATUS"
  exit 0
fi

exec 9>"$LOCK"
if ! flock -n 9; then
  echo "VISITOR_PRESENCE skip seat=${SEAT} reason=already-sitting" >&2
  exit 0
fi

offline_on_exit() {
  publish offline || true
}
trap offline_on_exit EXIT INT TERM

publish online
while :; do
  sleep "$TICK"
  publish online
done
