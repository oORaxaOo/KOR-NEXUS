#!/usr/bin/env bash
set -euo pipefail
LAUNCHER="$HOME/.local/bin/kor-workstation"
ICON="$HOME/.local/share/icons/hicolor/scalable/apps/kor-workstation.svg"
DESKTOP_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
DEST="$DESKTOP_DIR/kor-workstation.desktop"
if [[ ! -x "$LAUNCHER" ]]; then
  printf 'KOR-NEXUS ist noch nicht benutzerspezifisch installiert. Führe zuerst ./install-user.sh aus.\n' >&2
  exit 2
fi
mkdir -p "$DESKTOP_DIR"
python3 - "$LAUNCHER" "$ICON" "$DEST" <<'PY'
import sys
from pathlib import Path
launcher, icon, target = sys.argv[1:]
def quote(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$') + '"'
text = ('[Desktop Entry]\nType=Application\nName=KOR-NEXUS\nComment=Lokale Kor-Workstation starten\n'
        + f'Exec={quote(launcher)}\nIcon={icon}\n'
        + 'Terminal=false\nCategories=Office;Utility;Development;\nStartupNotify=true\n')
path = Path(target)
path.write_text(text, encoding='utf-8')
path.chmod(0o755)
print(f'Desktop-Verknüpfung erstellt: {path}')
PY
printf 'Hinweis: KDE kann beim ersten Start eine Sicherheitsbestätigung für die Desktop-Verknüpfung anzeigen.\n'
