import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from integrations.hermes.kor_client import KorNexusClient, KorNexusError, default_data_home, validate_loopback_url


class FakeKorHandler(BaseHTTPRequestHandler):
    data_home = ""
    last_path = ""

    def log_message(self, *_args):
        return

    def do_GET(self):
        parsed = urlsplit(self.path)
        type(self).last_path = self.path
        if parsed.path == "/api/health":
            payload = {
                "ok": True,
                "app": "KOR-NEXUS",
                "version": "1.20.0",
                "database": "SQLite",
                "data_dir": self.data_home,
                "backup_count": 2,
                "python": "3.12.0",
                "system": {"cpu_load_1min": 0.1},
            }
        elif parsed.path == "/api/tasks":
            payload = {"items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        elif parsed.path == "/api/records":
            payload = {"items": [{"module": parse_qs(parsed.query).get("module", [""])[0]}]}
        elif parsed.path == "/api/resources":
            payload = {"items": [{"id": 9, "name": "Testressource"}]}
        elif parsed.path == "/api/dashboard/projects":
            payload = {"items": [{"id": 4, "title": "Testprojekt"}], "total": 1}
        elif parsed.path == "/api/news":
            payload = {"items": [{"title": "Cache-Titel"}], "sources": []}
        elif parsed.path == "/api/system/health":
            payload = {"cpu_load_1min": 0.1, "ram_used_pct": 20.0}
        else:
            payload = {"ok": False, "error": "not found"}
            self.send_response(404)
            body = json.dumps(payload).encode()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class KorNexusClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_home = Path(self.temp.name) / "kor-workstation"
        self.data_home.mkdir()
        FakeKorHandler.data_home = str(self.data_home.resolve())
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeKorHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.client = KorNexusClient(self.base_url, data_home=self.data_home)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def test_refuses_non_loopback_and_non_http_urls(self):
        for url in (
            "https://127.0.0.1:8765",
            "http://example.com:8765",
            "http://127.0.0.1:8765/path",
            "http://user:pass@127.0.0.1:8765",
        ):
            with self.subTest(url=url), self.assertRaises(KorNexusError):
                validate_loopback_url(url)

    def test_only_accepts_expected_kor_nexus_instance_and_hides_data_path(self):
        status = self.client.get_status()
        self.assertEqual(status["app"], "KOR-NEXUS")
        self.assertEqual(status["version"], "1.20.0")
        self.assertNotIn("data_dir", status)

    def test_task_list_is_bounded(self):
        result = self.client.list_tasks(2)
        self.assertEqual(result["returned"], 2)
        self.assertTrue(result["truncated"])
        self.assertEqual([item["id"] for item in result["items"]], [1, 2])

    def test_records_module_is_validated_and_encoded(self):
        result = self.client.list_records("archive", 10)
        self.assertEqual(result["items"][0]["module"], "archive")
        self.assertIn("module=archive", FakeKorHandler.last_path)
        with self.assertRaises(KorNexusError):
            self.client.list_records("../../etc", 10)

    def test_project_dashboard_filters_are_forwarded(self):
        result = self.client.list_projects(region="Sachsen", status="aktiv", project_id=4)
        self.assertEqual(result["items"][0]["id"], 4)
        self.assertIn("region=Sachsen", FakeKorHandler.last_path)
        self.assertIn("status=aktiv", FakeKorHandler.last_path)
        self.assertIn("project_id=4", FakeKorHandler.last_path)

    def test_news_reads_cached_items_and_does_not_request_refresh(self):
        result = self.client.list_news()
        self.assertEqual(result["items"][0]["title"], "Cache-Titel")
        self.assertNotIn("refresh=1", FakeKorHandler.last_path)

    def test_rejects_mismatched_user_data_profile(self):
        other = Path(self.temp.name) / "other-profile"
        other.mkdir()
        client = KorNexusClient(self.base_url, data_home=other)
        with self.assertRaises(KorNexusError):
            client.get_status()

    def test_explicit_kor_nexus_data_home_overrides_xdg_default(self):
        explicit = Path(self.temp.name) / "custom-kor-data"
        with patch.dict("os.environ", {
            "KOR_NEXUS_DATA_HOME": str(explicit),
            "XDG_DATA_HOME": str(Path(self.temp.name) / "other-xdg"),
        }):
            self.assertEqual(default_data_home(), explicit)

    def test_runtime_file_discovers_the_dynamic_kor_port(self):
        runtime = self.data_home / "runtime.json"
        runtime.write_text(json.dumps({"port": self.server.server_port}), encoding="utf-8")
        client = KorNexusClient(data_home=self.data_home)
        status = client.get_status()
        self.assertEqual(status["app"], "KOR-NEXUS")
        self.assertEqual(client.base_url, self.base_url)

    def test_project_id_rejects_invalid_values(self):
        for invalid in (True, -1, "1;DROP", "1.5", "not-a-number"):
            with self.subTest(project_id=invalid), self.assertRaises(KorNexusError):
                self.client.list_projects(project_id=invalid)


if __name__ == "__main__":
    unittest.main()
