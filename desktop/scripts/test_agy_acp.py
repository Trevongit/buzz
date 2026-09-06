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
    """Minimal agy --print stand-in.

    Mirrors current agy: a bare `--print` consumes the next argv as the prompt.
    `--print --output-format` is the production failure (exit 2).
    """

    def __init__(self, path: Path) -> None:
        path.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "--print" ] || [ "$2" = "--print" ]; then\n'
            '  echo "Error: --print took the next token as its prompt" >&2\n'
            "  exit 2\n"
            "fi\n"
            "echo fake-agy\n"
            'echo args:"$@"\n',
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

    def test_print_flag_attaches_prompt(self) -> None:
        from importlib.machinery import SourceFileLoader

        mod = SourceFileLoader("agy_acp_mod", str(ADAPTER)).load_module()
        cmd = mod.agy_argv("who are you and which model?")
        self.assertNotIn(
            "--print",
            cmd,
            "bare --print consumes the next argv (was --output-format, exit 2)",
        )
        self.assertIn("--print=who are you and which model?", cmd)
        fmt_at = cmd.index("--output-format")
        self.assertEqual(cmd[fmt_at + 1], "text")

    def test_empty_stdout_surfaces_headless_permission_stderr(self) -> None:
        from importlib.machinery import SourceFileLoader

        mod = SourceFileLoader("agy_acp_mod2", str(ADAPTER)).load_module()
        msg = mod.format_agy_result(
            0,
            "",
            'jetski: no output produced — a tool required the "command" permission',
        )
        self.assertIn("command", msg)
        self.assertNotEqual(msg, "(agy produced no text)")
        skip = mod.agy_argv("hi")
        os.environ["AGY_ACP_SKIP_PERMISSIONS"] = "1"
        try:
            armed = mod.agy_argv("hi")
        finally:
            os.environ.pop("AGY_ACP_SKIP_PERMISSIONS", None)
        self.assertNotIn("--dangerously-skip-permissions", skip)
        self.assertIn("--dangerously-skip-permissions", armed)

    def test_compose_print_prompt_truncates_fat_system(self) -> None:
        from importlib.machinery import SourceFileLoader

        mod = SourceFileLoader("agy_acp_mod3", str(ADAPTER)).load_module()
        fat = "BASE " * 400
        out = mod.compose_print_prompt(fat, "hello")
        self.assertIn("hello", out)
        self.assertIn("[system truncated for --print]", out)
        self.assertLess(len(out), len(fat) + 80)
        short = mod.compose_print_prompt("You are Prism.", "hello")
        self.assertEqual(short, "You are Prism.\n\nhello")


if __name__ == "__main__":
    unittest.main()
