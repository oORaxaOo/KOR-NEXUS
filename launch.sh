#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null 2>&1 || { echo 'KOR-NEXUS benötigt Python 3.' >&2; exit 1; }
exec python3 "$ROOT/core/server.py"
