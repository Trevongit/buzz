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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --room) ROOM="$2"; shift 2 ;;
    --seat) SEAT="$2"; shift 2 ;;
    --once) ONCE=1; shift ;;
    --secs) TICK="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: wake.sh [--room name|uuid] [--seat ID] [--once] [--secs N]"
      echo "  VISITOR_REQUIRE_MENTION=1 (default)  VISITOR_ROLE=grok|codex|agy"
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

visitor_load_seat_env "$SEAT"
DIR="$(visitor_seat_dir "$SEAT")"
if [[ -z "$ROOM" && -f "${DIR}/last-room.json" ]]; then
  ROOM="$(python3 -c 'import json; d=json.load(open("'"$DIR"'/last-room.json")); print(d.get("channel_id") or d.get("name") or "")')"
fi
if [[ -z "$ROOM" ]]; then
  echo "VISITOR_FAIL no room — set --room or join first" >&2
  exit 1
fi
CID="$(visitor_resolve_room "$ROOM")"
SELF="${BUZZ_PUBLIC_KEY:-}"
ROLE="${VISITOR_ROLE:-grok}"
NAMES="${VISITOR_NAMES:-$SEAT}"
REQUIRE="${VISITOR_REQUIRE_MENTION:-1}"
IS_DM=0
if [[ "${ROOM}" == DM-* ]] || [[ "${VISITOR_IS_DM:-0}" == "1" ]]; then
  IS_DM=1
fi

STATE="${DIR}/visitor-wake-${CID}.json"
poll_once() {
  local json
  json="$(visitor_run messages get --channel "$CID" --limit "$LIMIT" 2>/dev/null || true)"
  json="${json#"${json%%[![:space:]]*}"}"
  if [[ -z "$json" ]] || [[ "${json:0:1}" != '[' && "${json:0:1}" != '{' ]]; then
    json='[]'
  fi
  python3 - "$json" "$STATE" "$SELF" "$SEAT" "$CID" "$ROOM" "$ROLE" "$NAMES" "$REQUIRE" "$IS_DM" "$VISITOR_ROOT" <<'PY'
import json, sys
from pathlib import Path

sys.path.insert(0, sys.argv[11])
from gate import admit_budget, should_wake

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
pubkeys = [self_pk] if self_pk else []

try:
    st = json.loads(state_path.read_text()) if state_path.exists() else {"seen_ids": [], "since": 0}
except json.JSONDecodeError:
    st = {"seen_ids": [], "since": 0}
seen = set(st.get("seen_ids") or [])
since = int(st.get("since") or 0)
new_max = since
candidates = []
for m in data:
    if not isinstance(m, dict):
        continue
    mid = m.get("id") or ""
    ts = int(m.get("created_at") or 0)
    pk = m.get("pubkey") or ""
    if mid and mid in seen:
        if ts > new_max:
            new_max = ts
        continue
    if mid:
        seen.add(mid)
    if ts > new_max:
        new_max = ts
    content = (m.get("content") or "").replace("\n", " ").strip()
    wake, reason = should_wake(
        content=m.get("content") or "",
        from_pubkey=pk,
        self_pubkey=self_pk,
        is_dm=is_dm,
        require_mention=require,
        names=names,
        pubkeys=pubkeys,
        seat_role=role,
    )
    if not wake:
        continue
    preview = content[:80].replace('"', "'")
    candidates.append({
        "id": mid,
        "ts": ts,
        "from": pk,
        "preview": preview,
        "content": m.get("content") or "",
        "reason": reason,
    })
kept, overflow = admit_budget(candidates)
st["seen_ids"] = list(seen)[-80:]
st["since"] = new_max
st["channel_id"] = cid
state_path.write_text(json.dumps(st, indent=2) + "\n")
if overflow:
    print(f"VISITOR_ADMIT overflow seat={seat} channel={cid} pending={len(candidates)}", file=sys.stderr)
for w in kept:
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
Path(sys.argv[2]).write_text(json.dumps({"since": max_ts, "seen_ids": ids[-50:], "channel_id": sys.argv[3]}, indent=2)+"\n")
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
