#!/usr/bin/env python3
"""Browser regression test for the Code Workbench launch flow."""
from __future__ import annotations

import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(WEB)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.route("**/api/ide/status", lambda route: route.fulfill(
                status=200, content_type="application/json",
                body=json.dumps({
                    "available": True, "running": False, "url": "",
                    "workspaces": [{"name": "KOR-NEXUS", "path": str(ROOT), "git": True}],
                }),
            ))
            page.route("**/api/ide/start", lambda route: route.fulfill(
                status=200, content_type="application/json",
                body=json.dumps({"url": origin + "/ide/"}),
            ))
            page.route("**/ide/**", lambda route: route.fulfill(
                status=200, content_type="text/html",
                body="<title>Mock code-server</title><main>IDE ready</main>",
            ))
            page.goto(origin + "/code.html", wait_until="domcontentloaded")
            page.locator("#launchIde").wait_for(state="visible")
            page.wait_for_function("!document.querySelector('#launchIde').disabled")
            with page.expect_popup() as popup_info:
                page.locator("#launchIde").click()
            ide_tab = popup_info.value
            ide_tab.wait_for_url("**/ide/")
            ide_tab.wait_for_load_state("domcontentloaded")
            ide_tab.wait_for_function("document.title === 'Mock code-server'")
            assert "Mock code-server" in ide_tab.title(), "IDE window did not navigate to the returned URL"
            assert page.locator("#workspaceMessage").inner_text().startswith("IDE gestartet"), "UI did not report launch success"
            print("Code Workbench launch browser regression test passed.")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
