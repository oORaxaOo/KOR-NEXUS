#!/usr/bin/env bash
# Provider-neutral CI entry point. Use unchanged in local shells or CI runners.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
MODE="${1:-full}"
case "$MODE" in quick|full) ;; *) echo 'Verwendung: scripts/ci.sh [quick|full]' >&2; exit 2;; esac
printf 'KOR-NEXUS CI-Gate | mode=%s | project=%s\n' "$MODE" "$ROOT"
bash scripts/release-check.sh "$MODE"
printf 'CI-Gate erfolgreich. Der plattformunabhängige Prüflauf baut kein Arch-Paket und installiert nichts. Der native Paketbau läuft separat in .github/workflows/release.yml auf Arch Linux.\n'
