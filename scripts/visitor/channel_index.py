#!/usr/bin/env python3
"""Build and dump a bounded channel-index pack."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PACK_VERSION = 1
MAX_ROOMS = 80
MAX_MESSAGES = 20
DEFAULT_OUT = Path.home() / ".buzz-dev" / "channel-index.json"
DEFAULT_MAP = Path.home() / ".buzz-dev" / "channel-index-map.json"


def _clip_text(value: Any, limit: int = 4000) -> str:
    text = value if isinstance(value, str) else ""
    if len(text) > limit:
        return text[:limit]
    return text


def project_message(raw: dict[str, Any]) -> dict[str, Any]:
    kind = raw.get("kind")
    created = raw.get("created_at")
    return {
        "id": _clip_text(raw.get("id"), 64),
        "pubkey": _clip_text(raw.get("pubkey"), 64),
        "created_at": int(created) if isinstance(created, int) else 0,
        "kind": int(kind) if isinstance(kind, int) else 0,
        "content": _clip_text(raw.get("content")),
    }


def build_pack(
    rooms: list[dict[str, Any]],
    written_at: int | None = None,
) -> dict[str, Any]:
    clipped = rooms[:MAX_ROOMS]
    out_rooms: list[dict[str, Any]] = []
    for room in clipped:
        messages = room.get("messages")
        if not isinstance(messages, list):
            messages = []
        out_rooms.append(
            {
                "id": _clip_text(room.get("id"), 64),
                "name": _clip_text(room.get("name"), 120),
                "messages": [project_message(m) for m in messages[:MAX_MESSAGES] if isinstance(m, dict)],
            }
        )
    return {
        "version": PACK_VERSION,
        "written_at": int(written_at if written_at is not None else time.time()),
        "rooms": out_rooms,
    }


def _run_buzz(args: list[str]) -> Any:
    cmd = ["buzz", "--format", "compact", *args]
    env = os.environ.copy()
    raw = subprocess.check_output(cmd, env=env, text=True)
    return json.loads(raw) if raw.strip() else []


def _channel_name(channels: list[Any], room: str) -> str:
    for row in channels:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("channel_id") or row.get("id") or "")
        if cid == room:
            return str(row.get("name") or room)
    return room


def dump_live(rooms: list[str], limit: int, out: Path, all_rooms: bool = False) -> dict[str, Any]:
    limit = max(1, min(limit, MAX_MESSAGES))
    try:
        channels = _run_buzz(["channels", "list"])
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        channels = []
    if not isinstance(channels, list):
        channels = []
    if all_rooms:
        rooms = [
            str(row.get("channel_id") or row.get("id") or "")
            for row in channels
            if isinstance(row, dict)
        ]
        rooms = [r for r in rooms if r]
    rooms = rooms[:MAX_ROOMS]
    packed_rooms: list[dict[str, Any]] = []
    for room in rooms:
        try:
            messages = _run_buzz(["messages", "get", "--channel", room, "--limit", str(limit)])
        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
            messages = []
        if not isinstance(messages, list):
            messages = []
        packed_rooms.append(
            {
                "id": room,
                "name": _channel_name(channels, room),
                "messages": messages,
            }
        )
    pack = build_pack(packed_rooms)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pack, indent=2) + "\n")
    slim = {
        "version": PACK_VERSION,
        "written_at": pack["written_at"],
        "rooms": [
            {
                "id": room["id"],
                "name": room["name"],
                "n": len(room["messages"]),
                "t": room["messages"][-1]["created_at"] if room["messages"] else 0,
                "c": (room["messages"][-1]["content"] if room["messages"] else "")[:80],
            }
            for room in pack["rooms"]
        ],
    }
    map_path = out.with_name("channel-index-map.json") if out == DEFAULT_OUT else out.with_name(out.stem + "-map.json")
    map_path.write_text(json.dumps(slim, separators=(",", ":")) + "\n")
    return pack


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump a bounded channel-index pack")
    parser.add_argument("--room", action="append", default=[], help="Channel UUID (repeatable)")
    parser.add_argument("--all", action="store_true", help="Every channel the seat can list")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    if not args.room and not args.all:
        print("error: --room or --all required", file=sys.stderr)
        return 1
    pack = dump_live(args.room, args.limit, Path(args.out), all_rooms=args.all)
    print(json.dumps({"ok": True, "rooms": len(pack["rooms"]), "out": args.out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
