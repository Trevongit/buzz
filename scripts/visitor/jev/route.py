"""Route one wake through prefilter + Jev + compose. Fail closed. No key in output."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from audit import append_audit
from call import post_systemone
from compose import decide, load_jobs
from prefilter import skip_jev

STATE_PATH = Path.home() / ".buzz-dev" / "control-room" / "jev-last.json"


def should_ring_extras(
    action: str,
    wake: dict[str, Any],
    owner_pk: str = "",
    error: str = "",
) -> bool:
    """Whether extras Grok should spend a turn on this wake."""
    if error or action in ("stop", "ask-prime", "wake-grok"):
        return True
    reason = (wake.get("reason") or "").strip().lower()
    if reason == "dm":
        return True
    frm = (wake.get("from") or "").strip().lower()
    own = (owner_pk or "").strip().lower()
    if own and frm.startswith(own[:12]):
        return True
    # Codex/agy: lamp + audit only. Extras must not steal their job.
    # ignore: saver — extras stays quiet.
    return False


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


def route_wake(wake: dict[str, Any], jobs: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = jobs or load_jobs()
    text = str(wake.get("preview") or wake.get("content") or "")
    skip = skip_jev(text)
    if skip:
        return {
            "action": "ignore",
            "wall": "private",
            "reason": skip,
            "error": "",
            "skipped": True,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    fake = os.environ.get("VISITOR_JEV_FAKE")
    payload: dict[str, Any] = {}
    started = time.perf_counter()
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
    ms = round((time.perf_counter() - started) * 1000)

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
    usage = payload.get("usage") or {}
    out["input_tokens"] = usage.get("input_tokens")
    out["output_tokens"] = usage.get("output_tokens")
    out["model"] = payload.get("model") or spec.get("model")
    out["ms"] = ms
    out["skipped"] = False
    return out


def _as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def write_state(decision: dict[str, Any], wake: dict[str, Any]) -> None:
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
    last = {
        "action": action,
        "wall": decision.get("wall") or "private",
        "reason": decision.get("reason") or "",
        "error": decision.get("error") or "",
        "from": (wake.get("from") or "")[:12],
        "room": wake.get("channel") or "",
        "id": wake.get("id") or "",
        "preview": (wake.get("preview") or "")[:120],
        "input_tokens": _as_int(decision.get("input_tokens")),
        "output_tokens": _as_int(decision.get("output_tokens")),
        "model": decision.get("model") or "",
        "ms": _as_int(decision.get("ms")),
        "skipped": bool(decision.get("skipped")),
    }
    # Control-room lamp reads top-level outcome (not last.action).
    record = {
        "updated_at": int(time.time()),
        "outcome": action,
        "action": action,
        "wall": last["wall"],
        "reason": last["reason"],
        "error": last["error"],
        "from": last["from"],
        "room": last["room"],
        "id": last["id"],
        "preview": last["preview"],
        "last": last,
        "counts": counts,
        "live": True,
    }
    STATE_PATH.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    append_audit(
        {
            "outcome": action,
            "wall": last["wall"],
            "reason": last["reason"],
            "error": last["error"],
            "from": last["from"],
            "room": last["room"],
            "id": last["id"],
            "preview": last["preview"],
            "input_tokens": last["input_tokens"],
            "output_tokens": last["output_tokens"],
            "model": last["model"],
            "ms": last["ms"],
            "skipped": last["skipped"],
        }
    )
