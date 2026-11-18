#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_ROOT="$(cd -- "$(dirname -- "$0")/../.." && pwd)"
PYTHON_BIN="$(printenv PYTHON 2>/dev/null || true)"
[[ -n "$PYTHON_BIN" ]] || PYTHON_BIN=python3
XDG_DATA_HOME_VALUE="$(printenv XDG_DATA_HOME 2>/dev/null || true)"
[[ -n "$XDG_DATA_HOME_VALUE" ]] || XDG_DATA_HOME_VALUE="$HOME/.local/share"
DATA_HOME="$XDG_DATA_HOME_VALUE/kor-workstation"
INSTALLED_APP="$XDG_DATA_HOME_VALUE/kor-workstation-app"
HERMES_HOME="$(printenv HERMES_HOME 2>/dev/null || true)"
[[ -n "$HERMES_HOME" ]] || HERMES_HOME="$HOME/.hermes"
APP_ROOT="$(printenv KOR_NEXUS_APP_ROOT 2>/dev/null || true)"
if [[ -z "$APP_ROOT" ]]; then
  if [[ -s "$INSTALLED_APP/integrations/hermes/mcp_server.py" ]]; then
    APP_ROOT="$INSTALLED_APP"
  else
    APP_ROOT="$REPOSITORY_ROOT"
  fi
fi
VENV="$(printenv KOR_NEXUS_HERMES_VENV 2>/dev/null || true)"
[[ -n "$VENV" ]] || VENV="$DATA_HOME/hermes-mcp-venv"
PLUGIN_DIR="$HERMES_HOME/plugins/kor-nexus"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
  echo "Fehler: $PYTHON_BIN wurde nicht gefunden." >&2
  exit 2
}
[[ -s "$APP_ROOT/integrations/hermes/requirements.txt" ]] || {
  echo "Fehler: Hermes-Integrationsdateien fehlen unter $APP_ROOT." >&2
  exit 2
}
[[ -s "$APP_ROOT/integrations/hermes/plugin/adapter.py" ]] || {
  echo "Fehler: Hermes-Plattformplugin fehlt unter $APP_ROOT." >&2
  exit 2
}

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Fehler: Die Hermes-MCP-Integration benötigt Python 3.11 oder neuer.")
PY

mkdir -p "$(dirname -- "$VENV")" "$HERMES_HOME" "$HERMES_HOME/plugins"
chmod 700 "$HERMES_HOME"
if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --disable-pip-version-check -r "$APP_ROOT/integrations/hermes/requirements.txt"
"$VENV/bin/python" -m py_compile \
  "$APP_ROOT/integrations/hermes/kor_client.py" \
  "$APP_ROOT/integrations/hermes/mcp_server.py" \
  "$APP_ROOT/integrations/hermes/doctor.py" \
  "$APP_ROOT/integrations/hermes/plugin/adapter.py"

# Preserve an existing bridge token; create one only for the first setup.
"$PYTHON_BIN" - "$DATA_HOME" "$HERMES_HOME/.env" <<'PY'
import os
import secrets
import sys
from pathlib import Path

data_home = Path(sys.argv[1]).expanduser()
env_file = Path(sys.argv[2]).expanduser()
data_home.mkdir(parents=True, exist_ok=True, mode=0o700)
try:
    os.chmod(data_home, 0o700)
except OSError:
    pass
token_file = data_home / "hermes-bridge-token"
if token_file.is_file():
    token = token_file.read_text(encoding="utf-8").strip()
else:
    token = secrets.token_urlsafe(32)
    token_file.write_text(token + "\n", encoding="utf-8")
try:
    os.chmod(token_file, 0o600)
except OSError:
    pass

env_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
try:
    os.chmod(env_file.parent, 0o700)
except OSError:
    pass
lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
updates = {
    "KOR_NEXUS_BRIDGE_TOKEN": token,
    "KOR_NEXUS_DATA_HOME": str(data_home),
    "KOR_NEXUS_ALLOWED_USERS": "local-user",
    "KOR_NEXUS_HOME_CHANNEL": "main",
}
for key, value in updates.items():
    encoded = value.replace("\\", "\\\\").replace('"', '\\"')
    line = f'{key}="{encoded}"'
    found = False
    for index, existing in enumerate(lines):
        if existing.lstrip().startswith(key + "="):
            lines[index] = line
            found = True
            break
    if not found:
        lines.append(line)
temporary = env_file.with_name(env_file.name + ".partial")
temporary.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
try:
    os.chmod(temporary, 0o600)
except OSError:
    pass
temporary.replace(env_file)
PY

# Install/update only this plugin directory; other Hermes plugins stay untouched.
mkdir -p "$PLUGIN_DIR"
cp -a "$APP_ROOT/integrations/hermes/plugin/." "$PLUGIN_DIR/"
"$PYTHON_BIN" -m py_compile "$PLUGIN_DIR/adapter.py"

cat <<EOF

KOR-NEXUS / HERMES - BASISBRUECKE EINGERICHTET

Hermes-Plattformplugin:
  $PLUGIN_DIR

Privater Bridge-Token:
  $DATA_HOME/hermes-bridge-token
  (Dateirechte: 0600; Token wurde in ~/.hermes/.env eingetragen)

1. Ergänze diesen Block in ~/.hermes/config.yaml:

gateway:
  platforms:
    kor_nexus:
      enabled: true
      extra:
        data_home: "$DATA_HOME"

2. Ergänze diesen MCP-Block auf oberster Ebene in ~/.hermes/config.yaml:

mcp_servers:
  kor_nexus:
    command: "$VENV/bin/python"
    args:
      - "$APP_ROOT/integrations/hermes/mcp_server.py"
    connect_timeout: 20
    timeout: 120

3. KOR-NEXUS starten und danach das Hermes Gateway neu starten:
   hermes gateway restart

MCP-Diagnose:
  "$VENV/bin/python" "$APP_ROOT/integrations/hermes/doctor.py"

Der KOR-NEXUS-Chat ist ein zusätzlicher lokaler Hermes-Kanal.
Andere bereits eingerichtete Hermes-Plattformen bleiben unverändert.
Die Anwendung bearbeitet config.yaml nicht automatisch.
EOF
