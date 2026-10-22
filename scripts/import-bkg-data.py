#!/usr/bin/env python3
"""Download BKG VG250 Länder polygons, transform to WGS84 with GDAL, and import locally."""
from __future__ import annotations
import datetime, json, os, shutil, sqlite3, subprocess, sys, tempfile, urllib.request, zipfile
from pathlib import Path
BKG_URL = "https://daten.gdz.bkg.bund.de/produkte/vg/vg250_ebenen_0101/aktuell/vg250_01-01.utm32s.shape.ebenen.zip"
MAX_DOWNLOAD = 120 * 1024 * 1024
STATE_NAMES = {"Baden-Württemberg","Bayern","Berlin","Brandenburg","Bremen","Hamburg","Hessen","Mecklenburg-Vorpommern","Niedersachsen","Nordrhein-Westfalen","Rheinland-Pfalz","Saarland","Sachsen","Sachsen-Anhalt","Schleswig-Holstein","Thüringen"}
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home()/".local/share"))/"kor-workstation"
DB_PATH = DATA_HOME/"kor-workstation.sqlite3"
OUTPUT = DATA_HOME/"geodata"/"germany-states.geojson"

def safe_extract(zf, target):
    root=target.resolve()
    for item in zf.infolist():
        dest=(target/item.filename).resolve()
        if dest != root and root not in dest.parents: raise ValueError("Unsicherer Pfad im ZIP-Archiv.")
    zf.extractall(target)

def download(path):
    req=urllib.request.Request(BKG_URL,headers={"User-Agent":"KOR-NEXUS geodata importer"})
    total=0
    with urllib.request.urlopen(req,timeout=45) as response, path.open("wb") as out:
        if response.status != 200: raise RuntimeError("BKG HTTP "+str(response.status))
        while True:
            chunk=response.read(1024*1024)
            if not chunk: break
            total+=len(chunk)
            if total>MAX_DOWNLOAD: raise RuntimeError("Download überschreitet 120 MiB.")
            out.write(chunk)
    if total<1024: raise RuntimeError("Download ist unerwartet klein.")

def convert(extract_dir):
    if not shutil.which("ogr2ogr"): raise RuntimeError("GDAL/ogr2ogr fehlt. Installiere unter Arch Linux: sudo pacman -S gdal")
    shapes=list(extract_dir.rglob("VG250_LAN.shp"))+list(extract_dir.rglob("*LAN*.shp"))
    if not shapes: raise RuntimeError("Keine Shapefile-Länderebene (LAN) im BKG-Archiv gefunden.")
    with tempfile.TemporaryDirectory(prefix="kor-bkg-convert-") as tmp:
        dest=Path(tmp)/"states.geojson"
        proc=subprocess.run(["ogr2ogr","-f","GeoJSON","-t_srs","EPSG:4326",str(dest),str(shapes[0])],capture_output=True,text=True,timeout=180)
        if proc.returncode: raise RuntimeError("ogr2ogr: "+proc.stderr[-1200:])
        raw=json.loads(dest.read_text(encoding="utf-8"))
    features=[]
    for f in raw.get("features",[]):
        p=f.get("properties") or {}; name=p.get("GEN") or p.get("LAN_NAME") or p.get("NAME_1") or p.get("NAME")
        geom=f.get("geometry")
        if name in STATE_NAMES and geom and geom.get("type") in ("Polygon","MultiPolygon"):
            features.append({"type":"Feature","properties":{"name":name,"ags":p.get("AGS") or p.get("ARS") or p.get("LAN") or ""},"geometry":geom})
    found={f["properties"]["name"] for f in features}
    if len(features)!=16 or found!=STATE_NAMES: raise RuntimeError("Bundesland-Validierung fehlgeschlagen; fehlend: "+", ".join(sorted(STATE_NAMES-found)))
    return {"type":"FeatureCollection","name":"BKG VG250 Ländergrenzen (EPSG:4326)","source":"Bundesamt für Kartographie und Geodäsie (BKG), VG250, dl-de/by-2-0","features":sorted(features,key=lambda f:f["properties"]["name"])}

def import_db(data):
    DATA_HOME.mkdir(parents=True,exist_ok=True,mode=0o700); OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(data,ensure_ascii=False,separators=(",",":"))
    # Write the validated file atomically, then persist the same data to SQLite.
    tmp=OUTPUT.with_suffix(".geojson.tmp"); tmp.write_text(payload,encoding="utf-8"); tmp.replace(OUTPUT)
    with sqlite3.connect(DB_PATH,timeout=15) as con:
        con.execute("CREATE TABLE IF NOT EXISTS geodata_features(id INTEGER PRIMARY KEY AUTOINCREMENT,feature_type TEXT NOT NULL DEFAULT 'bundesland',name TEXT NOT NULL UNIQUE,ags TEXT,geometry_json TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS geodata_assets(key TEXT PRIMARY KEY,geojson TEXT NOT NULL,updated_at TEXT NOT NULL)")
        now=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        for f in data["features"]:
            p=f["properties"]
            con.execute("""INSERT INTO geodata_features(feature_type,name,ags,geometry_json) VALUES('bundesland',?,?,?) ON CONFLICT(name) DO UPDATE SET ags=excluded.ags,geometry_json=excluded.geometry_json""",(p["name"],str(p["ags"]),json.dumps(f["geometry"],ensure_ascii=False,separators=(",",":"))))
        con.execute("""INSERT INTO geodata_assets(key,geojson,updated_at) VALUES('germany-states',?,?) ON CONFLICT(key) DO UPDATE SET geojson=excluded.geojson,updated_at=excluded.updated_at""",(payload,now))
    try: os.chmod(DB_PATH,0o600)
    except OSError: pass

def main():
    if not shutil.which("ogr2ogr"): print("Fehler: GDAL/ogr2ogr fehlt (Arch Linux: sudo pacman -S gdal).",file=sys.stderr); return 2
    try:
        with tempfile.TemporaryDirectory(prefix="kor-bkg-") as tmp:
            tmp=Path(tmp); archive=tmp/"vg250.zip"; extracted=tmp/"data"; extracted.mkdir()
            print("Lade offizielle BKG-VG250-Daten herunter …"); download(archive)
            print("Entpacke geprüftes Archiv …")
            with zipfile.ZipFile(archive) as zf: safe_extract(zf,extracted)
            print("Transformiere Geometrien nach EPSG:4326 …"); data=convert(extracted); import_db(data)
        print("OK: 16 Bundesländer in GeoJSON und SQLite importiert: "+str(OUTPUT))
        print("Quellenhinweis: BKG, dl-de/by-2-0"); return 0
    except Exception as exc: print("Import fehlgeschlagen: "+str(exc),file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
