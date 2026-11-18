from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from kor_client import KorApiError, KorNexusClient, resolve_base_url


class Handler(BaseHTTPRequestHandler):
    requests = []
    body = {"ok": True, "items": []}
    status = 200
    redirect = None

    def do_GET(self):
        type(self).requests.append((self.command, self.path))
        body = json.dumps(type(self).body).encode()
        self.send_response(type(self).status)
        if type(self).redirect:
            self.send_header("Location", type(self).redirect)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_write(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        type(self).requests.append((self.command, self.path, payload))
        body = json.dumps({"ok": True, "received": payload}).encode()
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self._handle_write()

    def do_PATCH(self):
        self._handle_write()

    def log_message(self, *_args):
        pass


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        Handler.requests = []
        Handler.body = {"ok": True, "items": []}
        Handler.status = 200
        Handler.redirect = None
        self.client = KorNexusClient(self.url)

    def test_rejects_non_loopback_urls_and_non_http(self):
        for url in ("https://127.0.0.1", "http://example.com", "http://127.0.0.1/private",
                    "http://user:pass@127.0.0.1", "http://127.0.0.1?token=x"):
            with self.subTest(url=url), self.assertRaises(KorApiError):
                resolve_base_url(url)

    def test_loopback_urls_are_normalized(self):
        self.assertEqual(resolve_base_url("http://localhost:8765/"), "http://localhost:8765")
        self.assertEqual(resolve_base_url("http://[::1]:8765"), "http://[::1]:8765")

    def test_only_allowlisted_read_and_write_routes_are_allowed(self):
        with self.assertRaises(KorApiError):
            self.client.request("GET", "/etc/passwd")
        with self.assertRaises(KorApiError):
            self.client.request("POST", "/api/restore", {})
        with self.assertRaises(KorApiError):
            self.client.request("PATCH", "/api/actions/proposals/1/execute", {})
        for method in ("DELETE", "PUT"):
            with self.subTest(method=method), self.assertRaises(KorApiError):
                self.client.request(method, "/api/tasks/1")
        before = len(Handler.requests)
        with self.assertRaises(KorApiError):
            self.client.request("PATCH", "/api/tasks/0", {})
        self.assertEqual(len(Handler.requests), before)

    def test_create_task_validates_fields_and_posts_only_to_tasks_endpoint(self):
        self.client.create_task("Karte prüfen", area="Atlas", priority=2, estimated_minutes=45)
        method, path, payload = Handler.requests[-1]
        self.assertEqual((method, path), ("POST", "/api/tasks"))
        self.assertEqual(payload["title"], "Karte prüfen")
        self.assertEqual(payload["area"], "Atlas")
        self.assertEqual(payload["priority"], 2)
        self.assertEqual(payload["estimated_minutes"], 45)
        before = len(Handler.requests)
        with self.assertRaises(KorApiError):
            self.client.create_task("x" * 181)
        with self.assertRaises(KorApiError):
            self.client.create_task("Bad priority", priority=99)
        self.assertEqual(len(Handler.requests), before)

    def test_update_task_uses_validated_positive_id_and_patch_allowlist(self):
        self.client.update_task(7, done=True, priority=1, clear_due_date=True)
        method, path, payload = Handler.requests[-1]
        self.assertEqual((method, path), ("PATCH", "/api/tasks/7"))
        self.assertEqual(payload, {"done": True, "due_at": None, "priority": 1})
        before = len(Handler.requests)
        with self.assertRaises(KorApiError):
            self.client.update_task(0, done=True)
        with self.assertRaises(KorApiError):
            self.client.update_task(7, done=True, due_at="2026-12-01T10:00:00+01:00", clear_due_date=True)
        self.assertEqual(len(Handler.requests), before)

    def test_create_and_update_record_are_limited_to_record_modules(self):
        self.client.create_record("archive", "Grundsatz", "Inhalt", tags=["Kor", "Wissen"])
        method, path, payload = Handler.requests[-1]
        self.assertEqual((method, path), ("POST", "/api/records"))
        self.assertEqual(payload["module"], "archive")
        self.assertEqual(payload["tags"], ["Kor", "Wissen"])
        self.client.update_record(12, title="Neuer Titel", update_tags=True, tags=[])
        method, path, payload = Handler.requests[-1]
        self.assertEqual((method, path), ("PATCH", "/api/records/12"))
        self.assertEqual(payload, {"title": "Neuer Titel", "tags": []})
        before = len(Handler.requests)
        with self.assertRaises(KorApiError):
            self.client.create_record("private", "Nicht erlaubt")
        with self.assertRaises(KorApiError):
            self.client.update_record(12)
        self.assertEqual(len(Handler.requests), before)

    def test_module_is_allowlisted_and_query_encoded(self):
        with self.assertRaises(KorApiError):
            self.client.list_records("../../private")
        self.client.list_records("projects")
        self.assertEqual(Handler.requests[-1][1], "/api/records?module=projects")

    def test_event_cursor_and_limit_are_validated(self):
        with self.assertRaises(KorApiError):
            self.client.get_events(since=-1)
        with self.assertRaises(KorApiError):
            self.client.get_events(limit=501)
        self.client.get_events(4, 8)
        self.assertEqual(Handler.requests[-1][1], "/api/events?since=4&limit=8")

    def test_dashboard_filters_are_validated(self):
        with self.assertRaises(KorApiError):
            self.client.get_dashboard(status="not-a-status")
        with self.assertRaises(KorApiError):
            self.client.get_dashboard(project_id=0)

    def test_error_response_body_is_not_leaked(self):
        Handler.status = 500
        Handler.body = {"private": "record contents"}
        with self.assertRaises(KorApiError) as caught:
            self.client.get_status()
        self.assertNotIn("record contents", str(caught.exception))

    def test_redirects_are_not_followed(self):
        Handler.status = 302
        Handler.redirect = "https://example.com/collect"
        with self.assertRaises(KorApiError):
            self.client.get_status()

    def test_non_object_json_response_is_rejected(self):
        Handler.body = ["not", "an", "object"]
        with self.assertRaises(KorApiError):
            self.client.get_status()

    def test_runtime_file_port_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_home = os.path.join(tmp, "xdg")
            target = os.path.join(data_home, "kor-workstation")
            os.makedirs(target)
            with open(os.path.join(target, "runtime.json"), "w", encoding="utf-8") as handle:
                json.dump({"port": 9876}, handle)
            with patch.dict(os.environ, {"XDG_DATA_HOME": data_home, "KOR_NEXUS_BASE_URL": ""}):
                self.assertEqual(resolve_base_url(), "http://127.0.0.1:9876")


if __name__ == "__main__":
    unittest.main()
