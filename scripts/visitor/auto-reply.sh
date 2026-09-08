#!/usr/bin/env bash
# L2 on VISITOR_WAKE: one print-mode brain turn, then idle again (0 tokens).
# Codex/agy TUIs do not consume wake.sh stdout — without this, DMs sit forever.
# Grok Build uses monitor(buzz-watcher.sh) instead; this path no-ops grok.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/lib.sh"

SEAT="$(visitor_resolve_seat)"
ROOMS=()
DMS=()
DRY=0
ONCE=0
CATCH=0
TICK="${VISITOR_WATCH_SECS:-15}"
TO="${VISITOR_TURN_TIMEOUT_SECS:-180}"
LOG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seat) SEAT="$2"; shift 2 ;;
    --room) ROOMS+=("$2"); shift 2 ;;
    --dm) DMS+=("$2"); shift 2 ;;
    --secs) TICK="$2"; shift 2 ;;
    --timeout) TO="$2"; shift 2 ;;
    --once) ONCE=1; shift ;;
    --catch-up) CATCH=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help)
      echo "Usage: auto-reply.sh --seat ID --room UUID [--dm UUID] [--once] [--catch-up] [--dry-run]"
      echo "  --dm UUID  admit without @mention (Prime DMs). Rooms stay mention-gated."
      echo "  Idle = wake.sh. On VISITOR_WAKE, kit posts one print-mode body."
      echo "  Grok: use monitor(buzz-watcher.sh). Do not mint seats. Do not rewrite agent.env."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

ROLE="$(visitor_default_role "$SEAT")"
if [[ -z "$ROLE" ]]; then
  ROLE="$(python3 "${ROOT}/gate.py" role-from-seat --seat "$SEAT")"
fi
if [[ "$ROLE" == "grok" ]]; then
  echo "VISITOR_TURN skip seat=$SEAT reason=grok-uses-monitor" >&2
  exit 2
fi
TICK="$(visitor_bound_limit "$TICK" 300)"
TO="$(visitor_bound_limit "$TO" 300)"

if [[ "$DRY" != "1" ]]; then
  visitor_load_seat_env "$SEAT"
fi
# Own cursor so a TUI wake.sh on the same UUID cannot eat L2 wakes.
export VISITOR_WAKE_STATE_PREFIX="${VISITOR_WAKE_STATE_PREFIX:-l2-}"
DIR="$(visitor_seat_dir "$SEAT")"
LOG="${VISITOR_AUTO_REPLY_LOG:-${DIR}/auto-reply.log}"
LEASE_JSON="${DIR}/l2-lease.json"
LEASE_TTL="${VISITOR_L2_LEASE_TTL_SECS:-300}"
LEASE_EPOCH=""
if [[ "$DRY" != "1" ]]; then
  mkdir -p "$DIR"
  exec 9>"${DIR}/l2-lease.lock"
  if ! flock -n 9; then
    if python3 "${ROOT}/gate.py" l2-lease --action stale --file "$LEASE_JSON" --ttl "$LEASE_TTL" >/dev/null; then
      echo "VISITOR_TURN fail seat=$SEAT reason=lease-held-stale" >&2
    else
      echo "VISITOR_TURN fail seat=$SEAT reason=lease-held" >&2
    fi
    exit 1
  fi
  LEASE_EPOCH="$(python3 "${ROOT}/gate.py" l2-lease --action take --file "$LEASE_JSON" --pid "$$" --ttl "$LEASE_TTL")"
fi

if [[ "$CATCH" == "1" && "$ONCE" != "1" ]]; then
  echo "error: --catch-up requires --once" >&2
  exit 1
fi

room_is_forced_dm() {
  local r="$1" d
  for d in "${DMS[@]+"${DMS[@]}"}"; do
    [[ "$d" == "$r" ]] && return 0
  done
  return 1
}

if [[ ${#DMS[@]} -gt 0 ]]; then
  ROOMS+=("${DMS[@]}")
  if [[ "$DRY" != "1" ]]; then
    for d in "${DMS[@]}"; do
      visitor_mark_dm "$SEAT" "$d" || true
    done
  fi
fi
if [[ ${#ROOMS[@]} -eq 0 ]]; then
  if [[ "$DRY" == "1" ]]; then
    echo "error: --room required" >&2
    exit 1
  fi
  visitor_assert_last_room_bus "$DIR" || exit 3
  last="$(visitor_last_room "$DIR" || true)"
  if [[ -z "$last" ]]; then
    echo "error: --room required" >&2
    exit 1
  fi
  ROOMS=("$last")
fi

brain_argv() {
  local cwd
  case "$ROLE" in
    grok)
      echo "error: grok auto-reply is monitor(buzz-watcher.sh) not print-mode" >&2
      return 2
      ;;
    agy)
      echo "agy --print-timeout ${TO}s --mode=accept-edits --dangerously-skip-permissions --print=<prompt-file>"
      ;;
    codex)
      cwd="${VISITOR_CODEX_ROOT:-${DIR}/l2-scratch}"
      echo "codex exec --ephemeral --skip-git-repo-check -s read-only -C ${cwd} -"
      ;;
    *)
      echo "error: no print-mode brain for role=$ROLE" >&2
      return 2
      ;;
  esac
}

write_prompt() {
  local room="$1" preview="$2" hist="$3" out="$4" must="${5:-0}" hint
  hint="$(printf '%s' "$hist" | python3 "${ROOT}/gate.py" l2-hint --preview "$preview" 2>/dev/null || true)"
  cat >"$out" <<EOF
You are Buzz visitor seat ${SEAT} role ${ROLE}. A mention-gated or DM event woke you.
Channel: ${room}
Preview: ${preview}
Dest: ${hint:-none}

Write ONLY the message body to post (phone-safe bullets, short). No tools. No fences.
No nsec. Do not ping Helix/PATCH/Prism/Ember. Do not mint seats.
Vendor team: Grok steward/kit, Codex volume+safety, agy Google-class scout (not agy-acp).
One NEW finding per post. Duplicate skip is the kit (same-body hash), not your job.
Do not treat a first line that greets Prime (Trevor) as silence when Dest names you or all.

NO_REPLY is allowed only when you are not the dest (no COLLAB to: ${ROLE}|all, no @mention, not a DM).
EOF
  if [[ "$ROLE" == "codex" ]]; then
    cat >>"$out" <<'EOF'
Codex workflow: fail-closed safety + bounded volume. TUI is listen-only. This L2 post is Buzz evidence.
TTY (collab.sh --dry-run) is for tight pairs with agy before promoting. Turbo is house spawn, not this seat.
One safety finding. Then COLLAB to: agy or leave idle. Do not to: all. Do not start a second auto-reply.
EOF
  fi
  if [[ "$must" == "1" ]]; then
    cat >>"$out" <<EOF
MUST REPLY: Dest is you. Do not output NO_REPLY. Write one new phone-safe bullet from your role, then idle.
EOF
  fi
  cat >>"$out" <<EOF

History (bounded):
${hist}
EOF
}

invoke_brain() {
  local cwd
  : >"$out_file"
  case "$ROLE" in
    grok)
      echo "VISITOR_TURN skip seat=$SEAT reason=grok-uses-monitor" >&2
      return 2
      ;;
    agy)
      cwd="${VISITOR_AGY_ROOT:-${DIR}/l2-scratch}"
      mkdir -p "$cwd"
      if [[ -d "$cwd/.git" ]]; then
        echo "VISITOR_TURN fail seat=$SEAT reason=repo-cwd" >&2
        return 1
      fi
      if ! ( cd "$cwd" && env -u BUZZ_PRIVATE_KEY -u BUZZ_NSEC -u BUZZ_AUTH_TAG \
          timeout "${TO}s" agy --print-timeout "${TO}s" \
          --mode=accept-edits --dangerously-skip-permissions \
          --print="$(cat "$prompt_file")" >"$out_file" ) >>"$LOG" 2>&1; then
        echo "VISITOR_TURN fail seat=$SEAT room=$room reason=agy-print" >&2
        return 1
      fi
      ;;
    codex)
      cwd="${VISITOR_CODEX_ROOT:-${DIR}/l2-scratch}"
      mkdir -p "$cwd"
      if [[ -d "$cwd/.git" ]]; then
        echo "VISITOR_TURN fail seat=$SEAT reason=repo-cwd" >&2
        return 1
      fi
      if ! env -u BUZZ_PRIVATE_KEY -u BUZZ_NSEC -u BUZZ_AUTH_TAG \
        timeout "${TO}s" codex exec --ephemeral --skip-git-repo-check \
        -s read-only -C "$cwd" -o "$out_file" - \
        <"$prompt_file" >>"$LOG" 2>&1; then
        echo "VISITOR_TURN fail seat=$SEAT room=$room reason=codex-exec" >&2
        return 1
      fi
      ;;
    *)
      echo "VISITOR_TURN fail seat=$SEAT reason=unknown-role" >&2
      return 2
      ;;
  esac
  python3 "${ROOT}/gate.py" redact-log --file "$LOG" || true
}

run_turn() {
  local room="$1" preview="$2" hist="${3:-}" wake_id="${4:-}" prompt_file out_file
  local names noreply_reason dm_flag=0
  echo "VISITOR_TURN start seat=$SEAT role=$ROLE room=$room preview=${preview:0:80}"
  echo "VISITOR_STATE state=generating seat=$SEAT role=$ROLE room=$room"
  if [[ "$DRY" == "1" ]]; then
    brain_argv || true
    echo "VISITOR_TURN dry-run seat=$SEAT role=$ROLE"
    return 0
  fi
  prompt_file="${DIR}/auto-reply-prompt.txt"
  out_file="${DIR}/auto-reply-out.txt"
  names="${SEAT},${ROLE}"
  if room_is_forced_dm "$room" || visitor_channel_is_dm "$SEAT" "$room"; then
    dm_flag=1
  fi
  write_prompt "$room" "$preview" "$hist" "$prompt_file" 0
  chmod 600 "$prompt_file" 2>/dev/null || true
  invoke_brain || return $?
  if grep -qx 'NO_REPLY' "$out_file" 2>/dev/null; then
    noreply_reason="$(
      printf '%s' "$hist" | python3 "${ROOT}/gate.py" l2-noreply \
        --role "$ROLE" --names "$names" --preview "$preview" --dm "$dm_flag" \
        2>/dev/null || true
    )"
    if [[ "$noreply_reason" != "noreply-ok" ]]; then
      echo "VISITOR_STATE state=retry-must-reply seat=$SEAT room=$room reason=${noreply_reason:-collab-must-reply}"
      write_prompt "$room" "$preview" "$hist" "$prompt_file" 1
      invoke_brain || return $?
    fi
  fi
  if grep -qx 'NO_REPLY' "$out_file" 2>/dev/null; then
    echo "VISITOR_TURN skip seat=$SEAT room=$room reason=no-reply"
    return 0
  fi
  if [[ ! -s "$out_file" ]]; then
    echo "VISITOR_TURN fail seat=$SEAT room=$room reason=empty-reply" >&2
    return 1
  fi
  if grep -Eiq 'nsec1[a-z0-9]{20,}|BUZZ_PRIVATE_KEY[[:space:]]*=' "$out_file"; then
    echo "VISITOR_TURN fail seat=$SEAT room=$room reason=secret-in-body" >&2
    return 1
  fi
  local journal="${DIR}/l2-posted.json"
  if python3 "${ROOT}/gate.py" l2-body --action check \
      --file "$journal" --room "$room" --body-file "$out_file"; then
    echo "VISITOR_TURN skip seat=$SEAT room=$room reason=same-body"
    return 0
  fi
  if [[ -n "${LEASE_EPOCH:-}" ]]; then
    if ! python3 "${ROOT}/gate.py" l2-lease --action check \
        --file "$LEASE_JSON" --pid "$$" --epoch "$LEASE_EPOCH" --ttl "$LEASE_TTL" >/dev/null; then
      echo "VISITOR_TURN fail seat=$SEAT room=$room reason=stale-lease" >&2
      return 1
    fi
  fi
  echo "VISITOR_STATE state=posting seat=$SEAT room=$room"
  python3 "${ROOT}/gate.py" l2-body --action inflight-begin \
    --file "$journal" --room "$room" --body-file "$out_file" --wake "${wake_id:-}" || true
  local post_out="" post_rc=0
  post_out="$(bash "${ROOT}/post.sh" --seat "$SEAT" --room "$room" --file "$out_file" 2>>"$LOG")" || post_rc=$?
  local posted_id=""
  posted_id="$(printf '%s\n' "$post_out" | python3 "${ROOT}/gate.py" parse-send-id 2>/dev/null || true)"
  if [[ -z "$posted_id" ]]; then
    posted_id="$(printf '%s\n' "$post_out" | sed -n 's/^VISITOR_POST event_id=//p' | tail -1)"
  fi
  if [[ -z "$posted_id" && -f "$LOG" ]]; then
    posted_id="$(python3 "${ROOT}/gate.py" parse-send-id <"$LOG" 2>/dev/null || true)"
  fi
  python3 "${ROOT}/gate.py" redact-log --file "$LOG" || true
  if [[ -n "$posted_id" ]]; then
    python3 "${ROOT}/gate.py" l2-body --action record \
      --file "$journal" --room "$room" --body-file "$out_file" --event "$posted_id" || true
    echo "VISITOR_STATE state=posted seat=$SEAT room=$room event_id=$posted_id"
    echo "VISITOR_TURN ok seat=$SEAT room=$room event_id=$posted_id"
    if [[ -n "$wake_id" && "$wake_id" != "catch" ]]; then
      python3 "${ROOT}/gate.py" l2-posted --action record \
        --file "$journal" --wake "$wake_id" --event "$posted_id" || true
    fi
    return 0
  fi
  echo "VISITOR_STATE state=failed seat=$SEAT room=$room reason=post-idempotent"
  echo "VISITOR_TURN fail seat=$SEAT room=$room reason=post-no-unsee rc=${post_rc}" >&2
  return 4
}

unsee_wake() {
  local room="$1" eid="$2" state
  [[ -n "$eid" && "$eid" != "catch" ]] || return 0
  state="${DIR}/visitor-wake-${VISITOR_WAKE_STATE_PREFIX:-}${room}.json"
  python3 - "$state" "$eid" <<'PY'
import json, sys
from pathlib import Path
p, eid = Path(sys.argv[1]), sys.argv[2]
if not p.is_file() or not eid:
    raise SystemExit(0)
try:
    st = json.loads(p.read_text(encoding="utf-8"))
except json.JSONDecodeError:
    raise SystemExit(0)
if not isinstance(st, dict):
    raise SystemExit(0)
seen = [x for x in (st.get("seen_ids") or []) if x != eid and not str(x).startswith(eid)]
st["seen_ids"] = seen[-80:]
st["last_wake"] = 0
p.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
PY
}

hist_for() {
  local room="$1"
  if [[ "$DRY" == "1" ]]; then
    echo "(dry-run: no relay read)"
    return 0
  fi
  visitor_run --format compact messages get --channel "$room" --limit 8 2>/dev/null \
    | python3 -c 'import sys; t=sys.stdin.read(); print(t[-2048:] if t else "(empty)")'
}

poll_room() {
  local room="$1" wake parsed preview hist eid
  if [[ "$DRY" == "1" ]]; then
    run_turn "$room" "dry" "(dry-run: no relay read)"
    return 0
  fi
  wake_args=(--seat "$SEAT" --room "$room" --once)
  if room_is_forced_dm "$room" || visitor_channel_is_dm "$SEAT" "$room"; then
    wake_args+=(--dm)
  fi
  wake="$(
    VISITOR_WAKE_ONCE=1 bash "${ROOT}/wake.sh" "${wake_args[@]}" 2>/dev/null || true
  )"
  if [[ "$CATCH" == "1" && -z "$wake" ]]; then
    wake="VISITOR_WAKE match seat=$SEAT room=$room channel=$room reason=catch-up from=prime id=catch preview=catch-up"
  fi
  parsed="$(printf '%s\n' "$wake" | python3 "${ROOT}/gate.py" parse-wake || true)"
  if [[ -z "$parsed" || "$parsed" == "{}" ]]; then
    return 1
  fi
  preview="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1] or "{}").get("preview") or "")' "$parsed")"
  eid="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1] or "{}").get("id") or "")' "$parsed")"
  journal="${DIR}/l2-posted.json"
  if python3 "${ROOT}/gate.py" l2-posted --action check --file "$journal" --wake "$eid"; then
    echo "VISITOR_STATE state=posted seat=$SEAT room=$room reason=already"
    return 0
  fi
  hist="$(hist_for "$room")"
  local rc=0
  set +e
  run_turn "$room" "$preview" "$hist" "$eid"
  rc=$?
  set -e
  if [[ "$rc" -eq 0 ]]; then
    return 0
  fi
  if [[ "$rc" -eq 4 ]]; then
    echo "VISITOR_TURN fail seat=$SEAT room=$room reason=no-unsee-after-send" >&2
    python3 "${ROOT}/gate.py" redact-log --file "$LOG" || true
    return 1
  fi
  if python3 "${ROOT}/gate.py" l2-retry --file "$journal" --wake "$eid"; then
    unsee_wake "$room" "$eid"
  else
    echo "VISITOR_TURN fail seat=$SEAT room=$room reason=retry-exhausted" >&2
  fi
  python3 "${ROOT}/gate.py" redact-log --file "$LOG" || true
  return 1
}

drain_room() {
  local room="$1" n=0
  poll_room "$room" || return 0
  if room_is_forced_dm "$room" || visitor_channel_is_dm "$SEAT" "$room"; then
    while [[ "$n" -lt 3 ]]; do
      n=$((n + 1))
      poll_room "$room" || break
    done
  fi
}

join_rooms_before_seed() {
  local r
  for r in "${ROOMS[@]}"; do
    if room_is_forced_dm "$r" || visitor_channel_is_dm "$SEAT" "$r"; then
      continue
    fi
    bash "${ROOT}/join.sh" --seat "$SEAT" --room "$r" >>"$LOG" 2>&1 || true
  done
}

if [[ "$DRY" == "1" ]]; then
  poll_room "${ROOMS[0]}" || true
  exit 0
fi

# Seed wake cursors after membership. Starting L2 on an unjoined room
# captures an empty head and misses the first mentions (19af73d3).
join_rooms_before_seed

if [[ "$ONCE" == "1" ]]; then
  for r in "${ROOMS[@]}"; do
    drain_room "$r" || true
  done
  exit 0
fi

while true; do
  if [[ -n "${LEASE_EPOCH:-}" ]]; then
    python3 "${ROOT}/gate.py" l2-lease --action heartbeat \
      --file "$LEASE_JSON" --pid "$$" --epoch "$LEASE_EPOCH" >/dev/null || true
  fi
  for r in "${ROOMS[@]}"; do
    drain_room "$r" || true
  done
  sleep "$TICK"
done
