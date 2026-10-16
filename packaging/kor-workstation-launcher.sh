#!/usr/bin/env bash
set -euo pipefail
umask 077
APP_DIR=/opt/kor-workstation
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/kor-workstation"
mkdir -p "$LOG_DIR"
chmod 700 "$LOG_DIR"
if [[ -f "$LOG_DIR/server.log" && $(stat -c %s "$LOG_DIR/server.log" 2>/dev/null || echo 0) -gt 5242880 ]]; then
  mv -f "$LOG_DIR/server.log" "$LOG_DIR/server.log.1"
fi
if ! command -v python3 >/dev/null 2>&1; then
  printf 'KOR-NEXUS benötigt Python 3. Bitte installiere das Paket python.\n' >&2
  exit 127
fi
exec python3 "$APP_DIR/core/server.py" >> "$LOG_DIR/server.log" 2>&1
