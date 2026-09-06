#!/usr/bin/env python3
"""Offline tests for the visitor gate. No relay. No secrets."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from gate import (  # noqa: E402
    admit_budget,
    addressed_to,
    align_relays,
    cooldown_blocks,
    filter_wakes,
    mention_names_from_card,
    normalize_relay,
    parse_collab_envelope,
    parse_public_txt,
    record_prime_escalation,
    relay_from_seat_dir,
    render_envelope,
    roster_report,
    should_escalate_to_prime,
    should_post_prime_escalation,
    should_wake,
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

    def test_agy_not_substring_of_strategy(self):
        self.assertFalse(addressed_to("strategy review", ["agy"], []))
        wake, reason = should_wake(
            content="strategy review",
            from_pubkey="aa",
            self_pubkey="bb",
            is_dm=False,
            require_mention=True,
            names=["agy"],
            pubkeys=["bb"],
            seat_role="agy",
        )
        self.assertFalse(wake)
        self.assertEqual(reason, "unaddressed")

    def test_at_agy_wakes(self):
        self.assertTrue(addressed_to("hey @agy scout the tree", ["agy"], []))

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
            addressed_to(
                "see 01b23ef7d3c9 please",
                ["x"],
                ["01b23ef7d3c9dfbfbc874e7ed752f05033c74c5ba11444c1989527ed81c5c4af"],
            )
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

    def test_hermes_role_ok(self):
        text = render_envelope(from_role="hermes", to_role="all", task="mention-only")
        env = parse_collab_envelope(text)
        assert env is not None
        self.assertEqual(env["from"], "hermes")

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

    def test_byte_cap_is_not_multiplied(self):
        events = [{"preview": "x" * 1000} for _ in range(4)]
        kept, overflow = admit_budget(events, max_events=3, max_bytes=2048)
        self.assertEqual(len(kept), 2)
        self.assertTrue(overflow)


class CooldownAndFilterTests(unittest.TestCase):
    def _msg(self, mid: str, content: str, pk: str = "aa") -> dict:
        return {"id": mid, "content": content, "pubkey": pk, "created_at": 100}

    def test_cooldown_blocks(self):
        self.assertTrue(cooldown_blocks(100, 120, 30))
        self.assertFalse(cooldown_blocks(100, 131, 30))
        self.assertFalse(cooldown_blocks(0, 50, 30))

    def test_filter_unaddressed_consumed_mention_emitted(self):
        msgs = [
            self._msg("1", "hello"),
            self._msg("2", "@codex-buzz go"),
        ]
        out = filter_wakes(
            msgs,
            state={"seen_ids": [], "since": 0, "last_wake": 0},
            self_pk="bb",
            names=["codex-buzz"],
            pubkeys=["bb"],
            seat_role="codex",
            require_mention=True,
            is_dm=False,
            now_unix=1000,
            cooldown_secs=30,
        )
        self.assertEqual(len(out["wakes"]), 1)
        self.assertEqual(out["wakes"][0]["id"], "2")
        self.assertIn("1", out["state"]["seen_ids"])
        self.assertIn("2", out["state"]["seen_ids"])

    def test_filter_cooldown_does_not_consume_mention(self):
        msgs = [self._msg("2", "@codex-buzz go")]
        out = filter_wakes(
            msgs,
            state={"seen_ids": [], "since": 0, "last_wake": 990},
            self_pk="bb",
            names=["codex-buzz"],
            pubkeys=["bb"],
            seat_role="codex",
            require_mention=True,
            is_dm=False,
            now_unix=1000,
            cooldown_secs=30,
        )
        self.assertTrue(out["cooldown"])
        self.assertEqual(out["wakes"], [])
        self.assertNotIn("2", out["state"]["seen_ids"])

    def test_overflow_does_not_consume_remainder(self):
        msgs = [self._msg(str(i), f"@codex-buzz n{i}") for i in range(5)]
        out = filter_wakes(
            msgs,
            state={"seen_ids": [], "since": 0, "last_wake": 0},
            self_pk="bb",
            names=["codex-buzz"],
            pubkeys=["bb"],
            seat_role="codex",
            require_mention=True,
            is_dm=False,
            now_unix=2000,
            cooldown_secs=0,
            max_events=3,
            max_bytes=2048,
        )
        self.assertTrue(out["overflow"])
        self.assertEqual(len(out["wakes"]), 3)
        seen = set(out["state"]["seen_ids"])
        self.assertEqual(len(seen), 3)
        leftover = [m["id"] for m in msgs if m["id"] not in seen]
        self.assertEqual(leftover, ["3", "4"])


class EscalationJournalTests(unittest.TestCase):
    def test_once_then_stop(self):
        allow, reason = should_post_prime_escalation({}, "need origin access")
        self.assertTrue(allow)
        self.assertEqual(reason, "ok")
        journal = record_prime_escalation({}, "need origin access", 9)
        allow2, reason2 = should_post_prime_escalation(journal, "Need Origin Access")
        self.assertFalse(allow2)
        self.assertEqual(reason2, "already-escalated")

    def test_cli_record_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prime-escalation.json"
            first = subprocess.run(
                ["python3", str(ROOT / "gate.py"), "escalate-record", "--journal", str(path), "--task", "stuck", "--now", "1"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            second = subprocess.run(
                ["python3", str(ROOT / "gate.py"), "escalate-check", "--journal", str(path), "--task", "stuck"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(second.returncode, 3)
            self.assertEqual(json.loads(second.stdout)["reason"], "already-escalated")


class RelayAlignTests(unittest.TestCase):
    def test_wss_and_https_same_host(self):
        self.assertEqual(
            normalize_relay("wss://groundfeed.communities.buzz.xyz"),
            normalize_relay("https://groundfeed.communities.buzz.xyz/"),
        )

    def test_mixed_hosts_not_aligned(self):
        report = align_relays(
            {
                "buzz": "https://groundfeed.communities.buzz.xyz",
                "codex-buzz": "wss://asus-g501vw.tailb74de6.ts.net",
            }
        )
        self.assertFalse(report["aligned"])
        self.assertEqual(len(report["unique"]), 2)

    def test_reads_public_txt_not_nsec(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "PUBLIC.txt").write_text(
                "seat: x\nrelay: wss://example.relay\n", encoding="utf-8"
            )
            Path(tmp, "agent.env").write_text(
                "BUZZ_PRIVATE_KEY=deadbeefdeadbeef\nBUZZ_RELAY_URL=https://ignored.example\n",
                encoding="utf-8",
            )
            url = relay_from_seat_dir(tmp)
            self.assertEqual(url, "wss://example.relay")
            self.assertNotIn("nsec", url)

    def test_never_opens_agent_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "agent.env").write_text(
                "BUZZ_PRIVATE_KEY=deadbeefdeadbeef\nBUZZ_RELAY_URL=https://secret.example\n",
                encoding="utf-8",
            )
            self.assertEqual(relay_from_seat_dir(tmp), "")


class RosterTests(unittest.TestCase):
    def test_drops_private_key_lines(self):
        card = parse_public_txt(
            "seat: agy-buzz\ndisplay_name: agy-buzz\n"
            "buzz_private_key=deadbeef\nrelay: wss://example.relay\n"
        )
        self.assertEqual(card["seat"], "agy-buzz")
        self.assertEqual(card["relay"], "wss://example.relay")
        self.assertNotIn("buzz_private_key", card)

    def test_same_bus_ready_mixed_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a"
            b = Path(tmp) / "b"
            c = Path(tmp) / "c"
            a.mkdir()
            b.mkdir()
            c.mkdir()
            a.joinpath("PUBLIC.txt").write_text(
                "seat: a\ndisplay_name: Buzz-codex\nrelay: wss://tail.example\n",
                encoding="utf-8",
            )
            b.joinpath("PUBLIC.txt").write_text(
                "seat: b\ndisplay_name: agy-buzz\nrelay: https://tail.example\n",
                encoding="utf-8",
            )
            c.joinpath("PUBLIC.txt").write_text(
                "seat: c\ndisplay_name: grok-build\nrelay: https://ground.example\n",
                encoding="utf-8",
            )
            ready = roster_report({"a": str(a), "b": str(b)})
            self.assertTrue(ready["ready"])
            self.assertEqual(ready["unique"], ["tail.example"])
            mixed = roster_report({"a": str(a), "c": str(c)})
            self.assertFalse(mixed["ready"])
            self.assertEqual(len(mixed["buses"]), 2)

    def test_mention_names_include_display(self):
        names = mention_names_from_card(
            {"seat": "codex-buzz", "display_name": "Buzz-codex"}, "codex-buzz"
        )
        self.assertIn("codex-buzz", names)
        self.assertIn("Buzz-codex", names)

    def test_start_collab_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a"
            b = Path(tmp) / "b"
            a.mkdir()
            b.mkdir()
            a.joinpath("PUBLIC.txt").write_text(
                "seat: a\nrelay: wss://one.example\n", encoding="utf-8"
            )
            b.joinpath("PUBLIC.txt").write_text(
                "seat: b\nrelay: wss://two.example\n", encoding="utf-8"
            )
            proc = subprocess.run(
                ["bash", str(ROOT / "start-collab.sh"), "--seats", "a,b", "--home", tmp],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
            self.assertNotIn("deadbeef", proc.stdout)
            a.joinpath("PUBLIC.txt").write_text(
                "seat: a\ndisplay_name: Alpha\nrelay: wss://one.example\n", encoding="utf-8"
            )
            b.joinpath("PUBLIC.txt").write_text(
                "seat: b\ndisplay_name: Beta\nrelay: https://one.example\n", encoding="utf-8"
            )
            ok = subprocess.run(
                ["bash", str(ROOT / "start-collab.sh"), "--seats", "a,b", "--home", tmp],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            self.assertIn("collab-ready", ok.stdout)
            self.assertIn("@Alpha", ok.stdout)


class HermesExampleTests(unittest.TestCase):
    def test_example_is_mention_only_and_secret_free(self):
        text = (ROOT / "hermes-gateway.example.yaml").read_text()
        self.assertIn("require_mention: true", text)
        self.assertIn("allow_all_users: false", text)
        self.assertIn("interim_assistant_messages: false", text)
        self.assertNotIn("nsec1", text)
        self.assertNotIn("BUZZ_PRIVATE_KEY=", text)
        self.assertIn("Do not add it to managed-agents.json", text)


class SetupScriptTests(unittest.TestCase):
    def test_check_exits_2_without_hermes(self):
        proc = subprocess.run(
            ["bash", str(ROOT / "hermes-setup.sh"), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn(proc.returncode, (0, 2), proc.stdout + proc.stderr)
        self.assertNotIn("nsec", proc.stdout.lower())
        if proc.returncode == 2:
            self.assertIn("offline", proc.stdout)

    def test_write_dir_is_complete_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                ["bash", str(ROOT / "hermes-setup.sh"), "--write-dir", tmp],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertRegex(proc.stdout, r"status=(offline|config-written)")
            written = Path(tmp) / "config.buzz.yaml"
            self.assertTrue(written.is_file())
            self.assertIn("require_mention: true", written.read_text())
            runner = Path(tmp) / "offline-gateway.sh"
            self.assertTrue(runner.is_file())
            body = runner.read_text()
            self.assertIn("wake.sh", body)
            self.assertNotIn("managed-agents", body)
            self.assertTrue((Path(tmp) / "NOT-DESKTOP-ACP.txt").is_file())

    def test_refuse_desktop_acp_path(self):
        proc = subprocess.run(
            ["bash", str(ROOT / "hermes-setup.sh"), "--write-dir", "/tmp/managed-agents-nope"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("refuse Desktop ACP", proc.stderr)


class InstallProfileTests(unittest.TestCase):
    def test_dry_run(self):
        proc = subprocess.run(
            ["bash", str(ROOT / "install-profile.sh"), "--brain", "codex", "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("status=dry-run", proc.stdout)

    def test_writes_skill_without_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "buzz-visitor"
            proc = subprocess.run(
                ["bash", str(ROOT / "install-profile.sh"), "--brain", "agy", "--dest", str(dest)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            skill = (dest / "SKILL.md").read_text()
            self.assertIn("COLLAB v0", skill)
            self.assertNotIn("nsec1", skill)
            self.assertIn("do not mint", proc.stdout.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
