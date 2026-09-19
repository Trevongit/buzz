"""Apply THREE-JOBS.json cutoffs in code. No HTTP."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prefilter import skip_jev

JOBS_PATH = Path(__file__).with_name("THREE-JOBS.json")


def load_jobs(path: Path | None = None) -> dict[str, Any]:
    p = path or JOBS_PATH
    with p.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("THREE-JOBS.json must be an object")
    return data


def decide(
    *,
    text: str,
    needs_chair: float,
    who_choice: str,
    who_confidence: float,
    public_ok: float,
    jobs: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Return action, wall, and reason. Fail closed on bad input."""
    skip = skip_jev(text)
    if skip:
        return {"action": "ignore", "wall": "private", "reason": skip}

    spec = jobs or load_jobs()
    cut = spec.get("cutoffs") or {}
    try:
        low = float(cut["needs_chair_unsure_low"])
        high = float(cut["needs_chair_unsure_high"])
        who_min = float(cut["who_min_confidence"])
        public_yes = float(cut["public_ok_yes"])
    except (KeyError, TypeError, ValueError):
        return {"action": "stop", "wall": "private", "reason": "bad cutoffs"}

    wall = "public" if public_ok >= public_yes else "private"
    who = (who_choice or "").strip().lower()

    if needs_chair < low:
        return {"action": "ignore", "wall": wall, "reason": "needs_chair below low"}
    if low <= needs_chair <= high:
        return {"action": "ask-prime", "wall": wall, "reason": "needs_chair unsure"}
    if who == "ignore":
        return {"action": "ignore", "wall": wall, "reason": "who=ignore"}
    if who == "other" or who_confidence < who_min:
        return {"action": "ask-prime", "wall": wall, "reason": "who unsure or other"}
    if who in ("grok", "codex", "agy"):
        return {"action": f"wake-{who}", "wall": wall, "reason": f"who={who}"}
    return {"action": "ask-prime", "wall": wall, "reason": "unknown who"}
