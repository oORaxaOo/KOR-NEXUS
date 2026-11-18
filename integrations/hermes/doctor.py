"""Run a read-only connectivity check against the local KOR-NEXUS instance."""
from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations.hermes.kor_client import KorNexusClient, KorNexusError


def main() -> int:
    try:
        client = KorNexusClient()
        status = client.get_status()
        print(json.dumps({"connected": True, "kor_nexus": status}, ensure_ascii=False, indent=2))
        return 0
    except KorNexusError as exc:
        print(json.dumps({"connected": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
