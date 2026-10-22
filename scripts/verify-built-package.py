#!/usr/bin/env python3
"""Verify metadata and essential payload paths in a package built by makepkg."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: verify-built-package.py PACKAGE")
pkg = Path(sys.argv[1])
if not pkg.is_file() or pkg.stat().st_size == 0:
    raise SystemExit(f"Package missing or empty: {pkg}")
info = subprocess.run(["pacman", "-Qp", "--info", str(pkg)], check=True, text=True, capture_output=True).stdout
listing = subprocess.run(["pacman", "-Qp", "--list", str(pkg)], check=True, text=True, capture_output=True).stdout
for token in ("Name            : kor-workstation", "Version         : 1.20.0"):
    if token not in info:
        raise SystemExit(f"Package metadata missing expected value: {token}")
for expected in (
    "opt/kor-workstation/core/server.py",
    "opt/kor-workstation/core/window.py",
    "opt/kor-workstation/core/github_integration.py",
    "opt/kor-workstation/web/js/hud.js",
    "opt/kor-workstation/web/github.html",
    "opt/kor-workstation/web/js/github-center.js",
    "usr/share/doc/kor-workstation/GITHUB_CENTER.md",
    "opt/kor-workstation/web/geodata/world.geojson",
    "usr/bin/kor-workstation",
    "usr/bin/kor-workstation-stop",
    "usr/share/applications/kor-workstation.desktop",
):
    if expected not in listing:
        raise SystemExit(f"Package file missing: {expected}")
print(f"OK package metadata and payload: {pkg}")
