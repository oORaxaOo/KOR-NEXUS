#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v pacman >/dev/null 2>&1 || ! command -v makepkg >/dev/null 2>&1; then
  printf 'Dieses Skript benötigt Arch Linux oder eine Arch-basierte Distribution mit pacman und makepkg.\n' >&2
  exit 2
fi
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  printf 'Bitte makepkg als normaler Benutzer ausführen, nicht als root.\n' >&2
  exit 2
fi
for path in PKGBUILD scripts/create-source-archive.py; do
  [[ -s "$ROOT/$path" ]] || { printf 'Projektdatei fehlt: %s\n' "$path" >&2; exit 2; }
done
command -v python3 >/dev/null 2>&1 || { printf 'Python 3 fehlt.\n' >&2; exit 127; }
printf 'KOR-NEXUS: Erzeuge das Quellarchiv und baue das Arch-Paket …\n'
python3 scripts/create-source-archive.py
makepkg --syncdeps --cleanbuild --force --noconfirm
shopt -s nullglob
packages=("$ROOT"/kor-workstation-*.pkg.tar.*)
shopt -u nullglob
if [[ "${#packages[@]}" -ne 1 || ! -s "${packages[0]}" ]]; then
  printf 'Erwartet wurde genau ein gebautes Paket; gefunden: %s.\n' "${#packages[@]}" >&2
  exit 3
fi
printf '\nPaket erstellt: %s\n' "${packages[0]}"
printf 'Jetzt wird pacman zur Installation mit Administratorbestätigung aufgerufen.\n'
sudo pacman -U -- "${packages[0]}"
printf '\nInstallation abgeschlossen. Öffne im KDE-Anwendungsmenü „KOR-NEXUS“.\n'
printf 'Zum Beenden des lokalen Servers: kor-workstation-stop\n'
