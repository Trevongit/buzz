"""Wake log: a second delivery after a reply is a replay, and the file list stays out."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import wake_log

EID = "a" * 64
RID = "b" * 64
OTHER = "c" * 64


class WakeLogTests(unittest.TestCase):
    def test_reply_then_second_wake_is_a_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            first = wake_log.note_wake("buzz-control", EID, now=100, home=home)
            wake_log.note_reply("buzz-control", EID, RID, now=110, home=home)
            second = wake_log.note_wake("buzz-control", EID, now=200, home=home)
            raw = (home / "buzz-control" / "wake-log.json").read_text()
        self.assertEqual(first["kind"], "new")
        self.assertEqual(second["kind"], "replay")
        self.assertEqual(second["reply_id"], RID)
        self.assertNotIn("preview", raw)
        self.assertNotIn("secret-plan", raw)

    def test_open_wake_is_not_a_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wake_log.note_wake("buzz-control", EID, now=100, home=home)
            second = wake_log.note_wake("buzz-control", EID, now=200, home=home)
        self.assertEqual(second["kind"], "open")

    def test_unknown_handoff_is_no_ear_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            text = f"BUZZ_WAKE match id={OTHER} preview=secret-plan.txt"
            out = wake_log.annotate_prompt("buzz-control", text, now=300, home=home)
            raw = json.dumps(json.loads((home / "buzz-control" / "wake-log.json").read_text()))
        self.assertIn("NO EAR RECORD", out)
        self.assertNotIn("secret-plan", raw)
        self.assertNotIn(text, raw)

    def test_plain_paste_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            text = "Say what this repo is, then stop."
            self.assertEqual(wake_log.annotate_prompt("buzz-control", text, now=1, home=home), text)
            self.assertFalse((home / "buzz-control" / "wake-log.json").exists())

    def test_lamp_is_quiet_until_a_fresh_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wake_log.note_wake("buzz-control", EID, now=100, home=home)
            wake_log.note_reply("buzz-control", EID, RID, now=110, home=home)
            quiet = wake_log.lamp_view(home=home, now=120)
            wake_log.note_wake("buzz-control", EID, now=200, home=home)
            hot = wake_log.lamp_view(home=home, now=200)
            cold = wake_log.lamp_view(home=home, now=200 + wake_log.WINDOW_S + 5)
        self.assertEqual(quiet["why"], "quiet")
        self.assertTrue(hot["hot"])
        self.assertIn("buzz-control", hot["why"])
        self.assertNotIn(EID, hot["why"])
        self.assertFalse(cold["hot"])
