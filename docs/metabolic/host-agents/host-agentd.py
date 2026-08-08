#!/usr/bin/env python3
"""host-agentd — thin HTTP control plane for headless host agents.

Wraps `buzz-host-agents` for the traveling laptop Remote Agents UI.
Bind to Tailscale IP or 127.0.0.1; never expose to the public internet.

Env:
  HOST_AGENTD_TOKEN     required shared secret (Authorization: Bearer …)
  HOST_AGENTD_HOST      default 127.0.0.1 (use Tailscale IP on home)
  HOST_AGENTD_PORT      default 8787
  BUZZ_HOST_AGENTS      path to buzz-host-agents script
  BUZZ_HOST_ROLE        home|laptop
  BUZZ_HOST_ID          hostname

Endpoints:
  GET  /v1/health
  GET  /v1/status
  GET  /v1/agents
  POST /v1/agents/{seat}/arm     JSON { "preset", "room"? }
  POST /v1/agents/{seat}/disarm  JSON { "preset"? }
  GET  /v1/agents/{seat}/logs?tail=80
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


TOKEN = env("HOST_AGENTD_TOKEN")
BIND_HOST = env("HOST_AGENTD_HOST", "127.0.0.1")
BIND_PORT = int(env("HOST_AGENTD_PORT", "8787") or "8787")
CLI = env("BUZZ_HOST_AGENTS") or str(
    Path(__file__).resolve().with_name("buzz-host-agents")
)


def run_cli(args: list[str], timeout: float = 120.0) -> tuple[int, str, str]:
    cli_path = Path(CLI)
    if not cli_path.is_file():
        return 127, "", f"buzz-host-agents not found: {CLI}"
    # Always invoke via bash so non-executable installs still work
    cmd = ["bash", str(cli_path), *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ},
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError:
        return 127, "", "bash not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def status_json() -> dict[str, Any]:
    code, out, err = run_cli(["status", "--json"])
    if code != 0:
        return {
            "ok": False,
            "error": err.strip() or out.strip() or f"exit {code}",
            "raw": out,
        }
    try:
        data = json.loads(out)
        data["ok"] = True
        return data
    except json.JSONDecodeError:
        # Older CLI may not support --json; parse human status lightly
        return {
            "ok": True,
            "schema": "host-agent.status.v0",
            "raw": out,
            "stderr": err,
            "host_id": env("BUZZ_HOST_ID") or None,
            "host_role": env("BUZZ_HOST_ROLE") or None,
        }


class Handler(BaseHTTPRequestHandler):
    server_version = "host-agentd/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("host-agentd: " + (fmt % args) + "\n")

    def _unauthorized(self) -> None:
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error":"unauthorized"}')

    def _json(self, code: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _check_auth(self) -> bool:
        if not TOKEN:
            self._json(500, {"error": "HOST_AGENTD_TOKEN not configured"})
            return False
        auth = self.headers.get("Authorization") or ""
        if auth == f"Bearer {TOKEN}" or auth == TOKEN:
            return True
        # also allow X-Host-Agent-Token
        if (self.headers.get("X-Host-Agent-Token") or "") == TOKEN:
            return True
        self._unauthorized()
        return False

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        if not self._check_auth():
            return
        path = urlparse(self.path).path
        qs = parse_qs(urlparse(self.path).query)

        if path in ("/v1/health", "/health"):
            self._json(200, {"ok": True, "service": "host-agentd"})
            return

        if path in ("/v1/status", "/status"):
            self._json(200, status_json())
            return

        if path in ("/v1/location-proof", "/location-proof"):
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                from location_proof import build_location_proof, write_proof_file

                st = status_json()
                proof = build_location_proof(st if st.get("ok") else None)
                write_proof_file(proof)
                self._json(200, {"ok": True, **proof})
            except Exception as exc:  # keep controller alive
                self._json(500, {"ok": False, "error": str(exc)[:200]})
            return

        if path in ("/v1/agents", "/agents"):
            st = status_json()
            agents = st.get("seats") if isinstance(st, dict) else []
            self._json(
                200,
                {
                    "ok": st.get("ok", False) if isinstance(st, dict) else False,
                    "host_id": st.get("host_id") if isinstance(st, dict) else None,
                    "host_role": st.get("host_role") if isinstance(st, dict) else None,
                    "agents": agents or [],
                    "status": st,
                },
            )
            return

        if path.startswith("/v1/agents/") and path.endswith("/logs"):
            # /v1/agents/{seat}/logs
            parts = path.strip("/").split("/")
            # v1 agents seat logs
            seat = parts[2] if len(parts) >= 4 else ""
            tail = int((qs.get("tail") or ["80"])[0])
            role = env("BUZZ_HOST_ROLE") or "home"
            unit_root = Path.home() / ".buzz-dev" / "hosts" / role / "units"
            logs: list[str] = []
            if unit_root.is_dir() and seat:
                for log in sorted(unit_root.glob(f"{seat}-*/watch.log")):
                    try:
                        lines = log.read_text(errors="replace").splitlines()
                        logs.append(f"--- {log.name} ---")
                        logs.extend(lines[-tail:])
                    except OSError as exc:
                        logs.append(f"error reading {log}: {exc}")
            self._json(200, {"ok": True, "seat": seat, "lines": logs})
            return

        self._json(404, {"error": "not_found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        if not self._check_auth():
            return
        path = urlparse(self.path).path
        body = self._read_json()

        # /v1/agents/{seat}/arm|disarm
        parts = [p for p in path.strip("/").split("/") if p]
        # ["v1","agents",seat,"arm"]
        if len(parts) == 4 and parts[0] == "v1" and parts[1] == "agents":
            seat = parts[2]
            action = parts[3]
            preset = str(body.get("preset") or "co-lab-gemma")
            room = str(body.get("room") or "")

            allowed = {
                "co-lab-gemma",
                "co-lab-watch",
                "push-nerve",
                "codex-home",
                "codex@home",
                "status-only",
            }
            if preset not in allowed:
                self._json(
                    400,
                    {
                        "ok": False,
                        "error": f"unknown preset {preset}",
                        "allowed": sorted(allowed),
                    },
                )
                return

            if action == "arm":
                args = ["arm", "--preset", preset, "--seat", seat]
                if room:
                    args.extend(["--room", room])
                code, out, err = run_cli(args, timeout=180.0)
                # Never echo secrets if env leaked into stderr
                redacted_err = "\n".join(
                    ln
                    for ln in (err or "").splitlines()
                    if "TOKEN" not in ln.upper() and "PRIVATE" not in ln.upper()
                )
                self._json(
                    200 if code == 0 else 500,
                    {
                        "ok": code == 0,
                        "action": "arm",
                        "seat": seat,
                        "preset": preset,
                        "exit": code,
                        "stdout": out[-4000:],
                        "stderr": redacted_err[-2000:],
                    },
                )
                return

            if action == "disarm":
                args = ["disarm", "--preset", preset, "--seat", seat]
                code, out, err = run_cli(args, timeout=60.0)
                redacted_err = "\n".join(
                    ln
                    for ln in (err or "").splitlines()
                    if "TOKEN" not in ln.upper() and "PRIVATE" not in ln.upper()
                )
                self._json(
                    200 if code == 0 else 500,
                    {
                        "ok": code == 0,
                        "action": "disarm",
                        "seat": seat,
                        "preset": preset,
                        "exit": code,
                        "stdout": out[-4000:],
                        "stderr": redacted_err[-2000:],
                    },
                )
                return

        self._json(404, {"error": "not_found", "path": path})


def main() -> int:
    if not TOKEN:
        print("error: set HOST_AGENTD_TOKEN", file=sys.stderr)
        return 2
    if not Path(CLI).exists():
        print(f"error: CLI missing: {CLI}", file=sys.stderr)
        return 2
    # ensure executable path works via bash
    os.environ.setdefault("BUZZ_HOST_ROLE", env("BUZZ_HOST_ROLE") or "home")
    httpd = ThreadingHTTPServer((BIND_HOST, BIND_PORT), Handler)
    print(
        f"host-agentd listen http://{BIND_HOST}:{BIND_PORT} cli={CLI}",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("host-agentd stop", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
