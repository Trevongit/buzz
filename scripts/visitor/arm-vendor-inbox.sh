#!/usr/bin/env bash
# Sit a Codex/agy seat's inbox ear (auto-reply VISITOR_EAR=feed).
# Kitty glass is a separate tab on the log — not a second nerve.
# Do not run beside extra_channels. Do not start interactive TUI here.
set -euo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

SEAT=""
ROOM="${VISITOR_HOUSE_ROOM:-4dc8f551-6053-481e-8df0-31be95c4813d}"
DM=""
APPLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --seat) SEAT="$2"; shift 2 ;;
    --room) ROOM="$2"; shift 2 ;;
    --dm) DM="$2"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    -h|--help)
      echo "Usage: arm-vendor-inbox.sh --seat ID [--room UUID] [--dm UUID] [--apply]"
      echo "  Default dry-run. Idle = feed ear. TUI stays glass."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done
[[ -n "$SEAT" ]] || { echo "error: --seat" >&2; exit 1; }
[[ "$SEAT" != "buzz" && "$SEAT" != "buzz-control" ]] || { echo "error: grok mouths use buzz-inbox.sh not auto-reply" >&2; exit 2; }

visitor_load_seat_env "$SEAT"
DIR="$(visitor_seat_dir "$SEAT")"
LOG="${DIR}/auto-reply.log"
KIT="${VISITOR_ROOT}/auto-reply.sh"
cmd=(bash "$KIT" --seat "$SEAT" --room "$ROOM")
if [[ -n "$DM" ]]; then
  cmd+=(--dm "$DM")
fi
echo "VISITOR_EAR=feed ${cmd[*]} >>$LOG"
if [[ "$APPLY" != "1" ]]; then
  echo "dry-run (pass --apply to sit)"
  exit 0
fi
if pgrep -f "auto-reply.sh --seat ${SEAT}( |$)" >/dev/null 2>&1; then
  echo "already sitting --seat $SEAT (will not stack)"
  exit 0
fi
export VISITOR_EAR=feed
nohup "${cmd[@]}" >>"$LOG" 2>&1 &
echo "started pid $! seat=$SEAT ear=feed"
echo "glass: kitty @ --to unix:/tmp/kitty launch --type=tab --tab-title $( [[ $SEAT == buzz-* ]] && echo "$SEAT" || echo "buzz-$SEAT" ) -- tail -F $LOG"
