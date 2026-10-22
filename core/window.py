"""Native PyQt6 desktop shell for KOR-NEXUS and its internal tool windows."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from PyQt6.QtCore import QEvent, QUrl, Qt
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView


class KorNexusPage(QWebEnginePage):
    """Keep web popups inside native Qt windows instead of an external browser."""

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if url.scheme() == "kor-nexus" and url.host() == "quit":
            self.view().window().close()
            return False
        return super().acceptNavigationRequest(url, navigation_type, is_main_frame)

    def createWindow(self, window_type):
        host = self.view().window()
        create_popup = getattr(host, "create_popup_page", None)
        if callable(create_popup):
            return create_popup()
        return super().createWindow(window_type)


class KorNexusPopupWindow(QMainWindow):
    """A secondary native window for code-server and other intentional web popups."""

    def __init__(self, root_window: "KorNexusWindow", profile: QWebEngineProfile) -> None:
        super().__init__(root_window)
        self.root_window = root_window
        self.setWindowTitle("KOR-NEXUS // WORKBENCH")
        self.resize(1280, 820)
        self.view_widget = QWebEngineView(self)
        self.view_widget.setPage(KorNexusPage(profile, self.view_widget))
        self.setCentralWidget(self.view_widget)

    def create_popup_page(self):
        return self.root_window.create_popup_page()


class KorNexusWindow(QMainWindow):
    def __init__(self, url: str) -> None:
        super().__init__()
        self.setWindowTitle("KOR-NEXUS // COMMAND CENTER")
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self.setMinimumSize(960, 640)
        self.server_url = url.rstrip("/")
        self.profile_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "kor-workstation" / "qt_profile"
        self.profile_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        profile = QWebEngineProfile.defaultProfile()
        profile.setPersistentStoragePath(str(self.profile_dir))
        profile.setCachePath(str(self.profile_dir / "cache"))
        self._popup_windows: list[KorNexusPopupWindow] = []
        self.browser = QWebEngineView(self)
        self.browser.setPage(KorNexusPage(profile, self.browser))
        self.browser.setUrl(QUrl(url + ("&" if "?" in url else "?") + "native=1"))
        self.setCentralWidget(self.browser)
        self.showFullScreen()

    def create_popup_page(self):
        popup = KorNexusPopupWindow(self, self.browser.page().profile())
        self._popup_windows.append(popup)
        popup.destroyed.connect(lambda *_args, window=popup: self._forget_popup(window))
        popup.show()
        return popup.view_widget.page()

    def _forget_popup(self, window) -> None:
        try:
            self._popup_windows.remove(window)
        except ValueError:
            pass

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showMaximized()
            else:
                self.showFullScreen()
            event.accept()
            return True
        return super().eventFilter(watched, event)

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
        # Closing the main window ends the local core; closing a popup does not.
        try:
            request = Request(
                self.server_url + "/api/shutdown",
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
