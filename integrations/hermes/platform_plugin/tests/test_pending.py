from __future__ import annotations

import unittest
from collections import deque
from concurrent.futures import Future
import threading

from adapter import KORNexusAdapter


class PendingReplyTests(unittest.TestCase):
    def setUp(self):
        self.adapter = object.__new__(KORNexusAdapter)
        self.adapter._pending = {}
        self.adapter._pending_order = {"hud-session": deque()}
        self.adapter._pending_lock = threading.Lock()

    def test_only_oldest_pending_reply_is_completed(self):
        first, second = Future(), Future()
        self.adapter._pending = {"first": first, "second": second}
        self.adapter._pending_order["hud-session"].extend(["first", "second"])
        self.assertTrue(self.adapter._resolve_oldest_for_chat("hud-session", "first answer"))
        self.assertEqual(first.result(), "first answer")
        self.assertFalse(second.done())
        self.assertTrue(self.adapter._resolve_oldest_for_chat("hud-session", "second answer"))
        self.assertEqual(second.result(), "second answer")

    def test_message_resolution_is_correlated_by_message_id(self):
        future = Future()
        self.adapter._pending = {"message-id": future}
        self.assertTrue(self.adapter._resolve_message("message-id", "reply"))
        self.assertEqual(future.result(), "reply")

    def test_cleanup_removes_pending_entry_and_queue_member(self):
        future = Future()
        self.adapter._pending = {"message-id": future}
        self.adapter._pending_order["hud-session"].append("message-id")
        self.adapter._cleanup_pending("message-id", "hud-session")
        self.assertNotIn("message-id", self.adapter._pending)
        self.assertEqual(list(self.adapter._pending_order["hud-session"]), [])


if __name__ == "__main__":
    unittest.main()
