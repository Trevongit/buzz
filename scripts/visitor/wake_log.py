"""Durable wake line. Event id, first wake, and the post that answered it.

No preview and no message body. A replay is the same id after a reply.
A prompt handed in with an unknown id is a missing ear record.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

KEEP = 200
WINDOW_S = 12 * 3600
_ID = re.compile(r"^[0-9a-f]{64}$")
_WAKE_ID = re.compile(r"\bid=([0-9a-f]{64})\b")


def _hex64(value: str) -> str:
    s = (value or "").strip().lower()
    return s if _ID.fullmatch(s) else ""


def _seat_ok(seat: str) -> bool:
    name = (seat or "").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", name):
        return False
    return name.startswith("buzz") or name.endswith("-buzz")


def log_path(seat: str, home: Path | None = None) -> Path:
    root = Path(home) if home else Path.home() / ".buzz-dev" / "agents"
    return root / seat / "wake-log.json"


def _load(path: Path) -> dict:
    if not path.is_file():
        return {"rows": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"rows": []}
    if not isinstance(data, dict):
        return {"rows": []}
    rows = [r for r in (data.get("rows") or []) if isinstance(r, dict) and _hex64(str(r.get("id") or ""))]
    return {"rows": rows}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps({"rows": data.get("rows") or []}, indent=2) + "\n"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(blob, encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _find(rows: list[dict], eid: str) -> dict | None:
    for row in rows:
        if row.get("id") == eid:
            return row
    return None


def note_wake(seat: str, event_id: str, now: int | None = None, home: Path | None = None) -> dict:
    eid = _hex64(event_id)
    if not eid or not _seat_ok(seat):
        return {"kind": "plain"}
    now = int(time.time()) if now is None else int(now)
    path = log_path(seat, home)
    data = _load(path)
    row = _find(data["rows"], eid)
    if row is None:
        row = {
            "id": eid,
            "first_wake": now,
            "reply_id": "",
            "reply_at": 0,
            "replays": 0,
            "last_replay": 0,
            "no_ear": False,
        }
        data["rows"].append(row)
        data["rows"] = data["rows"][-KEEP:]
        _save(path, data)
        return {"kind": "new", "id": eid, "first_wake": now, "reply_id": ""}
    if row.get("reply_id"):
        row["replays"] = int(row.get("replays") or 0) + 1
        row["last_replay"] = now
        _save(path, data)
        return {
            "kind": "replay",
            "id": eid,
            "first_wake": int(row.get("first_wake") or 0),
            "reply_id": str(row.get("reply_id") or ""),
            "replays": int(row["replays"]),
        }
    return {"kind": "open", "id": eid, "first_wake": int(row.get("first_wake") or 0), "reply_id": ""}


def note_reply(
    seat: str,
    event_id: str,
    reply_id: str,
    now: int | None = None,
    home: Path | None = None,
) -> dict:
    eid = _hex64(event_id)
    rid = _hex64(reply_id)
    if not eid or not rid or not _seat_ok(seat):
        return {"kind": "plain"}
    now = int(time.time()) if now is None else int(now)
    path = log_path(seat, home)
    data = _load(path)
    row = _find(data["rows"], eid)
    if row is None:
        row = {
            "id": eid,
            "first_wake": now,
            "reply_id": rid,
            "reply_at": now,
            "replays": 0,
            "last_replay": 0,
            "no_ear": False,
        }
        data["rows"].append(row)
    else:
        row["reply_id"] = rid
        row["reply_at"] = now
    data["rows"] = data["rows"][-KEEP:]
    _save(path, data)
    return {"kind": "answered", "id": eid, "reply_id": rid}


def note_no_ear(seat: str, event_id: str, now: int | None = None, home: Path | None = None) -> dict:
    eid = _hex64(event_id)
    if not eid or not _seat_ok(seat):
        return {"kind": "plain"}
    now = int(time.time()) if now is None else int(now)
    path = log_path(seat, home)
    data = _load(path)
    row = _find(data["rows"], eid)
    if row is None:
        row = {
            "id": eid,
            "first_wake": now,
            "reply_id": "",
            "reply_at": 0,
            "replays": 0,
            "last_replay": 0,
            "no_ear": True,
        }
        data["rows"].append(row)
        data["rows"] = data["rows"][-KEEP:]
    else:
        row["no_ear"] = True
        if not row.get("first_wake"):
            row["first_wake"] = now
    _save(path, data)
    return {"kind": "no_ear", "id": eid, "first_wake": int(row.get("first_wake") or now)}


def classify(seat: str, event_id: str, home: Path | None = None) -> dict:
    """Read only. Does not create a row."""
    eid = _hex64(event_id)
    if not eid or not _seat_ok(seat):
        return {"kind": "plain"}
    row = _find(_load(log_path(seat, home))["rows"], eid)
    if row is None:
        return {"kind": "no_ear", "id": eid, "reply_id": ""}
    if row.get("reply_id"):
        return {
            "kind": "replay",
            "id": eid,
            "reply_id": str(row.get("reply_id") or ""),
            "first_wake": int(row.get("first_wake") or 0),
        }
    return {"kind": "open", "id": eid, "first_wake": int(row.get("first_wake") or 0), "reply_id": ""}


def annotate_prompt(seat: str, text: str, now: int | None = None, home: Path | None = None) -> str:
    """Prefix a handed wake line. Leaves every other paste alone."""
    found = _WAKE_ID.search(text or "")
    if not found or not _seat_ok(seat):
        return text
    eid = found.group(1)
    mark = classify(seat, eid, home=home)
    if mark.get("kind") == "replay":
        note_wake(seat, eid, now=now, home=home)
        reply = mark.get("reply_id") or ""
        return f"REPLAY of {eid}, answered by {reply}. Do not answer it again.\n{text}"
    if mark.get("kind") == "no_ear":
        note_no_ear(seat, eid, now=now, home=home)
        return f"NO EAR RECORD for {eid}. The ear has no wake for this id.\n{text}"
    return text


def lamp_view(home: Path | None = None, now: int | None = None) -> dict:
    """Scoreboard. Seat names and counts. No event ids and no preview."""
    now = int(time.time()) if now is None else int(now)
    root = Path(home) if home else Path.home() / ".buzz-dev" / "agents"
    files = sorted(root.glob("*/wake-log.json")) if root.is_dir() else []
    if not files:
        return {"present": False, "hot": False, "why": "no log", "replays": 0, "no_ear": 0}
    replays = 0
    missing = 0
    seats: list[str] = []
    for path in files:
        data = _load(path)
        seat = path.parent.name
        seat_hot = False
        for row in data["rows"]:
            stamp = int(row.get("last_replay") or row.get("first_wake") or 0)
            fresh = stamp > 0 and (now - stamp) <= WINDOW_S
            if int(row.get("replays") or 0) > 0 and fresh:
                replays += int(row.get("replays") or 0)
                seat_hot = True
            if row.get("no_ear") and fresh:
                missing += 1
                seat_hot = True
        if seat_hot and seat not in seats:
            seats.append(seat)
    if replays or missing:
        bits = []
        if replays:
            bits.append(f"replay {replays}")
        if missing:
            bits.append(f"no ear record {missing}")
        if seats:
            bits.append(", ".join(seats[:3]))
        return {
            "present": True,
            "hot": True,
            "why": " · ".join(bits),
            "replays": replays,
            "no_ear": missing,
        }
    return {"present": True, "hot": False, "why": "quiet", "replays": 0, "no_ear": 0}


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("usage: wake_log.py note-wake|note-reply|classify --seat S --id ID [--reply ID]")
        return 0
    cmd = args[0]
    kw: dict[str, str] = {}
    i = 1
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args):
            kw[args[i][2:]] = args[i + 1]
            i += 2
        else:
            i += 1
    seat = kw.get("seat") or ""
    eid = kw.get("id") or ""
    if cmd == "note-wake":
        out = note_wake(seat, eid)
    elif cmd == "note-reply":
        out = note_reply(seat, eid, kw.get("reply") or "")
    elif cmd == "classify":
        out = classify(seat, eid)
    else:
        print("kind=plain")
        return 2
    kind = out.get("kind") or "plain"
    extra = ""
    if out.get("reply_id"):
        extra += f" answered={out['reply_id']}"
    print(f"kind={kind}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv))
