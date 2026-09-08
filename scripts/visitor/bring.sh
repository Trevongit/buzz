#!/usr/bin/env bash
# One step: put the Buzz visitor skill on this computer for Grok, Codex, and agy.
# Then in that terminal say: use buzz
# Never mints seats. Never copies nsec. Never curl|bash.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY=1
fi
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: bring.sh [--dry-run]"
  echo "  Installs buzz-visitor into ~/.grok ~/.codex ~/.agy skill dirs."
  echo "  Puts 'buzz-skill' on PATH (~/.local/bin) so any terminal can re-run it."
  echo "  Then type: use buzz"
  exit 0
fi

if [[ ! -f "${ROOT}/SKILL.fragment.md" || ! -f "${ROOT}/install-profile.sh" ]]; then
  echo "error: run this from extras scripts/visitor (clone extras first)" >&2
  exit 1
fi

if [[ "$DRY" == "1" ]]; then
  bash "${ROOT}/install-profile.sh" --all --dry-run
  echo "status=dry-run"
  echo "next: use buzz"
  exit 0
fi

bash "${ROOT}/install-profile.sh" --all
mkdir -p "${HOME}/.local/bin"
ln -sfn "${ROOT}/bring.sh" "${HOME}/.local/bin/buzz-skill"
echo "ok  buzz-skill -> ${ROOT}/bring.sh"
echo ""
echo "Done. In Grok Build, Codex CLI, or agy type exactly:"
echo "  use buzz"
echo "Seats: Grok=buzz  Codex=codex-buzz  agy=agy-buzz"
echo "Community comes from that seat (open121 or asus-g501vw). Do not mint keys."
echo "status=ready"
