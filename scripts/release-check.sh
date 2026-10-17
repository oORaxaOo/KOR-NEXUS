#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
MODE="${1:-full}"
case "$MODE" in quick|full|package) ;; *) echo 'Verwendung: scripts/release-check.sh [quick|full|package]' >&2; exit 2;; esac
command -v python3 >/dev/null || { echo 'FEHLER: python3 fehlt' >&2; exit 2; }
command -v sha256sum >/dev/null || { echo 'FEHLER: sha256sum fehlt' >&2; exit 2; }
command -v tar >/dev/null || { echo 'FEHLER: tar fehlt' >&2; exit 2; }
VERSION="$(sed -n 's/^pkgver=//p' PKGBUILD | head -n1)"
[[ -n "$VERSION" ]] || { echo 'FEHLER: pkgver fehlt' >&2; exit 1; }
python3 - "$VERSION" <<'PY'
from pathlib import Path
import re,sys
v=sys.argv[1]
checks={
 'core/server.py':rf"^VERSION\s*=\s*['\"]{re.escape(v)}['\"]",
 'core/test_server.py':rf"['\"]version['\"]\s*:\s*['\"]{re.escape(v)}['\"]",
 'scripts/qa-preview-playwright.py':rf"version:\s*['\"]{re.escape(v)}['\"]",
 'scripts/test-installation.sh':rf"version['\"]\)\s*==\s*['\"]{re.escape(v)}['\"]",
 'scripts/test-built-package-installation.sh':rf"version['\"]\)\s*==\s*['\"]{re.escape(v)}['\"]",
}
for file,pattern in checks.items():
 text=Path(file).read_text(encoding='utf-8')
 if not re.search(pattern,text,re.M): raise SystemExit(f'FEHLER: Version {v} fehlt oder ist inkonsistent: {file}')
 if file=='core/test_server.py' and text.count(v)<2: raise SystemExit('FEHLER: API-Test-Fixtures enthalten uneinheitliche Versionsangaben')
print(f'OK Versionskonsistenz: {v}')
PY
python3 -m py_compile core/server.py core/test_server.py scripts/qa-preview-playwright.py scripts/create-source-archive.py
bash -n launch.sh stop.sh install-user.sh uninstall-user.sh scripts/build-arch-package.sh scripts/test-installation.sh scripts/verify-source.sh scripts/release-check.sh scripts/ci.sh scripts/test-built-package-installation.sh packaging/kor-workstation-launcher.sh packaging/kor-workstation-stop.sh
if command -v node >/dev/null 2>&1; then node --check web/app.js; echo 'OK JavaScript-Syntax'; else echo 'WARN node fehlt; JavaScript-Syntaxprüfung übersprungen'; fi
bash scripts/verify-source.sh
python3 - <<'PYFILES'
from pathlib import Path
required = [
 'core/server.py','core/__init__.py','web/index.html','web/styles.css','web/app.js',
 'web/geodata/world.geojson','packaging/kor-workstation-launcher.sh',
 'packaging/kor-workstation-stop.sh','packaging/kor-workstation.desktop',
 'packaging/icons/kor-workstation.svg','LICENSE','README.md','EXPORT_SCHEMA.md',
 'DECISIONS.md','PROJECT_STATUS.md','CHANGELOG.md','scripts/ci.sh','scripts/test-built-package-installation.sh'
]
missing=[f for f in required if not Path(f).is_file()]
if missing: raise SystemExit('FEHLER: Paketdateien fehlen: '+', '.join(missing))
print(f'OK Paketdateiliste: {len(required)} benötigte Dateien vorhanden')
PYFILES
python3 scripts/create-source-archive.py
FIRST_HASH="$(sha256sum "kor-workstation-${VERSION}.tar.gz" | cut -d' ' -f1)"
python3 scripts/create-source-archive.py >/dev/null
SECOND_HASH="$(sha256sum "kor-workstation-${VERSION}.tar.gz" | cut -d' ' -f1)"
[[ "$FIRST_HASH" == "$SECOND_HASH" ]] || { echo 'FEHLER: Quellarchiv ist nicht reproduzierbar' >&2; exit 1; }
echo "OK Reproduzierbarkeit: $FIRST_HASH"
sha256sum -c SOURCE_SHA256SUMS.txt
python3 - "$VERSION" <<'PY'
import sys,tarfile
from pathlib import Path
v=sys.argv[1]; p=Path(f'kor-workstation-{v}.tar.gz')
with tarfile.open(p,'r:gz') as t:
 members=t.getmembers()
 names={m.name.removeprefix('./') for m in members}
 required={'PKGBUILD','core/server.py','core/test_server.py','web/geodata/world.geojson','scripts/verify-source.sh','scripts/release-check.sh','scripts/ci.sh','scripts/create-source-archive.py','scripts/verify-built-package.py','scripts/test-built-package-installation.sh'}
 missing=required-names
 if missing: raise SystemExit(f'FEHLER: Quellarchiv-Dateien fehlen: {sorted(missing)}')
 if any(m.mtime != 0 for m in members): raise SystemExit('FEHLER: Quellarchiv-Zeitstempel nicht deterministisch')
 print(f'OK Quellarchiv: {len(members)} Einträge, erforderliche Dateien vorhanden, Zeitstempel normalisiert')
PY
if [[ "$MODE" != quick ]]; then
  python3 -m unittest -v core.test_server
  BROWSER_TIMEOUT="${KOR_BROWSER_QA_TIMEOUT:-120}"
  INSTALL_TIMEOUT="${KOR_INSTALL_TEST_TIMEOUT:-120}"
  if ! [[ "$BROWSER_TIMEOUT" =~ ^[1-9][0-9]*$ && "$INSTALL_TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
    echo 'FEHLER: QA-Timeouts müssen positive ganze Sekunden sein.' >&2
    exit 2
  fi
  if ! command -v timeout >/dev/null 2>&1; then
    echo 'FEHLER: timeout fehlt; sichere Laufzeitbegrenzung nicht verfügbar.' >&2
    exit 2
  fi
  if timeout --signal=TERM --kill-after=10s "${BROWSER_TIMEOUT}s" python3 scripts/qa-preview-playwright.py; then
    echo 'OK Browser-Smoke-Test'
  else
    status=$?
    echo "FEHLER Browser-Smoke-Test (Exit $status; Limit ${BROWSER_TIMEOUT}s)" >&2
    exit "$status"
  fi
  timeout --signal=TERM --kill-after=10s "${INSTALL_TIMEOUT}s" bash scripts/test-installation.sh
fi
if [[ "$MODE" == package ]]; then
  if ! command -v makepkg >/dev/null 2>&1; then echo 'NICHT VERFÜGBAR: makepkg fehlt; kein Arch-Paket gebaut.' >&2; exit 3; fi
  makepkg -f
else
  if command -v makepkg >/dev/null 2>&1; then echo 'INFO: makepkg verfügbar; Paketbau separat mit scripts/build-arch-package.sh ausführen.'; else echo 'NICHT VERFÜGBAR: makepkg/pacman fehlen; Paketbau und Zielsysteminstallation nicht ausgeführt.'; fi
fi
printf '\nRELEASE-CHECK BESTANDEN (%s). Paketbau/Installation nur wenn separat bestätigt.\n' "$MODE"
