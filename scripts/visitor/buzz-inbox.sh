#!/usr/bin/env bash
# One ear for every vendor seat: buzz feed get. Idle = 0 model tokens.
# Stdout is VISITOR_WAKE lines (same as wake.sh). Codex/agy/Grok all use this.
set -euo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

SEAT="$(visitor_resolve_seat)"
TICK="${VISITOR_WATCH_SECS:-15}"
LIMIT="${VISITOR_WATCH_LIMIT:-40}"
ONCE="${VISITOR_WAKE_ONCE:-0}"
TYPES="${VISITOR_FEED_TYPES:-mentions,needs_action,activity}"
LOG="${VISITOR_WATCHER_LOG:-/tmp/visitor-inbox.log}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seat) SEAT="$2"; shift 2 ;;
    --once) ONCE=1; shift ;;
    --secs) TICK="$2"; shift 2 ;;
    --types) TYPES="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: buzz-inbox.sh [--seat ID] [--once] [--secs N] [--types mentions,needs_action,activity]"
      echo "  One flock-friendly ear. Do not run beside extra_channels wake.sh for the same seat."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

visitor_load_seat_env "$SEAT"
LIMIT="$(visitor_bound_limit "$LIMIT" 100)"
TICK="$(visitor_bound_limit "$TICK" 300)"
DIR="$(visitor_seat_dir "$SEAT")"
SELF="${BUZZ_PUBLIC_KEY:-}"
ROLE="$(visitor_default_role "$SEAT")"
if [[ -z "${VISITOR_NAMES:-}" && -f "${DIR}/PUBLIC.txt" ]]; then
  NAMES="$(python3 "${VISITOR_ROOT}/gate.py" mention-names --dir "$DIR" --seat "$SEAT")"
else
  NAMES="${VISITOR_NAMES:-$SEAT}"
fi
REQUIRE="${VISITOR_REQUIRE_MENTION:-1}"
COOLDOWN="${VISITOR_COOLDOWN_SECS:-30}"
STATE="${DIR}/visitor-feed.json"
DM_FILE="$(visitor_dm_list "$SEAT")"
dm_ids=""
if [[ -f "$DM_FILE" ]]; then
  dm_ids="$(tr '\n' ',' <"$DM_FILE" | sed 's/,$//')"
fi
OWNED_FILE="${DIR}/owned-channels"
owned_ids=""
if [[ -f "$OWNED_FILE" ]]; then
  owned_ids="$(tr '\n' ',' <"$OWNED_FILE" | sed 's/,$//')"
fi

poll_once() {
  local since json out
  since="$(python3 -c 'import json,sys; from pathlib import Path
p=Path(sys.argv[1])
st={}
if p.is_file():
    try: st=json.loads(p.read_text())
    except Exception: st={}
print(int(st.get("since") or 0))
' "$STATE")"
  json="$(visitor_run feed get --since "$since" --limit "$LIMIT" --types "$TYPES" 2>/dev/null || true)"
  json="${json#"${json%%[![:space:]]*}"}"
  if [[ -z "$json" || "${json:0:1}" != '[' ]]; then
    json='[]'
  fi
  out="$(printf '%s\n' "$json" | python3 "${VISITOR_ROOT}/gate.py" feed-wakes \
      --state "$STATE" --self "$SELF" --names "$NAMES" --role "$ROLE" \
      --require "$REQUIRE" --dm-ids "$dm_ids" --owned-ids "$owned_ids" 2>/dev/null || true)"
  python3 - "$out" "$SEAT" "${VISITOR_JEV:-0}" "${VISITOR_ROOT}" <<'PY'
import json, sys
from pathlib import Path
try:
    blob = json.loads(sys.argv[1] or "{}")
except json.JSONDecodeError:
    blob = {}
seat = sys.argv[2]
jev_on = (sys.argv[3] or "0").strip().lower() in ("1", "true", "yes", "on")
jev_root = Path(sys.argv[4]) / "jev"
if jev_on:
    sys.path.insert(0, str(jev_root))
    try:
        from route import route_wake, write_state
    except Exception:
        route_wake = None
        write_state = None
else:
    route_wake = None
    write_state = None
for w in blob.get("wakes") or []:
    if not isinstance(w, dict):
        continue
    cid = w.get("channel") or ""
    frm = (w.get("from") or "")[:12]
    eid = w.get("id") or ""
    prev = w.get("preview") or ""
    reason = w.get("reason") or ""
    print(
        f"VISITOR_WAKE match seat={seat} room={cid} channel={cid} "
        f"reason={reason} from={frm} id={eid} preview={prev}"
    )
    # Grok Build monitor() matches this prefix (same as buzz-watcher.sh).
    print(
        f"BUZZ_WAKE match seat={seat} room=feed channel={cid} "
        f"since=0 from={frm} id={eid} preview={prev}"
    )
    if not jev_on:
        continue
    if route_wake is None:
        print(f"JEV_FAIL seat={seat} id={eid} error=import")
        continue
    try:
        d = route_wake(w)
        if write_state is not None:
            write_state(d, w)
        err = d.get("error") or ""
        line = (
            f"JEV_DECIDE seat={seat} id={eid} action={d.get('action')} "
            f"wall={d.get('wall')} reason={d.get('reason')}"
        )
        if err:
            print(f"JEV_FAIL seat={seat} id={eid} error={err}")
        print(line)
    except Exception as exc:
        print(f"JEV_FAIL seat={seat} id={eid} error={type(exc).__name__}")
PY
}

if [[ ! -f "$STATE" ]]; then
  now="$(date -u +%s)"
  python3 - "$STATE" "$now" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({"since": int(sys.argv[2]), "seen_ids": [], "ear": "feed", "last_wake": 0}, indent=2)+"\n")
PY
  echo "VISITOR_OK seeded-feed seat=$SEAT" >>"$LOG"
fi
JEV_FLAG=0
if [[ "${VISITOR_JEV:-0}" == "1" || "${VISITOR_JEV:-}" == "on" || "${VISITOR_JEV:-}" == "true" ]]; then
  JEV_FLAG=1
fi
echo "BUZZ_OK start seat=$SEAT ear=feed types=$TYPES tick=${TICK}s jev=${JEV_FLAG}"

if [[ "$ONCE" == "1" ]]; then
  poll_once
  exit 0
fi
while true; do
  poll_once || true
  sleep "$TICK"
done
