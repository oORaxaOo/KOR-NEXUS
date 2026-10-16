#!/usr/bin/env bash
set -euo pipefail
RUNTIME="${XDG_DATA_HOME:-$HOME/.local/share}/kor-workstation/runtime.json"
if [[ ! -s "$RUNTIME" ]]; then
  echo 'KOR-NEXUS läuft laut Laufzeitstatus nicht.'
  exit 0
fi
python3 - "$RUNTIME" <<'PY'
import json,sys,urllib.request
from pathlib import Path
try:
    runtime=Path(sys.argv[1])
    info=json.loads(runtime.read_text(encoding='utf-8'))
    port=int(info.get('port',0))
    if not 1024 <= port <= 65535: raise ValueError('Ungültiger lokaler Port')
    base=f'http://127.0.0.1:{port}'
    with urllib.request.urlopen(base+'/api/health',timeout=1.5) as response:
        health=json.loads(response.read(65536).decode('utf-8'))
    if health.get('app')!='KOR-NEXUS': raise RuntimeError('Auf dem gespeicherten Port läuft keine bestätigte KOR-NEXUS-Instanz.')
    req=urllib.request.Request(base+'/api/shutdown',data=b'{}',headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=2) as response:
        result=json.loads(response.read(65536).decode('utf-8'))
    print(result.get('message','KOR-NEXUS wird beendet.'))
except FileNotFoundError:
    print('KOR-NEXUS läuft laut Laufzeitstatus nicht.')
except Exception as exc:
    print(f'KOR-NEXUS konnte nicht sicher beendet werden: {exc}',file=sys.stderr)
    sys.exit(1)
PY
