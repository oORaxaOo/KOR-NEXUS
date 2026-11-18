#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_ROOT="$(cd -- "$(dirname -- "\${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="\${PYTHON:-python3}"
XDG_DATA_HOME_VALUE="\${XDG_DATA_HOME:-$HOME/.local/share}"
DATA_HOME="$XDG_DATA_HOME_VALUE/kor-workstation"
INSTALLED_APP="$XDG_DATA_HOME_VALUE/kor-workstation-app"
if [[ -n "\${KOR_NEXUS_APP_ROOT:-}" ]]; then
  APP_ROOT="$(cd -- "$KOR_NEXUS_APP_ROOT" && pwd)"
elif [[ -f "$INSTALLED_APP/integrations/hermes/mcp_server.py" ]]; then
  APP_ROOT="$INSTALLED_APP"
else
  APP_ROOT="$REPOSITORY_ROOT"
fi
VENV="\${KOR_NEXUS_HERMES_VENV:-$DATA_HOME/hermes-mcp-venv}"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
  echo "Fehler: $PYTHON_BIN wurde nicht gefunden." >&2
  exit 2
}

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Fehler: Die Hermes-MCP-Integration benötigt Python 3.11 oder neuer.")
PY

mkdir -p "$(dirname -- "$VENV")"
if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --disable-pip-version-check --upgrade pip
"$VENV/bin/python" -m pip install --disable-pip-version-check -r "$APP_ROOT/integrations/hermes/requirements.txt"
"$VENV/bin/python" -m py_compile "$APP_ROOT/integrations/hermes/kor_client.py" "$APP_ROOT/integrations/hermes/mcp_server.py" "$APP_ROOT/integrations/hermes/doctor.py"

cat <<EOF

KOR-NEXUS MCP-Server wurde eingerichtet.

Füge diesen Block unter mcp_servers in ~/.hermes/config.yaml ein:

mcp_servers:
  kor_nexus:
    command: "$VENV/bin/python"
    args:
      - "$APP_ROOT/integrations/hermes/mcp_server.py"
    connect_timeout: 20
    timeout: 15

Danach Hermes Gateway neu starten. Der Server bietet zunächst ausschließlich lesende Werkzeuge.
Diagnose: "$VENV/bin/python" "$APP_ROOT/integrations/hermes/doctor.py"
EOF
