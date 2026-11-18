"""Loopback-only Hermes platform adapter for the KOR-NEXUS local chat surface.

The adapter deliberately uses only the Python standard library for HTTP polling.
Network I/O is moved to a worker thread so a local KOR-NEXUS timeout never blocks
the Hermes gateway event loop.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from gateway.config import Platform, PlatformConfig
from gateway.platforms._shared import extra_or_secret, get_scoped_secret, seed_extra_from_env
from gateway.platforms.base import BasePlatformAdapter, SendResult
from gateway.platforms.event import MessageEvent, MessageType

logger = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 1024 * 1024
MAX_MESSAGE_CHARS = 20000
POLL_INTERVAL_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 5.0


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects: a loopback bridge must never forward its bearer token elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def _default_data_home() -> Path:
    configured = get_scoped_secret("KOR_NEXUS_DATA_HOME", "").strip()
    if configured:
        return Path(configured).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    root = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return root / "kor-workstation"


def _loopback_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("KOR-NEXUS muss über eine Loopback-HTTP-Adresse erreichbar sein.")
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("KOR-NEXUS URL enthält nicht erlaubte Bestandteile.")
    port = parsed.port or 8765
    if not 1024 <= port <= 65535:
        raise ValueError("KOR-NEXUS Port liegt außerhalb des erlaubten Bereichs.")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return f"http://{host}:{port}"


class KorNexusAdapter(BasePlatformAdapter):
    """Hermes gateway channel backed by the authenticated KOR-NEXUS SQLite queue."""

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform("kor_nexus"))
        extra = config.extra or {}
        self.token = extra_or_secret(extra, "token", "KOR_NEXUS_BRIDGE_TOKEN").strip()
        configured_home = extra_or_secret(extra, "data_home", "KOR_NEXUS_DATA_HOME").strip()
        self.data_home = Path(configured_home).expanduser() if configured_home else _default_data_home()
        configured_url = extra_or_secret(extra, "base_url", "KOR_NEXUS_BRIDGE_URL").strip()
        self.explicit_base_url = _loopback_base_url(configured_url) if configured_url else None
        self._poll_task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        self._last_warning_at = 0.0
        self.max_message_length = 16000

    @property
    def name(self) -> str:
        return "KOR-NEXUS"

    def _base_url(self) -> str:
        if self.explicit_base_url:
            return self.explicit_base_url
        runtime = self.data_home / "runtime.json"
        try:
            info = json.loads(runtime.read_text(encoding="utf-8"))
            port = int(info.get("port", 8765))
            if not 1024 <= port <= 65535:
                raise ValueError("invalid port")
        except (OSError, UnicodeError, ValueError, TypeError, AttributeError):
            port = 8765
        return f"http://127.0.0.1:{port}"

    def _request_json(self, method: str, route: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.token:
            raise RuntimeError("KOR_NEXUS_BRIDGE_TOKEN ist nicht konfiguriert.")
        base = self._base_url()
        url = base + route
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "KOR-NEXUS-Hermes-Platform/0.1",
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
        )
        try:
            with _HTTP.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                if response.geturl() != url:
                    raise RuntimeError("KOR-NEXUS Bridge hat eine unerwartete Weiterleitung versucht.")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                status = response.status
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise RuntimeError("KOR-NEXUS Bridge-Token wurde abgelehnt.") from exc
            raise RuntimeError(f"KOR-NEXUS antwortete mit HTTP {exc.code}.") from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise RuntimeError("KOR-NEXUS ist lokal nicht erreichbar.") from exc
        if not 200 <= status < 300:
            raise RuntimeError(f"KOR-NEXUS antwortete mit HTTP {status}.")
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("KOR-NEXUS Antwort überschreitet das Größenlimit.")
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise RuntimeError("KOR-NEXUS lieferte ungültiges JSON.") from exc
        if not isinstance(result, dict) or result.get("ok") is False:
            raise RuntimeError(
                str(result.get("error", "Ungültige KOR-NEXUS Antwort."))[:300]
                if isinstance(result, dict) else "Ungültige KOR-NEXUS Antwort."
            )
        return result

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        if not self.token:
            logger.error("KOR-NEXUS: bridge token is missing")
            return False
        try:
            await asyncio.to_thread(self._request_json, "GET", "/api/hermes/bridge/status")
        except Exception as exc:
            logger.error("KOR-NEXUS: local bridge check failed: %s", exc)
            return False
        self._stop_event = asyncio.Event()
        self._mark_connected()
        self._poll_task = asyncio.create_task(self._poll_loop(), name="kor-nexus-hermes-poll")
        self._wire_plugin_handlers(None)
        return True

    async def disconnect(self) -> None:
        if self._stop_event:
            self._stop_event.set()
        task = self._poll_task
        self._poll_task = None
        if task and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._stop_event = None
        self._mark_disconnected()

    async def _poll_loop(self) -> None:
        stop = self._stop_event
        if stop is None:
            return
        while not stop.is_set():
            try:
                batch = await asyncio.to_thread(
                    self._request_json, "GET", "/api/hermes/bridge/inbox?limit=10"
                )
                for item in batch.get("items", []):
                    if not isinstance(item, dict):
                        continue
                    message_id = str(item.get("id", "")).strip()
                    conversation_id = str(item.get("conversation_id", "")).strip()
                    content = str(item.get("content", "")).strip()
                    if not message_id or not conversation_id or not content:
                        continue
                    if len(content) > MAX_MESSAGE_CHARS:
                        content = content[:MAX_MESSAGE_CHARS]
                    sender_id = str(item.get("sender_id") or "local-user")
                    sender_name = str(item.get("sender_name") or "Lokaler Nutzer")
                    source = self.build_source(
                        chat_id=conversation_id,
                        chat_name=f"KOR-NEXUS · {conversation_id}",
                        chat_type="dm",
                        user_id=sender_id,
                        user_name=sender_name,
                        message_id=message_id,
                    )
                    event = MessageEvent(
                        text=content,
                        message_type=MessageType.TEXT,
                        user_id=sender_id,
                        user_name=sender_name,
                        source=source,
                        message_id=message_id,
                        timestamp=dt.datetime.now(),
                        metadata={"kor_nexus_message_id": message_id},
                    )
                    await self.handle_message(event)
                    if getattr(event, "_gateway_accepted", False):
                        await asyncio.to_thread(
                            self._request_json,
                            "POST",
                            "/api/hermes/bridge/ack",
                            {"message_ids": [message_id]},
                        )
                    else:
                        logger.warning(
                            "KOR-NEXUS: Hermes gateway has not accepted message %s; it remains queued",
                            message_id,
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                now = asyncio.get_running_loop().time()
                if now - self._last_warning_at > 30:
                    logger.warning("KOR-NEXUS bridge poll failed: %s", exc)
                    self._last_warning_at = now
            try:
                await asyncio.wait_for(stop.wait(), timeout=POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                pass

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        text = str(content or "").strip()
        if not text:
            return SendResult(success=True, message_id=uuid.uuid4().hex)
        try:
            result = await asyncio.to_thread(
                self._request_json,
                "POST",
                "/api/hermes/bridge/replies",
                {"conversation_id": str(chat_id), "content": text[:MAX_MESSAGE_CHARS]},
            )
            return SendResult(success=True, message_id=str(result.get("id") or uuid.uuid4().hex))
        except Exception as exc:
            return SendResult(success=False, error=str(exc), retryable=True)

    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        return {"name": f"KOR-NEXUS · {chat_id}", "type": "dm"}


def check_requirements() -> bool:
    return bool(get_scoped_secret("KOR_NEXUS_BRIDGE_TOKEN", "").strip())


def validate_config(config) -> bool:
    extra = getattr(config, "extra", {}) or {}
    return bool(extra_or_secret(extra, "token", "KOR_NEXUS_BRIDGE_TOKEN").strip())


def _env_enablement() -> dict | None:
    token = get_scoped_secret("KOR_NEXUS_BRIDGE_TOKEN", "").strip()
    if not token:
        return None
    return seed_extra_from_env(
        (
            ("KOR_NEXUS_BRIDGE_TOKEN", "token", None),
            ("KOR_NEXUS_DATA_HOME", "data_home", None),
            ("KOR_NEXUS_BRIDGE_URL", "base_url", None),
        ),
        home_env="KOR_NEXUS_HOME_CHANNEL",
        home_default="main",
    )


def register(ctx):
    """Register KOR-NEXUS as an optional, local-only Hermes gateway platform."""
    ctx.register_platform(
        name="kor_nexus",
        label="KOR-NEXUS",
        adapter_factory=KorNexusAdapter,
        check_fn=check_requirements,
        validate_config=validate_config,
        required_env=["KOR_NEXUS_BRIDGE_TOKEN"],
        env_enablement_fn=_env_enablement,
        cron_deliver_env_var="KOR_NEXUS_HOME_CHANNEL",
        allowed_users_env="KOR_NEXUS_ALLOWED_USERS",
        max_message_length=16000,
        platform_hint=(
            "You are chatting from the user's local KOR-NEXUS command center. "
            "KOR-NEXUS data tools are available through the configured MCP server. "
            "Use them when the user asks about tasks, projects, records, resources, or cached news."
        ),
        emoji="⌘",
    )
