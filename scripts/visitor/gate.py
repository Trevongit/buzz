#!/usr/bin/env python3
"""Visitor mention gate + COLLAB v0 envelope. No network. No secrets."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Optional

COLLAB_HEADER = "COLLAB v0"
STATUS_OPEN = "OPEN"
STATUS_DONE = "DONE"
STATUS_BLOCKED = "BLOCKED"
ROLES = ("grok", "codex", "agy", "goose", "hermes")
DEFAULT_ROLE_SEATS = {
    "grok": "buzz",
    "codex": "codex-buzz",
    "agy": "agy-buzz",
    "goose": "goose",
    "hermes": "hermes-buzz",
}
DEFAULT_COOLDOWN_SECS = 30
DEFAULT_MAX_EVENTS = 3
DEFAULT_MAX_BYTES = 2048
DEFAULT_L2_LEASE_TTL_SECS = 300
DEFAULT_L2_BODY_CAP = 80
DEFAULT_L2_RETRY_MAX = 3
DEFAULT_L2_LOG_MAX_BYTES = 65536
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
    """Parse a COLLAB v0 block. Unknown keys ignored. None if not an envelope.

    The header may follow other body text (lab posts put the round token last).
    """
    text = (content or "").strip()
    if not text:
        return None
    lines = text.splitlines()
    start = None
    for i, raw in enumerate(lines):
        s = raw.strip()
        s = re.sub(r"^```[a-zA-Z0-9]*\s*", "", s).strip()
        if s.upper().startswith(COLLAB_HEADER.upper()):
            start = i
    if start is None:
        return None
    fields: dict[str, str] = {}
    for raw in lines[start + 1 :]:
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


def collab_send_gate(content: str) -> dict[str, Any]:
    """Classify a post body. Raw --content/--file COLLAB is the same seam as --to/--task."""
    env = parse_collab_envelope(content)
    if not env:
        return {
            "envelope": False,
            "escalate": False,
            "from": "",
            "to": "",
            "task": "",
            "status": "",
            "need_prime": "false",
        }
    return {
        "envelope": True,
        "escalate": should_escalate_to_prime(env),
        "from": _norm(env.get("from") or ""),
        "to": _norm(env.get("to") or ""),
        "task": (env.get("task") or "").strip(),
        "status": (env.get("status") or STATUS_OPEN).upper(),
        "need_prime": _norm(env.get("need_prime") or "false"),
    }


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
    if env:
        if envelope_to(env, seat_role, names):
            return True, "collab"
        # Round token wins over extra @mentions (Trial 2: dual-@ woke Codex
        # while COLLAB to: agy).
        return False, "collab-other"
    if not require_mention:
        return True, "open"
    if addressed_to(content, names, pubkeys):
        return True, "mention"
    return False, "unaddressed"


def l2_wake_blob(preview: str, hist: str) -> str:
    """Join wake preview with bounded history contents for dest checks."""
    parts = [preview or ""]
    raw = (hist or "").strip()
    if raw.startswith("["):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            for ev in data:
                if isinstance(ev, dict):
                    parts.append(str(ev.get("content") or ""))
            return "\n".join(parts)
    parts.append(raw)
    return "\n".join(parts)


def l2_collab_hint(content: str) -> str:
    env = parse_collab_envelope(content)
    if not env:
        return ""
    to = env.get("to") or ""
    fr = env.get("from") or ""
    task = (env.get("task") or "").strip()
    return f"COLLAB to: {to} from: {fr} task: {task}"


def redact_auto_reply_log(text: str, max_bytes: int = DEFAULT_L2_LOG_MAX_BYTES) -> str:
    """Strip secrets and cap diagnostics. Codex finding: log must not keep prompts/keys."""
    out = text or ""
    out = re.sub(r"nsec1[a-z0-9]{20,}", "nsec1[redacted]", out, flags=re.IGNORECASE)
    out = re.sub(
        r"BUZZ_PRIVATE_KEY\s*=\s*\S+",
        "BUZZ_PRIVATE_KEY=[redacted]",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"BUZZ_NSEC\s*=\s*\S+",
        "BUZZ_NSEC=[redacted]",
        out,
        flags=re.IGNORECASE,
    )
    if max_bytes > 0 and len(out.encode("utf-8")) > max_bytes:
        raw = out.encode("utf-8")[-max_bytes:]
        out = raw.decode("utf-8", errors="ignore")
    return out


def l2_retry_bump(
    journal: dict[str, Any],
    wake_id: str,
    max_n: int = DEFAULT_L2_RETRY_MAX,
) -> tuple[dict[str, Any], bool, int]:
    """Count a failed turn. False = stop (do not unsee; no more retries)."""
    if not wake_id or wake_id == "catch":
        return dict(journal), False, 0
    retries = dict(journal.get("retries") or {})
    n = int(retries.get(wake_id) or 0) + 1
    retries[wake_id] = n
    out = dict(journal)
    out["retries"] = retries
    return out, n <= int(max_n), n


def l2_noreply_allowed(
    *,
    content: str,
    seat_role: str,
    names: list[str],
    is_dm: bool = False,
) -> tuple[bool, str]:
    """Print-mode may emit NO_REPLY only when this seat is not the dest.

    Trial 2: agy woke on COLLAB to: all but preview was 'Trevor,' and chose
    NO_REPLY. Duplicate skip is same-body in the kit, not NO_REPLY.
    """
    if is_dm:
        return False, "dm-must-reply"
    env = parse_collab_envelope(content)
    if env and envelope_to(env, seat_role, names):
        return False, "collab-must-reply"
    if addressed_to(content, names, []):
        return False, "mention-must-reply"
    return True, "noreply-ok"


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


COMMUNITY_ALIASES = {
    # Desktop switcher names (what Prime sees), then relay hosts.
    "open121": "groundfeed.communities.buzz.xyz",
    "groundfeed": "groundfeed.communities.buzz.xyz",
    "asus-g501vw": "asus-g501vw.tailb74de6.ts.net",
    "tailscale": "asus-g501vw.tailb74de6.ts.net",
    "librarian": "asus-g501vw.tailb74de6.ts.net",
    "asus": "asus-g501vw.tailb74de6.ts.net",
    "local": "localhost:3000",
    "localhost": "localhost:3000",
}


def resolve_community_want(raw: str) -> str:
    """Map a community name or URL to a host. Empty if none given."""
    s = _norm(raw).lstrip("#")
    if not s:
        return ""
    if s in COMMUNITY_ALIASES:
        return COMMUNITY_ALIASES[s]
    return normalize_relay(raw) or s


def community_for_seat(seat_dir: str, want: str = "") -> dict[str, Any]:
    """Default community is PUBLIC.txt. Ask if missing; refuse a silent other bus."""
    card = public_card_from_dir(seat_dir)
    host = normalize_relay(card.get("relay") or "")
    want_host = resolve_community_want(want)
    if not host:
        return {
            "ok": False,
            "reason": "community-missing",
            "host": "",
            "want": want_host,
            "relay": "",
        }
    if want_host and want_host != host:
        return {
            "ok": False,
            "reason": "community-mismatch",
            "host": host,
            "want": want_host,
            "relay": card.get("relay") or "",
        }
    return {
        "ok": True,
        "reason": "community-ok",
        "host": host,
        "want": want_host or host,
        "relay": card.get("relay") or "",
    }


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
    """seats: name -> relay URL. Fail-closed: aligned only when every named
    seat resolved and they share exactly one host. Empty/missing is not aligned.
    """
    hosts: dict[str, str] = {}
    for name, url in seats.items():
        host = normalize_relay(url)
        if host:
            hosts[name] = host
    unique = sorted(set(hosts.values()))
    missing = sorted(n for n, u in seats.items() if not normalize_relay(u))
    return {
        "aligned": len(unique) == 1 and not missing,
        "hosts": hosts,
        "unique": unique,
        "missing": missing,
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


_AT_NAME = re.compile(r"@([A-Za-z0-9_.-]{2,64})")


def mention_pubkeys_from_content(content: str, agents_home: str) -> list[str]:
    """Map @names in body to PUBLIC.txt pubkeys. Never opens agent.env."""
    home = Path(agents_home)
    cards: list[dict[str, str]] = []
    if home.is_dir():
        for d in sorted(home.iterdir()):
            if not d.is_dir():
                continue
            card = public_card_from_dir(str(d))
            if not card.get("seat"):
                card["seat"] = d.name
            cards.append(card)
    found: list[str] = []
    seen: set[str] = set()
    for raw in _AT_NAME.findall(content or ""):
        n = _norm(raw)
        for card in cards:
            names = mention_names_from_card(card, card.get("seat") or "")
            pk = card.get("pubkey_hex") or ""
            if n not in {_norm(x) for x in names}:
                continue
            if pk and pk not in seen:
                seen.add(pk)
                found.append(pk)
            break
    return found


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
        "aligned": len(unique) == 1 and not missing,
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


def last_room_bus_ok(seat_dir: str) -> dict[str, Any]:
    """Fail-closed: last-room.json relay host must match PUBLIC.txt when set.
    Missing last-room (or a card with no relay) is not a mismatch. Never opens agent.env."""
    pub_host = normalize_relay(relay_from_seat_dir(seat_dir))
    path = Path(seat_dir) / "last-room.json"
    if not path.is_file():
        return {
            "ok": True,
            "reason": "no-last-room",
            "last_host": "",
            "public_host": pub_host,
        }
    try:
        loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        loaded = None
    if not isinstance(loaded, dict):
        return {
            "ok": False,
            "reason": "last-room-invalid",
            "last_host": "",
            "public_host": pub_host,
        }
    last_host = normalize_relay(str(loaded.get("relay") or ""))
    if not last_host:
        return {
            "ok": True,
            "reason": "last-room-relay-missing",
            "last_host": "",
            "public_host": pub_host,
        }
    if not pub_host:
        return {
            "ok": False,
            "reason": "public-relay-missing",
            "last_host": last_host,
            "public_host": "",
        }
    if last_host != pub_host:
        return {
            "ok": False,
            "reason": "last-room-bus-mismatch",
            "last_host": last_host,
            "public_host": pub_host,
        }
    return {
        "ok": True,
        "reason": "last-room-bus-match",
        "last_host": last_host,
        "public_host": pub_host,
    }


def public_env_relay_ok(seat_dir: str, env_relay: str) -> dict[str, Any]:
    """Fail-closed: process BUZZ_RELAY_URL host must match PUBLIC.txt.
    Never opens agent.env. Does not write files."""
    pub_host = normalize_relay(relay_from_seat_dir(seat_dir))
    env_host = normalize_relay(env_relay)
    if not pub_host:
        reason = "public-relay-missing"
        ok = False
    elif not env_host:
        reason = "env-relay-missing"
        ok = False
    elif pub_host != env_host:
        reason = "public-env-mismatch"
        ok = False
    else:
        reason = "public-env-match"
        ok = True
    return {
        "ok": ok,
        "reason": reason,
        "public_host": pub_host,
        "env_host": env_host,
    }


def parse_send_event_id(raw: str) -> str:
    """Extract accepted event_id from buzz messages send JSON. Empty if missing."""
    text = (raw or "").strip()
    if not text:
        return ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return ""
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return ""
    if not isinstance(data, dict):
        return ""
    if data.get("accepted") is False:
        return ""
    eid = data.get("event_id") or ""
    return eid if isinstance(eid, str) else ""


def l2_already_posted(journal: dict[str, Any], wake_id: str) -> bool:
    if not wake_id:
        return False
    posted = journal.get("posted") or {}
    if not isinstance(posted, dict):
        return False
    return wake_id in posted or any(
        str(k).startswith(wake_id) or wake_id.startswith(str(k)[:12])
        for k in posted
    )


def l2_record_posted(
    journal: dict[str, Any], wake_id: str, event_id: str, now_unix: int
) -> dict[str, Any]:
    posted = dict(journal.get("posted") or {})
    if wake_id and event_id:
        posted[wake_id] = {"event_id": event_id, "unix": now_unix}
    out = dict(journal)
    out["posted"] = posted
    return out


def normalize_l2_body(text: str) -> str:
    """Collapse whitespace so bullet clones hash the same."""
    return " ".join((text or "").split())


def l2_body_hash(text: str) -> str:
    return hashlib.sha256(normalize_l2_body(text).encode("utf-8")).hexdigest()


def l2_round_key(text: str) -> str:
    """Scope by COLLAB task when present; otherwise the body itself."""
    env = parse_collab_envelope(text)
    if env:
        task = _norm(env.get("task") or "")
        if task:
            return f"task:{task}"
    return "body"


def l2_suppress_key(channel: str, text: str) -> str:
    ch = _norm(channel)
    if not ch:
        return ""
    return f"{ch}|{l2_round_key(text)}|{l2_body_hash(text)}"


def l2_body_suppressed(journal: dict[str, Any], channel: str, text: str) -> bool:
    key = l2_suppress_key(channel, text)
    if not key:
        return False
    bodies = journal.get("bodies") or {}
    if isinstance(bodies, dict) and key in bodies:
        return True
    inflight = journal.get("inflight") or {}
    return isinstance(inflight, dict) and key in inflight


def l2_inflight_begin(
    journal: dict[str, Any],
    channel: str,
    text: str,
    wake_id: str,
    now_unix: int,
) -> dict[str, Any]:
    """Mark a send started so a timeout cannot send the same body again."""
    key = l2_suppress_key(channel, text)
    inflight = dict(journal.get("inflight") or {})
    if key:
        inflight[key] = {"wake": wake_id, "unix": int(now_unix)}
    out = dict(journal)
    out["inflight"] = inflight
    return out


def l2_inflight_clear(
    journal: dict[str, Any], channel: str, text: str
) -> dict[str, Any]:
    key = l2_suppress_key(channel, text)
    inflight = dict(journal.get("inflight") or {})
    if key and key in inflight:
        del inflight[key]
    out = dict(journal)
    out["inflight"] = inflight
    return out


def l2_record_body(
    journal: dict[str, Any],
    channel: str,
    text: str,
    event_id: str,
    now_unix: int,
    cap: int = DEFAULT_L2_BODY_CAP,
) -> dict[str, Any]:
    bodies: dict[str, Any] = dict(journal.get("bodies") or {})
    key = l2_suppress_key(channel, text)
    if key:
        bodies[key] = {"event_id": event_id, "unix": int(now_unix)}
    if cap > 0 and len(bodies) > cap:
        ranked = sorted(
            bodies.items(),
            key=lambda kv: int((kv[1] or {}).get("unix") or 0)
            if isinstance(kv[1], dict)
            else 0,
        )
        bodies = dict(ranked[-cap:])
    out = dict(journal)
    out["bodies"] = bodies
    return out


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def l2_lease_take(
    state: dict[str, Any], pid: int, now_unix: int, ttl: int = DEFAULT_L2_LEASE_TTL_SECS
) -> dict[str, Any]:
    epoch = int(state.get("epoch") or 0) + 1
    return {
        "epoch": epoch,
        "pid": int(pid),
        "unix": int(now_unix),
        "ttl": int(ttl),
    }


def l2_lease_heartbeat(
    state: dict[str, Any], pid: int, epoch: int, now_unix: int
) -> tuple[Optional[dict[str, Any]], str]:
    if int(state.get("epoch") or 0) != int(epoch):
        return None, "stale-epoch"
    if int(state.get("pid") or 0) != int(pid):
        return None, "stale-pid"
    out = dict(state)
    out["unix"] = int(now_unix)
    return out, "ok"


def l2_lease_check(
    state: dict[str, Any],
    pid: int,
    epoch: int,
    now_unix: int,
    ttl: int = DEFAULT_L2_LEASE_TTL_SECS,
    pid_alive: Callable[[int], bool] = _pid_alive,
) -> tuple[bool, str]:
    if int(state.get("epoch") or 0) != int(epoch):
        return False, "stale-epoch"
    if int(state.get("pid") or 0) != int(pid):
        return False, "stale-pid"
    age = int(now_unix) - int(state.get("unix") or 0)
    if ttl > 0 and age > int(ttl):
        return False, "lease-expired"
    if not pid_alive(int(pid)):
        return False, "pid-dead"
    return True, "ok"


def l2_lease_is_stale(
    state: dict[str, Any],
    now_unix: int,
    ttl: int = DEFAULT_L2_LEASE_TTL_SECS,
    pid_alive: Callable[[int], bool] = _pid_alive,
) -> bool:
    pid = int(state.get("pid") or 0)
    if pid and pid_alive(pid):
        age = int(now_unix) - int(state.get("unix") or 0)
        return ttl > 0 and age > int(ttl)
    return True


def parse_wake_line(line: str) -> dict[str, str]:
    """Parse a `VISITOR_WAKE …` stdout line. Empty dict if not a wake."""
    s = (line or "").strip()
    if not s.startswith("VISITOR_WAKE"):
        return {}
    out: dict[str, str] = {}
    for part in s.split()[1:]:
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        k, v = k.strip(), v.strip()
        if k:
            out[k] = v
    return out


def role_from_seat(seat_id: str, mapping: dict[str, str] | None = None) -> str:
    """Inverse of DEFAULT_ROLE_SEATS. Unknown seats return empty (not grok)."""
    m = dict(DEFAULT_ROLE_SEATS)
    if mapping:
        m.update(mapping)
    s = _norm(seat_id)
    if not s:
        return ""
    for role, seat in m.items():
        if _norm(seat) == s:
            return role
    for role in ROLES:
        if s == role or s.startswith(f"{role}-"):
            return role
    return ""


def parse_role_seats(raw: str) -> dict[str, str]:
    out = dict(DEFAULT_ROLE_SEATS)
    for part in (raw or "").split(","):
        part = part.strip()
        if ":" not in part:
            continue
        k, _, v = part.partition(":")
        k, v = _norm(k), v.strip()
        if k and v:
            out[k] = v
    return out


def same_bus_for_roles(
    *,
    from_role: str,
    to_role: str,
    agents_home: str,
    role_seats: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Fail-closed: COLLAB `to:` must share the sender's PUBLIC.txt host."""
    mapping = dict(DEFAULT_ROLE_SEATS)
    if role_seats:
        mapping.update(role_seats)
    home = Path(agents_home)
    dest = _norm(to_role)
    fr = mapping.get(_norm(from_role), "")
    if dest in ("all", "*"):
        dirs = {s: str(home / s) for s in mapping.values()}
        report = roster_report(dirs)
        present = {
            s: p
            for s, p in dirs.items()
            if normalize_relay(relay_from_seat_dir(p))
        }
        from_host = normalize_relay(relay_from_seat_dir(str(home / fr))) if fr else ""
        unique = sorted(
            {
                normalize_relay(relay_from_seat_dir(p))
                for p in present.values()
            }
        )
        unique = [h for h in unique if h]
        # Parked/missing seats (hermes) must not block. Mixed *present* buses do.
        ok = (
            bool(from_host)
            and len(present) >= 2
            and unique == [from_host]
        )
        return {
            "ok": ok,
            "reason": "all-ready" if ok else "to-all-not-ready",
            "from_seat": fr,
            "to_seat": "all",
            "report": report,
        }
    to = mapping.get(dest, dest)
    dirs: dict[str, str] = {}
    if fr:
        dirs[fr] = str(home / fr)
    if to:
        dirs[to] = str(home / to)
    report = roster_report(dirs)
    ok = bool(report.get("ready"))
    return {
        "ok": ok,
        "reason": "same-bus" if ok else "mixed-or-missing",
        "from_seat": fr,
        "to_seat": to,
        "report": report,
    }


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


def _agents_home(kw: dict[str, str]) -> Path:
    if kw.get("home"):
        return Path(kw["home"])
    env = (os.environ.get("VISITOR_AGENTS_HOME") or "").strip()
    if env:
        return Path(env)
    return Path.home() / ".buzz-dev" / "agents"


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

    if len(sys.argv) > 1 and sys.argv[1] == "same-bus":
        kw = _parse_kw(sys.argv[2:])
        home = str(_agents_home(kw))
        report = same_bus_for_roles(
            from_role=kw.get("from", ""),
            to_role=kw.get("to", ""),
            agents_home=home,
            role_seats=parse_role_seats(kw.get("role_seats") or ""),
        )
        json.dump({k: report[k] for k in ("ok", "reason", "from_seat", "to_seat")}, sys.stdout)
        sys.stdout.write("\n")
        raise SystemExit(0 if report["ok"] else 3)

    if len(sys.argv) > 1 and sys.argv[1] == "role-from-seat":
        kw = _parse_kw(sys.argv[2:])
        print(role_from_seat(kw.get("seat") or ""))
        raise SystemExit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "mention-pubkeys":
        kw = _parse_kw(sys.argv[2:])
        home = kw.get("home") or str(_agents_home(kw))
        body = sys.stdin.read()
        for pk in mention_pubkeys_from_content(body, home):
            print(pk)
        raise SystemExit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "parse-send-id":
        print(parse_send_event_id(sys.stdin.read()), end="")
        raise SystemExit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "l2-posted":
        kw = _parse_kw(sys.argv[2:])
        path = Path(kw.get("file") or "")
        try:
            journal = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            journal = {}
        if not isinstance(journal, dict):
            journal = {}
        action = kw.get("action") or "check"
        wake_id = kw.get("wake") or ""
        if action == "check":
            raise SystemExit(0 if l2_already_posted(journal, wake_id) else 1)
        if action == "record":
            journal = l2_record_posted(
                journal, wake_id, kw.get("event") or "", int(time.time())
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
            raise SystemExit(0)
        raise SystemExit(2)

    if len(sys.argv) > 1 and sys.argv[1] == "l2-body":
        kw = _parse_kw(sys.argv[2:])
        path = Path(kw.get("file") or "")
        try:
            journal = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            journal = {}
        if not isinstance(journal, dict):
            journal = {}
        body_path = kw.get("body_file") or kw.get("body-file") or ""
        text = Path(body_path).read_text(encoding="utf-8") if body_path else sys.stdin.read()
        room = kw.get("room") or ""
        action = kw.get("action") or "check"
        if action == "check":
            raise SystemExit(0 if l2_body_suppressed(journal, room, text) else 1)
        if action == "record":
            journal = l2_inflight_clear(journal, room, text)
            journal = l2_record_body(
                journal, room, text, kw.get("event") or "", int(time.time())
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
            raise SystemExit(0)
        if action == "inflight-begin":
            journal = l2_inflight_begin(
                journal, room, text, kw.get("wake") or "", int(time.time())
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
            raise SystemExit(0)
        raise SystemExit(2)

    if len(sys.argv) > 1 and sys.argv[1] == "l2-lease":
        kw = _parse_kw(sys.argv[2:])
        path = Path(kw.get("file") or "")
        try:
            state = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            state = {}
        if not isinstance(state, dict):
            state = {}
        action = kw.get("action") or "check"
        pid = int(kw.get("pid") or "0")
        epoch = int(kw.get("epoch") or "0")
        ttl = int(kw.get("ttl") or str(DEFAULT_L2_LEASE_TTL_SECS))
        now = int(time.time())
        if action == "take":
            state = l2_lease_take(state, pid, now, ttl)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            print(state["epoch"])
            raise SystemExit(0)
        if action == "heartbeat":
            nxt, reason = l2_lease_heartbeat(state, pid, epoch, now)
            if nxt is None:
                print(reason)
                raise SystemExit(1)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(nxt, indent=2) + "\n", encoding="utf-8")
            print("ok")
            raise SystemExit(0)
        if action == "check":
            ok, reason = l2_lease_check(state, pid, epoch, now, ttl)
            print(reason)
            raise SystemExit(0 if ok else 1)
        if action == "stale":
            stale = l2_lease_is_stale(state, now, ttl)
            print("stale" if stale else "held")
            raise SystemExit(0 if stale else 1)
        raise SystemExit(2)

    if len(sys.argv) > 1 and sys.argv[1] == "redact-log":
        kw = _parse_kw(sys.argv[2:])
        path = Path(kw.get("file") or "")
        if not path.is_file():
            raise SystemExit(0)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            raise SystemExit(0)
        max_b = int(kw.get("max_bytes") or str(DEFAULT_L2_LOG_MAX_BYTES))
        path.write_text(redact_auto_reply_log(raw, max_b), encoding="utf-8")
        raise SystemExit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "l2-retry":
        kw = _parse_kw(sys.argv[2:])
        path = Path(kw.get("file") or "")
        try:
            journal = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            journal = {}
        if not isinstance(journal, dict):
            journal = {}
        journal, ok, n = l2_retry_bump(journal, kw.get("wake") or "")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
        print(n)
        raise SystemExit(0 if ok else 1)

    if len(sys.argv) > 1 and sys.argv[1] == "l2-noreply":
        kw = _parse_kw(sys.argv[2:])
        hist = sys.stdin.read()
        blob = l2_wake_blob(kw.get("preview") or "", hist)
        names = [x.strip() for x in (kw.get("names") or "").split(",") if x.strip()]
        role = kw.get("role") or ""
        if not names:
            names = [role] if role else []
        is_dm = _norm(kw.get("dm") or "") in ("1", "true", "yes")
        allowed, reason = l2_noreply_allowed(
            content=blob, seat_role=role, names=names, is_dm=is_dm
        )
        print(reason)
        raise SystemExit(0 if allowed else 1)

    if len(sys.argv) > 1 and sys.argv[1] == "l2-hint":
        kw = _parse_kw(sys.argv[2:])
        hist = sys.stdin.read()
        blob = l2_wake_blob(kw.get("preview") or "", hist)
        print(l2_collab_hint(blob), end="")
        raise SystemExit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "parse-wake":
        parsed = parse_wake_line(sys.stdin.read())
        json.dump(parsed, sys.stdout)
        sys.stdout.write("\n")
        raise SystemExit(0 if parsed else 1)

    if len(sys.argv) > 1 and sys.argv[1] == "send-gate":
        report = collab_send_gate(sys.stdin.read())
        json.dump(report, sys.stdout)
        sys.stdout.write("\n")
        raise SystemExit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "community-for-seat":
        kw = _parse_kw(sys.argv[2:])
        report = community_for_seat(kw.get("dir") or "", kw.get("want") or "")
        json.dump(report, sys.stdout)
        sys.stdout.write("\n")
        raise SystemExit(0 if report["ok"] else 3)

    if len(sys.argv) > 1 and sys.argv[1] in ("public-env", "relay-from-dir", "last-room-bus"):
        kw = _parse_kw(sys.argv[2:])
        d = kw.get("dir") or ""
        if sys.argv[1] == "relay-from-dir":
            print(relay_from_seat_dir(d), end="")
            raise SystemExit(0)
        if sys.argv[1] == "last-room-bus":
            report = last_room_bus_ok(d)
            json.dump(report, sys.stdout)
            sys.stdout.write("\n")
            raise SystemExit(0 if report["ok"] else 3)
        report = public_env_relay_ok(d, kw.get("relay") or "")
        json.dump(report, sys.stdout)
        sys.stdout.write("\n")
        raise SystemExit(0 if report["ok"] else 3)

    if len(sys.argv) > 1 and sys.argv[1] in ("relay-align", "roster", "mention-names"):
        kw = _parse_kw(sys.argv[2:])
        home = _agents_home(kw)
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
        seat_role=payload.get("seat_role") or "",
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
