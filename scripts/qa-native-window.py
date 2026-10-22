#!/usr/bin/env python3
"""Exercise the native Qt window and verify IDE popups stay inside KOR-NEXUS."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from PyQt6.QtCore import QPoint, QTimer, Qt, QUrl
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core.window import KorNexusWindow

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class Handler(SimpleHTTPRequestHandler):
    origin = ""

    def log_message(self, *_args):
        pass

    def send_json(self, payload, status=200):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/ide/status":
            return self.send_json({
                "available": True,
                "running": False,
                "url": "",
                "workspaces": [{"name": "KOR-NEXUS", "path": str(ROOT), "git": True}],
            })
        if path == "/ide/":
            raw = b"<!doctype html><html><head><title>Native IDE Mock</title></head><body>IDE ready</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        return super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        size = int(self.headers.get("Content-Length", "0"))
        if size:
            self.rfile.read(size)
        if path == "/api/ide/start":
            return self.send_json({"url": self.origin + "/ide/"})
        if path == "/api/shutdown":
            return self.send_json({"ok": True})
        return self.send_json({"error": "not found"}, 404)


def main() -> None:
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(WEB)))
    Handler.origin = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    with tempfile.TemporaryDirectory(prefix="kor-native-window-") as data_home:
        os.environ["XDG_DATA_HOME"] = data_home
        app = QApplication([])
        app.setApplicationName("KOR-NEXUS native-window QA")
        window = KorNexusWindow(Handler.origin)
        window.show()
        window.browser.setUrl(QUrl(Handler.origin + "/code.html"))
        state = {"clicked": False, "done": False, "attempts": 0, "error": ""}

        def finish(error=""):
            if state["done"]:
                return
            state["done"] = True
            state["error"] = error
            app.quit()

        def poll():
            if state["done"]:
                return
            state["attempts"] += 1
            if state["attempts"] > 240:
                finish("Timed out waiting for native Code Workbench popup.")
                return

            if not state["clicked"]:
                def inspect_button(result):
                    if state["done"]:
                        return
                    if not isinstance(result, dict) or not result.get("enabled"):
                        QTimer.singleShot(100, poll)
                        return
                    rect = result.get("rect") or {}
                    x = int(rect.get("x", -1))
                    y = int(rect.get("y", -1))
                    if x < 0 or y < 0:
                        QTimer.singleShot(100, poll)
                        return
                    state["clicked"] = True
                    QTest.mouseClick(window.browser, Qt.MouseButton.LeftButton, pos=QPoint(x, y))
                    QTimer.singleShot(150, poll)

                window.browser.page().runJavaScript(
                    "(() => { const b=document.querySelector('#launchIde'); if(!b) return null; "
                    "const r=b.getBoundingClientRect(); return {enabled:!b.disabled, "
                    "rect:{x:r.x+r.width/2,y:r.y+r.height/2}}; })()",
                    inspect_button,
                )
                return

            if window._popup_windows:
                popup = window._popup_windows[0]
                current_url = popup.view_widget.url().toString()
                if current_url.endswith("/ide/"):
                    popup.view_widget.page().runJavaScript(
                        "document.title",
                        lambda title: finish() if title == "Native IDE Mock" else QTimer.singleShot(100, poll),
                    )
                    return
            QTimer.singleShot(100, poll)

        QTimer.singleShot(500, poll)
        try:
            app.exec()
            if state["error"]:
                raise SystemExit(state["error"])
            if not state["done"]:
                raise SystemExit("Native Qt window QA exited before completion.")
            if not window._popup_windows:
                raise SystemExit("IDE did not open a secondary native Qt window.")
            popup = window._popup_windows[0]
            if not popup.view_widget.url().toString().endswith("/ide/"):
                raise SystemExit("Native IDE window did not navigate to the API-returned URL.")
            print("PASS: KOR-NEXUS opens a native main window and keeps the Code Workbench in a secondary native Qt window.")
        finally:
            for popup in list(window._popup_windows):
                popup.close()
            window.close()
            app.processEvents()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    main()
