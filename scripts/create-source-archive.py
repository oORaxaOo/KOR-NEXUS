#!/usr/bin/env python3
"""Create a deterministic source archive; the outer PKGBUILD pins its hash."""
from __future__ import annotations
import gzip, hashlib, io, os, re, shutil, sys, tarfile, tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
pkgbuild = (root / 'PKGBUILD').read_text(encoding='utf-8')
version_match = re.search(r'^pkgver=(\S+)$', pkgbuild, re.M)
name_match = re.search(r'^pkgname=(\S+)$', pkgbuild, re.M)
if not version_match or not name_match:
    raise SystemExit('FEHLER: pkgname/pkgver fehlen in PKGBUILD')
version, name = version_match.group(1), name_match.group(1)
server = (root / 'core/server.py').read_text(encoding='utf-8')
if not re.search(rf"^VERSION\s*=\s*['\"]{re.escape(version)}['\"]", server, re.M):
    raise SystemExit('FEHLER: pkgver und core/server.py VERSION stimmen nicht überein')

exclude_dirs = {'.git', 'node_modules', 'dist', 'src-tauri', 'archive', 'preview', '__pycache__', 'backups'}
exclude_suffixes = {'.pyc', '.sqlite3'}
def ignored(path: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in exclude_dirs for part in rel.parts): return True
    if path.name.endswith('.tar.gz') or path.name.endswith('.pkg.tar.zst') or path.name.endswith('.pkg.tar.xz'): return True
    if path.name in {'SOURCE_SHA256SUMS.txt'}: return True
    if path.suffix in exclude_suffixes: return True
    return False

with tempfile.TemporaryDirectory(prefix='kor-nexus-release-') as tmp:
    stage = Path(tmp) / 'source'
    stage.mkdir()
    for item in root.iterdir():
        if ignored(item): continue
        dest = stage / item.name
        if item.is_dir(): shutil.copytree(item, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        elif item.is_file(): shutil.copy2(item, dest)
    # Break the impossible self-hash cycle: the outer PKGBUILD pins the archive hash.
    staged_pkg = stage / 'PKGBUILD'
    staged_text = staged_pkg.read_text(encoding='utf-8')
    staged_text = re.sub(r"^sha256sums=\('[0-9a-fA-F]{64}'\)", "sha256sums=('PINNED_BY_OUTER_PKGBUILD')", staged_text, flags=re.M)
    staged_pkg.write_text(staged_text, encoding='utf-8')
    archive = root / f'{name}-{version}.tar.gz'
    with archive.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode='w', format=tarfile.PAX_FORMAT) as tar:
            for path in sorted(stage.rglob('*'), key=lambda p: p.relative_to(stage).as_posix()):
                rel = Path('.') / path.relative_to(stage)
                info = tar.gettarinfo(str(path), arcname=rel.as_posix())
                info.uid = info.gid = 0; info.uname = info.gname = 'root'; info.mtime = 0
                info.pax_headers = {}
                if path.is_file():
                    with path.open('rb') as src: tar.addfile(info, src)
                else: tar.addfile(info)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    outer = (root / 'PKGBUILD').read_text(encoding='utf-8')
    outer = re.sub(r"^sha256sums=\('[^']+'\)", f"sha256sums=('{digest}')", outer, flags=re.M)
    (root / 'PKGBUILD').write_text(outer, encoding='utf-8')
    (root / 'SOURCE_SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(f'Quellarchiv: {archive}')
    print(f'SHA-256: {digest}')
