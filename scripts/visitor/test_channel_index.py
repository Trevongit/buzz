#!/usr/bin/env python3
from __future__ import annotations

import unittest

from channel_index import MAX_MESSAGES, MAX_ROOMS, build_pack, project_message


class ChannelIndexTests(unittest.TestCase):
    def test_project_message_keeps_signed_fields(self) -> None:
        msg = project_message(
            {
                "id": "ab" * 32,
                "pubkey": "cd" * 32,
                "created_at": 10,
                "kind": 9,
                "content": "hello",
                "sig": "drop-me",
            }
        )
        self.assertEqual(msg["content"], "hello")
        self.assertEqual(msg["kind"], 9)
        self.assertNotIn("sig", msg)

    def test_build_pack_caps_rooms_and_messages(self) -> None:
        rooms = [
            {
                "id": f"room-{i}",
                "name": f"n{i}",
                "messages": [{"id": "x", "pubkey": "y", "created_at": 1, "kind": 9, "content": "c"}]
                * (MAX_MESSAGES + 5),
            }
            for i in range(MAX_ROOMS + 3)
        ]
        pack = build_pack(rooms, written_at=99)
        self.assertEqual(pack["version"], 1)
        self.assertEqual(pack["written_at"], 99)
        self.assertEqual(len(pack["rooms"]), MAX_ROOMS)
        self.assertEqual(len(pack["rooms"][0]["messages"]), MAX_MESSAGES)
        self.assertEqual(pack["rooms"][0]["name"], "n0")


if __name__ == "__main__":
    unittest.main()
