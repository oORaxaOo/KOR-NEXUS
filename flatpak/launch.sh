#!/bin/sh
set -eu
cd /app/share/kor-nexus
exec python3 core/server.py
