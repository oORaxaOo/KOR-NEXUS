from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from core.hermes_bridge import HermesBridgeError, bridge_status, send_to_hermes


class BridgeHandler(BaseHTTPRequestHandler):
    expected_token = "test-token-that-is-long-enough-for-this-test"
    seen = []
    reply = "Antwort von Lilith"

    def _reply(self, status: int, value: dict) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        return self.headers.get("X-KOR-Bridge-Token") == type(self).expected_token

    def do_GET(self):
        if not self._authorized():
            return self._reply(403, {"ok": False})
        if self.path != "/health":
            return self._reply(404, {"ok": False})
        return self._reply(200, {"ok": True, "platform": "kor_nexus"})

    def do_POST(self):
        if not self._authorized():
            return self._reply(403, {"ok": False})
        if self.path != "/message":
            return self._reply(404, {"ok": False})
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        type(self).seen.append(payload)
        return self._reply(200, {"ok": True, "response": type(self).reply})

    def log_message(self, *_args):
        return


class HermesBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), BridgeHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        config_dir = Path(self.temp.name) / "config" / "kor-nexus"
        config_dir.mkdir(parents=True)
        (config_dir / "hermes-bridge.json").write_text(
            json.dumps({
                "version": 1,
                "host": "127.0.0.1",
                "port": self.port,
                "token": BridgeHandler.expected_token,
            }),
            encoding="utf-8",
        )
        self.env = patch.dict(os.environ, {
            "XDG_CONFIG_HOME": str(Path(self.temp.name) / "config"),
            "KOR_NEXUS_HERMES_CONFIG": "",
        })
        self.env.start()
        BridgeHandler.seen = []

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_bridge_status_reports_connected_without_exposing_credentials(self):
        result = bridge_status()
        self.assertTrue(result["available"])
        self.assertEqual(result["platform"], "kor_nexus")
        self.assertNotIn("token", result)
        self.assertNotIn("port", result)

    def test_message_is_sent_with_session_id_and_final_reply_is_returned(self):
        result = send_to_hermes("Status bitte", "hud-test-session")
        self.assertEqual(result, BridgeHandler.reply)
        self.assertEqual(BridgeHandler.seen, [{
            "message": "Status bitte",
            "session_id": "hud-test-session",
        }])

    def test_invalid_session_is_rejected_before_network_access(self):
        with self.assertRaises(HermesBridgeError):
            send_to_hermes("Hallo", "../outside")
        self.assertEqual(BridgeHandler.seen, [])

    def test_non_loopback_bridge_host_is_rejected(self):
        config = Path(self.temp.name) / "config" / "kor-nexus" / "hermes-bridge.json"
        value = json.loads(config.read_text(encoding="utf-8"))
        value["host"] = "example.com"
        config.write_text(json.dumps(value), encoding="utf-8")
        result = bridge_status()
        self.assertFalse(result["available"])
        self.assertNotIn("example.com", result["detail"])


if __name__ == "__main__":
    unittest.main()
