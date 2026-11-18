"""Authenticated local client for the Hermes KOR-NEXUS platform adapter."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import urllib.error
import urllib.request
import re

MAX_MESSAGE_CHARS = 12_000
MAX_RESPONSE_BYTES = 512 * 1024
DEFAULT_TIMEOUT = 240.0
_SESSION_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


class HermesBridgeError(RuntimeError):
    """Safe error surfaced to the local KOR-NEXUS UI."""


def bridge_config_path() -> Path:
    raw = os.environ.get("KOR_NEXUS_HERMES_CONFIG", "").strip()
    if raw:
        return Path(raw).expanduser()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser()
    return config_home / "kor-nexus" / "hermes-bridge.json"


def _load_config() -> dict:
    path = bridge_config_path()
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
            raise HermesBridgeError("Hermes ist nicht mit KOR-NEXUS verbunden.")
        value = json.loads(path.read_text(encoding="utf-8"))
    except HermesBridgeError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError):
        raise HermesBridgeError("Die lokale Hermes-Verbindung ist nicht verfügbar.") from None
    if not isinstance(value, dict):
        raise HermesBridgeError("Die lokale Hermes-Verbindung ist ungültig.")
    host, token, port = value.get("host"), value.get("token"), value.get("port")
    if host != "127.0.0.1":
        raise HermesBridgeError("Die Hermes-Verbindung ist nicht auf Loopback beschränkt.")
    if not isinstance(token, str) or len(token) < 32 or len(token) > 256:
        raise HermesBridgeError("Das lokale Hermes-Verbindungstoken ist ungültig.")
    if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise HermesBridgeError("Der lokale Hermes-Port ist ungültig.")
    return {"host": host, "port": port, "token": token}


def _request(path: str, *, method: str = "GET", payload: dict | None = None, timeout: float = 5.0) -> dict:
    if path not in {"/health", "/message"}:
        raise HermesBridgeError("Ungültiger Hermes-Endpunkt.")
    cfg = _load_config()
    data = None
    headers = {
        "Accept": "application/json",
        "X-KOR-Bridge-Token": cfg["token"],
        "User-Agent": "KOR-NEXUS-Hermes-Bridge/0.1",
        "Connection": "close",
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(
        f"http://{cfg['host']}:{cfg['port']}{path}",
        data=data,
        headers=headers,
        method=method,
    )

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, file_pointer, code, message, response_headers, new_url):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(req, timeout=max(1.0, min(float(timeout), DEFAULT_TIMEOUT))) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise HermesBridgeError("Die Hermes-Antwort überschreitet das erlaubte Größenlimit.")
    except HermesBridgeError:
        raise
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise HermesBridgeError("Hermes hat die lokale Anfrage abgelehnt.") from None
        if exc.code == 429:
            raise HermesBridgeError("Hermes ist ausgelastet. Bitte später erneut versuchen.") from None
        if exc.code == 503:
            raise HermesBridgeError("Lilith ist momentan nicht verfügbar.") from None
        if exc.code == 504:
            raise HermesBridgeError("Lilith hat innerhalb des Zeitlimits nicht geantwortet.") from None
        raise HermesBridgeError(f"Die Hermes-Verbindung ist fehlgeschlagen (HTTP {exc.code}).") from None
    except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError):
        raise HermesBridgeError("Das Hermes-Gateway ist lokal nicht erreichbar.") from None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise HermesBridgeError("Hermes hat keine gültige Antwort geliefert.") from None
    if not isinstance(value, dict):
        raise HermesBridgeError("Hermes hat ein unerwartetes Antwortformat geliefert.")
    if value.get("ok") is False:
        error = value.get("error")
        raise HermesBridgeError(str(error)[:300] if isinstance(error, str) else "Hermes-Anfrage fehlgeschlagen.")
    return value


def bridge_status() -> dict:
    """Return availability without exposing the token or local port."""
    try:
        result = _request("/health", timeout=2)
        return {
            "available": bool(result.get("ok")),
            "platform": "kor_nexus",
            "agent": "Lilith",
            "detail": "Hermes-Gateway verbunden." if result.get("ok") else "Hermes meldet keinen aktiven Zustand.",
        }
    except HermesBridgeError as exc:
        return {"available": False, "platform": "kor_nexus", "agent": "Lilith", "detail": str(exc)}


def send_to_hermes(message: str, session_id: str) -> str:
    """Send one HUD turn and wait for its correlated final reply."""
    if not isinstance(message, str) or not message.strip() or len(message) > MAX_MESSAGE_CHARS:
        raise HermesBridgeError(f"Die Nachricht muss zwischen 1 und {MAX_MESSAGE_CHARS} Zeichen enthalten.")
    if not isinstance(session_id, str) or not _SESSION_RE.fullmatch(session_id):
        raise HermesBridgeError("Die Chat-Sitzung ist ungültig.")
    result = _request(
        "/message",
        method="POST",
        payload={"message": message.strip(), "session_id": session_id},
        timeout=DEFAULT_TIMEOUT,
    )
    response = result.get("response")
    if not isinstance(response, str):
        raise HermesBridgeError("Lilith hat keine lesbare Textantwort zurückgegeben.")
    return response
