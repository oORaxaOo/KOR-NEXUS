"""Loopback-only HTTP client for the KOR-NEXUS application API."""
from __future__ import annotations

import ipaddress
import json
import os
import re
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
    """Bounded KOR-NEXUS API client with an explicit, narrow write allowlist."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0):
        self.base_url = resolve_base_url(base_url)
        try:
            timeout = float(timeout)
        except (TypeError, ValueError):
            timeout = 5.0
        self.timeout = max(1.0, min(timeout, 20.0))

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        method = method.upper()
        if not isinstance(path, str) or not path.startswith("/api/") or ".." in path.split("/"):
            raise KorApiError("Ungültiger KOR-NEXUS-API-Pfad.")
        if method == "GET":
            allowed_get_paths = {
                "/api/engine/status", "/api/tasks", "/api/records", "/api/resources",
                "/api/engine/alerts", "/api/dashboard/projects", "/api/events",
            }
            if urllib.parse.urlsplit(path).path not in allowed_get_paths:
                raise KorApiError("Dieser lesende KOR-NEXUS-Endpunkt ist nicht freigegeben.")
            if payload is not None:
                raise KorApiError("GET-Anfragen dürfen keine Schreibdaten enthalten.")
        elif method == "POST":
            route = urllib.parse.urlsplit(path).path
            allowed_fields = {
                "/api/tasks": {"title", "area", "due_at", "priority", "estimated_minutes", "blocked_reason"},
                "/api/records": {"module", "title", "body", "region", "tags"},
            }.get(route)
            if allowed_fields is None:
                raise KorApiError("Dieser schreibende KOR-NEXUS-Endpunkt ist nicht freigegeben.")
            if not isinstance(payload, dict) or not set(payload).issubset(allowed_fields):
                raise KorApiError("Die KOR-NEXUS-Schreibdaten enthalten nicht freigegebene Felder.")
        elif method == "PATCH":
            route = urllib.parse.urlsplit(path).path
            if re.fullmatch(r"/api/tasks/[1-9][0-9]*", route):
                allowed_fields = {"title", "area", "done", "due_at", "priority", "estimated_minutes", "actual_minutes", "blocked_reason"}
            elif re.fullmatch(r"/api/records/[1-9][0-9]*", route):
                allowed_fields = {"module", "title", "body", "region", "tags"}
            else:
                raise KorApiError("Dieser schreibende KOR-NEXUS-Endpunkt ist nicht freigegeben.")
            if not isinstance(payload, dict) or not payload or not set(payload).issubset(allowed_fields):
                raise KorApiError("Die KOR-NEXUS-Schreibdaten enthalten nicht freigegebene Felder oder sind leer.")
        else:
            raise KorApiError("Diese HTTP-Methode ist für die Integration nicht freigegeben.")
        data = None
        headers = {"Accept": "application/json", "User-Agent": "KOR-NEXUS-Hermes-MCP/0.1"}
        if payload is not None:
            if not isinstance(payload, dict):
                raise KorApiError("API-Eingaben müssen JSON-Objekte sein.")
            try:
                data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise KorApiError("Die API-Eingabe enthält ungültige JSON-Daten.") from exc
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)

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

    @staticmethod
    def _text(value: object, field: str, maximum: int, *, required: bool = False) -> str:
        if not isinstance(value, str):
            raise KorApiError(f"{field} muss Text sein.")
        value = value.strip()
        if required and not value:
            raise KorApiError(f"{field} darf nicht leer sein.")
        if len(value) > maximum:
            raise KorApiError(f"{field} überschreitet {maximum} Zeichen.")
        return value

    @staticmethod
    def _integer(value: object, field: str, minimum: int, maximum: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise KorApiError(f"{field} muss eine Ganzzahl zwischen {minimum} und {maximum} sein.")
        return value

    @staticmethod
    def _record_module(module: str) -> str:
        if module not in {"atlas", "projects", "archive", "simulation", "database"}:
            raise KorApiError("Unbekanntes KOR-NEXUS-Modul.")
        return module

    @classmethod
    def _tags(cls, tags: list[str] | None) -> list[str]:
        if tags is None:
            return []
        if not isinstance(tags, list) or len(tags) > 50:
            raise KorApiError("Tags müssen eine Liste mit höchstens 50 Einträgen sein.")
        return [cls._text(tag, "Tag", 60) for tag in tags]

    def create_task(
        self, title: str, area: str = "SYSTEM", due_at: str | None = None,
        priority: int = 3, estimated_minutes: int | None = None, blocked_reason: str = "",
    ) -> dict:
        payload = {
            "title": self._text(title, "Aufgabentitel", 180, required=True),
            "area": self._text(area, "Aufgabenbereich", 80) or "SYSTEM",
            "priority": self._integer(priority, "Priorität", 1, 5),
            "blocked_reason": self._text(blocked_reason, "Blockierungsgrund", 1000),
        }
        if due_at is not None:
            payload["due_at"] = self._text(due_at, "Fälligkeitsdatum", 100, required=True)
        if estimated_minutes is not None:
            payload["estimated_minutes"] = self._integer(estimated_minutes, "Geschätzte Minuten", 0, 10_000_000)
        return self.request("POST", "/api/tasks", payload)

    def update_task(
        self, task_id: int, title: str | None = None, area: str | None = None,
        done: bool | None = None, due_at: str | None = None, clear_due_date: bool = False,
        priority: int | None = None, estimated_minutes: int | None = None,
        actual_minutes: int | None = None, blocked_reason: str | None = None,
    ) -> dict:
        ident = self._integer(task_id, "Aufgaben-ID", 1, 2_147_483_647)
        if due_at is not None and clear_due_date:
            raise KorApiError("Fälligkeitsdatum setzen und löschen sind gegenseitig ausgeschlossen.")
        payload = {}
        if title is not None:
            payload["title"] = self._text(title, "Aufgabentitel", 180, required=True)
        if area is not None:
            payload["area"] = self._text(area, "Aufgabenbereich", 80)
        if done is not None:
            if not isinstance(done, bool):
                raise KorApiError("done muss true oder false sein.")
            payload["done"] = done
        if due_at is not None:
            payload["due_at"] = self._text(due_at, "Fälligkeitsdatum", 100, required=True)
        elif clear_due_date:
            payload["due_at"] = None
        if priority is not None:
            payload["priority"] = self._integer(priority, "Priorität", 1, 5)
        if estimated_minutes is not None:
            payload["estimated_minutes"] = self._integer(estimated_minutes, "Geschätzte Minuten", 0, 10_000_000)
        if actual_minutes is not None:
            payload["actual_minutes"] = self._integer(actual_minutes, "Tatsächliche Minuten", 0, 10_000_000)
        if blocked_reason is not None:
            payload["blocked_reason"] = self._text(blocked_reason, "Blockierungsgrund", 1000)
        if not payload:
            raise KorApiError("Mindestens ein Aufgabenfeld muss geändert werden.")
        return self.request("PATCH", f"/api/tasks/{ident}", payload)

    def create_record(
        self, module: str, title: str, body: str = "", region: str = "",
        tags: list[str] | None = None,
    ) -> dict:
        payload = {
            "module": self._record_module(module),
            "title": self._text(title, "Eintragstitel", 180, required=True),
            "body": self._text(body, "Eintragsinhalt", 100_000),
            "region": self._text(region, "Region", 180),
            "tags": self._tags(tags),
        }
        return self.request("POST", "/api/records", payload)

    def update_record(
        self, record_id: int, module: str | None = None, title: str | None = None,
        body: str | None = None, region: str | None = None, tags: list[str] | None = None,
        update_tags: bool = False,
    ) -> dict:
        ident = self._integer(record_id, "Datensatz-ID", 1, 2_147_483_647)
        payload = {}
        if module is not None:
            payload["module"] = self._record_module(module)
        if title is not None:
            payload["title"] = self._text(title, "Eintragstitel", 180, required=True)
        if body is not None:
            payload["body"] = self._text(body, "Eintragsinhalt", 100_000)
        if region is not None:
            payload["region"] = self._text(region, "Region", 180)
        if update_tags:
            payload["tags"] = self._tags(tags)
        elif tags is not None:
            payload["tags"] = self._tags(tags)
        if not payload:
            raise KorApiError("Mindestens ein Datensatzfeld muss geändert werden.")
        return self.request("PATCH", f"/api/records/{ident}", payload)

    def get_status(self) -> dict:
        return self.request("GET", "/api/engine/status")

    def list_tasks(self) -> list[dict]:
        return self.request("GET", "/api/tasks").get("items", [])

    def list_records(self, module: str) -> list[dict]:
        module = self._record_module(module)
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
