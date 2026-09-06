#!/usr/bin/env bash
# Join an existing Buzz room as a visitor. Does not mint a seat.
set -euo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ROOM=""
SEAT="$(visitor_resolve_seat)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --room) ROOM="$2"; shift 2 ;;
    --seat) SEAT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: join.sh --room <name|uuid> [--seat ID]"
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done
if [[ -z "$ROOM" ]]; then
  echo "error: --room required" >&2
  exit 1
fi
visitor_load_seat_env "$SEAT"
CID="$(visitor_resolve_room "$ROOM")"
visitor_run channels join --channel "$CID" >/dev/null
DIR="$(visitor_seat_dir "$SEAT")"
python3 - "$DIR/last-room.json" "$CID" "$ROOM" "${BUZZ_RELAY_URL}" <<'PY'
import json,sys,datetime
path,cid,name,relay=sys.argv[1:5]
json.dump({
    "channel_id": cid,
    "name": name,
    "relay": relay,
    "joined_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}, open(path,"w"), indent=2)
print()
PY
echo "joined seat=$SEAT channel=$CID room=$ROOM"
