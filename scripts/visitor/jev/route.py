"""Route one wake through prefilter + Jev + compose. Fail closed. No key in output."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from call import post_systemone
from compose import decide, load_jobs
from prefilter import skip_jev

STATE_PATH = Path.home() / ".buzz-dev" / "control-room" / "jev-last.json"


def _noul(answers: dict[str, Any], name: str) -> float | None:
    blob = answers.get(name) or {}
    val = blob.get("noul")
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _choice(answers: dict[str, Any], name: str) -> tuple[str, float]:
    blob = answers.get(name) or {}
    choice = str(blob.get("choice") or "")
    try:
        conf = float(blob.get("confidence") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    return choice, conf


def route_wake(wake: dict[str, Any], jobs: dict[str, Any] | None = None) -> dict[str, str]:
    spec = jobs or load_jobs()
    text = str(wake.get("preview") or wake.get("content") or "")
    skip = skip_jev(text)
    if skip:
        return {"action": "ignore", "wall": "private", "reason": skip, "error": ""}

    fake = os.environ.get("VISITOR_JEV_FAKE")
    if fake:
        try:
            answers = json.loads(fake)
        except json.JSONDecodeError:
            return {"action": "stop", "wall": "private", "reason": "bad fake", "error": "bad_fake"}
    else:
        state = {
            "from": wake.get("from") or "",
            "room": wake.get("channel") or wake.get("room") or "",
            "is_dm": (wake.get("reason") or "") == "dm",
            "text": text[:500],
        }
        payload = post_systemone(
            state=state,
            questions=spec.get("questions") or {},
            model=str(spec.get("model") or "jev-latest"),
        )
        if not payload.get("ok"):
            err = str(payload.get("error") or "call_failed")
            return {"action": "stop", "wall": "private", "reason": "jev error", "error": err}
        answers = payload.get("answers") or {}

    needs = _noul(answers, "needs_chair")
    public = _noul(answers, "public_ok")
    who, who_conf = _choice(answers, "who")
    if needs is None or public is None:
        return {"action": "stop", "wall": "private", "reason": "bad answers", "error": "bad_answers"}
    out = decide(
        text=text,
        needs_chair=needs,
        who_choice=who,
        who_confidence=who_conf,
        public_ok=public,
        jobs=spec,
    )
    out["error"] = ""
    return out


def write_state(decision: dict[str, str], wake: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    prev: dict[str, Any] = {}
    if STATE_PATH.is_file():
        try:
            prev = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}
    counts = prev.get("counts") if isinstance(prev.get("counts"), dict) else {}
    action = decision.get("action") or "stop"
    counts[action] = int(counts.get(action) or 0) + 1
    record = {
        "updated_at": int(time.time()),
        "last": {
            "action": action,
            "wall": decision.get("wall") or "private",
            "reason": decision.get("reason") or "",
            "error": decision.get("error") or "",
            "from": (wake.get("from") or "")[:12],
            "room": wake.get("channel") or "",
            "id": wake.get("id") or "",
            "preview": (wake.get("preview") or "")[:120],
        },
        "counts": counts,
        "live": True,
    }
    STATE_PATH.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
