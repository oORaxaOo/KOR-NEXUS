"""Loopback-only HTTP client for the KOR-NEXUS application API."""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import socket
import urllib.error
import urllib.parse
import urllib.request


class KorApiError(RuntimeError):
    """Safe, user-facing error from the local KOR-NEXUS API."""


def _loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _runtime_port() -> int | None:
    override = os.environ.get("KOR_NEXUS_RUNTIME_FILE", "").strip()
    if override:
        path = Path(override).expanduser()
    else:
        home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        path = home / "kor-workstation" / "runtime.json"
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        port = value.get("port") if isinstance(value, dict) else None
        if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
            return None
        return port
    except (OSError, UnicodeError, ValueError, TypeError):
        return None


def resolve_base_url(value: str | None = None) -> str:
    raw = (value or os.environ.get("KOR_NEXUS_BASE_URL", "")).strip()
    if not raw:
        raw = f"http://127.0.0.1:{_runtime_port() or 8765}"
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "http" or not _loopback(parsed.hostname or ""):
        raise KorApiError("KOR-NEXUS darf nur über eine lokale HTTP-Adresse angesprochen werden.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise KorApiError("Die KOR-NEXUS-Basisadresse enthält unzulässige URL-Bestandteile.")
    try:
        port = parsed.port or 8765
    except ValueError as exc:
        raise KorApiError("Der KOR-NEXUS-Port ist ungültig.") from exc
    if not 1 <= port <= 65535:
        raise KorApiError("Der KOR-NEXUS-Port ist ungültig.")
    host = parsed.hostname.lower()
    return f"http://[{host}]:{port}" if ":" in host else f"http://{host}:{port}"


class KorNexusClient:
    """Read-only JSON client. Phase I deliberately rejects all write methods."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0):
        self.base_url = resolve_base_url(base_url)
        try:
            timeout = float(timeout)
        except (TypeError, ValueError):
            timeout = 5.0
        self.timeout = max(1.0, min(timeout, 20.0))

    def request(self, method: str, path: str) -> dict:
        if method.upper() != "GET":
            raise KorApiError("Phase I erlaubt ausschließlich lesende GET-Anfragen.")
        if not path.startswith("/api/") or ".." in path.split("/"):
            raise KorApiError("Ungültiger KOR-NEXUS-API-Pfad.")
        request = urllib.request.Request(
            self.base_url + path,
            headers={"Accept": "application/json", "User-Agent": "KOR-NEXUS-Hermes-MCP/0.1"},
            method="GET",
        )

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            with opener.open(request, timeout=self.timeout) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise KorApiError("Die KOR-NEXUS-Antwort überschreitet das erlaubte Größenlimit.")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise KorApiError("Der angeforderte KOR-NEXUS-Endpunkt wurde nicht gefunden.") from None
            if exc.code in (400, 409, 422):
                raise KorApiError(f"KOR-NEXUS hat die Anfrage abgelehnt (HTTP {exc.code}).") from None
            if exc.code in (401, 403):
                raise KorApiError("KOR-NEXUS hat den lokalen Zugriff abgelehnt.") from None
            raise KorApiError(f"KOR-NEXUS ist momentan nicht verfügbar (HTTP {exc.code}).") from None
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError):
            raise KorApiError("KOR-NEXUS ist lokal nicht erreichbar. Ist die Anwendung gestartet?") from None
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise KorApiError("KOR-NEXUS hat keine gültige JSON-Antwort geliefert.") from exc
        if not isinstance(value, dict):
            raise KorApiError("KOR-NEXUS hat ein unerwartetes Antwortformat geliefert.")
        if value.get("ok") is False:
            raise KorApiError("KOR-NEXUS konnte die Anfrage nicht abschließen.")
        return value

    def get_status(self) -> dict:
        return self.request("GET", "/api/engine/status")

    def list_tasks(self) -> list[dict]:
        return self.request("GET", "/api/tasks").get("items", [])

    def list_records(self, module: str) -> list[dict]:
        if module not in {"atlas", "projects", "archive", "simulation", "database"}:
            raise KorApiError("Unbekanntes KOR-NEXUS-Modul.")
        query = urllib.parse.urlencode({"module": module})
        return self.request("GET", f"/api/records?{query}").get("items", [])

    def list_resources(self) -> list[dict]:
        return self.request("GET", "/api/resources").get("items", [])

    def list_alerts(self, status: str) -> list[dict]:
        if status not in {"open", "acknowledged", "resolved", "all"}:
            raise KorApiError("Unbekannter KOR-NEXUS-Warnmeldungsstatus.")
        query = urllib.parse.urlencode({"status": status})
        return self.request("GET", f"/api/engine/alerts?{query}").get("items", [])

    def get_dashboard(self, region: str = "", status: str = "", project_id: int | None = None) -> dict:
        if status not in {"", "geplant", "aktiv", "blockiert", "abgeschlossen", "unbekannt", "gemischt"}:
            raise KorApiError("Unbekannter Projektstatus.")
        params: dict[str, str | int] = {}
        if region:
            params["region"] = region[:180]
        if status:
            params["status"] = status
        if project_id is not None:
            if isinstance(project_id, bool) or not isinstance(project_id, int) or project_id < 1:
                raise KorApiError("Die Projekt-ID muss eine positive Ganzzahl sein.")
            params["project_id"] = project_id
        query = "?" + urllib.parse.urlencode(params) if params else ""
        return self.request("GET", "/api/dashboard/projects" + query)

    def get_events(self, since: int = 0, limit: int = 100) -> dict:
        if isinstance(since, bool) or not isinstance(since, int) or since < 0:
            raise KorApiError("Der Ereignis-Cursor muss eine nichtnegative Ganzzahl sein.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise KorApiError("Der Ereignisumfang muss zwischen 1 und 500 liegen.")
        query = urllib.parse.urlencode({"since": since, "limit": limit})
        return self.request("GET", f"/api/events?{query}")
