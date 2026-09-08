#!/usr/bin/env bash
# Prime says "use buzz": pick this seat's community, probe it, open Prime DM.
# Does not mint seats. Does not rewrite agent.env. Portable = PUBLIC.txt bus.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/lib.sh"

SEAT="$(visitor_resolve_seat)"
WANT=""
OWNER="${BUZZ_OWNER_PUBKEY:-}"
DRY=0
ARM=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seat) SEAT="$2"; shift 2 ;;
    --community|--relay|--bus) WANT="$2"; shift 2 ;;
    --owner) OWNER="$2"; shift 2 ;;
    --arm) ARM=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help)
      echo "Usage: use-buzz.sh [--seat ID] [--community name|url] [--owner PUBKEY] [--arm] [--dry-run]"
      echo "  Default community is PUBLIC.txt (portable). Ask Prime if missing."
      echo "  Other bus than PUBLIC.txt is community-mismatch (silent empty room)."
      echo "  --arm prints L2/watcher next-step; does not steal an existing lease."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

DIR="$(visitor_seat_dir "$SEAT")"
if [[ "$DRY" == "1" ]]; then
  report="$(python3 "${ROOT}/gate.py" community-for-seat --dir "$DIR" --want "$WANT")"
  echo "$report"
  python3 -c 'import json,sys; d=json.loads(sys.argv[1]); raise SystemExit(0 if d.get("ok") else 3)' "$report"
  echo "VISITOR_USE dry-run seat=$SEAT"
  exit 0
fi

if [[ ! -f "${DIR}/agent.env" ]]; then
  echo "error: no identity at ${DIR}/agent.env — use an existing seat; do not mint" >&2
  echo "VISITOR_USE fail reason=no-seat" >&2
  echo "Ask Prime: which existing Buzz seat should this visitor use?"
  exit 2
fi

if [[ -z "$OWNER" && -f "${DIR}/owner.json" ]]; then
  OWNER="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("pubkey") or json.load(open(sys.argv[1])).get("owner") or "")' "${DIR}/owner.json" 2>/dev/null || true)"
fi

visitor_load_seat_env "$SEAT" || exit 1
report="$(python3 "${ROOT}/gate.py" community-for-seat --dir "$DIR" --want "$WANT")"
host="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("host") or "")' "$report")"
reason="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("reason") or "")' "$report")"
if ! python3 -c 'import json,sys; raise SystemExit(0 if json.loads(sys.argv[1]).get("ok") else 3)' "$report"; then
  echo "VISITOR_USE fail reason=$reason host=$host want=$WANT seat=$SEAT" >&2
  case "$reason" in
    community-missing)
      echo "Ask Prime: which Buzz community should this seat use? (name, URL, or invite)"
      ;;
    community-mismatch)
      echo "Ask Prime: seat community is $host; requested $WANT is a different bus (silent empty room)."
      ;;
    *)
      echo "Ask Prime: Buzz community is not ready ($reason)."
      ;;
  esac
  exit 3
fi

if ! timeout 8s visitor_run --format compact channels list >/dev/null 2>&1; then
  echo "VISITOR_USE fail reason=community-unavailable host=$host seat=$SEAT" >&2
  echo "Tell Prime: community $host is not reachable right now."
  exit 3
fi

DM=""
if [[ -n "$OWNER" ]]; then
  dm_json="$(visitor_run --format compact dms open --pubkey "$OWNER" 2>/dev/null || true)"
  DM="$(python3 -c 'import json,sys
raw=sys.argv[1].strip()
if not raw:
    raise SystemExit(0)
try:
    d=json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(0)
print(d.get("dm_id") or d.get("channel_id") or d.get("id") or "")
' "$dm_json" 2>/dev/null || true)"
  if [[ -n "$DM" ]]; then
    visitor_mark_dm "$SEAT" "$DM" || true
  fi
else
  echo "VISITOR_USE note=no-owner-dm (set BUZZ_OWNER_PUBKEY or owner.json)" >&2
fi

LAST=""
if visitor_assert_last_room_bus "$DIR" 2>/dev/null; then
  LAST="$(visitor_last_room "$DIR" || true)"
fi

echo "VISITOR_USE ok seat=$SEAT host=$host dm=${DM:-none} last_room=${LAST:-none}"
ROLE="$(visitor_default_role "$SEAT")"
if [[ "$ROLE" == "grok" ]]; then
  echo "next: monitor(buzz-watcher.sh) with BUZZ_WATCH_EXTRA_CHANNELS=${DM}"
else
  if [[ -n "$LAST" && -n "$DM" ]]; then
    echo "next: auto-reply.sh --seat $SEAT --room $LAST --dm $DM"
  elif [[ -n "$DM" ]]; then
    echo "next: auto-reply.sh --seat $SEAT --dm $DM"
  else
    echo "next: auto-reply.sh --seat $SEAT --room <uuid> --dm <prime-dm-uuid>"
  fi
fi

if [[ "$ARM" == "1" && "$ROLE" != "grok" ]]; then
  if [[ -f "${DIR}/l2-lease.json" ]] && ! python3 "${ROOT}/gate.py" l2-lease --action stale --file "${DIR}/l2-lease.json" >/dev/null; then
    echo "VISITOR_USE already-armed seat=$SEAT"
    exit 0
  fi
  echo "VISITOR_USE note=not-starting-l2 (start auto-reply from the session; do not stack)"
fi
