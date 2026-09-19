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
    if not first:
        return "empty text"
    for prefix in SKIP_PREFIXES:
        if first.startswith(prefix):
            return f"watcher/control line starts with {prefix}"
    body = first.lstrip()
    if body.startswith("👀"):
        return "eyes-only ack"
    low = body.lower()
    if low.startswith("copy.") or low.startswith("copy ") or low.startswith("**copy"):
        return "copy ack"
    if low.startswith("`copy"):
        return "copy ack tag"
    return None
