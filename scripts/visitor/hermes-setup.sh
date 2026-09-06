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
    -h|--help)
      echo "Usage: hermes-setup.sh [--check] [--write-dir DIR]"
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

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
    echo "install: https://hermes-agent.nousresearch.com  then: hermes gateway setup → Buzz"
    echo "do_not: Desktop runtime hermes-acp for this path"
    exit 2
  fi
  echo "status=ready"
  exit 0
fi

mkdir -p "$WRITE_DIR"
cp "$example" "$WRITE_DIR/config.buzz.yaml"
cat >"$WRITE_DIR/README.txt" <<EOF
Hermes Buzz visitor (gateway ③)

1. Put BUZZ_PRIVATE_KEY in ~/.hermes/.env (never this directory if it is git-tracked).
2. Set extra.relay_url and extra.channels in config.buzz.yaml.
3. Merge into Hermes gateway.platforms.buzz (see Nous docs).
4. hermes gateway start
5. Do not add hermes-acp to Buzz Desktop Agents for this path.
EOF
echo "wrote $WRITE_DIR/config.buzz.yaml"
if [[ -z "$hermes_bin" ]]; then
  echo "status=config-written-adapter-missing"
  exit 2
fi
echo "status=config-written"
