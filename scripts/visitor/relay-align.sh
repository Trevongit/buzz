#!/usr/bin/env bash
# Compare visitor seats' relays (PUBLIC.txt only). Never prints nsec.
# Exit 0 aligned, 3 mismatch, 1 usage.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEATS="${VISITOR_SEATS:-buzz,codex-buzz,agy-buzz}"
HOME_AGENTS="${VISITOR_AGENTS_HOME:-$HOME/.buzz-dev/agents}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --seats) SEATS="$2"; shift 2 ;;
    --home) HOME_AGENTS="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: relay-align.sh [--seats a,b,c] [--home DIR]"
      echo "  Exit 0 = every named seat shares one PUBLIC.txt host. 3 = mixed/missing."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done
export VISITOR_AGENTS_HOME="$HOME_AGENTS"
out="$(python3 "${ROOT}/gate.py" relay-align --seats "$SEATS" --home "$HOME_AGENTS" || true)"
echo "$out"
python3 -c 'import json,sys; r=json.loads(sys.argv[1]);
print("aligned=" + ("yes" if r.get("aligned") else "no"))
print("hosts=" + ",".join(sorted(set((r.get("hosts") or {}).values()))))
miss=r.get("missing") or []
if miss:
    print("missing=" + ",".join(miss))
' "$out"
python3 -c 'import json,sys; raise SystemExit(0 if json.loads(sys.argv[1]).get("aligned") else 3)' "$out"
