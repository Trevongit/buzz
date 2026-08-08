#!/usr/bin/env python3
"""seat-location.v0 proof builder + optional board heartbeat (P6).

Does not replace HTTP control. Hybrid plan: proofs ride JSON/status;
optional phone-safe board line on ability channel.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional


SCHEMA = "seat-location.v0"


def host_role() -> str:
    return os.environ.get("BUZZ_HOST_ROLE") or "home"


def host_id() -> str:
    return os.environ.get("BUZZ_HOST_ID") or os.uname().nodename


def registry_path() -> Path:
    override = os.environ.get("BUZZ_HOST_REGISTRY")
    if override:
        return Path(override)
    return Path.home() / ".buzz-dev" / "hosts" / host_role() / "registry.json"


def units_dir() -> Path:
    return Path.home() / ".buzz-dev" / "hosts" / host_role() / "units"


def load_registry() -> dict[str, Any]:
    path = registry_path()
    if not path.is_file():
        return {"seats": [], "host_id": host_id(), "host_role": host_role()}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"seats": [], "host_id": host_id(), "host_role": host_role()}


def live_units() -> list[dict[str, Any]]:
    root = units_dir()
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for pidf in root.glob("*/watch.pid"):
        unit = pidf.parent.name
        pid: Optional[int] = None
        alive = False
        try:
            pid = int(pidf.read_text().strip())
            os.kill(pid, 0)
            alive = True
        except (ValueError, OSError, ProcessLookupError):
            alive = False
        out.append(
            {
                "unit_name": unit,
                "unit_pid": pid,
                "alive": alive,
            }
        )
    return out


def build_location_proof(status: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Assemble seat-location.v0 document for all registry seats."""
    reg = load_registry()
    units = live_units()
    now = int(time.time())
    seats_out = []
    for seat in reg.get("seats") or []:
        sid = seat.get("seat_id") or ""
        unit_match = next(
            (u for u in units if u["unit_name"].startswith(sid + "-") or u["unit_name"] == sid),
            None,
        )
        surface = (
            seat.get("surface_root")
            or os.environ.get(f"BUZZ_SURFACE_ROOT_{sid.upper().replace('-', '_')}")
            or os.environ.get("BUZZ_SURFACE_ROOT")
            or ""
        )
        health = "stopped"
        if unit_match and unit_match.get("alive"):
            health = "online"
        elif seat.get("expected_online"):
            health = "stale"
        seats_out.append(
            {
                "seat_id": sid,
                "pubkey": seat.get("pubkey") or seat.get("pubkey_hint") or "",
                "host_id": reg.get("host_id") or host_id(),
                "host_role": reg.get("host_role") or host_role(),
                "surface_root": surface,
                "surface_kind": seat.get("surface_kind") or ("path" if surface else ""),
                "git_head": seat.get("git_head") or "",
                "runtime": ",".join(seat.get("runtimes") or []),
                "model": seat.get("model") or "",
                "health": health,
                "channels": seat.get("channels") or [],
                "project_ids": seat.get("project_ids") or [],
                "unit_name": (unit_match or {}).get("unit_name") or "",
                "unit_pid": (unit_match or {}).get("unit_pid"),
                "updated_at": now,
            }
        )
    proof = {
        "schema": SCHEMA,
        "host_id": reg.get("host_id") or host_id(),
        "host_role": reg.get("host_role") or host_role(),
        "ts": now,
        "seats": seats_out,
        "status_excerpt": {
            "relay_ok": (status or {}).get("relay", {}).get("ok") if status else None,
            "ollama_ok": (status or {}).get("ollama", {}).get("ok") if status else None,
        },
    }
    return proof


def phone_safe_board_line(proof: dict[str, Any]) -> str:
    seats = proof.get("seats") or []
    bits = []
    for s in seats:
        bits.append(
            f"{s.get('seat_id')}={s.get('health')}"
            + (f"@{s.get('unit_pid')}" if s.get("unit_pid") else "")
        )
    return (
        f"## HOST location proof\n\n"
        f"`host={proof.get('host_id')} role={proof.get('host_role')} "
        f"seats={', '.join(bits) or 'none'} ts={proof.get('ts')}`\n\n"
        f"`seat-location.v0 · heartbeat`"
    )


def write_proof_file(proof: dict[str, Any]) -> Path:
    path = Path.home() / ".buzz-dev" / "hosts" / host_role() / "location-proof.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proof, indent=2) + "\n")
    return path


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--write", action="store_true", help="write location-proof.json")
    p.add_argument("--print-board", action="store_true", help="print phone-safe board markdown")
    args = p.parse_args()
    proof = build_location_proof()
    if args.write:
        path = write_proof_file(proof)
        print(f"wrote {path}")
    if args.print_board:
        print(phone_safe_board_line(proof))
    if not args.write and not args.print_board:
        print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
