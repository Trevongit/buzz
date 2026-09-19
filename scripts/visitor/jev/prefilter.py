"""Cheap checks that must run in code before we spend a Jev call."""
from __future__ import annotations

SKIP_PREFIXES = (
    "BUZZ_OK",
    "BUZZ_WAKE",
    "BUZZ_FAIL",
    "BUZZ_ADMIT",
    "VISITOR_WAKE",
    "VISITOR_USE",
    "COLLAB to:",
)


def skip_jev(text: str) -> str | None:
    """Return a reason to skip Jev, or None to call it."""
    first = (text or "").strip().splitlines()[0] if text else ""
    for prefix in SKIP_PREFIXES:
        if first.startswith(prefix):
            return f"watcher/control line starts with {prefix}"
    if not first:
        return "empty text"
    return None
