#!/usr/bin/env python3
"""Offline tests for the visitor gate. No relay. No secrets."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from gate import (  # noqa: E402
    admit_budget,
    parse_collab_envelope,
    render_envelope,
    should_escalate_to_prime,
    should_wake,
    addressed_to,
)


class MentionTests(unittest.TestCase):
    def test_unaddressed_hello_does_not_wake(self):
        wake, reason = should_wake(
            content="hello",
            from_pubkey="aa",
            self_pubkey="bb",
            is_dm=False,
            require_mention=True,
            names=["codex-buzz"],
            pubkeys=["bb"],
            seat_role="codex",
        )
        self.assertFalse(wake)
        self.assertEqual(reason, "unaddressed")

    def test_at_name_wakes(self):
        wake, reason = should_wake(
            content="@codex-buzz take the patch",
            from_pubkey="aa",
            self_pubkey="bb",
            is_dm=False,
            require_mention=True,
            names=["codex-buzz"],
            pubkeys=["bb"],
            seat_role="codex",
        )
        self.assertTrue(wake)
        self.assertEqual(reason, "mention")

    def test_self_echo_never_wakes(self):
        wake, reason = should_wake(
            content="@codex-buzz hi from me",
            from_pubkey="bb",
            self_pubkey="bb",
            is_dm=False,
            require_mention=True,
            names=["codex-buzz"],
            pubkeys=["bb"],
            seat_role="codex",
        )
        self.assertFalse(wake)
        self.assertEqual(reason, "self-echo")

    def test_dm_always_wakes(self):
        wake, reason = should_wake(
            content="yes",
            from_pubkey="aa",
            self_pubkey="bb",
            is_dm=True,
            require_mention=True,
            names=["codex-buzz"],
            pubkeys=["bb"],
            seat_role="codex",
        )
        self.assertTrue(wake)
        self.assertEqual(reason, "dm")

    def test_pubkey_prefix(self):
        self.assertTrue(
            addressed_to("see 01b23ef7d3c9 please", ["x"], ["01b23ef7d3c9dfbfbc874e7ed752f05033c74c5ba11444c1989527ed81c5c4af"])
        )


class EnvelopeTests(unittest.TestCase):
    def test_render_roundtrip(self):
        text = render_envelope(
            from_role="grok",
            to_role="codex",
            task="land visitor kit tests",
            status="OPEN",
        )
        env = parse_collab_envelope(text)
        self.assertIsNotNone(env)
        assert env is not None
        self.assertEqual(env["from"], "grok")
        self.assertEqual(env["to"], "codex")
        self.assertEqual(env["status"], "OPEN")
        self.assertEqual(env["need_prime"], "false")

    def test_blocked_without_flag_does_not_escalate(self):
        text = render_envelope(
            from_role="agy",
            to_role="grok",
            task="relay 401",
            status="BLOCKED",
            need_prime=False,
        )
        env = parse_collab_envelope(text)
        self.assertFalse(should_escalate_to_prime(env))

    def test_blocked_need_prime_escalates(self):
        text = render_envelope(
            from_role="codex",
            to_role="grok",
            task="need origin access",
            status="BLOCKED",
            need_prime=True,
        )
        env = parse_collab_envelope(text)
        self.assertTrue(should_escalate_to_prime(env))

    def test_collab_to_seat_wakes(self):
        text = render_envelope(from_role="grok", to_role="codex", task="review PR")
        wake, reason = should_wake(
            content=text,
            from_pubkey="aa",
            self_pubkey="bb",
            is_dm=False,
            require_mention=True,
            names=["codex-buzz"],
            pubkeys=["bb"],
            seat_role="codex",
        )
        self.assertTrue(wake)
        self.assertEqual(reason, "collab")

    def test_collab_to_other_role_silent(self):
        text = render_envelope(from_role="grok", to_role="agy", task="scout")
        wake, reason = should_wake(
            content=text,
            from_pubkey="aa",
            self_pubkey="bb",
            is_dm=False,
            require_mention=True,
            names=["codex-buzz"],
            pubkeys=["bb"],
            seat_role="codex",
        )
        self.assertFalse(wake)
        self.assertEqual(reason, "unaddressed")

    def test_hello_is_not_envelope(self):
        self.assertIsNone(parse_collab_envelope("hello"))

    def test_render_rejects_bad_role(self):
        with self.assertRaises(ValueError):
            render_envelope(from_role="helix", to_role="codex", task="no")


class BudgetTests(unittest.TestCase):
    def test_overflow_caps_three(self):
        events = [{"preview": "a" * 10} for _ in range(8)]
        kept, overflow = admit_budget(events, max_events=3, max_bytes=2048)
        self.assertEqual(len(kept), 3)
        self.assertTrue(overflow)


class HermesExampleTests(unittest.TestCase):
    def test_example_is_mention_only_and_secret_free(self):
        text = (ROOT / "hermes-gateway.example.yaml").read_text()
        self.assertIn("require_mention: true", text)
        self.assertIn("allow_all_users: false", text)
        self.assertIn("interim_assistant_messages: false", text)
        self.assertNotIn("nsec1", text)
        self.assertNotIn("BUZZ_PRIVATE_KEY=", text)


class SetupScriptTests(unittest.TestCase):
    def test_check_exits_2_without_hermes(self):
        proc = subprocess.run(
            ["bash", str(ROOT / "hermes-setup.sh"), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        # Missing hermes → 2; present → 0. Never 1 from this path.
        self.assertIn(proc.returncode, (0, 2), proc.stdout + proc.stderr)
        self.assertNotIn("nsec", proc.stdout.lower())

    def test_write_dir_copies_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                ["bash", str(ROOT / "hermes-setup.sh"), "--write-dir", tmp],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertIn(proc.returncode, (0, 2), proc.stdout + proc.stderr)
            written = Path(tmp) / "config.buzz.yaml"
            self.assertTrue(written.is_file())
            self.assertIn("require_mention: true", written.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
