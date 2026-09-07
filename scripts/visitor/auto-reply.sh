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
DRY=0
ONCE=0
CATCH=0
TICK="${VISITOR_WATCH_SECS:-15}"
TO="${VISITOR_TURN_TIMEOUT_SECS:-120}"
LOG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seat) SEAT="$2"; shift 2 ;;
    --room) ROOMS+=("$2"); shift 2 ;;
    --secs) TICK="$2"; shift 2 ;;
    --timeout) TO="$2"; shift 2 ;;
    --once) ONCE=1; shift ;;
    --catch-up) CATCH=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help)
      echo "Usage: auto-reply.sh --seat ID --room UUID [--room UUID] [--once] [--catch-up] [--dry-run]"
      echo "  Idle = wake.sh. On VISITOR_WAKE, one agy -p / codex exec turn that must post."
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
DIR="$(visitor_seat_dir "$SEAT")"
LOG="${VISITOR_AUTO_REPLY_LOG:-${DIR}/auto-reply.log}"
if [[ "$DRY" != "1" ]]; then
  mkdir -p "$DIR"
fi

if [[ "$CATCH" == "1" && "$ONCE" != "1" ]]; then
  echo "error: --catch-up requires --once" >&2
  exit 1
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
      cwd="${VISITOR_CODEX_ROOT:-$HOME/PROJECTS/buzz-origin-plus}"
      echo "codex exec --ephemeral --skip-git-repo-check -s danger-full-access -C ${cwd} -"
      ;;
    *)
      echo "error: no print-mode brain for role=$ROLE" >&2
      return 2
      ;;
  esac
}

write_prompt() {
  local room="$1" preview="$2" hist="$3" out="$4"
  cat >"$out" <<EOF
You are Buzz visitor seat ${SEAT} role ${ROLE}. A mention-gated or DM event woke you.
Channel: ${room}
Preview: ${preview}

Read the history below, then reply in-room with extras visitor scripts (key in env, never argv):
  ROOT=${ROOT}
  export BUZZ_SEAT_ID=${SEAT}
  export VISITOR_ROLE=${ROLE}
  bash "\$ROOT/post.sh" --seat ${SEAT} --room ${room} --content "…"
Or: buzz --relay "\$BUZZ_RELAY_URL" messages send --channel ${room} --content "…" --mention <pubkey>

Rules: phone-safe bullets. Do not ping Helix/PATCH/Prism/Ember. Do not mint seats.
Do not rewrite agent.env. Do not print nsec. Do not Custom-harness. If nothing to add, post nothing.
One short reply. Then stop.

History (bounded):
${hist}
EOF
}

run_turn() {
  local room="$1" preview="$2" hist="${3:-}" prompt_file cmd cwd
  echo "VISITOR_TURN start seat=$SEAT role=$ROLE room=$room preview=${preview:0:80}"
  if [[ "$DRY" == "1" ]]; then
    brain_argv || true
    echo "VISITOR_TURN dry-run seat=$SEAT role=$ROLE"
    return 0
  fi
  prompt_file="${DIR}/auto-reply-prompt.txt"
  write_prompt "$room" "$preview" "$hist" "$prompt_file"
  chmod 600 "$prompt_file" 2>/dev/null || true
  case "$ROLE" in
    grok)
      echo "VISITOR_TURN skip seat=$SEAT reason=grok-uses-monitor" >&2
      return 2
      ;;
    agy)
      cwd="${VISITOR_AGY_ROOT:-$HOME/PROJECTS/agy-uni-adapt}"
      if ! ( cd "$cwd" && timeout "${TO}s" agy --print-timeout "${TO}s" \
          --mode=accept-edits --dangerously-skip-permissions \
          --print="$(cat "$prompt_file")" ) >>"$LOG" 2>&1; then
        echo "VISITOR_TURN fail seat=$SEAT room=$room reason=agy-print" >&2
        return 1
      fi
      ;;
    codex)
      cwd="${VISITOR_CODEX_ROOT:-$HOME/PROJECTS/buzz-origin-plus}"
      if ! timeout "${TO}s" codex exec --ephemeral --skip-git-repo-check \
        -s danger-full-access -C "$cwd" - <"$prompt_file" >>"$LOG" 2>&1; then
        echo "VISITOR_TURN fail seat=$SEAT room=$room reason=codex-exec" >&2
        return 1
      fi
      ;;
    *)
      echo "VISITOR_TURN fail seat=$SEAT reason=unknown-role" >&2
      return 2
      ;;
  esac
  echo "VISITOR_TURN ok seat=$SEAT room=$room"
}

hist_for() {
  local room="$1"
  if [[ "$DRY" == "1" ]]; then
    echo "(dry-run: no relay read)"
    return 0
  fi
  visitor_run --format compact messages get --channel "$room" --limit 8 2>/dev/null \
    | python3 -c 'import sys; t=sys.stdin.read(); print(t[:2048] if t else "(empty)")'
}

poll_room() {
  local room="$1" wake parsed preview hist
  if [[ "$DRY" == "1" ]]; then
    run_turn "$room" "dry" "(dry-run: no relay read)"
    return 0
  fi
  wake="$(
    VISITOR_WAKE_ONCE=1 bash "${ROOT}/wake.sh" --seat "$SEAT" --room "$room" --once 2>/dev/null || true
  )"
  if [[ "$CATCH" == "1" && -z "$wake" ]]; then
    wake="VISITOR_WAKE match seat=$SEAT room=$room channel=$room reason=catch-up from=prime id=catch preview=catch-up"
  fi
  parsed="$(printf '%s\n' "$wake" | python3 "${ROOT}/gate.py" parse-wake || true)"
  if [[ -z "$parsed" || "$parsed" == "{}" ]]; then
    return 0
  fi
  preview="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1] or "{}").get("preview") or "")' "$parsed")"
  hist="$(hist_for "$room")"
  run_turn "$room" "$preview" "$hist"
}

if [[ "$DRY" == "1" ]]; then
  poll_room "${ROOMS[0]}"
  exit 0
fi

if [[ "$ONCE" == "1" ]]; then
  for r in "${ROOMS[@]}"; do
    poll_room "$r" || true
  done
  exit 0
fi

while true; do
  for r in "${ROOMS[@]}"; do
    poll_room "$r" || true
  done
  sleep "$TICK"
done
