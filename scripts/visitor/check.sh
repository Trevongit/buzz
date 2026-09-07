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

python3 "${ROOT}/test_visitor.py" >/dev/null 2>&1 && ok "test_visitor.py" || bad "test_visitor.py"

echo "skip hermes (parked paywall) — free path is buzz-cli + wake.sh"
if grep -q 'require_mention: true' "${ROOT}/hermes-gateway.example.yaml"; then
  ok "hermes example mention-only (offline only)"
else
  bad "hermes example"
fi
hermes_check="$(bash "${ROOT}/hermes-setup.sh" --check 2>&1 || true)"
if printf '%s\n' "$hermes_check" | grep -Eiq 'curl[[:space:]].+\|[[:space:]]*bash|https?://.+\|[[:space:]]*bash'; then
  bad "hermes-setup --check must not curl|bash install"
else
  ok "hermes-setup no curl|bash"
fi
if printf '%s\n' "$hermes_check" | grep -Eiq 'nousportal|install\.sh'; then
  bad "hermes-setup must not advertise an install URL"
else
  ok "hermes-setup no install URL"
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

home="${VISITOR_AGENTS_HOME:-$HOME/.buzz-dev/agents}"
align_out="$(python3 "${ROOT}/gate.py" relay-align --seats "${VISITOR_SEATS:-buzz,codex-buzz,agy-buzz}" --home "$home" || true)"
if python3 -c 'import json,sys; raise SystemExit(0 if json.loads(sys.argv[1]).get("aligned") else 1)' "$align_out"; then
  ok "visitor seats share one relay host"
else
  echo "warn mixed/missing relays (silent empty room) — start-collab.sh --seats on one bus"
  python3 -c 'import json,sys; r=json.loads(sys.argv[1] or "{}"); print("hosts=" + str(r.get("hosts"))); print("missing=" + str(r.get("missing")))' "$align_out" || true
fi
if bash "${ROOT}/start-collab.sh" --seats "codex-buzz,agy-buzz,goose" --home "$home" >/dev/null 2>&1; then
  ok "codex+agy+goose same-bus collab-ready"
else
  echo "skip same-bus Tailscale trio (missing PUBLIC.txt or split)"
fi
if bash "${ROOT}/install-profile.sh" --brain hermes --dry-run >/dev/null 2>&1; then
  bad "install-profile must refuse parked hermes"
else
  ok "install-profile refuses hermes"
fi
if bash "${ROOT}/install-profile.sh" --brain goose --dry-run >/dev/null 2>&1; then
  bad "install-profile must refuse minting a goose seat"
else
  ok "install-profile refuses goose mint"
fi
goose_check="$(bash "${ROOT}/goose-cli.sh" --check 2>&1 || true)"
if printf '%s\n' "$goose_check" | grep -Eiq 'curl[[:space:]].+\|[[:space:]]*bash|https?://.+\|[[:space:]]*bash'; then
  bad "goose-cli --check must not curl|bash install"
else
  ok "goose-cli no curl|bash"
fi
if printf '%s\n' "$goose_check" | grep -Eq '^(/usr/bin/goose|/bin/goose)$'; then
  bad "goose-cli must not select /usr/bin/goose"
else
  ok "goose-cli not system goose"
fi
if grep -q 'send-gate' "${ROOT}/post.sh" && grep -q -- '--from-escalate' "${ROOT}/escalate.sh"; then
  ok "send-gate + from-escalate fences"
else
  bad "missing send-gate / from-escalate fences"
fi
ar="$(VISITOR_ROLE=agy bash "${ROOT}/auto-reply.sh" --seat agy-buzz --room 00000000-0000-4000-8000-000000000001 --dry-run --once 2>/dev/null || true)"
if printf '%s\n' "$ar" | grep -q 'agy --print' && printf '%s\n' "$ar" | grep -q 'VISITOR_TURN dry-run'; then
  ok "auto-reply dry-run print-mode"
else
  bad "auto-reply.sh dry-run must print agy --print"
fi
if grep -q 'managed-agents' "${ROOT}/auto-reply.sh"; then
  bad "auto-reply must not mention Desktop catalog"
else
  ok "auto-reply not Desktop ACP"
fi
if grep -q -- '--dm' "${ROOT}/wake.sh" && grep -q 'visitor_channel_is_dm' "${ROOT}/wake.sh"; then
  ok "wake.sh --dm for UUID DMs"
else
  bad "wake.sh must admit DMs via --dm (not DM-* prefix only)"
fi
if grep -q -- '--content -' "${ROOT}/post.sh" && grep -q 'mention-pubkeys' "${ROOT}/post.sh"; then
  ok "post.sh stdin body + mention pubkeys"
else
  bad "post.sh must send --content - and --mention pubkeys"
fi
if grep -q 'l2-lease.lock' "${ROOT}/auto-reply.sh" && grep -q 'VISITOR_STATE state=posted' "${ROOT}/auto-reply.sh"; then
  ok "L2 lease + posted state"
else
  bad "auto-reply must take a lease and emit posted/failed states"
fi
if grep -q 'VISITOR_DM_COOLDOWN_SECS' "${ROOT}/wake.sh" && grep -q 'l2-' "${ROOT}/auto-reply.sh"; then
  ok "DM cooldown 0 + L2 cursor"
else
  bad "DM auto-reply must not share TUI wake state or 30s cooldown"
fi
role="$(python3 "${ROOT}/gate.py" role-from-seat --seat codex-buzz)"
if [[ "$role" == "codex" ]]; then
  ok "seat-to-role codex-buzz=codex"
else
  bad "seat-to-role (got $role)"
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "visitor-check: pass"
