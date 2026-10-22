"""Opt-in LAN discovery; UDP beacons contain no user data."""
import socket, threading, time
PORT=8766
BEACON=b"KOR_NEXUS_BEACON_ACTIVE"
_lock=threading.RLock(); _peers={}; _logs=[]; _enabled=False; _stop=threading.Event()
def log(level,component,message):
    item={"time":time.strftime("%H:%M:%S"),"level":level,"component":component,"message":str(message)[:300]}
    with _lock: _logs.append(item); del _logs[:-50]
def status():
    now=time.time()
    with _lock: return {"enabled":_enabled,"port":PORT,"connected_peers":sorted(ip for ip,seen in _peers.items() if now-seen<=35)}
def logs():
    with _lock: return list(_logs)
def _listen():
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    try:
        sock.bind(("",PORT)); sock.settimeout(1)
        log("INFO","MESH","UDP-Empfang auf Port %s aktiv."%PORT)
        while not _stop.is_set():
            try: data,addr=sock.recvfrom(256)
            except socket.timeout: continue
            if data!=BEACON or addr[0]=="127.0.0.1": continue
            with _lock: new=addr[0] not in _peers; _peers[addr[0]]=time.time()
            if new: log("READY","MESH","KOR-NEXUS erkannt: "+addr[0])
            now=time.time()
            with _lock:
                for ip,seen in list(_peers.items()):
                    if now-seen>35: del _peers[ip]
    except OSError as exc: log("WARN","MESH","UDP-Empfang nicht verfügbar: "+str(exc))
    finally: sock.close()
def _broadcast():
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
    try:
        while not _stop.wait(10):
            try: sock.sendto(BEACON,("255.255.255.255",PORT))
            except OSError as exc: log("WARN","MESH","UDP-Senden nicht verfügbar: "+str(exc))
    finally: sock.close()
def start():
    global _enabled
    with _lock:
        if _enabled: return
        _enabled=True; _stop.clear()
    log("INFO","MESH","LAN-Erkennung aktiviert; keine persönlichen Daten werden gesendet.")
    threading.Thread(target=_listen,name="kor-mesh-listen",daemon=True).start()
    threading.Thread(target=_broadcast,name="kor-mesh-broadcast",daemon=True).start()
def stop():
    global _enabled
    _stop.set()
    with _lock: _enabled=False; _peers.clear()
    log("INFO","MESH","LAN-Erkennung deaktiviert.")
