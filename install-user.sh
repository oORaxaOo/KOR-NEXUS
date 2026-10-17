#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null 2>&1 || { echo 'Python 3 fehlt. Bitte Python 3 installieren.' >&2; exit 1; }
[[ -s "$ROOT/core/server.py" && -s "$ROOT/core/engine.py" && -s "$ROOT/core/ai_provider.py" && -s "$ROOT/web/index.html" && -s "$ROOT/web/app.js" && -s "$ROOT/web/geodata/world.geojson" ]] || { echo 'Installationsdateien fehlen; bitte das vollständige Archiv entpacken.' >&2; exit 1; }
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$DATA_HOME/kor-workstation-app"
RUNTIME_DIR="$DATA_HOME/kor-workstation"
BIN_DIR="$HOME/.local/bin"
APP_MENU="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/kor-workstation"

# Stop the currently installed server before replacing code or assets.
if [[ -s "$RUNTIME_DIR/runtime.json" ]]; then
  if [[ -x "$BIN_DIR/kor-workstation-stop" ]]; then
    "$BIN_DIR/kor-workstation-stop" >/dev/null || { echo 'Aktualisierung abgebrochen: laufende Instanz konnte nicht sicher beendet werden.' >&2; exit 1; }
  else
    XDG_DATA_HOME="$DATA_HOME" "$ROOT/stop.sh" >/dev/null || { echo 'Aktualisierung abgebrochen: laufende Instanz konnte nicht sicher beendet werden.' >&2; exit 1; }
  fi
  for _ in {1..50}; do
    [[ ! -s "$RUNTIME_DIR/runtime.json" ]] && break
    sleep 0.1
  done
  [[ ! -s "$RUNTIME_DIR/runtime.json" ]] || { echo 'Aktualisierung abgebrochen: der Server meldet sich nach dem Stop nicht ab. Daten und alte Programmdateien bleiben erhalten.' >&2; exit 1; }
fi

mkdir -p "$APP_DIR/core" "$APP_DIR/web/geodata" "$APP_DIR/scripts" "$BIN_DIR" "$APP_MENU" "$ICON_DIR" "$LOG_DIR"
chmod 700 "$LOG_DIR"
install -m 644 "$ROOT/core/server.py" "$ROOT/core/engine.py" "$ROOT/core/ai_provider.py" "$APP_DIR/core/"
install -m 644 "$ROOT/core/__init__.py" "$APP_DIR/core/__init__.py"
install -m 644 "$ROOT/web/index.html" "$ROOT/web/styles.css" "$ROOT/web/app.js" "$APP_DIR/web/"
install -m 644 "$ROOT/web/geodata/world.geojson" "$APP_DIR/web/geodata/world.geojson"
install -m 644 "$ROOT/scripts/setup-local-ai.sh" "$APP_DIR/scripts/setup-local-ai.sh"
install -m 644 "$ROOT/packaging/icons/kor-workstation.svg" "$ICON_DIR/kor-workstation.svg"

# Build a launcher with shell-safe, literal paths (including spaces).
printf -v APP_DIR_Q '%q' "$APP_DIR"
printf -v LOG_DIR_Q '%q' "$LOG_DIR"
cat > "$BIN_DIR/kor-workstation" <<EOF2
#!/usr/bin/env bash
set -euo pipefail
umask 077
APP_DIR=$APP_DIR_Q
LOG_DIR=$LOG_DIR_Q
mkdir -p "\$LOG_DIR"
chmod 700 "\$LOG_DIR"
if [[ -f "\$LOG_DIR/server.log" && \$(stat -c %s "\$LOG_DIR/server.log" 2>/dev/null || echo 0) -gt 5242880 ]]; then
  mv -f "\$LOG_DIR/server.log" "\$LOG_DIR/server.log.1"
fi
if ! command -v python3 >/dev/null 2>&1; then
  printf 'KOR-NEXUS benötigt Python 3.\\n' >&2
  exit 127
fi
DATA_HOME=\${XDG_DATA_HOME:-\$HOME/.local/share}
AI_PYTHON="\$DATA_HOME/kor-workstation/ai-venv/bin/python"
if [[ -x "\$AI_PYTHON" ]]; then PYTHON="\$AI_PYTHON"; else PYTHON="\$(command -v python3)"; fi
exec "\$PYTHON" "\$APP_DIR/core/server.py" >> "\$LOG_DIR/server.log" 2>&1
EOF2
chmod 755 "$BIN_DIR/kor-workstation"
install -m 755 "$ROOT/packaging/kor-workstation-stop.sh" "$BIN_DIR/kor-workstation-stop"

# Desktop Entry Exec uses double quotes and escaped backslashes/quotes, not shell %q.
python3 - "$BIN_DIR/kor-workstation" "$APP_MENU/kor-workstation.desktop" <<'PY'
import sys
from pathlib import Path
exe,dest=sys.argv[1:]
def desktop_quote(s): return '"'+s.replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$')+'"'
dest=Path(dest)
dest.write_text('[Desktop Entry]\nType=Application\nName=KOR-NEXUS\nGenericName=Local Knowledge and Planning Workspace\nComment=Lokale SQLite-Workstation für Wissen, Projekte und Lageübersichten\nExec='+desktop_quote(exe)+'\nIcon=kor-workstation\nTerminal=false\nCategories=Office;Utility;Development;\nKeywords=Kor;Notizen;Projekte;Archiv;Atlas;SQLite;\nStartupNotify=true\n',encoding='utf-8')
dest.chmod(0o644)
PY
python3 -m py_compile "$APP_DIR/core/server.py" "$APP_DIR/core/engine.py" "$APP_DIR/core/ai_provider.py"
printf '\nKOR-NEXUS wurde für diesen Benutzer installiert.\n'
printf 'Start: Anwendungsmenü „KOR-NEXUS“ oder %q\n' "$BIN_DIR/kor-workstation"
printf 'Stop:  %q\n' "$BIN_DIR/kor-workstation-stop"
printf 'Datenbank/Backups bleiben getrennt unter: %s/kor-workstation\n' "$DATA_HOME"
printf 'Startprotokoll (max. zwei Generationen): %s/server.log\n' "$LOG_DIR"
printf 'Browser: Chromium/Chrome wird bevorzugt; Firefox oder xdg-open/gio sind Fallbacks.\n'
