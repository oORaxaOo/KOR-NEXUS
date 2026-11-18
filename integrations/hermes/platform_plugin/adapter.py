"""KOR-NEXUS local HUD platform adapter for Hermes Agent."""
from __future__ import annotations

import asyncio
import contextlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import threading
import uuid
from collections import defaultdict, deque
from concurrent.futures import Future, TimeoutError as FutureTimeout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult
from gateway.platforms.event import MessageEvent, MessageType, ProcessingOutcome

logger = logging.getLogger(__name__)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876
MAX_BODY_BYTES = 64 * 1024
MAX_MESSAGE_CHARS = 12_000
MAX_PENDING_REQUESTS = 8
DEFAULT_REPLY_TIMEOUT = 240.0
_SESSION_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


def _loopback_peer(value: str) -> bool:
    try:
        return ipaddress.ip_address(value.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _config_path() -> Path:
    override = os.environ.get("KOR_NEXUS_HERMES_CONFIG", "").strip()
    if override:
        return Path(override).expanduser()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser()
    return config_home / "kor-nexus" / "hermes-bridge.json"


def _write_runtime_config(token: str, port: int) -> None:
    target = _config_path()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with contextlib.suppress(OSError):
        target.parent.chmod(0o700)
    if target.is_symlink():
        raise RuntimeError("Refusing to write the Hermes bridge configuration through a symlink.")
    payload = json.dumps({"version": 1, "host": DEFAULT_HOST, "port": port, "token": token}, separators=(",", ":"))
    temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
        with contextlib.suppress(OSError):
            target.chmod(0o600)
    finally:
        with contextlib.suppress(OSError):
            temp.unlink()


def _remove_runtime_config(token: str) -> None:
    target = _config_path()
    try:
        if target.is_symlink() or not target.is_file() or target.stat().st_size > 4096:
            return
        value = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(value, dict) and hmac.compare_digest(str(value.get("token", "")), token):
            target.unlink(missing_ok=True)
    except (OSError, UnicodeError, ValueError, TypeError):
        return


class _HTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _RequestHandler(BaseHTTPRequestHandler):
    @property
    def adapter(self):
        return self.server.adapter

    def log_message(self, fmt, *args):
        logger.debug("[kor_nexus] bridge HTTP: " + fmt, *args)

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not _loopback_peer(self.client_address[0]):
            return False
        host = (self.headers.get("Host") or "").split(":", 1)[0].strip("[]").lower()
        if host not in {"127.0.0.1", "localhost", "::1"}:
            return False
        origin = self.headers.get("Origin")
        if origin:
            parsed = urlsplit(origin)
            if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
                return False
        supplied = self.headers.get("X-KOR-Bridge-Token", "")
        return bool(supplied) and hmac.compare_digest(
            supplied.encode("utf-8"), self.adapter._bridge_token.encode("utf-8")
        )

    def do_GET(self):
        if self.path != "/health":
            return self._json(404, {"ok": False, "error": "not found"})
        if not self._authorized():
            return self._json(403, {"ok": False, "error": "forbidden"})
        return self._json(200, {"ok": True, "platform": "kor_nexus", "version": 1})

    def do_POST(self):
        if self.path != "/message":
            return self._json(404, {"ok": False, "error": "not found"})
        if not self._authorized():
            return self._json(403, {"ok": False, "error": "forbidden"})
        if not self.adapter._request_slots.acquire(blocking=False):
            return self._json(429, {"ok": False, "error": "too many concurrent requests"})
        try:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._json(400, {"ok": False, "error": "invalid Content-Length"})
            if length < 1 or length > MAX_BODY_BYTES:
                return self._json(413, {"ok": False, "error": "request body too large"})
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeError, ValueError):
                return self._json(400, {"ok": False, "error": "invalid JSON"})
            if not isinstance(payload, dict):
                return self._json(400, {"ok": False, "error": "JSON object required"})
            message, session_id = payload.get("message"), payload.get("session_id")
            if not isinstance(message, str) or not message.strip() or len(message) > MAX_MESSAGE_CHARS:
                return self._json(400, {"ok": False, "error": "message must contain 1–12000 characters"})
            if not isinstance(session_id, str) or not _SESSION_RE.fullmatch(session_id):
                return self._json(400, {"ok": False, "error": "invalid session_id"})
            try:
                response = self.adapter.submit_message(session_id, message.strip())
            except TimeoutError:
                return self._json(504, {"ok": False, "error": "Lilith did not reply before timeout"})
            except RuntimeError:
                logger.exception("[kor_nexus] message dispatch failed")
                return self._json(503, {"ok": False, "error": "Lilith is not accepting messages"})
            return self._json(200, {"ok": True, "response": response})
        finally:
            self.adapter._request_slots.release()


class KORNexusAdapter(BasePlatformAdapter):
    """A single Hermes Gateway adapter for the embedded KOR-NEXUS HUD."""
    interactive_resume = True

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform("kor_nexus"))
        extra = getattr(config, "extra", {}) or {}
        try:
            requested_port = int(extra.get("port", os.environ.get("KOR_NEXUS_PANEL_PORT", DEFAULT_PORT)))
        except (TypeError, ValueError):
            requested_port = DEFAULT_PORT
        self._port = requested_port if 0 <= requested_port <= 65535 else DEFAULT_PORT
        self._bridge_token = secrets.token_urlsafe(48)
        self._httpd = None
        self._thread = None
        self._loop = None
        self._pending: dict[str, Future] = {}
        self._pending_order: dict[str, deque[str]] = defaultdict(deque)
        self._pending_lock = threading.Lock()
        self._request_slots = threading.BoundedSemaphore(MAX_PENDING_REQUESTS)

    @property
    def name(self) -> str:
        return "KOR-NEXUS"

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        self._loop = asyncio.get_running_loop()
        try:
            self._httpd = _HTTPServer((DEFAULT_HOST, self._port), _RequestHandler)
        except OSError as exc:
            if self._port == 0:
                self._set_fatal_error("bind_failed", f"KOR-NEXUS bridge could not bind: {exc}", retryable=True)
                return False
            logger.warning("[kor_nexus] configured port %d is unavailable; falling back to an OS-assigned loopback port: %s", self._port, exc)
            try:
                self._httpd = _HTTPServer((DEFAULT_HOST, 0), _RequestHandler)
            except OSError as fallback_exc:
                self._set_fatal_error("bind_failed", f"KOR-NEXUS bridge could not bind: {fallback_exc}", retryable=True)
                return False
        self._httpd.adapter = self
        bound_port = int(self._httpd.server_address[1])
        try:
            _write_runtime_config(self._bridge_token, bound_port)
        except Exception:
            self._httpd.server_close()
            self._httpd = None
            logger.exception("[kor_nexus] could not publish owner-only bridge configuration")
            self._set_fatal_error("config_write_failed", "Could not publish local bridge configuration", retryable=False)
            return False
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="kor-nexus-bridge", daemon=True)
        self._thread.start()
        self._mark_connected(listener_base=f"http://{DEFAULT_HOST}:{bound_port}")
        logger.info("[kor_nexus] Local HUD bridge listening on %s:%d", DEFAULT_HOST, bound_port)
        return True

    async def disconnect(self) -> None:
        self._mark_disconnected()
        httpd, self._httpd = self._httpd, None
        if httpd is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(httpd.shutdown)
                httpd.server_close()
        thread, self._thread = self._thread, None
        if thread is not None:
            await asyncio.to_thread(thread.join, 2.0)
        with self._pending_lock:
            pending = list(self._pending.values())
            self._pending.clear()
            self._pending_order.clear()
        for future in pending:
            if not future.done():
                future.set_exception(RuntimeError("Hermes gateway is shutting down"))
        _remove_runtime_config(self._bridge_token)
        self._loop = None

    def _cleanup_pending(self, message_id: str, chat_id: str) -> None:
        with self._pending_lock:
            self._pending.pop(message_id, None)
            queue = self._pending_order.get(chat_id)
            if queue is not None:
                with contextlib.suppress(ValueError):
                    queue.remove(message_id)
                if not queue:
                    self._pending_order.pop(chat_id, None)

    def _resolve_message(self, message_id: str, response: str) -> bool:
        with self._pending_lock:
            future = self._pending.get(message_id)
            if future is None or future.done():
                return False
            future.set_result(response)
            return True

    def _resolve_oldest_for_chat(self, chat_id: str, response: str) -> bool:
        with self._pending_lock:
            queue = self._pending_order.get(chat_id, ())
            for message_id in queue:
                future = self._pending.get(message_id)
                if future is not None and not future.done():
                    future.set_result(response)
                    return True
            return False

    async def _dispatch(self, event: MessageEvent) -> None:
        # Hermes handle_message is async; await it so admission completes before we
        # block the HTTP worker waiting for the correlated final reply.
        await self.handle_message(event)

    def submit_message(self, session_id: str, text: str) -> str:
        if self._loop is None or not self._running:
            raise RuntimeError("Gateway adapter is not connected")
        chat_id = "hud-" + session_id
        message_id = uuid.uuid4().hex
        future: Future = Future()
        with self._pending_lock:
            self._pending[message_id] = future
            self._pending_order[chat_id].append(message_id)
        source = self.build_source(
            chat_id=chat_id,
            chat_name="KOR-NEXUS HUD",
            chat_type="dm",
            user_id="local-owner",
            user_name="KOR-NEXUS",
            message_id=message_id,
        )
        event = MessageEvent(
            text=text,
            message_type=MessageType.TEXT,
            user_id="local-owner",
            user_name="KOR-NEXUS",
            source=source,
            message_id=message_id,
            metadata={"kor_nexus_hud": True},
        )
        try:
            asyncio.run_coroutine_threadsafe(self._dispatch(event), self._loop).result(timeout=10)
            if not event._gateway_accepted:
                raise RuntimeError("Gateway did not accept the HUD message")
            response = future.result(timeout=DEFAULT_REPLY_TIMEOUT)
            if not isinstance(response, str):
                raise RuntimeError("Gateway returned an invalid response")
            return response
        except FutureTimeout as exc:
            raise TimeoutError("Gateway reply timed out") from exc
        finally:
            self._cleanup_pending(message_id, chat_id)

    async def send(self, chat_id: str, content: str, reply_to: str | None = None,
                   metadata: dict[str, Any] | None = None) -> SendResult:
        if (metadata or {}).get("notify"):
            self._resolve_oldest_for_chat(str(chat_id), content or "")
        return SendResult(success=True, message_id=str(uuid.uuid4()))

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        return None

    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        return {"name": "KOR-NEXUS HUD", "type": "dm"}

    async def on_processing_complete(self, event: MessageEvent, outcome: ProcessingOutcome) -> None:
        message_id = str(getattr(event, "message_id", "") or "")
        if not message_id:
            return
        if outcome is ProcessingOutcome.FAILURE:
            self._resolve_message(message_id, "Lilith konnte die Anfrage nicht abschließen. Bitte Gateway-Protokoll prüfen.")
        elif outcome is ProcessingOutcome.CANCELLED:
            self._resolve_message(message_id, "Die Anfrage wurde abgebrochen.")
        elif outcome is ProcessingOutcome.SUCCESS:
            streamed = getattr(event, "_streamed_final_response", "")
            if isinstance(streamed, str) and streamed:
                self._resolve_message(message_id, streamed)
            else:
                self._resolve_message(message_id, "Lilith hat keine Textantwort ausgegeben.")


def check_requirements() -> bool:
    # The adapter uses only the Python standard library and Hermes' own Gateway APIs.
    return True


def validate_config(config) -> bool:
    return bool(getattr(config, "enabled", False))


def register(ctx):
    """Entry point called by Hermes' plugin manager."""
    ctx.register_platform(
        name="kor_nexus",
        label="KOR-NEXUS",
        adapter_factory=KORNexusAdapter,
        check_fn=check_requirements,
        validate_config=validate_config,
        required_env=[],
        max_message_length=MAX_MESSAGE_CHARS,
        allowed_users_env="KOR_NEXUS_ALLOWED_USERS",
        platform_hint="You are replying inside the private local KOR-NEXUS command workspace. Use the KOR-NEXUS tools when structured project or task data is needed.",
        emoji="🧠",
    )
