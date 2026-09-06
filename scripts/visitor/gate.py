#!/usr/bin/env python3
"""Visitor mention gate + COLLAB v0 envelope. No network. No secrets."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

COLLAB_HEADER = "COLLAB v0"
STATUS_OPEN = "OPEN"
STATUS_DONE = "DONE"
STATUS_BLOCKED = "BLOCKED"
ROLES = ("grok", "codex", "agy", "hermes")
DEFAULT_COOLDOWN_SECS = 30
DEFAULT_MAX_EVENTS = 3
DEFAULT_MAX_BYTES = 2048
PUBKEY_MIN = 8


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _word_hit(content: str, needle: str) -> bool:
    """True when needle is @mentioned or a whole token (not a substring)."""
    n = _norm(needle).lstrip("@#")
    if not n:
        return False
    c = _norm(content)
    if f"@{n}" in c:
        return True
    return re.search(rf"(?<![a-z0-9_-]){re.escape(n)}(?![a-z0-9_-])", c) is not None


def addressed_to(content: str, names: list[str], pubkeys: list[str]) -> bool:
    """True when channel text names this seat (@name, seat id, pubkey prefix)."""
    c = _norm(content)
    if not c:
        return False
    for name in names:
        if _word_hit(content, name):
            return True
    for pk in pubkeys:
        p = _norm(pk)
        if len(p) < PUBKEY_MIN:
            continue
        if p in c or p[:12] in c or p[:16] in c:
            return True
    return False


def parse_collab_envelope(content: str) -> Optional[dict[str, str]]:
    """Parse a COLLAB v0 block. Unknown keys ignored. None if not an envelope."""
    text = (content or "").strip()
    if not text.upper().startswith(COLLAB_HEADER.upper()):
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
    max_events: int = DEFAULT_MAX_EVENTS,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> tuple[list[dict[str, Any]], bool]:
    """Keep the first events that fit the turn budget. overflow=True if truncated."""
    kept: list[dict[str, Any]] = []
    used = 0
    overflow = False
    for ev in events:
        body = str(ev.get("preview") or ev.get("content") or "")
        n = len(body.encode("utf-8"))
        if len(kept) >= max_events or used + n > max_bytes:
            overflow = True
            break
        kept.append(ev)
        used += n
    return kept, overflow


def cooldown_blocks(
    last_wake_unix: int,
    now_unix: int,
    cooldown_secs: int = DEFAULT_COOLDOWN_SECS,
) -> bool:
    if cooldown_secs <= 0 or last_wake_unix <= 0:
        return False
    return (now_unix - last_wake_unix) < cooldown_secs


def task_fingerprint(task: str) -> str:
    return _norm(task)[:200]


def normalize_relay(url: str) -> str:
    """Host of a Buzz relay. wss://x and https://x/ count as the same bus."""
    raw = (url or "").strip()
    if not raw:
        return ""
    no_scheme = re.sub(r"^[a-z][a-z0-9+.-]*://", "", raw, flags=re.I)
    host = no_scheme.split("/")[0].split("@")[-1].strip().lower()
    if host.endswith(":443") or host.endswith(":80"):
        host = host.rsplit(":", 1)[0]
    return host


def align_relays(seats: dict[str, str]) -> dict[str, Any]:
    """seats: name -> relay URL. aligned if every non-empty host matches."""
    hosts: dict[str, str] = {}
    for name, url in seats.items():
        host = normalize_relay(url)
        if host:
            hosts[name] = host
    unique = sorted(set(hosts.values()))
    return {
        "aligned": len(unique) <= 1,
        "hosts": hosts,
        "unique": unique,
        "missing": sorted(n for n, u in seats.items() if not normalize_relay(u)),
    }


def parse_public_txt(text: str) -> dict[str, str]:
    """Parse PUBLIC.txt. Drops nsec / private-key lines. Never reads agent.env."""
    card: dict[str, str] = {}
    allowed = ("seat", "display_name", "pubkey_hex", "npub", "relay")
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        low = line.lower()
        if "nsec1" in low or "buzz_private_key" in low:
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = _norm(key).replace(" ", "_")
        val = val.strip()
        if key in allowed and val:
            card[key] = val
    return card


def public_card_from_dir(seat_dir: str) -> dict[str, str]:
    pub = Path(seat_dir) / "PUBLIC.txt"
    if not pub.is_file():
        return {}
    return parse_public_txt(pub.read_text(encoding="utf-8", errors="replace"))


def mention_names_from_card(card: dict[str, str], seat_id: str = "") -> list[str]:
    names: list[str] = []
    for v in (card.get("seat"), card.get("display_name"), seat_id):
        n = (v or "").strip()
        if n and n not in names:
            names.append(n)
    return names


def roster_report(seat_dirs: dict[str, str]) -> dict[str, Any]:
    """Group existing seats by PUBLIC.txt relay host. agent.env is never opened."""
    cards: list[dict[str, Any]] = []
    buses: dict[str, list[str]] = {}
    missing: list[str] = []
    for seat, path in seat_dirs.items():
        card = public_card_from_dir(path)
        host = normalize_relay(card.get("relay") or "")
        names = mention_names_from_card(card, seat)
        pk = card.get("pubkey_hex") or ""
        cards.append(
            {
                "seat": seat,
                "display_name": card.get("display_name") or "",
                "pubkey_prefix": pk[:12],
                "relay": card.get("relay") or "",
                "host": host,
                "names": names,
            }
        )
        if not host:
            missing.append(seat)
            continue
        buses.setdefault(host, []).append(seat)
    hosts = {c["seat"]: c["host"] for c in cards if c["host"]}
    unique = sorted(set(hosts.values()))
    ready = len(unique) == 1 and len(hosts) >= 2 and not missing
    return {
        "aligned": len(unique) <= 1 and not missing,
        "ready": ready,
        "buses": buses,
        "missing": missing,
        "cards": cards,
        "hosts": hosts,
        "unique": unique,
    }


def relay_from_seat_dir(seat_dir: str) -> str:
    """PUBLIC.txt relay only. Never opens agent.env."""
    return public_card_from_dir(seat_dir).get("relay") or ""


def should_post_prime_escalation(
    journal: dict[str, Any],
    task: str,
) -> tuple[bool, str]:
    """Once-then-stop. Same task fingerprint never pings Prime twice."""
    fp = task_fingerprint(task)
    if not fp:
        return False, "empty-task"
    posted = journal.get("posted") or {}
    if not isinstance(posted, dict):
        posted = {}
    if fp in posted:
        return False, "already-escalated"
    return True, "ok"


def record_prime_escalation(
    journal: dict[str, Any],
    task: str,
    now_unix: int,
) -> dict[str, Any]:
    posted = dict(journal.get("posted") or {})
    posted[task_fingerprint(task)] = now_unix
    out = dict(journal)
    out["posted"] = posted
    out["last_task"] = task_fingerprint(task)
    out["last_unix"] = now_unix
    return out


def filter_wakes(
    messages: list[Any],
    *,
    state: dict[str, Any],
    self_pk: str,
    names: list[str],
    pubkeys: list[str],
    seat_role: str,
    require_mention: bool,
    is_dm: bool,
    now_unix: int,
    cooldown_secs: int = DEFAULT_COOLDOWN_SECS,
    max_events: int = DEFAULT_MAX_EVENTS,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    """Production wake seam used by wake.sh. Seen-set is updated only for
    consumed events; cooldown/overflow leaves candidates for the next tick."""
    seen = set(state.get("seen_ids") or [])
    since = int(state.get("since") or 0)
    last_wake = int(state.get("last_wake") or 0)
    new_max = since
    new_seen = set(seen)
    candidates: list[dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        mid = m.get("id") or ""
        ts = int(m.get("created_at") or 0)
        if ts > new_max:
            new_max = ts
        if mid and mid in seen:
            continue
        pk = m.get("pubkey") or ""
        content = m.get("content") or ""
        wake, reason = should_wake(
            content=content,
            from_pubkey=pk,
            self_pubkey=self_pk,
            is_dm=is_dm,
            require_mention=require_mention,
            names=names,
            pubkeys=pubkeys,
            seat_role=seat_role,
        )
        if not wake:
            if mid:
                new_seen.add(mid)
            continue
        preview = content.replace("\n", " ").strip()[:80].replace('"', "'")
        candidates.append(
            {
                "id": mid,
                "ts": ts,
                "from": pk,
                "preview": preview,
                "content": content,
                "reason": reason,
            }
        )
    cooling = cooldown_blocks(last_wake, now_unix, cooldown_secs)
    if cooling:
        return {
            "wakes": [],
            "overflow": False,
            "cooldown": True,
            "pending": len(candidates),
            "state": {
                "seen_ids": list(new_seen)[-80:],
                "since": new_max,
                "last_wake": last_wake,
                "channel_id": state.get("channel_id") or "",
            },
        }
    kept, overflow = admit_budget(
        candidates, max_events=max_events, max_bytes=max_bytes
    )
    for w in kept:
        mid = w.get("id") or ""
        if mid:
            new_seen.add(mid)
    return {
        "wakes": kept,
        "overflow": overflow,
        "cooldown": False,
        "pending": len(candidates),
        "state": {
            "seen_ids": list(new_seen)[-80:],
            "since": new_max,
            "last_wake": now_unix if kept else last_wake,
            "channel_id": state.get("channel_id") or "",
        },
    }


def _parse_kw(args: list[str]) -> dict[str, str]:
    kw: dict[str, str] = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args):
            kw[args[i][2:].replace("-", "_")] = args[i + 1]
            i += 2
        else:
            i += 1
    return kw


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "render":
        kw = _parse_kw(sys.argv[2:])
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

    if len(sys.argv) > 1 and sys.argv[1] in ("relay-align", "roster", "mention-names"):
        kw = _parse_kw(sys.argv[2:])
        home = Path(kw["home"]) if kw.get("home") else Path.home() / ".buzz-dev" / "agents"
        if sys.argv[1] == "mention-names":
            seat = kw.get("seat") or ""
            d = kw.get("dir") or str(home / seat)
            names = mention_names_from_card(public_card_from_dir(d), seat)
            print(",".join(names))
            raise SystemExit(0)
        seats_raw = kw.get("seats") or "buzz,codex-buzz,agy-buzz"
        seat_ids = [s.strip() for s in seats_raw.split(",") if s.strip()]
        if sys.argv[1] == "roster":
            dirs = {n: str(home / n) for n in seat_ids}
            report = roster_report(dirs)
            json.dump(report, sys.stdout)
            sys.stdout.write("\n")
            raise SystemExit(0 if report.get("ready") else 3)
        mapping = {n: relay_from_seat_dir(str(home / n)) for n in seat_ids}
        report = align_relays(mapping)
        json.dump(report, sys.stdout)
        sys.stdout.write("\n")
        raise SystemExit(0 if report["aligned"] else 3)

    if len(sys.argv) > 1 and sys.argv[1] in ("escalate-check", "escalate-record"):
        kw = _parse_kw(sys.argv[2:])
        path = kw.get("journal") or ""
        task = kw.get("task") or ""
        now = int(kw.get("now") or time.time())
        journal: dict[str, Any] = {}
        if path:
            try:
                with open(path, encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict):
                    journal = loaded
            except (OSError, json.JSONDecodeError):
                journal = {}
        allow, reason = should_post_prime_escalation(journal, task)
        if sys.argv[1] == "escalate-record":
            if allow:
                journal = record_prime_escalation(journal, task, now)
                if path:
                    with open(path, "w", encoding="utf-8") as fh:
                        json.dump(journal, fh, indent=2)
                        fh.write("\n")
            json.dump({"allow": allow, "reason": reason, "journal": journal}, sys.stdout)
        else:
            json.dump({"allow": allow, "reason": reason}, sys.stdout)
        sys.stdout.write("\n")
        raise SystemExit(0 if allow else 3)

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
