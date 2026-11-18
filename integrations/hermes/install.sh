#!/usr/bin/env bash
# Install the optional KOR-NEXUS MCP server without modifying Hermes or KOR-NEXUS core.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
SOURCE="$SCRIPT_DIR/mcp_server"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
TARGET="$DATA_HOME/kor-workstation/hermes-integration"

command -v python3 >/dev/null 2>&1 || { echo 'FEHLER: python3 fehlt.' >&2; exit 2; }
[[ -f "$SOURCE/server.py" && -f "$SOURCE/requirements.txt" ]] || { echo 'FEHLER: MCP-Quelldateien fehlen.' >&2; exit 2; }

mkdir -p "$TARGET"
rm -rf "$TARGET/mcp_server"
cp -a "$SOURCE" "$TARGET/mcp_server"
python3 -m venv "$TARGET/.venv"
"$TARGET/.venv/bin/python" -m pip install --upgrade pip
"$TARGET/.venv/bin/python" -m pip install -r "$TARGET/mcp_server/requirements.txt"

python3 - "$TARGET" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
python = root / ".venv" / "bin" / "python"
server = root / "mcp_server" / "server.py"
config = root / "hermes-mcp-config.yaml"
config.write_text(
    "mcp_servers:\n"
    "  kor_nexus:\n"
    f'    command: "{python}"\n'
    f'    args: ["{server}"]\n'
    "    timeout: 15\n"
    "    connect_timeout: 10\n"
    "    tools:\n"
    "      include:\n"
    "        - kor_get_status\n"
    "        - kor_list_tasks\n"
    "        - kor_list_projects\n"
    "        - kor_list_records\n"
    "        - kor_list_resources\n"
    "        - kor_get_alerts\n"
    "        - kor_get_dashboard\n"
    "        - kor_get_events\n",
    encoding="utf-8",
)
print(f"Konfigurationsvorlage: {config}")
PY

"$TARGET/.venv/bin/python" -m py_compile "$TARGET/mcp_server/kor_client.py" "$TARGET/mcp_server/server.py"
echo
echo 'KOR-NEXUS MCP-Server wurde installiert.'
echo 'Die Hermes-Konfiguration wurde NICHT automatisch verändert.'
echo 'Den kor_nexus-Eintrag aus der Vorlage unter mcp_servers: in ~/.hermes/config.yaml übernehmen.'
echo 'Danach: hermes mcp test kor_nexus'
