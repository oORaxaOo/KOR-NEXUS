"""Read-only HTTP client for the local KOR-NEXUS API.

The client deliberately talks to the public loopback API rather than importing
KOR-NEXUS internals or opening its SQLite database. This keeps the optional
Hermes integration isolated from the deterministic KOR-NEXUS core.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

APP_NAME = "KOR-NEXUS"
DEFAULT_PORT = 8765
DEFAULT_TIMEOUT = 5.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 100

# A local bridge must never route its HTTP request through environment-configured proxies.
_DIRECT_HTTP = build_opener(ProxyHandler({}))

READ_ROUTES = {
    "health": "/api/health",
    "system_health": "/api/system/health",
    "tasks": "/api/tasks",
    "records": "/api/records",
    "resources": "/api/resources",
    "projects": "/api/dashboard/projects",
    "news": "/api/news",
}

VALID_MODULES = {"atlas", "projects", "archive", "simulation", "database"}
VALID_PROJECT_STATUSES = {
    "geplant", "aktiv", "blockiert", "abgeschlossen", "unbekannt", "gemischt"
}


class KorNexusError(RuntimeError):
    """Raised when the local KOR-NEXUS API is unavailable or returns bad data."""


def default_data_home() -> Path:
    """Match KOR-NEXUS' XDG data directory selection."""
    explicit = os.environ.get("KOR_NEXUS_DATA_HOME", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    raw = os.environ.get("XDG_DATA_HOME", "").strip()
    root = Path(raw).expanduser() if raw else Path.home() / ".local" / "share"
    return root / "kor-workstation"


def validate_loopback_url(value: str) -> str:
    """Accept only plain HTTP URLs bound to a loopback host and optional port."""
    try:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as exc:
        raise KorNexusError("KOR-NEXUS URL ist ungültig.") from exc

    if parsed.scheme != "http":
        raise KorNexusError("KOR-NEXUS muss über lokales HTTP erreichbar sein.")
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise KorNexusError("Aus Sicherheitsgründen sind nur Loopback-Adressen erlaubt.")
    if parsed.username or parsed.password or parsed.path not in {"", "/"}:
        raise KorNexusError("KOR-NEXUS URL darf keine Zugangsdaten oder zusätzlichen Pfade enthalten.")
    if parsed.query or parsed.fragment:
        raise KorNexusError("KOR-NEXUS URL darf keine Query-Parameter oder Fragmente enthalten.")
    if port is not None and not 1024 <= port <= 65535:
        raise KorNexusError("KOR-NEXUS Port liegt außerhalb des erlaubten Bereichs.")

    host = f"[{hostname}]" if ":" in hostname else hostname
    return f"http://{host}:{port or DEFAULT_PORT}"


def _safe_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(minimum, min(maximum, number))


class KorNexusClient:
    """Small, bounded, read-only client for the KOR-NEXUS loopback API."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        data_home: str | Path | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        opener=None,
    ) -> None:
        self.data_home = Path(data_home).expanduser() if data_home else default_data_home()
        try:
            requested_timeout = float(timeout)
        except (TypeError, ValueError, OverflowError):
            requested_timeout = DEFAULT_TIMEOUT
        if not 1 <= requested_timeout <= 30:
            requested_timeout = DEFAULT_TIMEOUT
        self.timeout = requested_timeout
        self._opener = opener or _DIRECT_HTTP.open
        configured_url = base_url or os.environ.get("KOR_NEXUS_BASE_URL", "").strip()
        self._explicit_url = bool(configured_url)
        self.base_url = validate_loopback_url(configured_url) if configured_url else self._discover_url()
        self._verified_until = 0.0

    def _discover_url(self) -> str:
        """Read KOR-NEXUS' runtime port when available; otherwise use its default."""
        runtime_file = self.data_home / "runtime.json"
        try:
            info = json.loads(runtime_file.read_text(encoding="utf-8"))
            if not isinstance(info, dict):
                raise ValueError("runtime.json must contain an object")
            port = _safe_int(info.get("port"), default=DEFAULT_PORT, minimum=1024, maximum=65535)
        except (OSError, UnicodeError, ValueError, AttributeError):
            port = DEFAULT_PORT
        return f"http://127.0.0.1:{port}"

    def _refresh_url(self) -> None:
        if not self._explicit_url:
            discovered = self._discover_url()
            if discovered != self.base_url:
                self.base_url = discovered
                self._verified_until = 0.0

    def _request_json(self, route: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if route not in READ_ROUTES:
            raise KorNexusError("Dieser API-Endpunkt ist für die Hermes-Integration nicht freigegeben.")

        self._refresh_url()
        query = urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})
        url = self.base_url + READ_ROUTES[route]
        if query:
            url += "?" + query
        request = Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": "KOR-NEXUS-Hermes-MCP/0.1",
            },
        )

        try:
            with self._opener(request, timeout=self.timeout) as response:
                status = getattr(response, "status", None) or response.getcode()
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            try:
                detail = exc.read(4096).decode("utf-8", errors="replace")
            except OSError:
                detail = ""
            raise KorNexusError(f"KOR-NEXUS API antwortete mit HTTP {exc.code}: {detail[:300]}") from exc
        except (URLError, OSError, TimeoutError) as exc:
            raise KorNexusError("KOR-NEXUS ist lokal nicht erreichbar. Starte zuerst KOR-NEXUS.") from exc

        if status < 200 or status >= 300:
            raise KorNexusError(f"KOR-NEXUS API antwortete mit HTTP {status}.")
        if len(raw) > MAX_RESPONSE_BYTES:
            raise KorNexusError("KOR-NEXUS API-Antwort überschreitet das erlaubte Größenlimit.")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise KorNexusError("KOR-NEXUS lieferte keine gültige JSON-Antwort.") from exc
        if not isinstance(payload, dict):
            raise KorNexusError("KOR-NEXUS lieferte ein unerwartetes Antwortformat.")
        if payload.get("ok") is False:
            raise KorNexusError(str(payload.get("error") or "KOR-NEXUS API meldete einen Fehler.")[:300])
        return payload

    def _verify_identity(self, health: dict[str, Any]) -> None:
        if health.get("app") != APP_NAME or health.get("ok") is not True:
            raise KorNexusError("Der lokale Dienst ist nicht die erwartete KOR-NEXUS-Instanz.")
        reported = health.get("data_dir")
        if not isinstance(reported, str) or not reported.strip():
            raise KorNexusError("KOR-NEXUS meldet kein gültiges Datenverzeichnis.")
        try:
            actual_dir = Path(reported).expanduser().resolve()
            expected_dir = self.data_home.expanduser().resolve()
        except (OSError, RuntimeError) as exc:
            raise KorNexusError("KOR-NEXUS Datenverzeichnis konnte nicht geprüft werden.") from exc
        if actual_dir != expected_dir:
            raise KorNexusError("KOR-NEXUS läuft mit einem anderen Benutzer-Datenprofil; Zugriff abgebrochen.")

    def _ensure_ready(self) -> None:
        if time.monotonic() < self._verified_until:
            self._refresh_url()
            if time.monotonic() < self._verified_until:
                return
        health = self._request_json("health")
        self._verify_identity(health)
        self._verified_until = time.monotonic() + 15.0

    @staticmethod
    def _bounded_items(payload: dict[str, Any], limit: int) -> dict[str, Any]:
        items = payload.get("items")
        if not isinstance(items, list):
            raise KorNexusError("KOR-NEXUS lieferte keine gültige Elementliste.")
        bounded = dict(payload)
        bounded["items"] = items[:limit]
        bounded["returned"] = len(bounded["items"])
        bounded["truncated"] = len(items) > limit
        return bounded

    def get_status(self) -> dict[str, Any]:
        health = self._request_json("health")
        self._verify_identity(health)
        self._verified_until = time.monotonic() + 15.0
        # Do not expose the local filesystem path to the model unnecessarily.
        return {
            key: health.get(key)
            for key in ("ok", "app", "version", "database", "backup_count", "python", "system")
            if key in health
        }

    def get_system_health(self) -> dict[str, Any]:
        self._ensure_ready()
        return self._request_json("system_health")

    def list_tasks(self, limit: int = 50) -> dict[str, Any]:
        self._ensure_ready()
        limit = _safe_int(limit, default=50, minimum=1, maximum=MAX_ITEMS)
        return self._bounded_items(self._request_json("tasks"), limit)

    def list_records(self, module: str = "archive", limit: int = 30) -> dict[str, Any]:
        self._ensure_ready()
        if module not in VALID_MODULES:
            raise KorNexusError("Unbekanntes KOR-NEXUS-Modul.")
        limit = _safe_int(limit, default=30, minimum=1, maximum=MAX_ITEMS)
        return self._bounded_items(self._request_json("records", {"module": module}), limit)

    def list_resources(self, limit: int = 50) -> dict[str, Any]:
        self._ensure_ready()
        limit = _safe_int(limit, default=50, minimum=1, maximum=MAX_ITEMS)
        return self._bounded_items(self._request_json("resources"), limit)

    def list_projects(
        self,
        region: str = "",
        status: str = "",
        project_id: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        self._ensure_ready()
        if status and status not in VALID_PROJECT_STATUSES:
            raise KorNexusError("Unbekannter Projektstatus.")
        if region and (len(region) > 180 or any(ord(ch) < 32 for ch in region)):
            raise KorNexusError("Projektregion ist ungültig oder zu lang.")
        params: dict[str, Any] = {}
        if region.strip():
            params["region"] = region.strip()
        if status:
            params["status"] = status
        if project_id not in (0, None, ""):
            if isinstance(project_id, bool):
                raise KorNexusError("Projekt-ID muss eine positive Zahl sein.")
            try:
                normalized_project_id = int(project_id)
            except (TypeError, ValueError, OverflowError) as exc:
                raise KorNexusError("Projekt-ID muss eine positive Zahl sein.") from exc
            if normalized_project_id < 1 or str(normalized_project_id) != str(project_id).strip():
                raise KorNexusError("Projekt-ID muss eine positive ganze Zahl sein.")
            params["project_id"] = normalized_project_id
        limit = _safe_int(limit, default=50, minimum=1, maximum=MAX_ITEMS)
        return self._bounded_items(self._request_json("projects", params), limit)

    def list_news(self, limit: int = 20) -> dict[str, Any]:
        """Return the existing local RSS cache; do not trigger a network refresh."""
        self._ensure_ready()
        limit = _safe_int(limit, default=20, minimum=1, maximum=MAX_ITEMS)
        payload = self._request_json("news")
        items = payload.get("items")
        if not isinstance(items, list):
            raise KorNexusError("KOR-NEXUS lieferte keinen gültigen Nachrichten-Cache.")
        result = dict(payload)
        result["items"] = items[:limit]
        result["returned"] = len(result["items"])
        result["truncated"] = len(items) > limit
        return result
