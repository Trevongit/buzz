#!/usr/bin/env python3
"""Visitor mention gate + COLLAB v0 envelope. No network. No secrets."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

COLLAB_HEADER = "COLLAB v0"
STATUS_OPEN = "OPEN"
STATUS_DONE = "DONE"
STATUS_BLOCKED = "BLOCKED"
ROLES = ("grok", "codex", "agy")


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def addressed_to(content: str, names: list[str], pubkeys: list[str]) -> bool:
    """True when channel text names this seat (@name, seat id, pubkey prefix)."""
    c = _norm(content)
    if not c:
        return False
    for name in names:
        n = _norm(name).lstrip("@#")
        if not n:
            continue
        if n in c or f"@{n}" in c:
            return True
    for pk in pubkeys:
        p = _norm(pk)
        if len(p) < 8:
            continue
        if p in c or p[:12] in c or p[:16] in c:
            return True
    return False


def parse_collab_envelope(content: str) -> Optional[dict[str, str]]:
    """Parse a COLLAB v0 block. Unknown keys ignored. None if not an envelope."""
    text = (content or "").strip()
    if not text.upper().startswith(COLLAB_HEADER.upper()):
        # Allow a leading fence
        stripped = re.sub(r"^```[a-zA-Z0-9]*\n", "", text)
        if not stripped.upper().startswith(COLLAB_HEADER.upper()):
            return None
        text = stripped
    fields: dict[str, str] = {}
    for raw in text.splitlines()[1:]:
        line = raw.strip()
        if not line or line.startswith("```"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = _norm(key).replace("-", "_")
        val = val.strip()
        if key:
            fields[key] = val
    if not fields:
        return None
    fields.setdefault("status", STATUS_OPEN)
    fields.setdefault("need_prime", "false")
    return fields


def envelope_to(fields: dict[str, str], seat_role: str, seat_names: list[str]) -> bool:
    dest = _norm(fields.get("to") or "")
    if not dest:
        return False
    if dest in ("all", "*"):
        return True
    role = _norm(seat_role)
    if dest == role:
        return True
    for name in seat_names:
        if dest == _norm(name).lstrip("@#"):
            return True
    return False


def should_escalate_to_prime(fields: Optional[dict[str, str]]) -> bool:
    if not fields:
        return False
    status = _norm(fields.get("status") or "")
    need = _norm(fields.get("need_prime") or "")
    return status == _norm(STATUS_BLOCKED) and need in ("true", "1", "yes")


def should_wake(
    *,
    content: str,
    from_pubkey: str,
    self_pubkey: str,
    is_dm: bool,
    require_mention: bool,
    names: list[str],
    pubkeys: list[str],
    seat_role: str,
) -> tuple[bool, str]:
    """Return (wake?, reason). Self-echo never wakes."""
    if self_pubkey and from_pubkey and _norm(from_pubkey) == _norm(self_pubkey):
        return False, "self-echo"
    if is_dm:
        return True, "dm"
    env = parse_collab_envelope(content)
    if env and envelope_to(env, seat_role, names):
        return True, "collab"
    if not require_mention:
        return True, "open"
    if addressed_to(content, names, pubkeys):
        return True, "mention"
    return False, "unaddressed"


def render_envelope(
    *,
    from_role: str,
    to_role: str,
    task: str,
    status: str = STATUS_OPEN,
    need_prime: bool = False,
) -> str:
    fr = _norm(from_role)
    to = _norm(to_role)
    st = (status or STATUS_OPEN).upper()
    if fr not in ROLES:
        raise ValueError(f"from must be one of {ROLES}")
    if to not in ROLES + ("all",):
        raise ValueError(f"to must be one of {ROLES} or all")
    if st not in (STATUS_OPEN, STATUS_DONE, STATUS_BLOCKED):
        raise ValueError("status must be OPEN, DONE, or BLOCKED")
    task_line = (task or "").strip().replace("\n", " ")
    if not task_line:
        raise ValueError("task required")
    if st == STATUS_BLOCKED and not need_prime:
        # BLOCKED without need_prime stays in the agent loop.
        need_prime = False
    return (
        f"{COLLAB_HEADER}\n"
        f"from: {fr}\n"
        f"to: {to}\n"
        f"task: {task_line}\n"
        f"status: {st}\n"
        f"need_prime: {'true' if need_prime else 'false'}\n"
    )


def admit_budget(
    events: list[dict[str, Any]],
    *,
    max_events: int = 3,
    max_bytes: int = 2048,
) -> tuple[list[dict[str, Any]], bool]:
    """Keep the first events that fit the turn budget. overflow=True if truncated."""
    kept: list[dict[str, Any]] = []
    used = 0
    overflow = False
    for ev in events:
        body = str(ev.get("preview") or ev.get("content") or "")
        n = len(body.encode("utf-8"))
        if len(kept) >= max_events or used + n > max_bytes * max(1, max_events):
            overflow = True
            break
        kept.append(ev)
        used += n
    return kept, overflow


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "render":
        # visitor-post helper: --from --to --task --status --need-prime
        args = sys.argv[2:]
        kw: dict[str, str] = {}
        i = 0
        while i < len(args):
            if args[i].startswith("--") and i + 1 < len(args):
                kw[args[i][2:].replace("-", "_")] = args[i + 1]
                i += 2
            else:
                i += 1
        print(
            render_envelope(
                from_role=kw.get("from", "grok"),
                to_role=kw.get("to", "codex"),
                task=kw.get("task", ""),
                status=kw.get("status", STATUS_OPEN),
                need_prime=kw.get("need_prime", "false").lower() in ("1", "true", "yes"),
            ),
            end="",
        )
        raise SystemExit(0)

    payload = json.loads(sys.stdin.read() or "{}")
    wake, reason = should_wake(
        content=payload.get("content") or "",
        from_pubkey=payload.get("from_pubkey") or "",
        self_pubkey=payload.get("self_pubkey") or "",
        is_dm=bool(payload.get("is_dm")),
        require_mention=bool(payload.get("require_mention", True)),
        names=list(payload.get("names") or []),
        pubkeys=list(payload.get("pubkeys") or []),
        seat_role=payload.get("seat_role") or "grok",
    )
    env = parse_collab_envelope(payload.get("content") or "")
    json.dump(
        {
            "wake": wake,
            "reason": reason,
            "escalate_prime": should_escalate_to_prime(env),
            "envelope": env,
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
