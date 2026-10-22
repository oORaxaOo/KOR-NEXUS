"""Native PyQt6 shell for the KOR-NEXUS local web UI."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView


class KorNexusPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if url.scheme() == 'kor-nexus' and url.host() == 'quit':
            self.view().window().close()
            return False
        return super().acceptNavigationRequest(url, navigation_type, is_main_frame)


class KorNexusWindow(QMainWindow):
    def __init__(self, url: str) -> None:
        super().__init__()
        self.setWindowTitle("KOR-NEXUS // COMMAND CENTER")
        self.setMinimumSize(960, 640)
        self.browser = QWebEngineView(self)
        self.browser.setPage(KorNexusPage(QWebEngineProfile.defaultProfile(), self.browser))
        self.profile_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "kor-workstation" / "qt_profile"
        self.profile_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        profile = QWebEngineProfile.defaultProfile()
        profile.setPersistentStoragePath(str(self.profile_dir))
        profile.setCachePath(str(self.profile_dir / "cache"))
        self.browser.setUrl(QUrl(url + ("&" if "?" in url else "?") + "native=1"))
        self.setCentralWidget(self.browser)
        self.showFullScreen()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showMaximized()
            else:
                self.showFullScreen()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        # Notify the local core so its normal cleanup path can run.
        try:
            request = Request(
                self.browser.url().toString().rstrip("/") + "/api/shutdown",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=1.5):
                pass
        except Exception:
            pass
        event.accept()


def start_native_app(url: str) -> int:
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("KOR-NEXUS")
    app.setOrganizationName("KOR")
    window = KorNexusWindow(url)
    window.show()
    return app.exec()
