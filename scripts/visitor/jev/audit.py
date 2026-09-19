"""Bounded JSONL of Jev decisions so we can see value over time."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

AUDIT_PATH = Path.home() / ".buzz-dev" / "control-room" / "jev-audit.jsonl"
MAX_LINES = 2000


def append_audit(record: dict[str, Any], path: Path | None = None) -> None:
    dest = path or AUDIT_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    row = dict(record)
    row.setdefault("ts", int(time.time()))
    line = json.dumps(row, separators=(",", ":")) + "\n"
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(line)
    _trim(dest)


def _trim(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    lines = text.splitlines()
    if len(lines) <= MAX_LINES:
        return
    keep = lines[-MAX_LINES:]
    path.write_text("\n".join(keep) + "\n", encoding="utf-8")
