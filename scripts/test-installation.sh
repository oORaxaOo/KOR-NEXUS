#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
SERVER_PID=''
CONFLICT_PID=''
cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; fi
  if [[ -n "$CONFLICT_PID" ]] && kill -0 "$CONFLICT_PID" 2>/dev/null; then kill -9 "$CONFLICT_PID" 2>/dev/null || true; fi
  rm -rf "$TMP"
}
trap cleanup EXIT
export HOME="$TMP/home with spaces"
export XDG_DATA_HOME="$HOME/custom data"
export XDG_STATE_HOME="$HOME/custom state"
mkdir -p "$HOME" "$XDG_DATA_HOME/kor-workstation/backups" "$XDG_DATA_HOME/kor-workstation/geodata"
printf 'keep-backup' > "$XDG_DATA_HOME/kor-workstation/backups/keep.sqlite3"
printf 'keep-geo' > "$XDG_DATA_HOME/kor-workstation/geodata/keep.geojson"
"$ROOT/install-user.sh"
BIN="$HOME/.local/bin/kor-workstation"
STOP="$HOME/.local/bin/kor-workstation-stop"
DESKTOP="$XDG_DATA_HOME/applications/kor-workstation.desktop"
[[ -x "$BIN" && -x "$STOP" && -s "$DESKTOP" ]]
grep -F 'Exec="' "$DESKTOP" >/dev/null
# Occupy the preferred port when possible, to exercise the automatic fallback.
cat > "$TMP/hold-port.py" <<'PYPORT'
import socket,sys
from pathlib import Path
p=Path(sys.argv[1]); stop=Path(sys.argv[2]); s=socket.socket()
try:
    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',8765));s.listen(8);p.write_text('READY')
except OSError as e:
    p.write_text('SKIP:'+str(e));raise SystemExit(0)
s.settimeout(.25)
while not stop.exists():
    try:
        c,_=s.accept();c.close()
    except socket.timeout: continue
    except Exception: break
PYPORT
python3 -u "$TMP/hold-port.py" "$TMP/port-status" "$TMP/stop-port" >/dev/null 2>&1 &
CONFLICT_PID=$!
disown "$CONFLICT_PID" 2>/dev/null || true
for _ in {1..30}; do [[ -s "$TMP/port-status" ]] && break; sleep .1; done
PORT_STATUS="$(cat "$TMP/port-status" 2>/dev/null || echo SKIP)"
# Launch a real isolated server without invoking any browser.
KOR_NO_BROWSER=1 "$BIN" & SERVER_PID=$!
for _ in {1..80}; do
  [[ -s "$XDG_DATA_HOME/kor-workstation/runtime.json" ]] && break
  sleep 0.1
done
[[ -s "$XDG_DATA_HOME/kor-workstation/runtime.json" ]]
if [[ "$PORT_STATUS" == READY ]]; then
  python3 - "$XDG_DATA_HOME/kor-workstation/runtime.json" <<'PYPORTCHECK'
import json,sys
port=json.load(open(sys.argv[1]))['port'];assert int(port)!=8765, f'port conflict was not avoided: {port}'
PYPORTCHECK
  printf 'PASS: Port 8765 belegt; KOR-NEXUS verwendet einen freien Loopback-Port.\n'
else
  printf 'SKIP: Port 8765 konnte nicht kontrolliert reserviert werden (%s).\n' "$PORT_STATUS"
fi
python3 - "$XDG_DATA_HOME/kor-workstation/runtime.json" <<'PY'
import json,sys,time,urllib.request
from pathlib import Path
runtime=Path(sys.argv[1]); info=json.loads(runtime.read_text()); url=f"http://127.0.0.1:{int(info['port'])}/api/health"
for _ in range(40):
    try:
        with urllib.request.urlopen(url,timeout=.5) as r:
            data=json.load(r)
        assert data.get('app')=='KOR-NEXUS' and data.get('version')=='1.20.0',data
        break
    except Exception: time.sleep(.1)
else: raise SystemExit('installed server did not become healthy')
PY
# Reinstall while the server is live to verify safe upgrade/stop-before-replace.
"$ROOT/install-user.sh"
for _ in {1..30}; do kill -0 "$SERVER_PID" 2>/dev/null || break; sleep 0.1; done
if kill -0 "$SERVER_PID" 2>/dev/null; then kill "$SERVER_PID" 2>/dev/null || true; fi
wait "$SERVER_PID" 2>/dev/null || true
SERVER_PID=''
[[ ! -s "$XDG_DATA_HOME/kor-workstation/runtime.json" ]]
KOR_NO_BROWSER=1 "$BIN" & SERVER_PID=$!
for _ in {1..80}; do [[ -s "$XDG_DATA_HOME/kor-workstation/runtime.json" ]] && break; sleep 0.1; done
[[ -s "$XDG_DATA_HOME/kor-workstation/runtime.json" ]]
# Concurrent launcher call must reuse the existing instance, not spawn another server.
BEFORE_PORT="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["port"]' "$XDG_DATA_HOME/kor-workstation/runtime.json")"
"$BIN" > "$TMP/second-start.log" 2>&1
grep -E 'wird bereits gestartet|läuft bereits' "$XDG_STATE_HOME/kor-workstation/server.log" >/dev/null
AFTER_PORT="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["port"]' "$XDG_DATA_HOME/kor-workstation/runtime.json")"
[[ "$BEFORE_PORT" == "$AFTER_PORT" ]]
kill -0 "$SERVER_PID"
"$STOP"
for _ in {1..80}; do [[ ! -s "$XDG_DATA_HOME/kor-workstation/runtime.json" ]] && break; sleep 0.1; done
[[ ! -s "$XDG_DATA_HOME/kor-workstation/runtime.json" ]]
for _ in {1..30}; do kill -0 "$SERVER_PID" 2>/dev/null || break; sleep 0.1; done
if kill -0 "$SERVER_PID" 2>/dev/null; then kill "$SERVER_PID" 2>/dev/null || true; fi
for _ in {1..30}; do kill -0 "$SERVER_PID" 2>/dev/null || break; sleep 0.1; done
if kill -0 "$SERVER_PID" 2>/dev/null; then kill "$SERVER_PID" 2>/dev/null || true; fi
wait "$SERVER_PID" 2>/dev/null || true
SERVER_PID=''
# Mark the real application database after shutdown, then prove uninstall keeps it.
python3 - "$XDG_DATA_HOME/kor-workstation/kor-workstation.sqlite3" <<'PYDB'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);c.execute('CREATE TABLE IF NOT EXISTS preserved(value TEXT)');c.execute('DELETE FROM preserved');c.execute('INSERT INTO preserved VALUES(?)',('keep-db',));c.commit();c.close()
PYDB
# Uninstall removes app code and launch integration but never user data.
"$ROOT/uninstall-user.sh"
[[ ! -e "$XDG_DATA_HOME/kor-workstation-app" ]]
python3 - "$XDG_DATA_HOME/kor-workstation/kor-workstation.sqlite3" <<'PYDBCHECK'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);assert c.execute('SELECT value FROM preserved').fetchone()[0]=='keep-db';c.close()
PYDBCHECK
[[ -f "$XDG_DATA_HOME/kor-workstation/backups/keep.sqlite3" ]]
[[ -f "$XDG_DATA_HOME/kor-workstation/geodata/keep.geojson" ]]
printf 'OK  isolierte Benutzerinstallation, Pfade mit Leerzeichen, sicheres Upgrade, Doppelstart-Sperre, Stop und datenerhaltende Deinstallation\n'
