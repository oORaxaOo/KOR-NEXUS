#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v python3 >/dev/null 2>&1 || { echo 'Fehler: Python 3 fehlt.' >&2; exit 2; }
python3 -m py_compile core/server.py core/window.py core/test_server.py core/mesh.py core/simulation.py core/media.py core/github_integration.py tests/test_github_integration.py scripts/import-bkg-data.py scripts/test-advanced-features.py scripts/qa-code-workbench-playwright.py scripts/qa-native-window.py
python3 scripts/test-advanced-features.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
printf 'OK  Python-Syntax und Kernmodule\n'
python3 - <<'PY'
import json
from pathlib import Path
required=['core/__init__.py','core/server.py','core/window.py','core/test_server.py','core/mesh.py','core/simulation.py','core/media.py','core/github_integration.py','tests/test_github_integration.py','tests/test_code_workbench.py','scripts/import-bkg-data.py','scripts/test-advanced-features.py','scripts/qa-code-workbench-playwright.py','scripts/qa-native-window.py','web/js/hud-alerts.js','web/js/hud.js','web/js/media-hub.js','org.oORaxaOo.KorNexus.json','flatpak/launch.sh','flatpak/org.oORaxaOo.KorNexus.desktop','KDE_PLASMA_HUD.md','web/index.html','web/github.html','web/code.html','web/styles.css','web/app.js','web/js/github-center.js','web/geodata/world.geojson','GITHUB_CENTER.md','launch.sh','stop.sh','install-user.sh','uninstall-user.sh','packaging/kor-workstation.desktop','packaging/kor-workstation-launcher.sh','packaging/kor-workstation-stop.sh','packaging/icons/kor-workstation.svg','scripts/build-arch-package.sh','scripts/test-installation.sh','scripts/release-check.sh','scripts/ci.sh','scripts/create-source-archive.py','scripts/verify-built-package.py','PKGBUILD','README.md','EXPORT_SCHEMA.md','CHANGELOG.md','DECISIONS.md','PROJECT_STATUS.md']
for name in required:
    p=Path(name)
    if not p.is_file() or p.stat().st_size==0: raise SystemExit(f'FEHLER: Datei fehlt/leer: {name}')
    print('OK ',name)
html=Path('web/index.html').read_text()
if 'hud-alerts.js' not in html: raise SystemExit('FEHLER: HUD-Erweiterung nicht eingebunden')
if './github.html' not in html: raise SystemExit('FEHLER: GitHub Development Center ist nicht in der Navigation verlinkt')
if './code.html' not in html: raise SystemExit('FEHLER: Code Workbench ist nicht in der Kommandozentrale verlinkt')
code_html=Path('web/code.html').read_text()
if "api('/ide/status')" not in code_html or "api('/ide/start'," not in code_html: raise SystemExit('FEHLER: Code Workbench API-Anbindung fehlt')
if "127.0.0.1" not in Path('core/server.py').read_text(): raise SystemExit('FEHLER: lokaler Loopback-Bind der Code-IDE fehlt')
server_source=Path('core/server.py').read_text()
window_source=Path('core/window.py').read_text()
if 'def open_app(' in server_source or 'open_app_or_report' in server_source:
    raise SystemExit('FEHLER: externer Browser-Fallback ist noch im Server vorhanden')
if 'from core.window import start_native_app' not in server_source:
    raise SystemExit('FEHLER: nativer Desktop-Start ist nicht in den Server integriert')
if 'def createWindow(self, window_type)' not in window_source or 'KorNexusPopupWindow' not in window_source:
    raise SystemExit('FEHLER: Web-Popups werden nicht in eigenständige Qt-Fenster geleitet')
if 'Es wird absichtlich kein Browser geöffnet.' not in server_source:
    raise SystemExit('FEHLER: nativer Startfehler wird nicht ohne Browser-Fallback behandelt')
if 'web/code.html' not in Path('PKGBUILD').read_text(): raise SystemExit('FEHLER: Code Workbench fehlt im Arch-Paket')
github_html=Path('web/github.html').read_text()
if './js/github-center.js' not in github_html: raise SystemExit('FEHLER: GitHub-UI-Skript nicht eingebunden')
if 'core/github_integration.py' not in Path('PKGBUILD').read_text(): raise SystemExit('FEHLER: GitHub-Backend fehlt im Arch-Paket')
if 'core/media.py' not in Path('PKGBUILD').read_text(): raise SystemExit('FEHLER: erforderliches Media-Kernmodul fehlt im Arch-Paket')
manifest=json.loads(Path('org.oORaxaOo.KorNexus.json').read_text())
if manifest.get('app-id')!='org.oORaxaOo.KorNexus' or not manifest.get('modules'): raise SystemExit('FEHLER: Flatpak-Manifest ungültig')
for asset in ('./styles.css','./app.js'):
    if asset not in html: raise SystemExit(f'FEHLER: {asset} nicht eingebunden')
if "fetch('/api'+path" not in Path('web/app.js').read_text(): raise SystemExit('FEHLER: API-Client fehlt')
geo=json.loads(Path('web/geodata/world.geojson').read_text(encoding='utf-8'))
if geo.get('type')!='FeatureCollection' or len(geo.get('features',[]))<150: raise SystemExit('FEHLER: Offline-Weltgeometrien fehlen oder sind unvollständig')
if not any((f.get('properties') or {}).get('iso_a3')=='DEU' for f in geo['features']): raise SystemExit('FEHLER: Deutschlandgeometrie fehlt')
print(f"OK  Offline-GeoJSON: {len(geo['features'])} Features, {Path('web/geodata/world.geojson').stat().st_size} Byte")
print('OK  Lokale Frontend-Assets und API-Client')
PY
bash -n launch.sh stop.sh install-user.sh uninstall-user.sh scripts/build-arch-package.sh scripts/test-installation.sh scripts/release-check.sh scripts/ci.sh packaging/kor-workstation-launcher.sh packaging/kor-workstation-stop.sh
python3 - <<'PY'
from pathlib import Path
import re
p=Path('PKGBUILD').read_text()
version=re.search(r"^VERSION\s*=\s*['\"]([^'\"]+)['\"]", Path('core/server.py').read_text(), re.M)
if not version: raise SystemExit('FEHLER: Laufzeitversion fehlt')
for x in ('pkgname=kor-workstation',f'pkgver={version.group(1)}','depends=(\'python\' \'python-pyqt6\' \'python-pyqt6-webengine\')','packaging/kor-workstation.desktop','kor-workstation-stop.sh','EXPORT_SCHEMA.md','CHANGELOG.md','GITHUB_CENTER.md','core/github_integration.py','web/github.html','web/js/github-center.js'):
    if x not in p: raise SystemExit(f'FEHLER: Arch-Paketdefinition erwartet {x}')
print('OK  Arch-Paketdefinition enthält die Python-Kernlaufzeit')
PY
