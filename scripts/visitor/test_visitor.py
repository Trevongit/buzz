#!/usr/bin/env python3
"""Offline tests for the visitor gate. No relay. No secrets."""

from __future__ import annotations

import json
import os
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
    collab_send_gate,
    cooldown_blocks,
    filter_wakes,
    last_room_bus_ok,
    mention_names_from_card,
    normalize_relay,
    parse_collab_envelope,
    parse_public_txt,
    public_env_relay_ok,
    record_prime_escalation,
    relay_from_seat_dir,
    render_envelope,
    role_from_seat,
    roster_report,
    same_bus_for_roles,
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

    def test_send_gate_classifies_content(self):
        open_text = render_envelope(from_role="codex", to_role="agy", task="scout")
        blocked = render_envelope(
            from_role="codex",
            to_role="grok",
            task="need origin access",
            status="BLOCKED",
            need_prime=True,
        )
        self.assertFalse(collab_send_gate("hello")["envelope"])
        self.assertFalse(collab_send_gate(open_text)["escalate"])
        self.assertTrue(collab_send_gate(blocked)["escalate"])
        self.assertEqual(collab_send_gate(blocked)["from"], "codex")
        proc = subprocess.run(
            ["python3", str(ROOT / "gate.py"), "send-gate"],
            input=blocked,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["escalate"])

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

    def test_missing_or_empty_not_aligned(self):
        self.assertFalse(align_relays({})["aligned"])
        missing = align_relays({"a": "wss://one.example", "b": ""})
        self.assertFalse(missing["aligned"])
        self.assertEqual(missing["missing"], ["b"])
        same = align_relays(
            {"a": "wss://one.example", "b": "https://one.example/"}
        )
        self.assertTrue(same["aligned"])
        self.assertEqual(same["unique"], ["one.example"])

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

    def test_public_env_relay_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "PUBLIC.txt").write_text(
                "seat: x\nrelay: wss://tail.example\n", encoding="utf-8"
            )
            Path(tmp, "agent.env").write_text(
                "BUZZ_PRIVATE_KEY=deadbeefdeadbeef\nBUZZ_RELAY_URL=https://ground.example\n",
                encoding="utf-8",
            )
            bad = public_env_relay_ok(tmp, "https://ground.example")
            self.assertFalse(bad["ok"])
            self.assertEqual(bad["reason"], "public-env-mismatch")
            self.assertEqual(bad["public_host"], "tail.example")
            self.assertEqual(bad["env_host"], "ground.example")
            ok = public_env_relay_ok(tmp, "https://tail.example/")
            self.assertTrue(ok["ok"])
            missing = public_env_relay_ok(tmp + "-nope", "https://tail.example")
            self.assertFalse(missing["ok"])
            self.assertEqual(missing["reason"], "public-relay-missing")
            proc = subprocess.run(
                [
                    "python3",
                    str(ROOT / "gate.py"),
                    "public-env",
                    "--dir",
                    tmp,
                    "--relay",
                    "https://ground.example",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
            self.assertNotIn("deadbeef", proc.stdout)
            Path(tmp, "x").mkdir()
            Path(tmp, "x", "PUBLIC.txt").write_text(
                "seat: x\nrelay: wss://tail.example\n", encoding="utf-8"
            )
            Path(tmp, "x", "agent.env").write_text(
                "BUZZ_PRIVATE_KEY=deadbeefdeadbeef\n", encoding="utf-8"
            )
            bash = subprocess.run(
                [
                    "bash",
                    "-c",
                    'source "$1"; export VISITOR_AGENTS_HOME="$2"; '
                    "BUZZ_RELAY_URL=https://ground.example visitor_assert_public_relay x",
                    "_",
                    str(ROOT / "lib.sh"),
                    tmp,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bash.returncode, 3, bash.stdout + bash.stderr)
            self.assertIn("public-env-mismatch", bash.stderr)
            self.assertNotIn("deadbeef", bash.stdout + bash.stderr)
            good = subprocess.run(
                [
                    "bash",
                    "-c",
                    'source "$1"; export VISITOR_AGENTS_HOME="$2"; '
                    "BUZZ_RELAY_URL=https://tail.example visitor_assert_public_relay x",
                    "_",
                    str(ROOT / "lib.sh"),
                    tmp,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)


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
            self.assertFalse(roster_report({})["aligned"])
            self.assertFalse(roster_report({"z": str(tmp + "/nope")})["aligned"])

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
            align_ok = subprocess.run(
                [
                    "bash",
                    str(ROOT / "relay-align.sh"),
                    "--seats",
                    "a,b",
                    "--home",
                    tmp,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(align_ok.returncode, 0, align_ok.stdout + align_ok.stderr)
            align_miss = subprocess.run(
                [
                    "bash",
                    str(ROOT / "relay-align.sh"),
                    "--seats",
                    "a,missing-seat",
                    "--home",
                    tmp,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(align_miss.returncode, 3, align_miss.stdout + align_miss.stderr)
            self.assertIn("missing-seat", align_miss.stdout)
            dry = subprocess.run(
                [
                    "bash",
                    str(ROOT / "start-collab.sh"),
                    "--seats",
                    "a,b",
                    "--home",
                    tmp,
                    "--dry-run",
                    "--from",
                    "codex",
                    "--to",
                    "agy",
                    "--task",
                    "land visitor dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
            self.assertIn("COLLAB v0", dry.stdout)
            self.assertIn("DRY-RUN", dry.stdout)
            self.assertIn("need_prime: false", dry.stdout)
            self.assertNotIn("deadbeef", dry.stdout)


class RoleFromSeatTests(unittest.TestCase):
    def test_known_seats(self):
        self.assertEqual(role_from_seat("codex-buzz"), "codex")
        self.assertEqual(role_from_seat("agy-buzz"), "agy")
        self.assertEqual(role_from_seat("buzz"), "grok")
        self.assertEqual(role_from_seat("hermes-buzz"), "hermes")

    def test_unknown_is_not_grok(self):
        self.assertEqual(role_from_seat("buzz-origin-plus"), "")
        proc = subprocess.run(
            ["python3", str(ROOT / "gate.py"), "role-from-seat", "--seat", "codex-buzz"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "codex")

    def test_collab_envelope_wakes_mapped_role(self):
        text = render_envelope(from_role="agy", to_role="codex", task="take the patch")
        out = filter_wakes(
            [{"id": "e1", "content": text, "pubkey": "aa", "created_at": 1}],
            state={"seen_ids": [], "since": 0, "last_wake": 0},
            self_pk="bb",
            names=["codex-buzz", "Buzz-codex"],
            pubkeys=["bb"],
            seat_role=role_from_seat("codex-buzz"),
            require_mention=True,
            is_dm=False,
            now_unix=50,
            cooldown_secs=0,
        )
        self.assertEqual(len(out["wakes"]), 1)
        self.assertEqual(out["wakes"][0]["reason"], "collab")
        grok = filter_wakes(
            [{"id": "e1", "content": text, "pubkey": "aa", "created_at": 1}],
            state={"seen_ids": [], "since": 0, "last_wake": 0},
            self_pk="cc",
            names=["grok-build"],
            pubkeys=["cc"],
            seat_role=role_from_seat("buzz"),
            require_mention=True,
            is_dm=False,
            now_unix=50,
            cooldown_secs=0,
        )
        self.assertEqual(grok["wakes"], [])


class SameBusSendTests(unittest.TestCase):
    def _two_seats(self, tmp: str, same: bool) -> None:
        a = Path(tmp) / "codex-buzz"
        b = Path(tmp) / "agy-buzz"
        a.mkdir(exist_ok=True)
        b.mkdir(exist_ok=True)
        a.joinpath("PUBLIC.txt").write_text(
            "seat: codex-buzz\ndisplay_name: Buzz-codex\nrelay: wss://tail.example\n",
            encoding="utf-8",
        )
        relay = "https://tail.example" if same else "https://ground.example"
        b.joinpath("PUBLIC.txt").write_text(
            f"seat: agy-buzz\ndisplay_name: agy-buzz\nrelay: {relay}\n",
            encoding="utf-8",
        )

    def test_same_bus_ok_mixed_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._two_seats(tmp, True)
            ok = same_bus_for_roles(
                from_role="codex", to_role="agy", agents_home=tmp
            )
            self.assertTrue(ok["ok"])
            all_present = same_bus_for_roles(
                from_role="codex", to_role="all", agents_home=tmp
            )
            self.assertTrue(all_present["ok"], all_present)
            self._two_seats(tmp, False)
            bad = same_bus_for_roles(
                from_role="codex", to_role="agy", agents_home=tmp
            )
            self.assertFalse(bad["ok"])
            all_bus = same_bus_for_roles(
                from_role="codex", to_role="all", agents_home=tmp
            )
            self.assertFalse(all_bus["ok"])

    def test_to_all_fails_when_present_seats_span_buses(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._two_seats(tmp, True)
            grok = Path(tmp) / "buzz"
            grok.mkdir()
            grok.joinpath("PUBLIC.txt").write_text(
                "seat: buzz\nrelay: https://ground.example\n",
                encoding="utf-8",
            )
            all_bus = same_bus_for_roles(
                from_role="codex", to_role="all", agents_home=tmp
            )
            self.assertFalse(all_bus["ok"])
            self.assertEqual(all_bus["reason"], "to-all-not-ready")

    def test_collab_dry_run_never_loads_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._two_seats(tmp, True)
            proc = subprocess.run(
                [
                    "bash",
                    str(ROOT / "collab.sh"),
                    "open",
                    "--from",
                    "codex",
                    "--to",
                    "agy",
                    "--task",
                    "scout the tree",
                    "--home",
                    tmp,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("COLLAB v0", proc.stdout)
            self.assertIn("DRY-RUN not posted", proc.stdout)
            self.assertNotIn("error: no identity", proc.stderr)

    def test_collab_dry_run_mixed_exits_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._two_seats(tmp, False)
            proc = subprocess.run(
                [
                    "bash",
                    str(ROOT / "collab.sh"),
                    "open",
                    "--from",
                    "codex",
                    "--to",
                    "agy",
                    "--task",
                    "cross bus",
                    "--home",
                    tmp,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
            self.assertIn("VISITOR_COLLAB skip reason=", proc.stderr)
            self.assertIn("DRY-RUN not posted", proc.stdout)
            self.assertNotIn("error: no identity", proc.stderr)

    def test_post_blocked_need_prime_uses_escalate_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._two_seats(tmp, True)
            grok = Path(tmp) / "buzz"
            grok.mkdir(exist_ok=True)
            grok.joinpath("PUBLIC.txt").write_text(
                "seat: buzz\nrelay: https://ground.example\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    "bash",
                    str(ROOT / "post.sh"),
                    "--from",
                    "codex",
                    "--to",
                    "grok",
                    "--task",
                    "need origin access",
                    "--status",
                    "BLOCKED",
                    "--need-prime",
                    "true",
                    "--home",
                    tmp,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
            self.assertIn("prime-other-bus", proc.stderr)
            self.assertIn("DRY-RUN not posted", proc.stdout)
            self.assertNotIn("error: no identity", proc.stderr)

    def test_escalate_dry_run_does_not_ping(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._two_seats(tmp, True)
            grok = Path(tmp) / "buzz"
            grok.mkdir(exist_ok=True)
            grok.joinpath("PUBLIC.txt").write_text(
                "seat: buzz\ndisplay_name: grok-build\nrelay: wss://tail.example\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    "bash",
                    str(ROOT / "escalate.sh"),
                    "--from",
                    "codex",
                    "--to",
                    "grok",
                    "--task",
                    "need origin access",
                    "--home",
                    tmp,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("need_prime: true", proc.stdout)
            self.assertIn("DRY-RUN not posted", proc.stdout)
            self.assertNotIn("error: no identity", proc.stderr)

    def test_escalate_dry_run_mixed_exits_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._two_seats(tmp, True)
            grok = Path(tmp) / "buzz"
            grok.mkdir(exist_ok=True)
            grok.joinpath("PUBLIC.txt").write_text(
                "seat: buzz\ndisplay_name: grok-build\nrelay: https://ground.example\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    "bash",
                    str(ROOT / "escalate.sh"),
                    "--from",
                    "codex",
                    "--to",
                    "grok",
                    "--task",
                    "need origin access",
                    "--home",
                    tmp,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
            self.assertIn("prime-other-bus", proc.stderr)
            self.assertIn("DRY-RUN not posted", proc.stdout)
            self.assertNotIn("deadbeef", proc.stdout)

    def test_collab_blocked_need_prime_mixed_does_not_load_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._two_seats(tmp, False)
            grok = Path(tmp) / "buzz"
            grok.mkdir(exist_ok=True)
            grok.joinpath("PUBLIC.txt").write_text(
                "seat: buzz\nrelay: https://ground.example\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    "bash",
                    str(ROOT / "collab.sh"),
                    "blocked",
                    "--from",
                    "codex",
                    "--to",
                    "grok",
                    "--task",
                    "need origin access",
                    "--home",
                    tmp,
                    "--need-prime",
                    "true",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
            self.assertIn("prime-other-bus", proc.stderr)
            self.assertNotIn("error: no identity", proc.stderr)

    def test_content_blocked_need_prime_routes_escalate(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._two_seats(tmp, True)
            grok = Path(tmp) / "buzz"
            grok.mkdir(exist_ok=True)
            grok.joinpath("PUBLIC.txt").write_text(
                "seat: buzz\nrelay: https://ground.example\n",
                encoding="utf-8",
            )
            body = render_envelope(
                from_role="codex",
                to_role="grok",
                task="need origin access",
                status="BLOCKED",
                need_prime=True,
            )
            proc = subprocess.run(
                [
                    "bash",
                    str(ROOT / "post.sh"),
                    "--content",
                    body,
                    "--home",
                    tmp,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
            self.assertIn("prime-other-bus", proc.stderr)
            self.assertIn("DRY-RUN not posted", proc.stdout)
            self.assertNotIn("error: no identity", proc.stderr)

    def test_content_open_mixed_bus_exit_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._two_seats(tmp, False)
            body = render_envelope(from_role="codex", to_role="agy", task="cross bus")
            proc = subprocess.run(
                [
                    "bash",
                    str(ROOT / "post.sh"),
                    "--content",
                    body,
                    "--home",
                    tmp,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
            self.assertIn("VISITOR_COLLAB skip reason=", proc.stderr)
            self.assertNotIn("error: no identity", proc.stderr)

    def test_from_role_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._two_seats(tmp, True)
            proc = subprocess.run(
                [
                    "bash",
                    str(ROOT / "collab.sh"),
                    "open",
                    "--seat",
                    "codex-buzz",
                    "--from",
                    "grok",
                    "--to",
                    "agy",
                    "--task",
                    "wrong from",
                    "--home",
                    tmp,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("from-role-mismatch", proc.stderr)
            self.assertNotIn("error: no identity", proc.stderr)

    def test_file_cannot_combine_with_collab_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "body.txt"
            path.write_text("hello\n", encoding="utf-8")
            proc = subprocess.run(
                [
                    "bash",
                    str(ROOT / "post.sh"),
                    "--file",
                    str(path),
                    "--from",
                    "codex",
                    "--to",
                    "agy",
                    "--task",
                    "nope",
                    "--home",
                    tmp,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("--file cannot combine", proc.stderr)


class SeatDirTests(unittest.TestCase):
    def test_honors_visitor_agents_home(self):
        proc = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; VISITOR_AGENTS_HOME=/tmp/visitor-home visitor_seat_dir codex-buzz',
                "_",
                str(ROOT / "lib.sh"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "/tmp/visitor-home/codex-buzz")

    def test_gate_cli_home_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "codex-buzz"
            b = Path(tmp) / "agy-buzz"
            a.mkdir()
            b.mkdir()
            a.joinpath("PUBLIC.txt").write_text(
                "seat: codex-buzz\nrelay: wss://tail.example\n", encoding="utf-8"
            )
            b.joinpath("PUBLIC.txt").write_text(
                "seat: agy-buzz\nrelay: https://tail.example\n", encoding="utf-8"
            )
            env = os.environ.copy()
            env["VISITOR_AGENTS_HOME"] = tmp
            proc = subprocess.run(
                [
                    "python3",
                    str(ROOT / "gate.py"),
                    "same-bus",
                    "--from",
                    "codex",
                    "--to",
                    "agy",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(json.loads(proc.stdout)["ok"])


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
        self.assertIn("parked", proc.stdout.lower())
        self.assertIn("do_not: curl|bash", proc.stdout)
        self.assertNotRegex(proc.stdout.lower(), r"curl\s+\S+\s*\|\s*bash")
        self.assertNotIn("install:", proc.stdout.lower())
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
            self.assertNotIn('VISITOR_ROLE="${VISITOR_ROLE:-hermes}"', body)
            self.assertNotIn("managed-agents", body)
            self.assertTrue((Path(tmp) / "NOT-DESKTOP-ACP.txt").is_file())
            readme = (Path(tmp) / "README.txt").read_text()
            self.assertIn("PARKED", readme)
            self.assertIn("Do not curl|bash", readme)
            self.assertNotIn("hermes gateway start", readme)

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
    def test_refuse_parked_hermes(self):
        proc = subprocess.run(
            ["bash", str(ROOT / "install-profile.sh"), "--brain", "hermes", "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("parked", proc.stderr.lower())
        self.assertNotIn("status=dry-run", proc.stdout)
        self.assertNotIn("curl|bash", proc.stdout)

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

    def test_refuse_goose_mint(self):
        proc = subprocess.run(
            ["bash", str(ROOT / "install-profile.sh"), "--brain", "goose", "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("do not mint a Goose seat", proc.stderr)
        self.assertNotIn("status=dry-run", proc.stdout)
        self.assertNotIn("curl|bash", proc.stdout)


class LastRoomAndLimitTests(unittest.TestCase):
    def test_last_room_and_bound_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            seat = Path(tmp) / "codex-buzz"
            seat.mkdir()
            (seat / "last-room.json").write_text(
                '{"channel_id": "11111111-2222-3333-4444-555555555555", "name": "lab"}\n',
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    "bash",
                    "-c",
                    'source "$1"; visitor_last_room "$2"; visitor_bound_limit 500 100; visitor_bound_limit no 100; visitor_bound_limit 0 300',
                    "_",
                    str(ROOT / "lib.sh"),
                    str(seat),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
            self.assertEqual(
                lines,
                ["11111111-2222-3333-4444-555555555555", "100", "20", "20"],
            )

    def test_last_room_bus_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            seat = Path(tmp) / "x"
            seat.mkdir()
            (seat / "PUBLIC.txt").write_text(
                "seat: x\nrelay: wss://tail.example\n", encoding="utf-8"
            )
            (seat / "last-room.json").write_text(
                '{"channel_id": "11111111-2222-3333-4444-555555555555", "relay": "https://ground.example"}\n',
                encoding="utf-8",
            )
            bad = last_room_bus_ok(str(seat))
            self.assertFalse(bad["ok"])
            self.assertEqual(bad["reason"], "last-room-bus-mismatch")
            proc = subprocess.run(
                [
                    "bash",
                    "-c",
                    'source "$1"; visitor_assert_last_room_bus "$2"',
                    "_",
                    str(ROOT / "lib.sh"),
                    str(seat),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
            self.assertIn("last-room-bus-mismatch", proc.stderr)
            (seat / "last-room.json").write_text(
                '{"channel_id": "11111111-2222-3333-4444-555555555555", "relay": "wss://tail.example/"}\n',
                encoding="utf-8",
            )
            good = last_room_bus_ok(str(seat))
            self.assertTrue(good["ok"])
            cli = subprocess.run(
                ["python3", str(ROOT / "gate.py"), "last-room-bus", "--dir", str(seat)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)


class EscalateNoRecurseTests(unittest.TestCase):
    def test_escalate_script_passes_from_escalate(self):
        text = (ROOT / "escalate.sh").read_text(encoding="utf-8")
        self.assertIn("--from-escalate", text)

    def test_from_escalate_dry_run_does_not_reenter(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "codex-buzz"
            b = Path(tmp) / "agy-buzz"
            g = Path(tmp) / "buzz"
            a.mkdir()
            b.mkdir()
            g.mkdir()
            a.joinpath("PUBLIC.txt").write_text(
                "seat: codex-buzz\nrelay: wss://tail.example\n", encoding="utf-8"
            )
            b.joinpath("PUBLIC.txt").write_text(
                "seat: agy-buzz\nrelay: https://tail.example\n", encoding="utf-8"
            )
            g.joinpath("PUBLIC.txt").write_text(
                "seat: buzz\nrelay: wss://tail.example\n", encoding="utf-8"
            )
            proc = subprocess.run(
                [
                    "bash",
                    str(ROOT / "post.sh"),
                    "--from",
                    "codex",
                    "--to",
                    "grok",
                    "--task",
                    "need origin access",
                    "--status",
                    "BLOCKED",
                    "--need-prime",
                    "true",
                    "--from-escalate",
                    "--home",
                    tmp,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("need_prime: true", proc.stdout)
            self.assertIn("DRY-RUN not posted", proc.stdout)
            self.assertNotIn("Prime not pinged", proc.stdout)
            self.assertNotIn("error: no identity", proc.stderr)


class GooseCliTests(unittest.TestCase):
    def test_refuses_usr_bin_goose(self):
        env = os.environ.copy()
        env["GOOSE_BIN"] = "/usr/bin/goose"
        proc = subprocess.run(
            ["bash", str(ROOT / "goose-cli.sh"), "--check"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("system-goose-refused", proc.stdout)
        self.assertNotRegex(proc.stdout.lower(), r"curl\s+\S+\s*\|\s*bash")
        self.assertNotIn("nsec", proc.stdout.lower())

    def test_refuses_desktop_acp_fork_path(self):
        proc = subprocess.run(
            ["bash", str(ROOT / "goose-cli.sh"), "--check", "--fork", "/tmp/managed-agents-nope"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("refuse Desktop ACP", proc.stderr)

    def test_missing_fork_binary_is_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.pop("GOOSE_BIN", None)
            proc = subprocess.run(
                ["bash", str(ROOT / "goose-cli.sh"), "--check", "--fork", tmp],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertIn(proc.returncode, (2, 1), proc.stdout + proc.stderr)
            combined = proc.stdout + proc.stderr
            self.assertNotRegex(combined.lower(), r"curl\s+\S+\s*\|\s*bash")
            self.assertIn("do not", combined.lower())
            self.assertNotIn("/usr/bin/goose", proc.stdout.splitlines()[-1] if proc.stdout else "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
