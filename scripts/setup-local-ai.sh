#!/usr/bin/env bash
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
AI_VENV="$DATA_HOME/kor-workstation/ai-venv"
CONFIG_DIR="$CONFIG_HOME/kor-nexus"
CONFIG_FILE="$CONFIG_DIR/ai.json"

command -v python3 >/dev/null 2>&1 || { echo 'Python 3 fehlt.' >&2; exit 1; }
command -v realpath >/dev/null 2>&1 || { echo 'realpath fehlt.' >&2; exit 1; }

printf 'KOR-NEXUS — optionale lokale llama.cpp-KI\n'
printf 'Es wird kein Modell heruntergeladen. Wähle eine GGUF-Datei, die du bereits besitzt und deren Lizenz du geprüft hast.\n'
read -r -p 'Absoluter oder relativer Pfad zur lokalen .gguf-Datei: ' MODEL_INPUT
[[ -n "$MODEL_INPUT" && -f "$MODEL_INPUT" ]] || { echo 'Die Modelldatei wurde nicht gefunden; nichts wurde aktiviert.' >&2; exit 1; }
MODEL_PATH="$(realpath -- "$MODEL_INPUT")"
[[ "$MODEL_PATH" == *.gguf || "$MODEL_PATH" == *.GGUF ]] || { echo 'Erwartet wird eine Datei mit der Endung .gguf.' >&2; exit 1; }

mkdir -p "$(dirname "$AI_VENV")" "$CONFIG_DIR"
chmod 700 "$DATA_HOME/kor-workstation" "$CONFIG_DIR"
if [[ ! -x "$AI_VENV/bin/python" ]]; then
  python3 -m venv "$AI_VENV"
fi
printf 'Installiere die optionale Python-Bindung in einer isolierten Umgebung. Das kann je nach Rechner dauern.\n'
"$AI_VENV/bin/python" -m pip install --upgrade pip
"$AI_VENV/bin/python" -m pip install llama-cpp-python

CONFIG_FILE="$CONFIG_FILE" MODEL_PATH="$MODEL_PATH" "$AI_VENV/bin/python" - <<'PY'
import json, os
from pathlib import Path
dest=Path(os.environ['CONFIG_FILE'])
payload={
    'enabled': True,
    'model_path': os.environ['MODEL_PATH'],
    'context_size': 4096,
    'max_tokens': 512,
}
temporary=dest.with_suffix('.json.partial')
temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
temporary.chmod(0o600)
temporary.replace(dest)
PY
chmod 600 "$CONFIG_FILE"
printf '\nLokale KI wurde aktiviert. Starte KOR-NEXUS neu.\n'
printf 'Konfiguration: %s\n' "$CONFIG_FILE"
printf 'Virtuelle Umgebung: %s\n' "$AI_VENV"
printf 'Das Modell bleibt lokal; KOR-NEXUS lädt es erst bei der ersten Anfrage.\n'
