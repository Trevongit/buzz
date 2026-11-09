#!/usr/bin/env bash
# native_toolchain_c on Linux (host == target) resolves only `clang` and
# `llvm-ar`. A host with gcc/g++/gcc-ar and no clang fails Flutter native
# assets for buzz_secp256k1 (the 48s pre-push mobile-checks miss). Hermit
# clang shims exec `hermit` and cannot compile. When a real clang is missing,
# put gcc-backed wrappers first on PATH for this process tree.
set -euo pipefail

is_usable_clang() {
  local clang_bin target
  clang_bin="$(command -v clang 2>/dev/null || true)"
  [[ -n "$clang_bin" ]] || return 1
  target="$(readlink -f "$clang_bin")"
  [[ "$(basename "$target")" != hermit ]] || return 1
  command -v llvm-ar >/dev/null 2>&1
}

if is_usable_clang; then
  exec "$@"
fi

if ! command -v gcc >/dev/null 2>&1 || ! command -v gcc-ar >/dev/null 2>&1; then
  echo "mobile tests need clang+llvm-ar, or gcc+gcc-ar, for buzz_secp256k1 native assets" >&2
  exit 1
fi

dir="$(mktemp -d)"
trap 'rm -rf "$dir"' EXIT
cat >"$dir/clang" <<'EOF'
#!/bin/sh
exec gcc "$@"
EOF
cat >"$dir/clang++" <<'EOF'
#!/bin/sh
exec g++ "$@"
EOF
cat >"$dir/llvm-ar" <<'EOF'
#!/bin/sh
exec gcc-ar "$@"
EOF
chmod +x "$dir/clang" "$dir/clang++" "$dir/llvm-ar"
export PATH="$dir:$PATH"
exec "$@"
