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

# A chosen Off is remembered. A timeout or a crash leaves no row, so this start proceeds.
if [[ -n "$SEAT" ]] && python3 /home/trev/PROJECTS/buzz-control-room/scripts/watcher_hold.py held inbox "$SEAT"; then
  echo "Buzz inbox held. You turned this off. It stays off until you turn it on."
  exit 0
fi

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
OWNED_FILE="${DIR}/owned-channels"

id_list() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  tr '\n' ',' <"$f" | sed 's/,$//'
}

poll_once() {
  local since json out dm_ids owned_ids
  # Reread every tick. A list written after the ear starts must still count.
  dm_ids="$(id_list "$DM_FILE")"
  owned_ids="$(id_list "$OWNED_FILE")"
  since="$(python3 -c 'import json,sys; from pathlib import Path
p=Path(sys.argv[1]); now=int(sys.argv[2])
if not p.is_file():
    print(now); raise SystemExit
try:
    st=json.loads(p.read_text())
    if not isinstance(st, dict):
        raise ValueError("not a dict")
except Exception:
    st={"since": now, "seen_ids": [], "ear": "feed", "last_wake": 0}
    p.write_text(json.dumps(st, indent=2)+"\n")
print(int(st.get("since") or now))
' "$STATE" "$(date -u +%s)")"
  json="$(visitor_run feed get --since "$since" --limit "$LIMIT" --types "$TYPES" 2>/dev/null || true)"
  json="${json#"${json%%[![:space:]]*}"}"
  if [[ -z "$json" || "${json:0:1}" != '[' ]]; then
    json='[]'
  fi
  out="$(printf '%s\n' "$json" | python3 "${VISITOR_ROOT}/gate.py" feed-wakes \
      --state "$STATE" --self "$SELF" --names "$NAMES" --role "$ROLE" \
      --require "$REQUIRE" --dm-ids "$dm_ids" --owned-ids "$owned_ids" \
      --cooldown "${VISITOR_COOLDOWN_SECS:-30}" 2>/dev/null || true)"
  python3 - "$out" "$SEAT" "${VISITOR_JEV:-0}" "${VISITOR_ROOT}" "${VISITOR_OWNER_PK:-}" <<'PY'
import json, sys
from pathlib import Path
try:
    blob = json.loads(sys.argv[1] or "{}")
except json.JSONDecodeError:
    blob = {}
seat = sys.argv[2]
sys.path.insert(0, sys.argv[4])
try:
    from wake_log import note_wake
except Exception:
    note_wake = None
jev_on = (sys.argv[3] or "0").strip().lower() in ("1", "true", "yes", "on")
jev_root = Path(sys.argv[4]) / "jev"
owner_pk = sys.argv[5] if len(sys.argv) > 5 else ""
if jev_on:
    sys.path.insert(0, str(jev_root))
    try:
        from route import route_wake, write_state, should_ring_extras
    except Exception:
        route_wake = None
        write_state = None
        should_ring_extras = None
else:
    route_wake = None
    write_state = None
    should_ring_extras = None
for w in blob.get("wakes") or []:
    if not isinstance(w, dict):
        continue
    cid = w.get("channel") or ""
    frm = (w.get("from") or "")[:12]
    eid = w.get("id") or ""
    prev = w.get("preview") or ""
    reason = w.get("reason") or ""
    ring = True
    d = None
    if jev_on:
        if route_wake is None:
            print(f"JEV_FAIL seat={seat} id={eid} error=import")
        else:
            try:
                d = route_wake(w)
                if write_state is not None:
                    write_state(d, w)
                err = d.get("error") or ""
                if should_ring_extras is not None:
                    ring = should_ring_extras(
                        d.get("action") or "stop",
                        w,
                        owner_pk=owner_pk,
                        error=err,
                        ring=d.get("ring"),
                    )
                else:
                    ring = d.get("ring", True)
                if d.get("ring") is False and err:
                    continue
                if err:
                    print(f"JEV_FAIL seat={seat} id={eid} error={err}")
                print(
                    f"JEV_DECIDE seat={seat} id={eid} action={d.get('action')} "
                    f"wall={d.get('wall')} reason={d.get('reason')}"
                )
            except Exception as exc:
                print(f"JEV_FAIL seat={seat} id={eid} error={type(exc).__name__}")
                ring = True
    if not ring:
        print(
            f"JEV_QUIET seat={seat} id={eid} action={(d or {}).get('action')} "
            f"(extras did not spend a turn)"
        )
        continue
    replay = ""
    if note_wake is not None and eid:
        try:
            mark = note_wake(seat, eid)
        except Exception:
            mark = {}
        if mark.get("kind") == "replay" and mark.get("reply_id"):
            replay = f" replay=1 answered={mark['reply_id']}"
    print(
        f"VISITOR_WAKE match seat={seat} room={cid} channel={cid} "
        f"reason={reason} from={frm} id={eid}{replay} preview={prev}"
    )
    # Grok Build monitor() matches this prefix (same as buzz-watcher.sh).
    print(
        f"BUZZ_WAKE match seat={seat} room=feed channel={cid} "
        f"since=0 from={frm} id={eid} preview={prev}"
    )
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
