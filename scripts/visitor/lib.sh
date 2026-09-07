#!/usr/bin/env bash
# Portable Buzz visitor helpers. Key stays in seat agent.env — never argv.
# shellcheck shell=bash
set -euo pipefail

VISITOR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export VISITOR_ROOT

visitor_default_relay() {
  echo "${BUZZ_RELAY_URL:-https://groundfeed.communities.buzz.xyz}"
}

visitor_resolve_seat() {
  if [[ -n "${BUZZ_SEAT_ID:-}" ]]; then
    echo "$BUZZ_SEAT_ID"
    return
  fi
  local root base
  root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [[ -n "$root" ]]; then
    base="$(basename "$root")"
  else
    base="$(basename "$(pwd)")"
  fi
  base="$(echo "$base" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//;s/[[:space:]]\+/-/g')"
  base="$(echo "$base" | tr -cd '[:alnum:]._-' | sed 's/^-\+//;s/-\+$//')"
  echo "${base:-default}"
}

visitor_seat_dir() {
  local seat="${1:-$(visitor_resolve_seat)}"
  local home="${VISITOR_AGENTS_HOME:-$HOME/.buzz-dev/agents}"
  echo "${home}/${seat}"
}

visitor_dm_list() {
  echo "$(visitor_seat_dir "${1:-}")/dm-channels.txt"
}

visitor_mark_dm() {
  local seat="${1:-}" cid="${2:-}" f
  [[ -n "$seat" && -n "$cid" ]] || return 1
  f="$(visitor_dm_list "$seat")"
  mkdir -p "$(dirname "$f")"
  if [[ -f "$f" ]] && grep -qx "$cid" "$f"; then
    return 0
  fi
  echo "$cid" >>"$f"
}

visitor_channel_is_dm() {
  local seat="${1:-}" room="${2:-}" f
  [[ "$room" == DM-* ]] && return 0
  [[ "${VISITOR_IS_DM:-0}" == "1" ]] && return 0
  f="$(visitor_dm_list "$seat")"
  [[ -f "$f" ]] && grep -qx "$room" "$f"
}

visitor_default_role() {
  if [[ -n "${VISITOR_ROLE:-}" ]]; then
    echo "$VISITOR_ROLE"
    return
  fi
  local seat="${1:-$(visitor_resolve_seat)}"
  python3 "${VISITOR_ROOT}/gate.py" role-from-seat --seat "$seat"
}

visitor_find_cli() {
  if [[ -n "${BUZZ_CLI:-}" && -x "${BUZZ_CLI}" ]]; then
    echo "$BUZZ_CLI"
    return 0
  fi
  if command -v buzz >/dev/null 2>&1; then
    command -v buzz
    return 0
  fi
  local c
  for c in "${HOME}/.local/bin/buzz"; do
    if [[ -x "$c" ]]; then
      echo "$c"
      return 0
    fi
  done
  echo "error: buzz CLI not found. Build buzz-cli or set BUZZ_CLI." >&2
  return 1
}

visitor_assert_from_role() {
  local seat="${1:-}"
  local from_role="${2:-}"
  local derived
  derived="$(python3 "${VISITOR_ROOT}/gate.py" role-from-seat --seat "$seat" | tr -d '\n')"
  if [[ -n "$derived" && -n "$from_role" && "$derived" != "$from_role" ]]; then
    echo "error: from=$from_role does not match seat $seat (maps to $derived)" >&2
    echo "VISITOR_COLLAB skip reason=from-role-mismatch" >&2
    return 1
  fi
  return 0
}

visitor_assert_public_relay() {
  local seat="${1:-}"
  local dir out reason
  dir="$(visitor_seat_dir "$seat")"
  out="$(python3 "${VISITOR_ROOT}/gate.py" public-env --dir "$dir" --relay "${BUZZ_RELAY_URL:-}" || true)"
  if python3 -c 'import json,sys; raise SystemExit(0 if json.loads(sys.argv[1] or "{}").get("ok") else 3)' "$out"; then
    return 0
  fi
  reason="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1] or "{}").get("reason") or "public-env-mismatch")' "$out" 2>/dev/null || echo public-env-mismatch)"
  echo "error: PUBLIC.txt host does not match BUZZ_RELAY_URL (silent empty room)" >&2
  echo "VISITOR_COLLAB skip reason=${reason}" >&2
  return 3
}

visitor_load_seat_env() {
  local seat="${1:-$(visitor_resolve_seat)}"
  local dir envf pub
  dir="$(visitor_seat_dir "$seat")"
  envf="${dir}/agent.env"
  if [[ ! -f "$envf" ]]; then
    echo "error: no identity at $envf — use an existing seat; do not mint one from this kit" >&2
    return 1
  fi
  # shellcheck disable=SC1090
  set -a
  source "$envf"
  set +a
  # Process-only fill from PUBLIC.txt when agent.env omitted a URL.
  # Never rewrite agent.env. Mismatch vs PUBLIC.txt is fail-closed.
  pub="$(python3 "${VISITOR_ROOT}/gate.py" relay-from-dir --dir "$dir")"
  if [[ -z "${BUZZ_RELAY_URL:-}" && -n "$pub" ]]; then
    export BUZZ_RELAY_URL="$pub"
  else
    export BUZZ_RELAY_URL="${BUZZ_RELAY_URL:-$(visitor_default_relay)}"
  fi
  if [[ -z "${BUZZ_PRIVATE_KEY:-}" ]]; then
    echo "error: BUZZ_PRIVATE_KEY missing in $envf" >&2
    return 1
  fi
  visitor_assert_public_relay "$seat"
}

visitor_run() {
  local cli
  cli="$(visitor_find_cli)"
  "$cli" --relay "${BUZZ_RELAY_URL}" "$@"
}

visitor_assert_last_room_bus() {
  local dir="${1:-}"
  local out reason
  out="$(python3 "${VISITOR_ROOT}/gate.py" last-room-bus --dir "$dir" || true)"
  if python3 -c 'import json,sys; raise SystemExit(0 if json.loads(sys.argv[1] or "{}").get("ok") else 3)' "$out"; then
    return 0
  fi
  reason="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1] or "{}").get("reason") or "last-room-bus-mismatch")' "$out" 2>/dev/null || echo last-room-bus-mismatch)"
  echo "error: last-room.json relay does not match PUBLIC.txt (silent empty room)" >&2
  echo "VISITOR_COLLAB skip reason=${reason}" >&2
  return 3
}

visitor_last_room() {
  local dir="${1:-}"
  local f="${dir}/last-room.json"
  if [[ ! -f "$f" ]]; then
    return 1
  fi
  python3 -c 'import json,sys
from pathlib import Path
p=Path(sys.argv[1])
try:
    d=json.loads(p.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)
if not isinstance(d, dict):
    raise SystemExit(1)
print((d.get("channel_id") or d.get("name") or "").strip())
' "$f"
}

visitor_bound_limit() {
  local n="${1:-20}"
  local max="${2:-100}"
  if ! [[ "$n" =~ ^[1-9][0-9]*$ ]]; then
    echo "20"
    return
  fi
  if (( n > max )); then
    echo "$max"
  else
    echo "$n"
  fi
}

visitor_same_bus() {
  local from_role="$1"
  local to_role="$2"
  local home="$3"
  local role_seats="${4:-}"
  local bus_json reason
  local bus=(same-bus --from "$from_role" --to "$to_role" --home "$home")
  if [[ -n "$role_seats" ]]; then
    bus+=(--role-seats "$role_seats")
  fi
  bus_json="$(python3 "${VISITOR_ROOT}/gate.py" "${bus[@]}" || true)"
  if python3 -c 'import json,sys; raise SystemExit(0 if json.loads(sys.argv[1] or "{}").get("ok") else 3)' "$bus_json"; then
    return 0
  fi
  reason="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1] or "{}").get("reason") or "mixed-or-missing")' "$bus_json" 2>/dev/null || echo mixed-or-missing)"
  echo "error: COLLAB to=$to_role is not on the same relay bus as from=$from_role" >&2
  echo "VISITOR_COLLAB skip reason=${reason}" >&2
  return 3
}

visitor_resolve_room() {
  local room="$1"
  if [[ "$room" =~ ^[0-9a-fA-F]{8}- ]]; then
    echo "$room"
    return 0
  fi
  export ROOM_Q="$room"
  local list
  list="$(visitor_run channels list)"
  python3 -c '
import json,os,sys
want=os.environ["ROOM_Q"].strip().lower().lstrip("#")
data=json.load(sys.stdin)
for ch in data:
    name=(ch.get("name") or "").lower()
    if name==want or want in name:
        print(ch["channel_id"]); raise SystemExit
sys.exit(4)
' <<<"$list"
}
