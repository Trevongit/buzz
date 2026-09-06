#!/usr/bin/env bash
# Prepare Hermes gateway ③ as a Buzz visitor. Does not mint seats or Desktop runtimes.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_ONLY=0
WRITE_DIR="${HERMES_VISITOR_DIR:-$HOME/.hermes/buzz-visitor}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK_ONLY=1; shift ;;
    --write-dir) WRITE_DIR="$2"; shift 2 ;;
    --offline) shift ;;
    -h|--help)
      echo "Usage: hermes-setup.sh [--check] [--write-dir DIR] [--offline]"
      echo "  Writes mention-only gateway yaml + an offline poll runner."
      echo "  Never registers Desktop runtime hermes-acp."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

case "$WRITE_DIR" in
  *managed-agents*|*src-tauri*|*harness-catalog*)
    echo "error: refuse Desktop ACP path: $WRITE_DIR" >&2
    exit 1
    ;;
esac

example="${ROOT}/hermes-gateway.example.yaml"
if [[ ! -f "$example" ]]; then
  echo "error: missing $example" >&2
  exit 1
fi

if grep -Eiq 'nsec1|BUZZ_PRIVATE_KEY=' "$example"; then
  echo "error: example yaml must not contain secrets" >&2
  exit 1
fi
if ! grep -q 'require_mention: true' "$example"; then
  echo "error: example yaml must require_mention" >&2
  exit 1
fi
if ! grep -q 'allow_all_users: false' "$example"; then
  echo "error: example yaml must not allow_all_users" >&2
  exit 1
fi

hermes_bin="$(command -v hermes || true)"
echo "hermes_bin=${hermes_bin:-MISSING}"
echo "example=$example"

if [[ "$CHECK_ONLY" == "1" ]]; then
  if [[ -z "$hermes_bin" ]]; then
    echo "status=adapter-missing"
    echo "offline: hermes-setup.sh --write-dir DIR  (poll runner, not hermes-acp)"
    echo "install: https://hermes-agent.nousresearch.com  then: hermes gateway setup → Buzz"
    echo "do_not: Desktop runtime hermes-acp for this path"
    exit 2
  fi
  echo "status=ready"
  exit 0
fi

mkdir -p "$WRITE_DIR"
cp "$example" "$WRITE_DIR/config.buzz.yaml"
cat >"$WRITE_DIR/NOT-DESKTOP-ACP.txt" <<'EOF'
This directory is Hermes gateway ③ (visitor).
Do not copy it into Buzz Desktop Agents.
Do not add hermes-acp to managed-agents.json for this path.
Desktop runtime ① and this visitor path are different sockets.
EOF
cat >"$WRITE_DIR/offline-gateway.sh" <<EOF
#!/usr/bin/env bash
# Offline stand-in for Hermes gateway ③ when \`hermes\` is not installed.
# Mention-gated poll via scripts/visitor/wake.sh. Idle = 0 model tokens.
set -euo pipefail
VISITOR_ROOT="${ROOT}"
export VISITOR_REQUIRE_MENTION="\${VISITOR_REQUIRE_MENTION:-1}"
export VISITOR_WATCH_SECS="\${VISITOR_WATCH_SECS:-4}"
if [[ -z "\${BUZZ_SEAT_ID:-}" ]]; then
  echo "error: set BUZZ_SEAT_ID to an existing seat (do not mint)" >&2
  exit 1
fi
exec bash "\$VISITOR_ROOT/wake.sh" --seat "\$BUZZ_SEAT_ID" --secs "\$VISITOR_WATCH_SECS" "\$@"
EOF
chmod +x "$WRITE_DIR/offline-gateway.sh"
cat >"$WRITE_DIR/README.txt" <<EOF
Hermes Buzz visitor (gateway ③) — mention-only

If \`hermes\` is on PATH:
  1. Put BUZZ_PRIVATE_KEY in ~/.hermes/.env (never this directory if git-tracked).
  2. Merge config.buzz.yaml into Hermes gateway.platforms.buzz.
  3. hermes gateway start
  4. Do not add hermes-acp to Buzz Desktop Agents.

If \`hermes\` is missing (this host):
  1. Use an existing seat: export BUZZ_SEAT_ID=...
  2. bash $WRITE_DIR/offline-gateway.sh --room <channel>
  3. Cortex stays off until stdout prints VISITOR_WAKE.

This path is not Desktop ACP.
EOF
echo "wrote $WRITE_DIR/config.buzz.yaml"
echo "wrote $WRITE_DIR/offline-gateway.sh"
if [[ -z "$hermes_bin" ]]; then
  echo "status=offline"
  exit 0
fi
echo "status=config-written"
