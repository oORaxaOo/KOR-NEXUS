"""Privacy-preserving UDP broadcast discovery for KOR-NEXUS peers."""
from __future__ import annotations

import socket
import threading
import time

PORT = 8766
BEACON = b"KOR_NEXUS_BEACON_ACTIVE"
PEER_TTL_SECONDS = 30
_lock = threading.RLock()
_peers: dict[str, float] = {}
_logs: list[dict[str, str]] = []
_enabled = False
_stop = threading.Event()


def log(level: str, component: str, message: str) -> None:
    item = {"time": time.strftime("%H:%M:%S"), "level": str(level)[:20],
            "component": str(component)[:40], "message": str(message)[:300]}
    with _lock:
        _logs.append(item)
        del _logs[:-50]


def status() -> dict:
    now = time.time()
    with _lock:
        # Expire peers during reads as well as on incoming traffic, so the HUD
        # cannot display stale nodes when the network becomes quiet.
        for ip, seen in list(_peers.items()):
            if now - seen > PEER_TTL_SECONDS:
                del _peers[ip]
                _logs.append({"time": time.strftime("%H:%M:%S"), "level": "WARN",
                              "component": "MESH", "message": f"Verbindung zu KOR-Einheit unterbrochen: {ip}"})
        del _logs[:-50]
        return {"enabled": _enabled, "port": PORT,
                "connected_peers": sorted(_peers)}


def logs() -> list[dict[str, str]]:
    with _lock:
        return list(_logs)


def _local_ipv4_addresses() -> set[str]:
    addresses = {"127.0.0.1"}
    try:
        addresses.update(info[4][0] for info in socket.getaddrinfo(
            socket.gethostname(), None, socket.AF_INET, socket.SOCK_DGRAM
        ) if info[4] and info[4][0])
    except OSError:
        pass
    # Determine the outbound interface address without sending a packet.
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        addresses.add(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()
    return addresses


def _listen() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", PORT))
        sock.settimeout(1)
        log("INFO", "MESH", f"UDP-Horchposten auf Port {PORT} initialisiert.")
        while not _stop.is_set():
            try:
                data, addr = sock.recvfrom(256)
            except socket.timeout:
                continue
            except OSError as exc:
                if not _stop.is_set():
                    log("ERROR", "MESH", f"Fehler im Empfangskanal: {exc}")
                break
            if data.strip() != BEACON:
                continue
            ip = addr[0]
            if ip in _local_ipv4_addresses():
                continue
            now = time.time()
            with _lock:
                is_new = ip not in _peers
                _peers[ip] = now
            if is_new:
                log("READY", "MESH", f"Neue KOR-Kommandozentrale im LAN erkannt: {ip}")
    except OSError as exc:
        log("WARN", "MESH", f"UDP-Empfang nicht verfügbar (Port {PORT}): {exc}")
    finally:
        sock.close()


def _broadcast() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        log("INFO", "MESH", "LAN-Beacons werden alle 10 Sekunden gesendet.")
        while not _stop.wait(10):
            try:
                sock.sendto(BEACON, ("255.255.255.255", PORT))
            except OSError as exc:
                log("WARN", "MESH", f"UDP-Senden nicht verfügbar: {exc}")
    finally:
        sock.close()


def start() -> None:
    global _enabled
    with _lock:
        if _enabled:
            return
        _enabled = True
        _stop.clear()
    log("INFO", "MESH", "LAN-Erkennung aktiviert; Beacons enthalten keine persönlichen Daten.")
    threading.Thread(target=_listen, name="kor-mesh-listen", daemon=True).start()
    threading.Thread(target=_broadcast, name="kor-mesh-broadcast", daemon=True).start()


def stop() -> None:
    global _enabled
    _stop.set()
    with _lock:
        _enabled = False
        _peers.clear()
    log("INFO", "MESH", "LAN-Erkennung deaktiviert.")
