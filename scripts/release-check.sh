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
python3 -m py_compile core/server.py core/engine.py core/ai_provider.py core/test_server.py scripts/qa-preview-playwright.py scripts/create-source-archive.py
bash -n launch.sh stop.sh install-user.sh uninstall-user.sh scripts/setup-local-ai.sh scripts/build-arch-package.sh scripts/test-installation.sh scripts/verify-source.sh scripts/release-check.sh scripts/ci.sh scripts/test-built-package-installation.sh packaging/kor-workstation-launcher.sh packaging/kor-workstation-stop.sh
if command -v node >/dev/null 2>&1; then node --check web/app.js; echo 'OK JavaScript-Syntax'; else echo 'WARN node fehlt; JavaScript-Syntaxprüfung übersprungen'; fi
bash scripts/verify-source.sh
# Validate the file set required by PKGBUILD before packaging.
python3 - <<'PYFILES'
from pathlib import Path
required = [
 'core/server.py','core/engine.py','core/ai_provider.py','core/__init__.py','web/index.html','web/styles.css','web/app.js',
 'web/geodata/world.geojson','packaging/kor-workstation-launcher.sh',
 'packaging/kor-workstation-stop.sh','packaging/kor-workstation.desktop',
 'packaging/icons/kor-workstation.svg','LICENSE','README.md','EXPORT_SCHEMA.md',
 'DECISIONS.md','PROJECT_STATUS.md','CHANGELOG.md','scripts/ci.sh','scripts/setup-local-ai.sh','scripts/test-built-package-installation.sh'
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
# Validate archive integrity and required members before running tests.
python3 - "$VERSION" <<'PY'
import sys,tarfile
from pathlib import Path
v=sys.argv[1]; p=Path(f'kor-workstation-{v}.tar.gz')
with tarfile.open(p,'r:gz') as t:
 bad=t.getmembers()
 names={m.name.lstrip('./') for m in bad}
 required={'PKGBUILD','core/server.py','core/engine.py','core/ai_provider.py','core/test_server.py','web/geodata/world.geojson','scripts/verify-source.sh','scripts/release-check.sh','scripts/ci.sh','scripts/create-source-archive.py','scripts/verify-built-package.py','scripts/setup-local-ai.sh','scripts/test-built-package-installation.sh'}
 missing=required-names
 if missing: raise SystemExit(f'FEHLER: Quellarchiv-Dateien fehlen: {sorted(missing)}')
 if t.getmembers() and any(m.mtime != 0 for m in t.getmembers()): raise SystemExit('FEHLER: Quellarchiv-Zeitstempel nicht deterministisch')
 print(f'OK Quellarchiv: {len(bad)} Einträge, erforderliche Dateien vorhanden, Zeitstempel normalisiert')
PY
if [[ "$MODE" != quick ]]; then
  python3 -m unittest -v core.test_server
  if python3 scripts/qa-preview-playwright.py; then echo 'OK Browser-Smoke-Test'; else echo 'FEHLER Browser-Smoke-Test' >&2; exit 1; fi
  bash scripts/test-installation.sh
fi
if [[ "$MODE" == package ]]; then
  if ! command -v makepkg >/dev/null 2>&1; then echo 'NICHT VERFÜGBAR: makepkg fehlt; kein Arch-Paket gebaut.' >&2; exit 3; fi
  makepkg -f
else
  if command -v makepkg >/dev/null 2>&1; then echo 'INFO: makepkg verfügbar; Paketbau separat mit scripts/build-arch-package.sh ausführen.'; else echo 'NICHT VERFÜGBAR: makepkg/pacman fehlen; Paketbau und Zielsysteminstallation nicht ausgeführt.'; fi
fi
printf '\nRELEASE-CHECK BESTANDEN (%s). Paketbau/Installation nur wenn separat bestätigt.\n' "$MODE"
