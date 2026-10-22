#!/usr/bin/env bash
# Run only inside a disposable Arch Linux CI container/VM. Installs and removes
# the package in that isolated environment, never on the developer's host.
set -euo pipefail
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo 'This isolated package integration test must run as root inside disposable Arch CI.' >&2
  exit 2
fi
PKG="${1:-}"
[[ -f "$PKG" && -s "$PKG" ]] || { echo 'Usage: scripts/test-built-package-installation.sh PACKAGE' >&2; exit 2; }
command -v pacman >/dev/null
command -v runuser >/dev/null
TMP="$(mktemp -d /tmp/kor-package-test.XXXXXX)"
TEST_USER=korpkgtest
PID=''
cleanup() {
  if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
    runuser -u "$TEST_USER" -- env HOME="$TMP/home" XDG_DATA_HOME="$TMP/data" XDG_STATE_HOME="$TMP/state" /usr/bin/kor-workstation-stop >/dev/null 2>&1 || true
    kill "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
  pacman -Rns --noconfirm kor-workstation >/dev/null 2>&1 || true
  userdel "$TEST_USER" >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT
id "$TEST_USER" >/dev/null 2>&1 && { echo "Unexpected pre-existing test user $TEST_USER" >&2; exit 1; }
useradd --create-home --home-dir "$TMP/home" --shell /bin/bash "$TEST_USER"
mkdir -p "$TMP/home" "$TMP/data/kor-workstation/backups" "$TMP/data/kor-workstation/geodata" "$TMP/state"
chown -R "$TEST_USER:$TEST_USER" "$TMP"
printf 'preserve-backup' > "$TMP/data/kor-workstation/backups/preserve.sqlite3"
printf 'preserve-geo' > "$TMP/data/kor-workstation/geodata/preserve.geojson"
chmod 600 "$TMP/data/kor-workstation/backups/preserve.sqlite3" "$TMP/data/kor-workstation/geodata/preserve.geojson"
pacman -U --noconfirm "$PKG"
# Verify installed paths, executable bits, desktop entry and offline map payload.
for f in /opt/kor-workstation/core/server.py /opt/kor-workstation/core/media.py /opt/kor-workstation/core/github_integration.py /opt/kor-workstation/web/github.html /opt/kor-workstation/web/js/github-center.js /opt/kor-workstation/web/geodata/world.geojson /usr/bin/kor-workstation /usr/bin/kor-workstation-stop /usr/share/applications/kor-workstation.desktop; do
  [[ -e "$f" ]] || { echo "Missing installed path: $f" >&2; exit 1; }
done
[[ -x /usr/bin/kor-workstation && -x /usr/bin/kor-workstation-stop ]]
[[ -s /usr/share/applications/kor-workstation.desktop && -s /opt/kor-workstation/web/geodata/world.geojson ]]
[[ "$(stat -c '%a' /usr/bin/kor-workstation)" == 755 ]]
# Start using a dedicated unprivileged account and isolated XDG paths.
runuser -u "$TEST_USER" -- env HOME="$TMP/home" XDG_DATA_HOME="$TMP/data" XDG_STATE_HOME="$TMP/state" KOR_NO_BROWSER=1 /usr/bin/kor-workstation &
PID=$!
for _ in {1..100}; do
  [[ -s "$TMP/data/kor-workstation/runtime.json" ]] && break
  sleep 0.1
done
[[ -s "$TMP/data/kor-workstation/runtime.json" ]] || { echo 'Runtime file was not created' >&2; exit 1; }
runuser -u "$TEST_USER" -- env HOME="$TMP/home" XDG_DATA_HOME="$TMP/data" XDG_STATE_HOME="$TMP/state" python3 - "$TMP/data/kor-workstation/runtime.json" <<'PY'
import json,sys,time,urllib.request
from pathlib import Path
p=Path(sys.argv[1]); info=json.loads(p.read_text()); url=f"http://127.0.0.1:{int(info['port'])}/api/health"
for _ in range(50):
    try:
        with urllib.request.urlopen(url,timeout=.5) as r: data=json.load(r)
        assert data.get('app')=='KOR-NEXUS' and data.get('version')=='1.20.0', data
        break
    except Exception: time.sleep(.1)
else: raise SystemExit('Packaged server health check failed')
PY
# A second launch must reuse the process rather than create another instance.
PORT_BEFORE="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["port"])' "$TMP/data/kor-workstation/runtime.json")"
runuser -u "$TEST_USER" -- env HOME="$TMP/home" XDG_DATA_HOME="$TMP/data" XDG_STATE_HOME="$TMP/state" KOR_NO_BROWSER=1 /usr/bin/kor-workstation >/dev/null 2>&1
PORT_AFTER="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["port"])' "$TMP/data/kor-workstation/runtime.json")"
[[ "$PORT_BEFORE" == "$PORT_AFTER" ]]
runuser -u "$TEST_USER" -- env HOME="$TMP/home" XDG_DATA_HOME="$TMP/data" XDG_STATE_HOME="$TMP/state" /usr/bin/kor-workstation-stop
for _ in {1..80}; do [[ ! -s "$TMP/data/kor-workstation/runtime.json" ]] && break; sleep .1; done
[[ ! -s "$TMP/data/kor-workstation/runtime.json" ]]
for _ in {1..30}; do kill -0 "$PID" 2>/dev/null || break; sleep 0.1; done
if kill -0 "$PID" 2>/dev/null; then kill "$PID" 2>/dev/null || true; fi
wait "$PID" 2>/dev/null || true
PID=''
# Confirm SQLite was created, add a sentinel, then prove package removal preserves user data.
DB="$TMP/data/kor-workstation/kor-workstation.sqlite3"
[[ -s "$DB" ]] || { echo 'SQLite database was not created' >&2; exit 1; }
python3 - "$DB" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]); c.execute('CREATE TABLE IF NOT EXISTS package_test(value TEXT)'); c.execute('INSERT INTO package_test VALUES(?)',('preserve-db',)); c.commit(); c.close()
PY
pacman -Rns --noconfirm kor-workstation
[[ ! -e /opt/kor-workstation && ! -e /usr/bin/kor-workstation ]]
python3 - "$DB" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]); assert c.execute('SELECT value FROM package_test').fetchone()[0]=='preserve-db'; c.close()
PY
[[ "$(cat "$TMP/data/kor-workstation/backups/preserve.sqlite3")" == preserve-backup ]]
[[ "$(cat "$TMP/data/kor-workstation/geodata/preserve.geojson")" == preserve-geo ]]
printf 'OK isolated Arch package install/start/health/single-instance/stop/remove/data-retention test\n'
