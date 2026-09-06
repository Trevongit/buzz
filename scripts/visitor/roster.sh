#!/usr/bin/env bash
# Same-bus visitor roster from PUBLIC.txt. Never opens agent.env.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEATS="${VISITOR_SEATS:-buzz,codex-buzz,agy-buzz}"
HOME_AGENTS="${VISITOR_AGENTS_HOME:-$HOME/.buzz-dev/agents}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --seats) SEATS="$2"; shift 2 ;;
    --home) HOME_AGENTS="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: roster.sh [--seats a,b,c] [--home DIR]"
      echo "  Exit 0 = two+ seats on one host (collab-ready). 3 = split/missing."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done
export VISITOR_AGENTS_HOME="$HOME_AGENTS"
out="$(python3 "${ROOT}/gate.py" roster --seats "$SEATS" --home "$HOME_AGENTS" || true)"
echo "$out"
python3 -c '
import json,sys
r=json.loads(sys.argv[1])
print("ready=" + ("yes" if r.get("ready") else "no"))
for host, seats in sorted((r.get("buses") or {}).items()):
    cards={c["seat"]: c for c in r.get("cards") or []}
    ats=[]
    for s in seats:
        c=cards.get(s,{})
        label=c.get("display_name") or ((c.get("names") or [s])[0])
        ats.append("@" + label)
    print("bus " + host + " " + " ".join(ats))
miss=r.get("missing") or []
if miss:
    print("missing=" + ",".join(miss))
print("hint: collab only inside one bus; mixed relays are a silent empty room")
' "$out"
python3 -c 'import json,sys; raise SystemExit(0 if json.loads(sys.argv[1]).get("ready") else 3)' "$out"
