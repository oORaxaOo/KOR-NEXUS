#!/usr/bin/env bash
set -euo pipefail
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/kor-workstation"
RUNTIME="$DATA_HOME/runtime.json"
if [[ ! -s "$RUNTIME" ]]; then
  echo 'KOR-NEXUS läuft laut Laufzeitstatus nicht.'
  exit 0
fi
python3 - "$RUNTIME" <<'PY'
import json, sys, urllib.request
from pathlib import Path
runtime=Path(sys.argv[1])
try:
    info=json.loads(runtime.read_text(encoding='utf-8'))
    port=int(info.get('port',0))
    if not 1024 <= port <= 65535: raise ValueError('ungültiger Port')
    base=f'http://127.0.0.1:{port}'
    with urllib.request.urlopen(base+'/api/health',timeout=1.5) as response:
        health=json.loads(response.read().decode('utf-8'))
    if health.get('app')!='KOR-NEXUS':
        raise RuntimeError('Auf dem gespeicherten Port läuft keine bestätigte KOR-Instanz.')
    request=urllib.request.Request(base+'/api/shutdown',data=b'{}',headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(request,timeout=2) as response:
        result=json.loads(response.read().decode('utf-8'))
    print(result.get('message','KOR-NEXUS wird beendet.'))
except FileNotFoundError:
    print('KOR-NEXUS läuft laut Laufzeitstatus nicht.')
except Exception as exc:
    print(f'KOR-NEXUS konnte nicht beendet werden: {exc}',file=sys.stderr)
    sys.exit(1)
PY
