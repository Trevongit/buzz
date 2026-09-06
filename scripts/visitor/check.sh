#!/usr/bin/env bash
# Local health for the visitor kit. Never prints secrets.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/lib.sh"

fail=0
ok() { echo "ok  $1"; }
bad() { echo "FAIL $1"; fail=1; }

if visitor_find_cli >/dev/null 2>&1; then
  ok "buzz-cli $(visitor_find_cli)"
else
  bad "buzz-cli missing"
fi

python3 "${ROOT}/test_visitor.py" >/dev/null && ok "test_visitor.py" || bad "test_visitor.py"

if bash "${ROOT}/hermes-setup.sh" --check >/dev/null 2>&1; then
  ok "hermes gateway binary"
else
  echo "skip hermes binary (adapter-missing) — offline runner still valid"
  if grep -q 'require_mention: true' "${ROOT}/hermes-gateway.example.yaml"; then
    ok "hermes example mention-only"
  else
    bad "hermes example"
  fi
fi

acp_hits="$(grep -RInE 'managed-agents\.json' "$ROOT" --include='*.sh' --include='*.py' --include='*.md' --include='*.yaml' || true)"
if printf '%s\n' "$acp_hits" | grep -Eiv 'do not|not-desktop|refuse' | grep -Ev 'visitor kit must not write the Desktop catalog' | grep -q .; then
  bad "visitor kit must not write the Desktop catalog"
else
  ok "no Desktop ACP registration"
fi

seat="${BUZZ_SEAT_ID:-buzz}"
dir="$(visitor_seat_dir "$seat")"
if [[ -f "${dir}/agent.env" ]]; then
  ok "seat $seat has agent.env (unread)"
else
  echo "skip seat $seat (no agent.env) — kit does not mint"
fi

if grep -RInE 'nsec1[a-z0-9]+' "$ROOT" --include='*.md' --include='*.sh' --include='*.py' --include='*.yaml' --include='*.example.yaml' >/dev/null; then
  bad "secret-looking nsec in visitor kit"
else
  ok "no nsec in visitor kit"
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "visitor-check: pass"
