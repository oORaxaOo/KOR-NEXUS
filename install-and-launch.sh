#!/usr/bin/env bash
set -euo pipefail

# One-time setup and immediate launch for a complete KOR-NEXUS source checkout.
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -s "$ROOT/install-user.sh" || ! -s "$ROOT/core/server.py" || ! -s "$ROOT/web/index.html" ]]; then
  printf 'KOR-NEXUS: Bitte das vollständige Projektarchiv zuerst entpacken und dieses Skript aus dem Projektordner starten.\n' >&2
  exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
  printf 'KOR-NEXUS benötigt Python 3. Bitte über die Softwareverwaltung deiner Linux-Distribution installieren und erneut starten.\n' >&2
  exit 127
fi

printf 'KOR-NEXUS wird für deinen Benutzer eingerichtet …\n'
bash "$ROOT/install-user.sh"

LAUNCHER="$HOME/.local/bin/kor-workstation"
if [[ ! -x "$LAUNCHER" ]]; then
  printf 'Installation abgeschlossen, aber der Starter wurde nicht gefunden: %s\n' "$LAUNCHER" >&2
  exit 3
fi

# Start detached so the setup terminal can close. The application opens its own
# native desktop window and writes diagnostics to its private state log.
nohup "$LAUNCHER" >/dev/null 2>&1 </dev/null &
printf '\nFertig. KOR-NEXUS wird gestartet und sollte gleich sein eigenständiges Desktopfenster öffnen.\n'
printf 'Später genügt ein Klick auf „KOR-NEXUS“ im Anwendungsmenü.\n'
printf 'Falls kein Fenster erscheint, siehe: ${XDG_STATE_HOME:-$HOME/.local/state}/kor-workstation/server.log\n'
