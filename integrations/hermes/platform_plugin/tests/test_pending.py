from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
from collections import deque
from concurrent.futures import Future
import threading


def install_minimal_hermes_stubs():
    """The tests exercise adapter correlation logic without installing a Hermes Gateway."""
    if "gateway.config" in sys.modules:
        return

    gateway = types.ModuleType("gateway")
    gateway.__path__ = []
    config = types.ModuleType("gateway.config")
    platforms = types.ModuleType("gateway.platforms")
    platforms.__path__ = []
    base = types.ModuleType("gateway.platforms.base")
    event = types.ModuleType("gateway.platforms.event")

    class Platform(str):
        pass

    class PlatformConfig:
        pass

    class BasePlatformAdapter:
        def __init__(self, config, platform):
            self.config = config
            self.platform = platform
            self._running = False

        def build_source(self, **values):
            return types.SimpleNamespace(**values)

        async def handle_message(self, message_event):
            message_event._gateway_accepted = True

        def _mark_connected(self, **_kwargs):
            self._running = True

        def _mark_disconnected(self):
            self._running = False

        def _set_fatal_error(self, *_args, **_kwargs):
            self._running = False

    class SendResult:
        def __init__(self, success=True, message_id=""):
            self.success = success
            self.message_id = message_id

    class MessageType:
        TEXT = "text"

    class ProcessingOutcome:
        FAILURE = "failure"
        CANCELLED = "cancelled"
        COMPLETED = "completed"

    config.Platform = Platform
    config.PlatformConfig = PlatformConfig
    base.BasePlatformAdapter = BasePlatformAdapter
    base.SendResult = SendResult
    event.MessageEvent = type("MessageEvent", (), {})
    event.MessageType = MessageType
    event.ProcessingOutcome = ProcessingOutcome

    sys.modules.update({
        "gateway": gateway,
        "gateway.config": config,
        "gateway.platforms": platforms,
        "gateway.platforms.base": base,
        "gateway.platforms.event": event,
    })


install_minimal_hermes_stubs()
from gateway.config import PlatformConfig
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
        self.assertEqual(list(self.adapter._pending_order.get("hud-session", ())), [])

    def test_bridge_binds_loopback_and_requires_private_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "hermes-bridge.json"
            adapter = KORNexusAdapter(PlatformConfig())
            adapter._port = 0
            with patch.dict(os.environ, {"KOR_NEXUS_HERMES_CONFIG": str(config_path)}):
                try:
                    self.assertTrue(asyncio.run(adapter.connect()))
                    host, port = adapter._httpd.server_address[:2]
                    self.assertEqual(host, "127.0.0.1")
                    self.assertTrue(config_path.is_file())
                    self.assertEqual(config_path.stat().st_mode & 0o777, 0o600)
                    saved = json.loads(config_path.read_text(encoding="utf-8"))
                    self.assertEqual(saved["host"], "127.0.0.1")
                    self.assertEqual(saved["port"], port)
                    self.assertGreaterEqual(len(saved["token"]), 32)

                    with self.assertRaises(urllib.error.HTTPError) as rejected:
                        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
                    self.assertEqual(rejected.exception.code, 403)

                    request = urllib.request.Request(
                        f"http://127.0.0.1:{port}/health",
                        headers={"X-KOR-Bridge-Token": saved["token"]},
                    )
                    with urllib.request.urlopen(request, timeout=2) as response:
                        payload = json.load(response)
                    self.assertTrue(payload["ok"])
                    self.assertEqual(payload["platform"], "kor_nexus")
                finally:
                    if adapter._httpd is not None:
                        asyncio.run(adapter.disconnect())
                    self.assertFalse(config_path.exists())



if __name__ == "__main__":
    unittest.main()
