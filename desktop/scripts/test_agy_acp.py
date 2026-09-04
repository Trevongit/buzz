#!/usr/bin/env python3
"""Offline ACP handshake tests for desktop/scripts/agy-acp."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / "agy-acp"


class FakeAgy:
    """Minimal agy --print stand-in."""

    def __init__(self, path: Path) -> None:
        path.write_text(
            "#!/bin/sh\n"
            "echo fake-agy\n"
            "echo args:\"$@\"\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        self.path = path


def rpc(proc: subprocess.Popen, msg: dict) -> list[dict]:
    raw = json.dumps(msg) + "\n"
    assert proc.stdin is not None
    proc.stdin.write(raw.encode("utf-8"))
    proc.stdin.flush()
    assert proc.stdout is not None
    lines = []
    # Read until a response with matching id (notifications may precede it).
    req_id = msg.get("id")
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        parsed = json.loads(line.decode("utf-8"))
        lines.append(parsed)
        if req_id is not None and parsed.get("id") == req_id:
            break
    return lines


class TestAgyAcp(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        fake = Path(self.tmpdir.name) / "agy"
        FakeAgy(fake)
        env = os.environ.copy()
        env["AGY_ACP_BIN"] = str(fake)
        env["AGY_ACP_TIMEOUT"] = "5"
        self.proc = subprocess.Popen(
            [sys.executable, str(ADAPTER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def tearDown(self) -> None:
        self.proc.kill()
        self.proc.wait(timeout=2)
        self.tmpdir.cleanup()

    def test_initialize_session_prompt(self) -> None:
        init = rpc(
            self.proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": 1},
            },
        )
        self.assertEqual(init[-1]["result"]["agentInfo"]["name"], "agy-acp")
        cwd = self.tmpdir.name
        created = rpc(
            self.proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "session/new",
                "params": {"cwd": cwd, "mcpServers": []},
            },
        )
        sid = created[-1]["result"]["sessionId"]
        self.assertTrue(sid.startswith("ses_"))
        replies = rpc(
            self.proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "session/prompt",
                "params": {
                    "sessionId": sid,
                    "prompt": [{"type": "text", "text": "hello from buzz"}],
                },
            },
        )
        updates = [r for r in replies if r.get("method") == "session/update"]
        self.assertTrue(updates)
        chunk = updates[0]["params"]["update"]
        self.assertEqual(chunk["sessionUpdate"], "agent_message_chunk")
        self.assertIn("fake-agy", chunk["content"]["text"])
        done = [r for r in replies if r.get("id") == 3][-1]
        self.assertEqual(done["result"]["stopReason"], "end_turn")

    def test_rejects_relative_cwd(self) -> None:
        rpc(
            self.proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": 1},
            },
        )
        bad = rpc(
            self.proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "session/new",
                "params": {"cwd": "relative", "mcpServers": []},
            },
        )
        self.assertIn("error", bad[-1])


if __name__ == "__main__":
    unittest.main()
