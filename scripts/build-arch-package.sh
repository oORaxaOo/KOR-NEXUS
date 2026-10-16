#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then echo 'Bitte als normaler Benutzer ausführen, nicht als root.' >&2; exit 2; fi
INSTALL_AFTER_BUILD=0
if [[ "${1:-}" == "--install" ]]; then INSTALL_AFTER_BUILD=1; elif [[ -n "${1:-}" ]]; then echo 'Verwendung: scripts/build-arch-package.sh [--install]' >&2; exit 2; fi
command -v makepkg >/dev/null 2>&1 || { echo 'NICHT VERFÜGBAR: makepkg fehlt. Es wurde kein Arch-Paket gebaut.' >&2; exit 2; }
# Run the complete release gate before invoking the actual Arch package builder.
bash scripts/release-check.sh full
if (( INSTALL_AFTER_BUILD )); then
  echo 'Paketbau mit anschließender ausdrücklich angeforderter Installation.'
  makepkg -si
else
  echo 'Paketbau ohne Installation.'
  makepkg -f
  echo 'Paket wurde gebaut, aber nicht installiert.'
fi
