#!/usr/bin/env bash
# Resolve the Goose CLI fork for unattended recipes. Visitor only.
# Never /usr/bin/goose. Never mint a seat. Never Desktop ACP. Never curl|bash.
set -euo pipefail

CHECK=0
FORK="${VISITOR_GOOSE_ROOT:-${HOME}/PROJECTS/goose}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK=1; shift ;;
    --fork) FORK="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: goose-cli.sh [--check] [--fork DIR]"
      echo "  Prints the fork goose binary. Refuses /usr/bin/goose and Desktop ACP."
      echo "  Does not mint a seat. Does not install via curl|bash."
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done

case "$FORK" in
  *managed-agents*|*src-tauri*|*harness-catalog*)
    echo "error: refuse Desktop ACP path: $FORK" >&2
    exit 1
    ;;
esac

is_system_goose() {
  local p="$1"
  local resolved
  resolved="$(readlink -f "$p" 2>/dev/null || echo "$p")"
  case "$p" in
    /usr/bin/goose|/bin/goose) return 0 ;;
  esac
  case "$resolved" in
    /usr/bin/goose|/bin/goose|/usr/lib/goose/*|/lib/goose/*) return 0 ;;
  esac
  return 1
}

refuse_system_goose() {
  local p="$1"
  if is_system_goose "$p"; then
    echo "error: refuse system goose ($p). Build the fork at $FORK" >&2
    echo "do_not: mint goose seat; do_not: Desktop ACP; do_not: curl|bash" >&2
    return 1
  fi
  return 0
}

if [[ -n "${GOOSE_BIN:-}" ]]; then
  if ! refuse_system_goose "$GOOSE_BIN"; then
    if [[ "$CHECK" == "1" ]]; then
      echo "status=system-goose-refused"
      echo "fork=$FORK"
      echo "offline: build goose from the fork (do not curl|bash)"
      exit 2
    fi
    exit 1
  fi
  if [[ ! -x "${GOOSE_BIN}" ]]; then
    echo "error: GOOSE_BIN is not executable: $GOOSE_BIN" >&2
    exit 1
  fi
  if [[ "$CHECK" == "1" ]]; then
    echo "goose_bin=$GOOSE_BIN"
    echo "fork=$FORK"
    echo "status=fork-ok"
    echo "do_not: mint goose seat; do_not: Desktop ACP; do_not: /usr/bin/goose"
    exit 0
  fi
  echo "$GOOSE_BIN"
  exit 0
fi

found=""
for c in "${FORK}/target/release/goose" "${FORK}/target/debug/goose"; do
  if [[ -x "$c" ]] && refuse_system_goose "$c"; then
    found="$c"
    break
  fi
done

if [[ -z "$found" ]] && command -v goose >/dev/null 2>&1; then
  g="$(command -v goose)"
  if refuse_system_goose "$g"; then
    found="$g"
  elif [[ "$CHECK" == "1" ]]; then
    echo "status=system-goose-refused"
    echo "fork=$FORK"
    echo "offline: build goose from the fork (do not curl|bash)"
    exit 2
  else
    exit 1
  fi
fi

if [[ -z "$found" ]]; then
  echo "error: goose fork binary not found under $FORK" >&2
  echo "do_not: /usr/bin/goose; do_not: mint a goose seat; do_not: curl|bash install" >&2
  echo "offline: cargo build --release from the fork checkout" >&2
  if [[ "$CHECK" == "1" ]]; then
    echo "status=fork-binary-missing"
    exit 2
  fi
  exit 1
fi

if [[ "$CHECK" == "1" ]]; then
  echo "goose_bin=$found"
  echo "fork=$FORK"
  echo "status=fork-ok"
  echo "do_not: mint goose seat; do_not: Desktop ACP; do_not: /usr/bin/goose"
  exit 0
fi
echo "$found"
