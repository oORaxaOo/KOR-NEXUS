"""Local-only emergency media vault for KOR-NEXUS."""
from __future__ import annotations
import mimetypes, os, shutil, sqlite3
from pathlib import Path

DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "kor-workstation"
MEDIA_DIR = DATA_HOME / "emergency_vault"
DB_PATH = DATA_HOME / "kor-workstation.sqlite3"
ALLOWED_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".ogv", ".mp3", ".m4a", ".ogg", ".opus", ".wav", ".flac"}

def init_media_db():
    DATA_HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    try: os.chmod(MEDIA_DIR, 0o700)
    except OSError: pass
    with sqlite3.connect(DB_PATH, timeout=15) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS emergency_media (
          id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
          category TEXT NOT NULL DEFAULT 'Video', filename TEXT NOT NULL UNIQUE,
          is_favorite INTEGER NOT NULL DEFAULT 0)""")
        con.commit()

def _safe_file(name: str) -> Path | None:
    if not isinstance(name, str) or not name or name in {".", ".."} or Path(name).name != name or "/" in name or "\\" in name:
        return None
    path = (MEDIA_DIR / name).resolve()
    try: path.relative_to(MEDIA_DIR.resolve())
    except ValueError: return None
    if path.suffix.lower() not in ALLOWED_EXTENSIONS: return None
    return path

def check_emergency_readiness():
    init_media_db()
    with sqlite3.connect(DB_PATH, timeout=15) as con:
        con.row_factory = sqlite3.Row
        for path in MEDIA_DIR.iterdir():
            if path.is_file() and _safe_file(path.name):
                con.execute("INSERT OR IGNORE INTO emergency_media(title,category,filename) VALUES(?,?,?)",
                            (path.stem.replace("_", " "), "Audio" if path.suffix.lower() in {".mp3",".m4a",".ogg",".opus",".wav",".flac"} else "Video", path.name))
        con.commit()
        rows = [dict(row) for row in con.execute("SELECT id,title,category,filename,is_favorite FROM emergency_media ORDER BY is_favorite DESC,title COLLATE NOCASE")]
    items=[]; missing=0; ready=0
    for row in rows:
        path=_safe_file(row["filename"])
        available=bool(path and path.is_file() and os.access(path, os.R_OK))
        size=0
        if available:
            try:
                with path.open("rb") as stream:
                    stream.read(1)
                size=path.stat().st_size
                ready += 1
            except OSError:
                available=False
        if not available: missing += 1
        items.append({**row, "is_favorite":bool(row["is_favorite"]), "available":available,
                      "size_bytes":size, "path":"/local-media/"+__import__("urllib.parse",fromlist=["quote"]).quote(row["filename"]) if available else None})
    usage=shutil.disk_usage(MEDIA_DIR)
    return {"readiness_score":round(ready/max(len(items),1)*100), "free_storage_gb":round(usage.free/(1024**3),1),
            "total_items":len(items),"available_items":ready,"missing_items":missing,"vault_dir":str(MEDIA_DIR),"items":items}

def media_path(filename: str) -> Path | None:
    path=_safe_file(filename)
    return path if path and path.is_file() and os.access(path, os.R_OK) else None

def media_mime(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"

def set_media_favorite(file_id: int, favorite: bool) -> bool:
    init_media_db()
    with sqlite3.connect(DB_PATH, timeout=15) as con:
        cur=con.execute("UPDATE emergency_media SET is_favorite=? WHERE id=?", (1 if favorite else 0, int(file_id)))
        con.commit()
        return cur.rowcount > 0
