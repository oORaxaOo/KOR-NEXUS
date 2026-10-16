#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v python3 >/dev/null 2>&1 || { echo 'Fehler: Python 3 fehlt.' >&2; exit 2; }
python3 -m py_compile core/server.py core/test_server.py
printf 'OK  Python-Syntax und Kernmodule\n'
python3 - <<'PY'
import json
from pathlib import Path
required=['core/__init__.py','core/server.py','core/test_server.py','web/index.html','web/styles.css','web/app.js','web/geodata/world.geojson','launch.sh','stop.sh','install-user.sh','uninstall-user.sh','packaging/kor-workstation.desktop','packaging/kor-workstation-launcher.sh','packaging/kor-workstation-stop.sh','packaging/icons/kor-workstation.svg','scripts/build-arch-package.sh','scripts/test-installation.sh','scripts/release-check.sh','scripts/ci.sh','scripts/create-source-archive.py','scripts/verify-built-package.py','PKGBUILD','README.md','EXPORT_SCHEMA.md','CHANGELOG.md','DECISIONS.md','PROJECT_STATUS.md']
for name in required:
    p=Path(name)
    if not p.is_file() or p.stat().st_size==0: raise SystemExit(f'FEHLER: Datei fehlt/leer: {name}')
    print('OK ',name)
html=Path('web/index.html').read_text()
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
for x in ('pkgname=kor-workstation',f'pkgver={version.group(1)}','depends=(\'python\')','packaging/kor-workstation.desktop','kor-workstation-stop.sh','EXPORT_SCHEMA.md','CHANGELOG.md'):
    if x not in p: raise SystemExit(f'FEHLER: Arch-Paketdefinition erwartet {x}')
print('OK  Arch-Paketdefinition enthält die Python-Kernlaufzeit')
PY
