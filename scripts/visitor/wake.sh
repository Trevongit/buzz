#!/usr/bin/env bash
# Mention-gated visitor nerve. Stdout is only VISITOR_WAKE lines (or VISITOR_OK seed).
# Idle = poll, no LLM.
set -euo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ROOM=""
SEAT="$(visitor_resolve_seat)"
TICK="${VISITOR_WATCH_SECS:-15}"
LIMIT="${VISITOR_WATCH_LIMIT:-20}"
ONCE="${VISITOR_WAKE_ONCE:-0}"
LOG="${VISITOR_WATCHER_LOG:-/tmp/visitor-wake.log}"
FORCE_DM=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --room) ROOM="$2"; shift 2 ;;
    --seat) SEAT="$2"; shift 2 ;;
    --dm) FORCE_DM=1; shift ;;
    --once) ONCE=1; shift ;;
    --secs) TICK="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: wake.sh [--room name|uuid] [--seat ID] [--dm] [--once] [--secs N]"
      echo "  --dm  this UUID is a DM: admit without @mention (rooms stay mention-gated)"
      echo "  VISITOR_REQUIRE_MENTION=1 (default)  VISITOR_ROLE=grok|codex|agy"
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

visitor_load_seat_env "$SEAT"
LIMIT="$(visitor_bound_limit "$LIMIT" 100)"
TICK="$(visitor_bound_limit "$TICK" 300)"
DIR="$(visitor_seat_dir "$SEAT")"
if [[ -z "$ROOM" ]]; then
  visitor_assert_last_room_bus "$DIR" || exit 3
  ROOM="$(visitor_last_room "$DIR" || true)"
fi
if [[ -z "$ROOM" ]]; then
  echo "VISITOR_FAIL no room — set --room or join first" >&2
  exit 1
fi
CID="$(visitor_resolve_room "$ROOM")"
SELF="${BUZZ_PUBLIC_KEY:-}"
ROLE="$(visitor_default_role "$SEAT")"
DERIVED="$(python3 "${VISITOR_ROOT}/gate.py" role-from-seat --seat "$SEAT")"
if [[ -n "${VISITOR_ROLE:-}" && -n "$DERIVED" && "$ROLE" != "$DERIVED" ]]; then
  echo "VISITOR_WARN role=$ROLE seat=$SEAT maps-to=$DERIVED (COLLAB to:$DERIVED may miss this seat)" >&2
fi
if [[ -z "${VISITOR_NAMES:-}" && -f "${DIR}/PUBLIC.txt" ]]; then
  NAMES="$(python3 "${VISITOR_ROOT}/gate.py" mention-names --dir "$DIR" --seat "$SEAT")"
else
  NAMES="${VISITOR_NAMES:-$SEAT}"
fi
REQUIRE="${VISITOR_REQUIRE_MENTION:-1}"
COOLDOWN="${VISITOR_COOLDOWN_SECS:-30}"
IS_DM=0
if [[ "$FORCE_DM" == "1" ]]; then
  visitor_mark_dm "$SEAT" "$CID" || true
fi
if visitor_channel_is_dm "$SEAT" "$CID" || visitor_channel_is_dm "$SEAT" "$ROOM"; then
  IS_DM=1
fi
if [[ "$IS_DM" == "1" ]]; then
  COOLDOWN="${VISITOR_DM_COOLDOWN_SECS:-0}"
  if ! [[ "$COOLDOWN" =~ ^[0-9]+$ ]]; then
    COOLDOWN=0
  fi
fi

STATE_PREFIX="${VISITOR_WAKE_STATE_PREFIX:-}"
STATE="${DIR}/visitor-wake-${STATE_PREFIX}${CID}.json"
poll_once() {
  local json
  json="$(visitor_run messages get --channel "$CID" --limit "$LIMIT" 2>/dev/null || true)"
  json="${json#"${json%%[![:space:]]*}"}"
  if [[ -z "$json" ]] || [[ "${json:0:1}" != '[' && "${json:0:1}" != '{' ]]; then
    json='[]'
  fi
  python3 - "$json" "$STATE" "$SELF" "$SEAT" "$CID" "$ROOM" "$ROLE" "$NAMES" "$REQUIRE" "$IS_DM" "$VISITOR_ROOT" "$COOLDOWN" <<'PY'
import json, sys, time
from pathlib import Path

sys.path.insert(0, sys.argv[11])
from gate import filter_wakes

raw = sys.argv[1]
try:
    data = json.loads(raw or "[]")
except json.JSONDecodeError:
    data = []
if isinstance(data, dict):
    data = data.get("messages") or data.get("events") or []
if not isinstance(data, list):
    data = []

state_path = Path(sys.argv[2])
self_pk, seat, cid, room, role = sys.argv[3:8]
names = [n.strip() for n in sys.argv[8].split(",") if n.strip()]
require = sys.argv[9] != "0"
is_dm = sys.argv[10] == "1"
cooldown = int(sys.argv[12] or "30")
try:
    st = json.loads(state_path.read_text()) if state_path.exists() else {"seen_ids": [], "since": 0}
except json.JSONDecodeError:
    st = {"seen_ids": [], "since": 0}
if not isinstance(st, dict):
    st = {"seen_ids": [], "since": 0}
st["channel_id"] = cid
out = filter_wakes(
    data,
    state=st,
    self_pk=self_pk,
    names=names,
    pubkeys=[self_pk] if self_pk else [],
    seat_role=role,
    require_mention=require,
    is_dm=is_dm,
    now_unix=int(time.time()),
    cooldown_secs=cooldown,
)
state_path.write_text(json.dumps(out["state"], indent=2) + "\n")
if out.get("cooldown"):
    print(f"VISITOR_COOLDOWN seat={seat} channel={cid} pending={out.get('pending')}", file=sys.stderr)
if out.get("overflow"):
    print(f"VISITOR_ADMIT overflow seat={seat} channel={cid} pending={out.get('pending')}", file=sys.stderr)
for w in out.get("wakes") or []:
    print(
        f"VISITOR_WAKE match seat={seat} room={room} channel={cid} "
        f"reason={w.get('reason')} from={(w.get('from') or '')[:12]} "
        f"id={(w.get('id') or '')[:12]} preview={w.get('preview')}"
    )
PY
}

if [[ ! -f "$STATE" ]]; then
  json="$(visitor_run messages get --channel "$CID" --limit "$LIMIT" 2>/dev/null || echo '[]')"
  python3 - "$json" "$STATE" "$CID" <<'PY'
import json,sys,time
from pathlib import Path
try:
    data=json.loads(sys.argv[1] or "[]")
except json.JSONDecodeError:
    data=[]
if not isinstance(data, list):
    data=[]
ids=[m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
max_ts=max([int(m.get("created_at") or 0) for m in data if isinstance(m, dict)] or [int(time.time())])
Path(sys.argv[2]).write_text(json.dumps({"since": max_ts, "seen_ids": ids[-50:], "channel_id": sys.argv[3], "last_wake": 0}, indent=2)+"\n")
PY
  echo "VISITOR_OK seeded seat=$SEAT channel=$CID" >>"$LOG"
fi

if [[ "$ONCE" == "1" ]]; then
  poll_once
  exit 0
fi
while true; do
  poll_once || true
  sleep "$TICK"
done
