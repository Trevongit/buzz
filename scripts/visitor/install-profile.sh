#!/usr/bin/env bash
# Drop the shared visitor skill into a local Codex / agy / Grok skill dir.
# Never mints seats. Never copies nsec. Never registers Desktop ACP.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRAIN=""
DEST=""
DRY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --brain) BRAIN="$2"; shift 2 ;;
    --dest) DEST="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help)
      echo "Usage: install-profile.sh --brain grok|codex|agy [--dest DIR] [--dry-run]"
      echo "  Hermes/Nous Portal is parked (paywall). Free path: grok|codex|agy + wake.sh"
      echo "  Goose is the fork CLI recipe engine — do not mint a goose seat."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

case "$BRAIN" in
  hermes)
    echo "error: Hermes/Nous Portal is parked (paywall). Use --brain grok|codex|agy" >&2
    echo "free path: scripts/visitor/wake.sh (do not curl|bash install)" >&2
    exit 1
    ;;
  goose)
    echo "error: do not mint a Goose seat. Goose is the fork CLI, not Desktop ACP." >&2
    echo "free path: bash scripts/visitor/goose-cli.sh --check (not /usr/bin/goose)" >&2
    echo "recipes: ~/PROJECTS/goose (in-tree buzz/, workflow_recipes). Do not curl|bash." >&2
    exit 1
    ;;
  grok|codex|agy) ;;
  *) echo "error: --brain grok|codex|agy required" >&2; exit 1 ;;
esac

if [[ -z "$DEST" ]]; then
  case "$BRAIN" in
    grok) DEST="${HOME}/.grok/skills/buzz-visitor" ;;
    codex) DEST="${HOME}/.codex/skills/buzz-visitor" ;;
    agy) DEST="${HOME}/.agy/skills/buzz-visitor" ;;
  esac
fi

case "$DEST" in
  *managed-agents*|*src-tauri*)
    echo "error: refuse Desktop ACP path: $DEST" >&2
    exit 1
    ;;
esac

src="${ROOT}/SKILL.fragment.md"
if [[ ! -f "$src" ]]; then
  echo "error: missing $src" >&2
  exit 1
fi
if grep -Eiq 'nsec1|BUZZ_PRIVATE_KEY=' "$src"; then
  echo "error: skill fragment must not contain secrets" >&2
  exit 1
fi

echo "brain=$BRAIN"
echo "dest=$DEST"
if [[ "$DRY" == "1" ]]; then
  echo "status=dry-run"
  exit 0
fi

mkdir -p "$DEST"
{
  printf '%s\n' "---" "name: buzz-visitor" "description: Portable Buzz visitor collab (not Desktop ACP)." "---" ""
  cat "$src"
} >"${DEST}/SKILL.md"
cp "${ROOT}/profile.env.example" "${DEST}/profile.env.example"
echo "wrote ${DEST}/SKILL.md"
echo "status=installed"
echo "next: export BUZZ_SEAT_ID to an existing seat; do not mint"
