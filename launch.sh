#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null 2>&1 || { echo 'KOR-NEXUS benötigt Python 3.' >&2; exit 1; }
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
AI_PYTHON="$DATA_HOME/kor-workstation/ai-venv/bin/python"
if [[ -x "$AI_PYTHON" ]]; then PYTHON="$AI_PYTHON"; else PYTHON="$(command -v python3)"; fi
exec "$PYTHON" "$ROOT/core/server.py"
