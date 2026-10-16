#!/usr/bin/env bash
set -euo pipefail
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$DATA_HOME/kor-workstation-app"
RUNTIME="$DATA_HOME/kor-workstation/runtime.json"
# Stop the installed service first so the web assets are not removed underneath it.
if [[ -s "$RUNTIME" ]]; then
  python3 - "$RUNTIME" <<'PY' || true
import json,sys,urllib.request
from pathlib import Path
try:
    p=int(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')).get('port',0))
    if not 1024<=p<=65535: raise ValueError('port')
    base=f'http://127.0.0.1:{p}'
    with urllib.request.urlopen(base+'/api/health',timeout=1) as r: health=json.load(r)
    if health.get('app')=='KOR-NEXUS':
        req=urllib.request.Request(base+'/api/shutdown',data=b'{}',headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=2): pass
except Exception: pass
PY
  for _ in {1..40}; do
    [[ ! -s "$RUNTIME" ]] && break
    sleep 0.1
  done
fi
rm -f "$HOME/.local/bin/kor-workstation" "$HOME/.local/bin/kor-workstation-stop" "$DATA_HOME/applications/kor-workstation.desktop" "$DATA_HOME/icons/hicolor/scalable/apps/kor-workstation.svg"
rm -rf "$APP_DIR"
printf 'Programmdateien und Anwendungsmenüeintrag entfernt.\n'
printf 'Nutzerdaten und Backups wurden bewusst beibehalten: %s/kor-workstation\n' "$DATA_HOME"
