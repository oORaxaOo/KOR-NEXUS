#!/usr/bin/env python3
"""KOR-NEXUS local-first core. Standard library only; loopback-bound."""
from __future__ import annotations
import concurrent.futures, datetime as dt, fcntl, html, json, math, os, re, shutil, socket, sqlite3, sys, threading, time, urllib.error, urllib.parse, urllib.request, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.etree import ElementTree as ET
try:
    from core import mesh
    from core.simulation import simulate_resource_runway
except ModuleNotFoundError:
    # Support launchers that execute core/server.py by absolute path from any working directory.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core import mesh
    from core.simulation import simulate_resource_runway

from core.media import check_emergency_readiness, media_path, media_mime, init_media_db, set_media_favorite
from core import github_integration

APP_NAME = 'KOR-NEXUS'
VERSION = '1.20.0'
ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'
DATA_HOME = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'kor-workstation'
DB_PATH = DATA_HOME / 'kor-workstation.sqlite3'
BACKUP_DIR = DATA_HOME / 'backups'
GEODATA_DIR = DATA_HOME / 'geodata'
GERMANY_STATES_FILE = GEODATA_DIR / 'germany-states.geojson'
MAX_BODY = 12 * 1024 * 1024
BACKUP_KEEP = 12
BACKUP_INTERVAL = 30 * 60
UPLOAD_DIR = DATA_HOME / 'archive_attachments'
_system_logs = []
_system_logs_lock = threading.Lock()
FEEDS = [
  {'key':'tagesschau','name':'tagesschau.de','url':'https://www.tagesschau.de/index~rss2.xml'},
  {'key':'deutschlandfunk','name':'Deutschlandfunk','url':'https://www.deutschlandfunk.de/nachrichten-100.rss'},
  {'key':'welt','name':'WELT','url':'https://www.welt.de/feeds/latest.rss'},
]
MODULES = ('atlas','projects','archive','simulation','database')
STATE_NAMES = ['Baden-Württemberg','Bayern','Berlin','Brandenburg','Bremen','Hamburg','Hessen','Mecklenburg-Vorpommern','Niedersachsen','Nordrhein-Westfalen','Rheinland-Pfalz','Saarland','Sachsen','Sachsen-Anhalt','Schleswig-Holstein','Thüringen']
_db_lock = threading.RLock()
_backup_lock = threading.Lock()
_last_backup_monotonic = 0.0
_instance_lock_fd = None


def utcnow(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def add_system_log(level, component, message):
    entry={'time':time.strftime('%H:%M:%S'),'level':str(level)[:20],'component':str(component)[:40],'message':str(message)[:300]}
    with _system_logs_lock:
        _system_logs.append(entry)
        del _system_logs[:-50]

def get_system_health():
    result={'cpu_load_1min':None,'ram_used_pct':None,'storage_free_gb':None,'platform':sys.platform}
    try:
        with open('/proc/loadavg',encoding='ascii') as stream: result['cpu_load_1min']=float(stream.read().split()[0])
    except (OSError,ValueError,IndexError): pass
    try:
        memory={}
        with open('/proc/meminfo',encoding='ascii') as stream:
            for line in stream:
                key,sep,value=line.partition(':')
                if sep: memory[key]=int(value.split()[0])
        total=memory.get('MemTotal'); available=memory.get('MemAvailable')
        if total and available is not None: result['ram_used_pct']=round((total-available)/total*100,1)
    except (OSError,ValueError,IndexError): pass
    try:
        stat=os.statvfs(str(DATA_HOME))
        result['storage_free_gb']=round(stat.f_bavail*stat.f_frsize/(1024**3),1)
    except OSError: pass
    return result

def geojson_wgs84_coordinates_valid(value):
    """Validate nested GeoJSON coordinate arrays as WGS84 lon/lat pairs."""
    seen=0
    def walk(node):
        nonlocal seen
        if not isinstance(node,list) or not node: return False
        if len(node)>=2 and isinstance(node[0],(int,float)) and not isinstance(node[0],bool) and isinstance(node[1],(int,float)) and not isinstance(node[1],bool):
            lon,lat=float(node[0]),float(node[1]);seen+=1
            return -180<=lon<=180 and -90<=lat<=90 and seen<=2_000_000
        return all(walk(child) for child in node)
    return walk(value) and seen>0

class ClosingSQLiteConnection(sqlite3.Connection):
    """Keep sqlite's commit/rollback context behavior and always release the handle."""
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def db_connect():
    DATA_HOME.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15, factory=ClosingSQLiteConnection)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=15000')
    return con


def initialize():
    global _last_backup_monotonic
    DATA_HOME.mkdir(parents=True, exist_ok=True, mode=0o700); BACKUP_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Personal notes and backups are private to the local user by default.
    for private_dir in (DATA_HOME, BACKUP_DIR):
        try: os.chmod(private_dir, 0o700)
        except OSError: pass
    for partial in BACKUP_DIR.glob('kor-*.sqlite3.partial'):
        try: partial.unlink()
        except OSError: pass
    with _db_lock, db_connect() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript('''
          CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL CHECK(length(title)<=180),area TEXT NOT NULL DEFAULT 'SYSTEM',done INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY AUTOINCREMENT,module TEXT NOT NULL CHECK(module IN ('atlas','projects','archive','simulation','database')),title TEXT NOT NULL CHECK(length(title)<=180),body TEXT NOT NULL DEFAULT '',region TEXT NOT NULL DEFAULT '',tags TEXT NOT NULL DEFAULT '[]',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS idx_records_module_updated ON records(module, updated_at DESC);
          CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS units(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL CHECK(length(name)<=180),role TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'aktiv',biography TEXT NOT NULL DEFAULT '',region TEXT NOT NULL DEFAULT '',tags TEXT NOT NULL DEFAULT '[]',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS resources(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL CHECK(length(name)<=180),category TEXT NOT NULL DEFAULT 'Allgemein',quantity REAL NOT NULL DEFAULT 0 CHECK(quantity>=0),unit TEXT NOT NULL DEFAULT 'Stück',location TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS project_assignments(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,unit_id INTEGER REFERENCES units(id) ON DELETE SET NULL,resource_id INTEGER REFERENCES resources(id) ON DELETE SET NULL,quantity REAL NOT NULL DEFAULT 0 CHECK(quantity>=0),notes TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,CHECK((unit_id IS NOT NULL AND resource_id IS NULL) OR (unit_id IS NULL AND resource_id IS NOT NULL)));
          CREATE TABLE IF NOT EXISTS map_locations(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL CHECK(length(title)<=180),kind TEXT NOT NULL DEFAULT 'Projekt',region TEXT NOT NULL DEFAULT '',latitude REAL NOT NULL CHECK(latitude BETWEEN -90 AND 90),longitude REAL NOT NULL CHECK(longitude BETWEEN -180 AND 180),project_id INTEGER REFERENCES records(id) ON DELETE SET NULL,notes TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'geplant',progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,unit_id INTEGER REFERENCES units(id) ON DELETE SET NULL,resource_id INTEGER REFERENCES resources(id) ON DELETE SET NULL);
          CREATE INDEX IF NOT EXISTS idx_map_locations_region ON map_locations(region);
          CREATE TABLE IF NOT EXISTS geodata_assets(key TEXT PRIMARY KEY, geojson TEXT NOT NULL, updated_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS geodata_features(id INTEGER PRIMARY KEY AUTOINCREMENT,feature_type TEXT NOT NULL DEFAULT 'bundesland',name TEXT NOT NULL UNIQUE,ags TEXT,geometry_json TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS feed_items(id TEXT PRIMARY KEY,source_key TEXT NOT NULL,source_name TEXT NOT NULL,title TEXT NOT NULL,summary TEXT NOT NULL DEFAULT '',url TEXT NOT NULL,published TEXT NOT NULL DEFAULT '',fetched_at TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS idx_feed_published ON feed_items(published DESC);
          CREATE TABLE IF NOT EXISTS feed_status(source_key TEXT PRIMARY KEY,source_name TEXT NOT NULL,last_attempt TEXT,last_success TEXT,status TEXT NOT NULL DEFAULT 'Noch nicht abgerufen',item_count INTEGER NOT NULL DEFAULT 0);
        ''')
        con.execute('INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(1,?)',(utcnow(),))
        con.execute('INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(2,?)',(utcnow(),))
        con.execute('INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(3,?)',(utcnow(),))
        con.execute('INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(4,?)',(utcnow(),))
        # Additive migration for strategic planning; safe for existing 1.4.x databases.
        cols={r['name'] for r in con.execute('PRAGMA table_info(map_locations)')}
        for name,definition in [('status',"TEXT NOT NULL DEFAULT 'geplant'"),('progress','INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100)'),('task_id','INTEGER REFERENCES tasks(id) ON DELETE SET NULL'),('unit_id','INTEGER REFERENCES units(id) ON DELETE SET NULL'),('resource_id','INTEGER REFERENCES resources(id) ON DELETE SET NULL')]:
            if name not in cols: con.execute(f'ALTER TABLE map_locations ADD COLUMN {name} {definition}')
        con.execute('CREATE INDEX IF NOT EXISTS idx_map_locations_status ON map_locations(status)')
        con.execute('INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(5,?)',(utcnow(),))
        for k,v in [('language','de'),('backup_keep',str(BACKUP_KEEP)),('backup_interval_minutes','30'),('last_news_refresh',''),('unit_label_singular','Mitglied'),('unit_label_plural','Mitglieder')]:
            con.execute('INSERT OR IGNORE INTO settings(key,value,updated_at) VALUES(?,?,?)',(k,v,utcnow()))
        con.commit()
    try: os.chmod(DB_PATH, 0o600)
    except OSError: pass
    # A database that already existed is checkpointed on start, before normal use.
    try:
        create_backup('startup')
        _last_backup_monotonic = time.monotonic()
    except Exception as exc: print(f'[KOR] Start-Backup übersprungen: {exc}', file=sys.stderr)


def get_settings(con=None):
    own = con is None
    if own: con = db_connect()
    try: return {r['key']:r['value'] for r in con.execute('SELECT key,value FROM settings')}
    finally:
        if own: con.close()


def prune_backups(keep=None):
    try: keep = max(3,min(50,int(keep or get_settings().get('backup_keep',BACKUP_KEEP))))
    except Exception: keep=BACKUP_KEEP
    files=sorted(BACKUP_DIR.glob('kor-*.sqlite3'),key=lambda p:p.stat().st_mtime,reverse=True)
    for f in files[keep:]:
        try:f.unlink()
        except OSError:pass


def create_backup(reason='automatic', prune=True):
    global _last_backup_monotonic
    # SQLite's online backup API provides a consistent snapshot while writers
    # continue; only backup creation is serialized to avoid lock-order deadlocks.
    with _backup_lock:
        DATA_HOME.mkdir(parents=True,exist_ok=True); BACKUP_DIR.mkdir(parents=True,exist_ok=True)
        stamp=dt.datetime.now().strftime('%Y%m%d-%H%M%S')
        dest=BACKUP_DIR / f'kor-{stamp}-{re.sub("[^a-z0-9-]", "", reason.lower())[:16] or "manual"}-{uuid.uuid4().hex[:6]}.sqlite3'
        if not DB_PATH.exists():
            with db_connect() as con: con.execute('PRAGMA user_version=1')
        # Publish only a complete, verified backup. A crash must never leave a
        # half-written file that looks like a valid restore point.
        partial=dest.with_suffix(dest.suffix+'.partial')
        src=sqlite3.connect(DB_PATH,timeout=15)
        dst=sqlite3.connect(partial)
        try:
            src.backup(dst)
            check=dst.execute('PRAGMA integrity_check').fetchone()[0]
            if check!='ok': raise RuntimeError(f'Backupintegrität fehlgeschlagen: {check}')
        except Exception:
            dst.close();src.close()
            partial.unlink(missing_ok=True)
            raise
        else:
            dst.close();src.close()
        os.chmod(partial,0o600)
        os.replace(partial,dest)
        _last_backup_monotonic=time.monotonic()
        if prune: prune_backups()
        return {'name':dest.name,'size':dest.stat().st_size,'created_at':dt.datetime.fromtimestamp(dest.stat().st_mtime,dt.timezone.utc).isoformat(),'reason':reason}


def maybe_backup():
    global _last_backup_monotonic
    settings=get_settings()
    try: interval=max(5,int(settings.get('backup_interval_minutes','30')))*60
    except ValueError: interval=1800
    if time.monotonic()-_last_backup_monotonic>=interval:
        try:create_backup('automatic')
        except Exception as exc: print(f'[KOR] Automatisches Backup fehlgeschlagen: {exc}',file=sys.stderr)


def unit_dict(r):
    d=dict(r); d['tags']=json.loads(d.get('tags') or '[]'); return d

def task_dict(r): return {'id':r['id'],'title':r['title'],'area':r['area'],'done':bool(r['done']),'created_at':r['created_at'],'updated_at':r['updated_at']}
def record_dict(r): return {'id':r['id'],'module':r['module'],'title':r['title'],'body':r['body'],'region':r['region'],'tags':json.loads(r['tags'] or '[]'),'created_at':r['created_at'],'updated_at':r['updated_at']}


FEED_TIMEOUT_SECONDS = 5
FEED_MAX_BYTES = 2_000_000
FEED_MAX_ITEMS = 40


def _safe_http_url(value):
    """Accept only absolute HTTP(S) links without credentials or control chars."""
    if not isinstance(value, str) or len(value) > 4096 or any(ord(ch) < 32 for ch in value):
        return False
    try:
        parsed = urllib.parse.urlsplit(value.strip())
        return (parsed.scheme.lower() in ('http', 'https') and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None)
    except (ValueError, UnicodeError):
        return False


def _xml_text(node):
    return ''.join(node.itertext()).strip()


def fetch_one_feed(feed):
    source_url=feed.get('url','')
    parsed=urllib.parse.urlsplit(source_url)
    if parsed.scheme.lower() != 'https' or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError('Feed-Quelle muss eine gültige HTTPS-Adresse ohne Zugangsdaten sein.')
    req=urllib.request.Request(source_url,headers={'User-Agent':f'KOR-Workstation/{VERSION} (personal RSS reader)','Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9'})
    with urllib.request.urlopen(req,timeout=FEED_TIMEOUT_SECONDS) as response:
        status=getattr(response,'status',200)
        if status != 200: raise RuntimeError(f'HTTP {status}')
        length=response.headers.get('Content-Length') if getattr(response,'headers',None) else None
        if length:
            try:
                if int(length) > FEED_MAX_BYTES: raise ValueError('Feed überschreitet die Größenbegrenzung.')
            except ValueError as exc:
                if 'Größenbegrenzung' in str(exc): raise
        raw=response.read(FEED_MAX_BYTES+1)
    if not raw or not raw.strip(): raise ValueError('Feed-Antwort ist leer.')
    if len(raw)>FEED_MAX_BYTES: raise ValueError('Feed überschreitet die Größenbegrenzung.')
    # DTD/entity declarations are not needed by RSS/Atom and are rejected defensively.
    if re.search(br'<!\s*(DOCTYPE|ENTITY)\b',raw,re.IGNORECASE):
        raise ValueError('XML-DTD- und Entity-Deklarationen sind nicht erlaubt.')
    root=ET.fromstring(raw)
    root_tag=root.tag.rsplit('}',1)[-1].lower()
    if root_tag not in ('rss','rdf','feed'):
        raise ValueError('Antwort enthält kein unterstütztes RSS-/Atom-Dokument.')
    items=[]; seen=set()
    for node in root.iter():
        tag=node.tag.rsplit('}',1)[-1].lower()
        if tag not in ('item','entry'): continue
        def val(keys):
            for c in list(node):
                k=c.tag.rsplit('}',1)[-1].lower()
                if k in keys:
                    if k=='link':
                        href=c.attrib.get('href','').strip()
                        rel=c.attrib.get('rel','alternate').lower()
                        if href and rel in ('alternate',''): return href
                    text_value=_xml_text(c)
                    if text_value: return text_value
            return ''
        title=val({'title'})
        link=val({'link','guid','id'}).strip()
        if not title or not _safe_http_url(link): continue
        # Normalize only for identity, preserving the publisher's actual destination URL.
        identity=link.split('#',1)[0]
        if identity in seen: continue
        seen.add(identity)
        summary=val({'description','summary','subtitle','encoded','content'})
        summary=html.unescape(re.sub(r'<[^>]*>',' ',summary))
        summary=re.sub(r'\s+',' ',summary).strip()[:800]
        published=val({'pubdate','published','updated','date'})[:120]
        title=re.sub(r'[\x00-\x1f\x7f]',' ',title)
        title=re.sub(r'\s+',' ',title).strip()
        if title:
            items.append({'id':str(uuid.uuid5(uuid.NAMESPACE_URL,identity)),'source_key':feed['key'],'source_name':feed['name'],'title':title[:350],'summary':summary,'url':link,'published':published,'fetched_at':utcnow()})
        if len(items)>=FEED_MAX_ITEMS: break
    return items


def refresh_feeds():
    outcomes=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(3,max(1,len(FEEDS)))) as pool:
        futures={pool.submit(fetch_one_feed,f):f for f in FEEDS}
        for fut,feed in [(f,futures[f]) for f in futures]:
            try:
                fetched=fut.result()
                unique=[]; seen_ids=set(); seen_urls=set()
                for item in fetched:
                    identity=str(item.get('id','')); url=str(item.get('url','')).split('#',1)[0]
                    if not identity or identity in seen_ids or not _safe_http_url(url) or url in seen_urls: continue
                    seen_ids.add(identity); seen_urls.add(url); unique.append(item)
                outcomes.append((feed,unique,None))
            except Exception as exc: outcomes.append((feed,[],f'{type(exc).__name__}: {str(exc)}'[:250]))
    with _db_lock,db_connect() as con:
        for feed,items,error in outcomes:
            attempted=utcnow()
            old_count=con.execute('SELECT COUNT(*) FROM feed_items WHERE source_key=?',(feed['key'],)).fetchone()[0]
            # Failed refreshes and valid-but-empty feeds never erase the last known cache.
            if not error and items:
                con.execute('DELETE FROM feed_items WHERE source_key=?',(feed['key'],))
                con.executemany('INSERT OR REPLACE INTO feed_items(id,source_key,source_name,title,summary,url,published,fetched_at) VALUES(:id,:source_key,:source_name,:title,:summary,:url,:published,:fetched_at)',items)
            if error:
                status='Fehler: '+error
                last_success=None
                count=old_count
            elif not items:
                status='Aktuell · Feed leer; Cache beibehalten' if old_count else 'Aktuell · keine Einträge'
                last_success=attempted
                count=old_count
            else:
                status='Aktuell'
                last_success=attempted
                count=len(items)
            con.execute('INSERT INTO feed_status(source_key,source_name,last_attempt,last_success,status,item_count) VALUES(?,?,?,?,?,?) ON CONFLICT(source_key) DO UPDATE SET last_attempt=excluded.last_attempt,last_success=COALESCE(excluded.last_success,feed_status.last_success),status=excluded.status,item_count=excluded.item_count',
                        (feed['key'],feed['name'],attempted,last_success,status,count))
        con.execute("INSERT INTO settings(key,value,updated_at) VALUES('last_news_refresh',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",(utcnow(),utcnow()))
        con.commit()
    return {'sources':len(outcomes),'items':sum(len(x[1]) for x in outcomes),'errors':[{'source':f['name'],'message':e} for f,_,e in outcomes if e]}


def build_export(con):
    """Create portable schema v2. Database IDs are package-local reference keys only."""
    def rows(sql): return [dict(r) for r in con.execute(sql)]
    records=[]
    for r in con.execute('SELECT * FROM records ORDER BY id'):
        d=record_dict(r); d['id']=r['id']; records.append(d)
    return {
        'schema_version':2,'app':APP_NAME,'exported_at':utcnow(),
        'id_policy':'IDs are identifiers inside this export only; import remaps them to new local SQLite IDs.',
        'tasks':rows('SELECT * FROM tasks ORDER BY id'),
        'records':records,
        'map_locations':rows('SELECT l.*,p.title AS project_title,t.title AS task_title,u.name AS unit_name,rs.name AS resource_name FROM map_locations l LEFT JOIN records p ON p.id=l.project_id LEFT JOIN tasks t ON t.id=l.task_id LEFT JOIN units u ON u.id=l.unit_id LEFT JOIN resources rs ON rs.id=l.resource_id ORDER BY l.id'),
        'units':[unit_dict(r) for r in con.execute('SELECT * FROM units ORDER BY id')],
        'resources':rows('SELECT * FROM resources ORDER BY id'),
        'project_assignments':rows('SELECT * FROM project_assignments ORDER BY id'),
        'settings':get_settings(con),
        'geodata':{('germany_states' if r['key']=='germany-states' else r['key']):json.loads(r['geojson']) for r in con.execute('SELECT key,geojson FROM geodata_assets')},
        'news':{'items':rows('SELECT * FROM feed_items ORDER BY id'),'sources':rows('SELECT * FROM feed_status ORDER BY source_key')}
    }


def _portable_id_map(items, label):
    mapping={}
    for index,item in enumerate(items):
        if not isinstance(item,dict): raise ValueError(f'{label}: Eintrag {index+1} ist kein Objekt.')
        if 'id' not in item or item['id'] is None: continue
        key=str(item['id'])
        if not key or key in mapping: raise ValueError(f'{label}: doppelte oder leere Export-ID {key!r}.')
        mapping[key]=None
    return mapping


def _legacy_lookup(items, field, label, strict=False):
    lookup={}
    for item in items:
        key=str(item.get(field,'')).strip()
        if key: lookup.setdefault(key,[]).append(item)
    duplicates=[k for k,v in lookup.items() if len(v)>1]
    if duplicates and strict: raise ValueError(f'{label}: mehrdeutige Zuordnung über {field}: {duplicates[0]!r}.')
    return {k:v[0] for k,v in lookup.items()}


def validate_portable_import(payload):
    if not isinstance(payload,dict) or payload.get('schema_version') not in (1,2):
        raise ValueError('Ungültiges oder nicht unterstütztes Importformat (unterstützt werden Schema 1 und 2).')
    version=payload['schema_version']
    names=('tasks','records','map_locations') + (('units','resources','project_assignments') if version>=2 else ())
    limits={'tasks':50000,'records':50000,'map_locations':50000,'units':50000,'resources':50000,'project_assignments':100000}
    data={}
    for name in names:
        arr=payload.get(name,[])
        if not isinstance(arr,list) or len(arr)>limits[name]: raise ValueError(f'{name}: ungültige Liste oder zu viele Einträge.')
        data[name]=arr
    if version>=2:
        for name in ('units','resources','project_assignments'):
            if name not in payload: raise ValueError(f'Schema 2 benötigt das Feld {name}.')
    if not isinstance(payload.get('settings',{}),dict): raise ValueError('Einstellungen müssen ein JSON-Objekt sein.')
    if not isinstance(payload.get('geodata',{}),dict): raise ValueError('Geodaten müssen ein JSON-Objekt sein.')
    for key,items in data.items():
        _portable_id_map(items,key)
        if version>=2 and any(item.get('id') is None for item in items): raise ValueError(f'Schema 2 benötigt für jeden Eintrag in {key} eine Export-ID.')
    for r in data['records']:
        if r.get('module') not in MODULES or not str(r.get('title','')).strip() or len(str(r.get('title','')))>180: raise ValueError('Mindestens ein Datensatz ist ungültig.')
        if not isinstance(r.get('tags',[]),list): raise ValueError('Datensatz-Tags müssen Listen sein.')
    for t in data['tasks']:
        if not str(t.get('title','')).strip() or len(str(t.get('title','')))>180: raise ValueError('Mindestens eine Aufgabe ist ungültig.')
    for u in data.get('units',[]):
        if not str(u.get('name','')).strip() or len(str(u.get('name','')))>180 or not isinstance(u.get('tags',[]),list): raise ValueError('Mindestens ein Personenprofil ist ungültig.')
    for r in data.get('resources',[]):
        try: qty=float(r.get('quantity',0))
        except (TypeError,ValueError): raise ValueError('Ressourcenmenge ist ungültig.')
        if not str(r.get('name','')).strip() or not math.isfinite(qty) or qty<0 or qty>1e12: raise ValueError('Mindestens eine Ressource ist ungültig.')
    geo=payload.get('geodata',{})
    for key,geojson in geo.items():
        if not isinstance(key,str) or not key or not isinstance(geojson,dict): raise ValueError('Geodaten-Eintrag ist ungültig.')
        if key in ('germany-states','germany_states'):
            if geojson.get('type')!='FeatureCollection' or not isinstance(geojson.get('features'),list) or not 1<=len(geojson['features'])<=1000: raise ValueError('Bundesland-Geodaten im Import sind ungültig.')
            for feature in geojson['features']:
                geom=feature.get('geometry') if isinstance(feature,dict) else None
                if not isinstance(geom,dict) or geom.get('type') not in ('Polygon','MultiPolygon') or not geojson_wgs84_coordinates_valid(geom.get('coordinates')): raise ValueError('Importierte Bundesland-Geometrie muss Polygon/MultiPolygon in WGS84 sein.')
    # Validate explicit package-local references before touching the database.
    ids={name:{str(x['id']) for x in items if isinstance(x,dict) and x.get('id') is not None} for name,items in data.items()}
    records_by_id={str(x['id']):x for x in data['records'] if x.get('id') is not None}
    tasks_by_id={str(x['id']):x for x in data['tasks'] if x.get('id') is not None}
    units_by_id={str(x['id']):x for x in data.get('units',[]) if x.get('id') is not None}
    resources_by_id={str(x['id']):x for x in data.get('resources',[]) if x.get('id') is not None}
    projects=_legacy_lookup([r for r in data['records'] if r.get('module')=='projects'],'title','Projekte')
    tasks=_legacy_lookup(data['tasks'],'title','Aufgaben')
    units=_legacy_lookup(data.get('units',[]),'name','Personenprofile')
    resources=_legacy_lookup(data.get('resources',[]),'name','Ressourcen')
    # Legacy title fallback is accepted only if it resolves to exactly one item.
    if version==1:
        for loc in data['map_locations']:
            for field,title_field,items,label,target_ids in [('project_id','project_title',[r for r in data['records'] if r.get('module')=='projects'],'Projekt',ids['records']),('task_id','task_title',data['tasks'],'Aufgabe',ids['tasks']),('unit_id','unit_name',data.get('units',[]),'Personenprofil',ids.get('units',set())),('resource_id','resource_name',data.get('resources',[]),'Ressource',ids.get('resources',set()))]:
                if loc.get(field) not in (None,'') and str(loc.get(field)) in target_ids: continue
                name=str(loc.get(title_field,'')).strip()
                if name and sum(1 for item in items if str(item.get('title' if title_field in ('project_title','task_title') else 'name','')).strip()==name)>1:
                    raise ValueError(f'Mehrdeutige Legacy-Zuordnung für {label} {name!r}; Import abgebrochen.')
    def check_ref(item,field,target_map,target_lookup,label,allow_none=True):
        value=item.get(field)
        if value in (None,''): return
        if str(value) in target_map: return
        # For schema 2 an explicit but missing ID is never silently replaced by a title match.
        if version>=2: raise ValueError(f'{label}: Referenz {field}={value!r} zeigt auf keinen Eintrag im Export.')
        title_field={'project_id':'project_title','task_id':'task_title','unit_id':'unit_name','resource_id':'resource_name'}.get(field)
        title=str(item.get(title_field,'')).strip() if title_field else ''
        if title and title not in target_lookup: raise ValueError(f'{label}: keine eindeutige Zuordnung für {title_field}={title!r}.')
    for loc in data['map_locations']:
        if not str(loc.get('title','')).strip(): raise ValueError('Ein Kartenstandort hat keinen Titel.')
        try: lat=float(loc.get('latitude'));lon=float(loc.get('longitude'));progress=int(loc.get('progress',0) or 0)
        except (TypeError,ValueError): raise ValueError('Ein Kartenstandort hat ungültige Koordinaten/Fortschritt.')
        if not (-90<=lat<=90 and -180<=lon<=180) or not 0<=progress<=100: raise ValueError('Ein Kartenstandort liegt außerhalb gültiger Grenzen.')
        for field,target_map,target_lookup,label in [('project_id',ids['records'],projects,'Standort'),('task_id',ids['tasks'],tasks,'Standort'),('unit_id',ids.get('units',set()),units,'Standort'),('resource_id',ids.get('resources',set()),resources,'Standort')]:
            check_ref(loc,field,target_map,target_lookup,label)
        if loc.get('project_id') is not None and str(loc.get('project_id')) in records_by_id and records_by_id[str(loc['project_id'])].get('module')!='projects': raise ValueError('Standort verweist auf einen Datensatz, der kein Projekt ist.')
    for a in data.get('project_assignments',[]):
        if a.get('project_id') is None or a.get('unit_id') is None and a.get('resource_id') is None or a.get('unit_id') is not None and a.get('resource_id') is not None: raise ValueError('Zuweisung muss genau ein Personenprofil oder eine Ressource und ein Projekt referenzieren.')
        for field,target_map,label in [('project_id',ids['records'],'Projekt'),('unit_id',ids.get('units',set()),'Personenprofil'),('resource_id',ids.get('resources',set()),'Ressource')]:
            value=a.get(field)
            if value is not None and str(value) not in target_map: raise ValueError(f'Zuweisung referenziert ein unbekanntes {label} (Export-ID {value!r}).')
        if str(a.get('project_id')) in records_by_id and records_by_id[str(a['project_id'])].get('module')!='projects': raise ValueError('Zuweisung verweist auf einen Datensatz, der kein Projekt ist.')
        try: qty=float(a.get('quantity',0))
        except (TypeError,ValueError): raise ValueError('Zuweisungsmenge ist ungültig.')
        if not math.isfinite(qty) or qty<0 or qty>1e12: raise ValueError('Zuweisungsmenge ist ungültig.')
    for key,value in payload.get('settings',{}).items():
        if not isinstance(key,str) or not key or len(key)>100 or len(str(value))>10000: raise ValueError('Einstellungsschlüssel oder -wert ist ungültig.')
    news=payload.get('news',{})
    if not isinstance(news,dict) or not isinstance(news.get('items',[]),list) or not isinstance(news.get('sources',[]),list): raise ValueError('News-Cache ist ungültig.')
    news_ids=set()
    for item in news.get('items',[]):
        if not isinstance(item,dict) or any(k not in item or item[k] is None for k in ('id','source_key','source_name','title','url','fetched_at')): raise ValueError('News-Eintrag ist unvollständig.')
        key=str(item['id'])
        if not key or key in news_ids: raise ValueError('News-Cache enthält doppelte oder leere IDs.')
        news_ids.add(key)
        if len(str(item['title']))>1000 or len(str(item['url']))>10000: raise ValueError('News-Eintrag überschreitet Feldgrenzen.')
        if not _safe_http_url(str(item['url'])): raise ValueError('News-Eintrag enthält keine gültige HTTP(S)-Adresse.')
    source_ids=set()
    for item in news.get('sources',[]):
        if not isinstance(item,dict) or any(k not in item or item[k] is None for k in ('source_key','source_name')): raise ValueError('News-Quellenstatus ist unvollständig.')
        key=str(item['source_key'])
        if not key or key in source_ids: raise ValueError('News-Quellenstatus enthält doppelte Schlüssel.')
        source_ids.add(key)
        try: count=int(item.get('item_count',0))
        except (TypeError,ValueError): raise ValueError('News-Quellenstatus enthält eine ungültige Meldungsanzahl.')
        if count<0: raise ValueError('News-Quellenstatus enthält eine ungültige Meldungsanzahl.')
    data['version']=version; data['legacy_lookups']={'projects':projects,'tasks':tasks,'units':units,'resources':resources}
    return data



def portable_import_preview(payload):
    """Return a privacy-conscious, read-only import report; never writes or backs up."""
    def arr(key):
        value=payload.get(key,[]) if isinstance(payload,dict) else []
        return value if isinstance(value,list) else []
    records=arr('records'); geo=payload.get('geodata',{}) if isinstance(payload,dict) and isinstance(payload.get('geodata',{}),dict) else {}
    news=payload.get('news',{}) if isinstance(payload,dict) and isinstance(payload.get('news',{}),dict) else {}
    by_module={m:sum(1 for r in records if isinstance(r,dict) and r.get('module')==m) for m in MODULES}
    summary={'schema_version':payload.get('schema_version') if isinstance(payload,dict) else None,
             'tasks':len(arr('tasks')),'records':len(records),'records_by_module':by_module,
             'map_locations':len(arr('map_locations')),'units':len(arr('units')),
             'resources':len(arr('resources')),'project_assignments':len(arr('project_assignments')),
             'settings':len(payload.get('settings',{})) if isinstance(payload,dict) and isinstance(payload.get('settings',{}),dict) else 0,
             'geodata':len(geo),'geodata_features':sum(len(v.get('features',[])) for v in geo.values() if isinstance(v,dict) and isinstance(v.get('features'),list)),
             'news_items':len(news.get('items',[])) if isinstance(news.get('items',[]),list) else 0,
             'news_sources':len(news.get('sources',[])) if isinstance(news.get('sources',[]),list) else 0}
    issues=[]; seen=set()
    def issue(code,message):
        if code not in seen: issues.append({'code':code,'message':message});seen.add(code)
    if not isinstance(payload,dict):
        issue('invalid_format','Die Datei muss ein JSON-Objekt sein.')
    else:
        # Explicitly enumerate duplicate package IDs without exposing their values.
        keys=('tasks','records','map_locations','units','resources','project_assignments')
        for key in keys:
            items=payload.get(key,[])
            if not isinstance(items,list): continue
            values=[]
            for item in items:
                if isinstance(item,dict) and item.get('id') is not None: values.append(str(item['id']))
            if len(values)!=len(set(values)): issue('duplicate_ids',f'Doppelte Export-IDs in „{key}“ gefunden. Jede ID darf innerhalb einer Liste nur einmal vorkommen.')
        version=payload.get('schema_version')
        if version==1:
            locs=arr('map_locations')
            groups=[('project_title',[r for r in records if isinstance(r,dict) and r.get('module')=='projects'],'title','Projekt'),('task_title',arr('tasks'),'title','Aufgabe'),('unit_name',arr('units'),'name','Personenprofil'),('resource_name',arr('resources'),'name','Ressource')]
            for field,items,namefield,label in groups:
                names={}
                for item in items:
                    if isinstance(item,dict):
                        name=str(item.get(namefield,'')).strip()
                        if name:names[name]=names.get(name,0)+1
                if any(str(loc.get(field,'')).strip() and names.get(str(loc.get(field,'')).strip(),0)>1 for loc in locs if isinstance(loc,dict)):
                    issue('ambiguous_legacy_mapping',f'Mehrdeutige Legacy-Zuordnung für {label} erkannt. Der Name allein reicht nicht zur sicheren Verknüpfung.')
        try:
            validate_portable_import(payload)
        except (ValueError,TypeError,KeyError,AttributeError) as exc:
            raw=str(exc).lower()
            if 'referenz' in raw or 'referenziert' in raw or 'zuordnung' in raw or 'verweist' in raw:
                issue('missing_reference','Mindestens eine Verknüpfung fehlt, ist ungültig oder nicht eindeutig.')
            elif 'doppelte' in raw or 'doppelt' in raw:
                issue('duplicate_ids','Doppelte oder leere IDs gefunden. Bitte die Export-IDs korrigieren.')
            elif 'ungültig' in raw or 'unvollständig' in raw or 'benötigt' in raw or 'muss ' in raw:
                issue('invalid_fields','Mindestens ein Feld oder Abschnitt entspricht nicht dem unterstützten Schema.')
            else:
                issue('validation_failed','Die Datei hat die vollständige serverseitige Schema-Prüfung nicht bestanden.')
    return {'ok':True,'valid':not issues,'summary':summary,'issues':issues,
            'note':'Vorschau ist schreibgeschützt. Beim endgültigen Import wird die Datei erneut vollständig validiert.'}

def apply_portable_import(con, payload, now):
    data=validate_portable_import(payload); version=data['version']
    # Preserve current unit/resource tables on v1 browser/legacy imports; schema 1 never represented them.
    con.execute('BEGIN IMMEDIATE')
    con.execute('DELETE FROM map_locations'); con.execute('DELETE FROM project_assignments'); con.execute('DELETE FROM tasks'); con.execute('DELETE FROM records')
    if version>=2:
        con.execute('DELETE FROM units'); con.execute('DELETE FROM resources')
    task_map={};record_map={};unit_map={};resource_map={}
    for t in data['tasks']:
        cur=con.execute('INSERT INTO tasks(title,area,done,created_at,updated_at) VALUES(?,?,?,?,?)',(str(t['title']).strip(),str(t.get('area','SYSTEM'))[:80],int(bool(t.get('done'))),str(t.get('created_at',now))[:80],str(t.get('updated_at',now))[:80]))
        if t.get('id') is not None: task_map[str(t['id'])]=cur.lastrowid
    for r in data['records']:
        cur=con.execute('INSERT INTO records(module,title,body,region,tags,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(r['module'],str(r['title']).strip(),str(r.get('body',''))[:100000],str(r.get('region',''))[:180],json.dumps(r.get('tags',[]) if isinstance(r.get('tags',[]),list) else [],ensure_ascii=False),str(r.get('created_at',now))[:80],str(r.get('updated_at',now))[:80]))
        if r.get('id') is not None: record_map[str(r['id'])]=cur.lastrowid
    if version>=2:
        for u in data['units']:
            cur=con.execute('INSERT INTO units(name,role,status,biography,region,tags,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(str(u['name']).strip(),str(u.get('role',''))[:120],str(u.get('status','aktiv'))[:40],str(u.get('biography',''))[:100000],str(u.get('region',''))[:180],json.dumps(u.get('tags',[]),ensure_ascii=False),str(u.get('created_at',now))[:80],str(u.get('updated_at',now))[:80]))
            if u.get('id') is not None: unit_map[str(u['id'])]=cur.lastrowid
        for r in data['resources']:
            cur=con.execute('INSERT INTO resources(name,category,quantity,unit,location,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(str(r['name']).strip(),str(r.get('category','Allgemein'))[:80],float(r.get('quantity',0)),str(r.get('unit','Stück'))[:40],str(r.get('location',''))[:180],str(r.get('notes',''))[:10000],str(r.get('created_at',now))[:80],str(r.get('updated_at',now))[:80]))
            if r.get('id') is not None: resource_map[str(r['id'])]=cur.lastrowid
    def resolve_ref(item,field,mapping,legacy_name,lookup):
        if item.get(field) not in (None,''):
            key=str(item[field])
            if key in mapping:return mapping[key]
            if version>=2: raise ValueError(f'Ungültige Referenz {field}={key!r}.')
        name=str(item.get(legacy_name,'')).strip()
        if name and name in lookup:
            source=lookup[name]
            oldid=source.get('id')
            if oldid is not None: return mapping.get(str(oldid))
            if legacy_name=='project_title': row=con.execute("SELECT id FROM records WHERE module='projects' AND title=?",(name,)).fetchone()
            elif legacy_name=='task_title': row=con.execute('SELECT id FROM tasks WHERE title=?',(name,)).fetchone()
            elif legacy_name=='unit_name': row=con.execute('SELECT id FROM units WHERE name=?',(name,)).fetchone()
            elif legacy_name=='resource_name': row=con.execute('SELECT id FROM resources WHERE name=?',(name,)).fetchone()
            else: row=None
            return row['id'] if row else None
        return None
    lookups=data['legacy_lookups']
    for loc in data['map_locations']:
        pid=resolve_ref(loc,'project_id',record_map,'project_title',lookups['projects'])
        tid=resolve_ref(loc,'task_id',task_map,'task_title',lookups['tasks'])
        uid=resolve_ref(loc,'unit_id',unit_map,'unit_name',lookups['units']) if version>=2 else None
        rid=resolve_ref(loc,'resource_id',resource_map,'resource_name',lookups['resources']) if version>=2 else None
        # Old schema exports contain join display fields and may lack numeric IDs.
        if version==1:
            for field,table,lookup,namefield in [('project_id','records',lookups['projects'],'project_title'),('task_id','tasks',lookups['tasks'],'task_title')]:
                if loc.get(field) is None and str(loc.get(namefield,'')).strip() in lookup:
                    old=lookup[str(loc[namefield]).strip()].get('id'); mapped=(record_map if field=='project_id' else task_map).get(str(old))
                    if field=='project_id':pid=mapped
                    else:tid=mapped
        status=str(loc.get('status','geplant')); status=status if status in ('geplant','aktiv','blockiert','abgeschlossen') else 'geplant'
        con.execute('INSERT INTO map_locations(title,kind,region,latitude,longitude,project_id,notes,created_at,updated_at,status,progress,task_id,unit_id,resource_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(str(loc['title']).strip()[:180],str(loc.get('kind','Projekt'))[:40],str(loc.get('region',''))[:180],float(loc['latitude']),float(loc['longitude']),pid,str(loc.get('notes',''))[:10000],str(loc.get('created_at',now))[:80],str(loc.get('updated_at',now))[:80],status,int(loc.get('progress',0) or 0),tid,uid,rid))
    if version>=2:
        for a in data['project_assignments']:
            con.execute('INSERT INTO project_assignments(project_id,unit_id,resource_id,quantity,notes,created_at) VALUES(?,?,?,?,?,?)',(record_map[str(a['project_id'])],unit_map.get(str(a.get('unit_id'))) if a.get('unit_id') is not None else None,resource_map.get(str(a.get('resource_id'))) if a.get('resource_id') is not None else None,float(a.get('quantity',0)),str(a.get('notes',''))[:10000],str(a.get('created_at',now))[:80]))
    settings=payload.get('settings',{})
    if version>=2: con.execute('DELETE FROM settings')
    for key,value in settings.items():
        if not isinstance(key,str) or not key or len(key)>100: raise ValueError('Einstellungsschlüssel ist ungültig.')
        con.execute('INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',(key,str(value)[:10000],now))
    if version>=2:
        for key,value in [('language','de'),('backup_keep',str(BACKUP_KEEP)),('backup_interval_minutes','30'),('last_news_refresh',''),('unit_label_singular','Mitglied'),('unit_label_plural','Mitglieder')]: con.execute('INSERT OR IGNORE INTO settings(key,value,updated_at) VALUES(?,?,?)',(key,value,now))
    geo=payload.get('geodata',{})
    if version>=2: con.execute('DELETE FROM geodata_assets')
    for key,value in geo.items(): con.execute('INSERT INTO geodata_assets(key,geojson,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET geojson=excluded.geojson,updated_at=excluded.updated_at',(('germany-states' if key=='germany_states' else key),json.dumps(value,ensure_ascii=False,separators=(',',':')),now))
    if version>=2:
        news=payload.get('news',{})
        con.execute('DELETE FROM feed_items'); con.execute('DELETE FROM feed_status')
        for item in news.get('items',[]):
            required=('id','source_key','source_name','title','url','fetched_at')
            if any(k not in item for k in required): raise ValueError('News-Eintrag ist unvollständig.')
            con.execute('INSERT INTO feed_items(id,source_key,source_name,title,summary,url,published,fetched_at) VALUES(?,?,?,?,?,?,?,?)',(str(item['id']),str(item['source_key']),str(item['source_name']),str(item['title']),str(item.get('summary','')),str(item['url']),str(item.get('published','')),str(item['fetched_at'])))
        for item in news.get('sources',[]):
            con.execute('INSERT INTO feed_status(source_key,source_name,last_attempt,last_success,status,item_count) VALUES(?,?,?,?,?,?)',(str(item['source_key']),str(item['source_name']),item.get('last_attempt'),item.get('last_success'),str(item.get('status','Noch nicht abgerufen')),int(item.get('item_count',0))))
    violations=con.execute('PRAGMA foreign_key_check').fetchall()
    if violations: raise ValueError('Import würde ungültige Fremdschlüssel erzeugen; Transaktion wird zurückgerollt.')
    con.commit()
    return {'tasks':len(data['tasks']),'records':len(data['records']),'map_locations':len(data['map_locations']),'units':len(data.get('units',[])) if version>=2 else None,'resources':len(data.get('resources',[])) if version>=2 else None,'project_assignments':len(data.get('project_assignments',[])) if version>=2 else None,'geodata':len(geo)}


def project_dashboard(con, region_filter='', project_filter='', status_filter=''):
    """Build a read-only dashboard with ID-based joins and explicit unknowns."""
    projects=[dict(r) for r in con.execute("SELECT * FROM records WHERE module='projects' ORDER BY updated_at DESC,id DESC")]
    tasks={r['id']:dict(r) for r in con.execute('SELECT * FROM tasks')}
    units={r['id']:dict(r) for r in con.execute('SELECT * FROM units')}
    resources={r['id']:dict(r) for r in con.execute('SELECT * FROM resources')}
    locations=[dict(r) for r in con.execute('SELECT * FROM map_locations ORDER BY id')]
    assignments=[dict(r) for r in con.execute('SELECT * FROM project_assignments ORDER BY id')]
    result=[]
    for project in projects:
        pid=project['id']
        plocs=[loc for loc in locations if loc.get('project_id')==pid]
        passign=[a for a in assignments if a['project_id']==pid]
        regions=[]
        for value in [project.get('region')]+[loc.get('region') for loc in plocs]:
            value=(value or '').strip()
            if value and value not in regions: regions.append(value)
        statuses=list(dict.fromkeys(loc['status'] for loc in plocs if loc.get('status')))
        status='unbekannt' if not statuses else statuses[0] if len(statuses)==1 else 'gemischt'
        progress_values=[loc['progress'] for loc in plocs if isinstance(loc.get('progress'),(int,float))]
        linked_tasks=[]
        seen_tasks=set()
        for loc in plocs:
            tid=loc.get('task_id')
            task=tasks.get(tid) if tid is not None else None
            if task and tid not in seen_tasks:
                seen_tasks.add(tid)
                if not task.get('done'): linked_tasks.append({'id':tid,'title':task['title'],'area':task['area'],'done':False,'location_id':loc['id'],'location_title':loc['title']})
        members=[]; assigned_resources=[]
        for a in passign:
            if a.get('unit_id') is not None and a['unit_id'] in units:
                u=units[a['unit_id']]
                members.append({'assignment_id':a['id'],'id':u['id'],'name':u['name'],'role':u.get('role',''),'status':u.get('status',''),'region':u.get('region',''),'quantity':a.get('quantity'),'notes':a.get('notes','')})
            if a.get('resource_id') is not None and a['resource_id'] in resources:
                r=resources[a['resource_id']]
                assigned_resources.append({'assignment_id':a['id'],'id':r['id'],'name':r['name'],'category':r.get('category',''),'quantity':a.get('quantity'),'unit':r.get('unit') or None,'available_quantity':r.get('quantity'),'location':r.get('location',''),'notes':a.get('notes','')})
        project_locations=[{'id':l['id'],'title':l['title'],'region':l.get('region') or None,'latitude':l['latitude'],'longitude':l['longitude'],'status':l.get('status') or None,'progress':l.get('progress'),'task_id':l.get('task_id'),'unit_id':l.get('unit_id'),'resource_id':l.get('resource_id')} for l in plocs]
        if region_filter and region_filter not in regions: continue
        if project_filter and str(pid)!=str(project_filter): continue
        if status_filter and not (status_filter=='unbekannt' and not statuses) and status_filter not in statuses: continue
        result.append({'id':pid,'title':project['title'],'description':project.get('body') or '', 'region':project.get('region') or None,'regions':regions,'updated_at':project.get('updated_at'),'status':status,'statuses':statuses,'progress':round(sum(progress_values)/len(progress_values)) if progress_values else None,'locations':project_locations,'open_tasks':linked_tasks,'members':members,'resources':assigned_resources,'counts':{'locations':len(plocs),'open_tasks':len(linked_tasks),'members':len(members),'resources':len(assigned_resources)}})
    return {'items':result,'total':len(result),'filters':{'region':region_filter or None,'project_id':int(project_filter) if project_filter.isdigit() else None,'status':status_filter or None},'regions':sorted({region for project in projects for region in ([project.get('region')]+[loc.get('region') for loc in locations if loc.get('project_id')==project['id']]) if isinstance(region,str) and region.strip()}),'statuses':['geplant','aktiv','blockiert','abgeschlossen','unbekannt','gemischt'],'semantics':{'progress':'Durchschnitt ausschließlich vorhandener Kartenstandort-Fortschritte; null bedeutet keine Werte.','status':'Aus verknüpften Kartenstandorten abgeleitet; unbekannt bedeutet keine Statusdaten.','resource_quantities':'Je Ressource mit Originaleinheit ausgewiesen; keine Summierung inkompatibler Einheiten.','relationships':'Alle Verknüpfungen über numerische IDs.'}}



class AppHandler(BaseHTTPRequestHandler):
    server_version='KORLocalCore/1.0'
    sys_version=''
    def log_message(self,fmt,*args):
        if os.environ.get('KOR_DEBUG')=='1': super().log_message(fmt,*args)
    def _headers(self,status,ctype='application/json; charset=utf-8',length=None):
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Cache-Control','no-store');self.send_header('Cross-Origin-Resource-Policy','same-origin');self.send_header('Content-Security-Policy',"default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; frame-src https://www.youtube-nocookie.com https://www.youtube.com; media-src 'self' blob: data: https:; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'")
        if length is not None:self.send_header('Content-Length',str(length))
        self.end_headers()
    def send_json(self,obj,status=200):
        data=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode();self._headers(status,length=len(data));self.wfile.write(data)
    def fail(self,status,msg): self.send_json({'ok':False,'error':msg},status)
    def trusted(self):
        host=self.headers.get('Host','').lower().split(':')[0].strip('[]')
        if host not in ('127.0.0.1','localhost','::1'): return False
        origin=self.headers.get('Origin')
        if origin:
            p=urllib.parse.urlsplit(origin)
            if p.hostname not in ('127.0.0.1','localhost','::1') or p.port != self.server.server_port: return False
        return True
    def read_body(self):
        try:n=int(self.headers.get('Content-Length','0'))
        except ValueError: raise ValueError('Ungültige Content-Length')
        if n<0 or n>MAX_BODY: raise ValueError('Anfrage ist zu groß (max. 12 MiB)')
        raw=self.rfile.read(n) if n else b'{}'
        try: value=json.loads(raw.decode('utf-8'))
        except Exception: raise ValueError('Ungültiges JSON')
        if not isinstance(value,dict): raise ValueError('JSON muss ein Objekt sein')
        return value
    def do_GET(self):
        if not self.trusted(): return self.fail(403,'Nur lokale Anfragen sind erlaubt.')
        path=urllib.parse.urlsplit(self.path).path
        if path.startswith('/api/'): add_system_log('GET','API',path)
        q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        if path == '/api/github/status':
            try:
                info=github_integration.overview()
                return self.send_json({'ok':True,'connected':True,'user':info['user'],'repository_count':len(info['repositories'])})
            except github_integration.GitHubError as exc:
                return self.send_json({'ok':False,'connected':False,'error':str(exc)})
        if path == '/api/github/repositories':
            try: return self.send_json({'ok':True,**github_integration.overview()})
            except github_integration.GitHubError as exc: return self.send_json({'ok':False,'error':str(exc)},status=503)
        if path == '/api/github/repository':
            owner=q.get('owner',[''])[0]; repo=q.get('repo',[''])[0]
            try: return self.send_json({'ok':True,**github_integration.repository_data(owner,repo)})
            except github_integration.GitHubError as exc: return self.send_json({'ok':False,'error':str(exc)},status=400)
        if path == '/api/media/readiness':
            try:
                init_media_db()
                return self.send_json(check_emergency_readiness())
            except (OSError, sqlite3.Error) as exc:
                add_system_log('ERROR','MEDIA','Bereitschaftsprüfung fehlgeschlagen: '+str(exc))
                return self.fail(500,'Lokales Medienarchiv konnte nicht geprüft werden.')
        if path.startswith('/local-media/'):
            filename=urllib.parse.unquote(path[len('/local-media/'):])
            target=media_path(filename)
            if target is None: return self.fail(404,'Lokale Mediendatei nicht gefunden.')
            try:
                size=target.stat().st_size
                start,end=0,size-1
                status=200
                range_header=self.headers.get('Range','')
                if range_header.startswith('bytes=') and ',' not in range_header:
                    spec=range_header[6:].split('-',1)
                    try:
                        if spec[0]:
                            start=int(spec[0]); end=min(int(spec[1]),size-1) if spec[1] else size-1
                        elif spec[1]:
                            suffix=int(spec[1]); start=max(0,size-suffix); end=size-1
                        else: raise ValueError()
                        if start<0 or start>=size or end<start: raise ValueError()
                        status=206
                    except (ValueError,IndexError):
                        self.send_response(416); self.send_header('Content-Range',f'bytes */{size}'); self.send_header('Content-Length','0'); self.end_headers(); return
                length=max(0,end-start+1)
                self.send_response(status)
                self.send_header('Content-Type',media_mime(target))
                self.send_header('Content-Length',str(length))
                self.send_header('Accept-Ranges','bytes')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Cache-Control','no-store')
                if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
                self.end_headers()
                with target.open('rb') as stream:
                    stream.seek(start); remaining=length
                    while remaining:
                        chunk=stream.read(min(256*1024,remaining))
                        if not chunk: break
                        self.wfile.write(chunk); remaining-=len(chunk)
                return
            except (OSError, BrokenPipeError) as exc:
                add_system_log('WARN','MEDIA','Stream unterbrochen: '+str(exc))
                return
        if path.startswith('/api/'):
            maybe_backup()
            if path=='/api/health': return self.send_json({'ok':True,'app':APP_NAME,'version':VERSION,'database':'SQLite','data_dir':str(DATA_HOME),'backup_count':len(list(BACKUP_DIR.glob('kor-*.sqlite3'))),'python':sys.version.split()[0],'system':get_system_health()})
            if path=='/api/system/health': return self.send_json(get_system_health())
            if path=='/api/mesh/status': return self.send_json(mesh.status())
            if path=='/api/console/logs':
                with _system_logs_lock: local=list(_system_logs)
                return self.send_json({'logs':(local+mesh.logs())[-50:]})
            if path=='/api/geodata/features':
                with db_connect() as con: rows=[dict(r) for r in con.execute('SELECT id,feature_type,name,ags,geometry_json FROM geodata_features ORDER BY name')]
                for row in rows: row['geometry']=json.loads(row.pop('geometry_json'))
                return self.send_json({'items':rows,'count':len(rows)})
            if path=='/api/simulation/resource-runway':
                try:
                    days=int(q.get('days',['30'])[0]); burn=float(q.get('daily_burn_rate',['0'])[0]); stock=float(q.get('current_stock',['0'])[0])
                    return self.send_json({'timeline':simulate_resource_runway(days,burn,stock)})
                except (ValueError,TypeError) as exc: return self.fail(400,'Ungültige Simulationsparameter: '+str(exc))
            if path=='/api/tasks':
                with db_connect() as con:return self.send_json({'items':[task_dict(r) for r in con.execute('SELECT * FROM tasks ORDER BY done ASC,id DESC')]})
            if path=='/api/records':
                module=q.get('module',[''])[0]
                if module not in MODULES:return self.fail(400,'Unbekanntes Modul.')
                with db_connect() as con:return self.send_json({'items':[record_dict(r) for r in con.execute('SELECT * FROM records WHERE module=? ORDER BY updated_at DESC,id DESC',(module,))]})
            if path=='/api/settings':return self.send_json({'settings':get_settings()})
            if path=='/api/units':
                with db_connect() as con:return self.send_json({'items':[unit_dict(r) for r in con.execute('SELECT * FROM units ORDER BY id DESC')]})
            if path=='/api/resources':
                with db_connect() as con:return self.send_json({'items':[dict(r) for r in con.execute('SELECT * FROM resources ORDER BY id DESC')]})
            if path=='/api/assignments':
                with db_connect() as con:return self.send_json({'items':[dict(r) for r in con.execute('SELECT a.*,p.title project_title,u.name unit_name,r.name resource_name FROM project_assignments a JOIN records p ON p.id=a.project_id LEFT JOIN units u ON u.id=a.unit_id LEFT JOIN resources r ON r.id=a.resource_id ORDER BY a.id DESC')]})
            if path=='/api/dashboard/projects':
                region=(q.get('region',[''])[0] or '').strip()[:180]; project=(q.get('project_id',[''])[0] or '').strip(); status=(q.get('status',[''])[0] or '').strip()
                if project and (not project.isdigit() or int(project)<1): return self.fail(400,'Ungültige Projekt-ID.')
                if status and status not in ('geplant','aktiv','blockiert','abgeschlossen','unbekannt','gemischt'): return self.fail(400,'Unbekannter Projektstatus.')
                with db_connect() as con:return self.send_json(project_dashboard(con,region,project,status))
            if path=='/api/backups':
                files=sorted(BACKUP_DIR.glob('kor-*.sqlite3'),key=lambda p:p.stat().st_mtime,reverse=True)
                return self.send_json({'items':[{'name':p.name,'size':p.stat().st_size,'created_at':dt.datetime.fromtimestamp(p.stat().st_mtime,dt.timezone.utc).isoformat()} for p in files]})
            if path=='/api/export':
                with db_connect() as con: return self.send_json(build_export(con))
            if path=='/api/news':
                if q.get('refresh',['0'])[0]=='1':
                    result=refresh_feeds()
                else: result=None
                with db_connect() as con:
                    items=[dict(r) for r in con.execute('SELECT * FROM feed_items ORDER BY fetched_at DESC,published DESC LIMIT 100')]
                    statuses=[dict(r) for r in con.execute('SELECT * FROM feed_status ORDER BY source_name')]
                return self.send_json({'items':items,'sources':statuses,'refreshed':result,'cached':True})
            if path=='/api/regions': return self.send_json({'states':STATE_NAMES,'note':'Bundeslandnamen sind offline verfügbar. Präzise Grenzpolygone müssen als GeoJSON importiert werden.'})
            if path=='/api/geodata/germany-states':
                with db_connect() as con: row=con.execute("SELECT geojson,updated_at FROM geodata_assets WHERE key='germany-states'").fetchone()
                if row:
                    try:
                        geo=json.loads(row['geojson'])
                        return self.send_json({'available':True,'source':'user-import','geojson':geo,'feature_count':len(geo.get('features',[])),'updated_at':row['updated_at']})
                    except (ValueError,TypeError): return self.fail(500,'Importierte Bundesland-Geodaten sind beschädigt.')
                return self.send_json({'available':False,'source':None,'geojson':None,'feature_count':0,'note':'Kein Bundesland-GeoJSON importiert.'})
            if path=='/api/locations':
                with db_connect() as con:return self.send_json({'items':[dict(r) for r in con.execute('SELECT l.*,p.title AS project_title,t.title AS task_title,u.name AS unit_name,rs.name AS resource_name FROM map_locations l LEFT JOIN records p ON p.id=l.project_id LEFT JOIN tasks t ON t.id=l.task_id LEFT JOIN units u ON u.id=l.unit_id LEFT JOIN resources rs ON rs.id=l.resource_id ORDER BY l.updated_at DESC,l.id DESC')], 'projection':'equirectangular-marker-overlay','offline':True,'statuses':['geplant','aktiv','blockiert','abgeschlossen']})
            return self.fail(404,'API-Endpunkt nicht gefunden.')
        if path=='/': path='/index.html'
        rel=urllib.parse.unquote(path.lstrip('/'))
        f=(WEB/rel).resolve()
        try:f.relative_to(WEB.resolve())
        except ValueError:return self.fail(404,'Datei nicht gefunden.')
        if not f.is_file():return self.fail(404,'Datei nicht gefunden.')
        ctype={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml','.json':'application/json; charset=utf-8','.png':'image/png'}.get(f.suffix,'application/octet-stream')
        data=f.read_bytes();self._headers(200,ctype,len(data));self.wfile.write(data)
    def do_POST(self):
        if not self.trusted():return self.fail(403,'Nur lokale Anfragen sind erlaubt.')
        path=urllib.parse.urlsplit(self.path).path
        if path.startswith('/api/'): add_system_log('POST','API',path)
        if path.startswith('/api/github/'):
            try: data=self.read_body()
            except ValueError as exc: return self.fail(400,str(exc))
            try:
                owner=str(data.get('owner','')); repo=str(data.get('repo',''))
                if path=='/api/github/issues':
                    result=github_integration.create_issue(owner,repo,data.get('title',''),data.get('body',''))
                    return self.send_json({'ok':True,**result},status=201)
                if path=='/api/github/pulls':
                    result=github_integration.create_pull_request(owner,repo,data.get('title',''),data.get('head',''),data.get('base',''),data.get('body',''))
                    return self.send_json({'ok':True,**result},status=201)
                if path=='/api/github/branches':
                    result=github_integration.create_branch(owner,repo,data.get('branch',''),data.get('source',''))
                    return self.send_json({'ok':True,**result},status=201)
                if path=='/api/github/workflow-dispatch':
                    result=github_integration.dispatch_workflow(owner,repo,data.get('workflow',''),data.get('branch',''))
                    return self.send_json({'ok':True,**result},status=202)
                return self.fail(404,'Unbekannte GitHub-Aktion.')
            except github_integration.GitHubError as exc:
                return self.send_json({'ok':False,'error':str(exc)},status=400)
        if path=='/api/mesh/start':
            mesh.start(); return self.send_json({'ok':True,'mesh':mesh.status()})
        if path=='/api/mesh/stop':
            mesh.stop(); return self.send_json({'ok':True,'mesh':mesh.status()})
        if path=='/api/shutdown':
            self.send_json({'ok':True,'message':'KOR-NEXUS beendet.'})
            event=getattr(self.server,'shutdown_event',None)
            if event is not None: threading.Timer(0.2,event.set).start()
            return
        try:data=self.read_body()
        except ValueError as e:return self.fail(400,str(e))
        if path!='/api/import/preview': maybe_backup()
        now=utcnow()
        if path == '/api/media/favorite':
            try:
                file_id=int(data.get('id'))
                favorite=data.get('favorite')
                if file_id < 1 or not isinstance(favorite,bool): raise ValueError()
            except (TypeError,ValueError):
                return self.fail(400,'Ungültige Medien-ID oder Favoritenangabe.')
            try:
                if not set_media_favorite(file_id,favorite): return self.fail(404,'Medium nicht gefunden.')
                return self.send_json({'ok':True,'id':file_id,'is_favorite':favorite})
            except sqlite3.Error:
                return self.fail(500,'Favorit konnte nicht gespeichert werden.')
        if path=='/api/archive/upload':
            import base64, binascii
            filename=os.path.basename(str(data.get('filename','')).replace(chr(92),'/')).strip()
            encoded=data.get('content_base64')
            if not filename or filename in ('.','..') or len(filename)>180 or any(ord(ch)<32 for ch in filename): return self.fail(400,'Ungültiger Dateiname.')
            if not isinstance(encoded,str) or len(encoded)>11*1024*1024: return self.fail(400,'Datei fehlt oder ist zu groß (max. 8 MiB).')
            try: payload=base64.b64decode(encoded,validate=True)
            except (ValueError,binascii.Error): return self.fail(400,'Dateiinhalt ist kein gültiges Base64.')
            if not payload or len(payload)>8*1024*1024: return self.fail(400,'Datei muss zwischen 1 Byte und 8 MiB groß sein.')
            UPLOAD_DIR.mkdir(parents=True,exist_ok=True,mode=0o700)
            safe_name=re.sub(r'[^A-Za-z0-9._() -]','_',filename)[:140].strip(' .') or 'upload.bin'
            target=UPLOAD_DIR/(uuid.uuid4().hex+'-'+safe_name)
            target.write_bytes(payload)
            try: os.chmod(target,0o600)
            except OSError: pass
            add_system_log('INFO','ARCHIV','Datei lokal abgelegt: '+safe_name)
            return self.send_json({'ok':True,'filename':safe_name,'size':len(payload),'stored_name':target.name},201)
        if path=='/api/import/preview':
            return self.send_json(portable_import_preview(data.get('data')))
        if path=='/api/geodata/germany-states':
            geo=data.get('geojson') if isinstance(data,dict) else None
            if not isinstance(geo,dict) or geo.get('type')!='FeatureCollection' or not isinstance(geo.get('features'),list): return self.fail(400,'Erwartet wird eine GeoJSON FeatureCollection.')
            features=geo['features']
            if not 1 <= len(features) <= 1000: return self.fail(400,'GeoJSON muss zwischen 1 und 1000 Features enthalten.')
            valid_names=set(STATE_NAMES); found=set()
            for feature in features:
                if not isinstance(feature,dict) or feature.get('type')!='Feature' or not isinstance(feature.get('geometry'),dict): return self.fail(400,'GeoJSON enthält ein ungültiges Feature.')
                geom=feature['geometry']; props=feature.get('properties') or {}
                if geom.get('type') not in ('Polygon','MultiPolygon'): return self.fail(400,'Bundesland-Geometrien müssen Polygon oder MultiPolygon sein.')
                name=str(props.get('name') or props.get('NAME_1') or props.get('GEN') or props.get('NAME') or '').strip()
                if name: found.add(name)
                coords=geom.get('coordinates')
                if not isinstance(coords,list) or not coords or not geojson_wgs84_coordinates_valid(coords): return self.fail(400,'Geometrie enthält ungültige Koordinaten. Erwartet werden WGS84-Längen-/Breitengrade (EPSG:4326).')
            serialized=json.dumps(geo,ensure_ascii=False,separators=(',',':'))
            with db_connect() as con: con.execute('INSERT INTO geodata_assets(key,geojson,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET geojson=excluded.geojson,updated_at=excluded.updated_at',('germany-states',serialized,now))
            GEODATA_DIR.mkdir(parents=True,exist_ok=True)
            tmp=GERMANY_STATES_FILE.with_suffix('.geojson.tmp')
            tmp.write_text(serialized,encoding='utf-8');tmp.replace(GERMANY_STATES_FILE)
            return self.send_json({'ok':True,'available':True,'feature_count':len(features),'recognized_state_names':len(found & valid_names),'note':'Geometrien lokal in SQLite und als GeoJSON-Datei gespeichert; Quelle, Lizenz und Namen vor Nutzung prüfen.'},201)
        with _db_lock:
            try:
                if path=='/api/tasks':
                    title=str(data.get('title','')).strip();area=str(data.get('area','SYSTEM')).strip()[:80] or 'SYSTEM'
                    if not title or len(title)>180:return self.fail(400,'Titel muss zwischen 1 und 180 Zeichen lang sein.')
                    with db_connect() as con:
                        cur=con.execute('INSERT INTO tasks(title,area,done,created_at,updated_at) VALUES(?,?,0,?,?)',(title,area,now,now));r=con.execute('SELECT * FROM tasks WHERE id=?',(cur.lastrowid,)).fetchone()
                    return self.send_json({'item':task_dict(r)},201)
                if path=='/api/locations':
                    title=str(data.get('title','')).strip();region=str(data.get('region','')).strip()[:180];kind=str(data.get('kind','Projekt')).strip()[:40] or 'Projekt';notes=str(data.get('notes',''))
                    try: lat=float(data.get('latitude')); lon=float(data.get('longitude')); progress=int(data.get('progress',0))
                    except (TypeError,ValueError): return self.fail(400,'Koordinaten und Fortschritt müssen gültige Zahlen sein.')
                    status=str(data.get('status','geplant'))
                    if not title or len(title)>180 or len(notes)>10000 or not (-90<=lat<=90) or not (-180<=lon<=180) or not 0<=progress<=100 or status not in ('geplant','aktiv','blockiert','abgeschlossen'): return self.fail(400,'Ungültige Standortdaten, Status oder Fortschritt.')
                    refs={}
                    for field,table,extra in [('project_id','records'," AND module='projects'"),('task_id','tasks',''),('unit_id','units',''),('resource_id','resources','')]:
                        value=data.get(field); refs[field]=None if value in ('',None) else int(value) if str(value).isdigit() else -1
                        if refs[field]==-1:return self.fail(400,'Ungültige Verknüpfungs-ID.')
                    with db_connect() as con:
                        for field,table,extra in [('project_id','records'," AND module='projects'"),('task_id','tasks',''),('unit_id','units',''),('resource_id','resources','')]:
                            if refs[field] is not None and not con.execute(f'SELECT 1 FROM {table} WHERE id=?{extra}',(refs[field],)).fetchone():return self.fail(400,f'Verknüpfter Datensatz für {field} wurde nicht gefunden.')
                        cur=con.execute('INSERT INTO map_locations(title,kind,region,latitude,longitude,project_id,notes,created_at,updated_at,status,progress,task_id,unit_id,resource_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(title,kind,region,lat,lon,refs['project_id'],notes,now,now,status,progress,refs['task_id'],refs['unit_id'],refs['resource_id']))
                        row=con.execute('SELECT l.*,p.title AS project_title,t.title AS task_title,u.name AS unit_name,rs.name AS resource_name FROM map_locations l LEFT JOIN records p ON p.id=l.project_id LEFT JOIN tasks t ON t.id=l.task_id LEFT JOIN units u ON u.id=l.unit_id LEFT JOIN resources rs ON rs.id=l.resource_id WHERE l.id=?',(cur.lastrowid,)).fetchone()
                    return self.send_json({'item':dict(row)},201)
                if path=='/api/records':
                    module=data.get('module');title=str(data.get('title','')).strip();body=str(data.get('body',''));region=str(data.get('region',''));tags=data.get('tags',[])
                    if module not in MODULES:return self.fail(400,'Unbekanntes Modul.')
                    if not title or len(title)>180:return self.fail(400,'Titel muss zwischen 1 und 180 Zeichen lang sein.')
                    if len(body)>100000 or len(region)>180:return self.fail(400,'Inhalt überschreitet das zulässige Limit.')
                    if not isinstance(tags,list) or len(tags)>50:return self.fail(400,'Tags müssen eine Liste mit höchstens 50 Einträgen sein.')
                    tagjson=json.dumps([str(t)[:60] for t in tags],ensure_ascii=False)
                    with db_connect() as con:
                        cur=con.execute('INSERT INTO records(module,title,body,region,tags,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(module,title,body,region,tagjson,now,now));r=con.execute('SELECT * FROM records WHERE id=?',(cur.lastrowid,)).fetchone()
                    return self.send_json({'item':record_dict(r)},201)
                if path=='/api/units':
                    name=str(data.get('name','')).strip();bio=str(data.get('biography',''));tags=data.get('tags',[])
                    if not name or len(name)>180 or len(bio)>100000 or not isinstance(tags,list) or len(tags)>50:return self.fail(400,'Ungültige Einheitenfelder.')
                    with db_connect() as con:
                        cur=con.execute('INSERT INTO units(name,role,status,biography,region,tags,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(name,str(data.get('role',''))[:120],str(data.get('status','aktiv'))[:40],bio,str(data.get('region',''))[:180],json.dumps(tags[:50],ensure_ascii=False),now,now))
                    with db_connect() as con: row=con.execute('SELECT * FROM units WHERE id=?',(cur.lastrowid,)).fetchone()
                    return self.send_json({'item':unit_dict(row)},201)
                if path=='/api/resources':
                    name=str(data.get('name','')).strip()
                    try: qty=float(data.get('quantity',0))
                    except (TypeError,ValueError):return self.fail(400,'Menge muss eine Zahl sein.')
                    if not name or len(name)>180 or not math.isfinite(qty) or qty<0 or qty>1e12:return self.fail(400,'Ungültige Ressourcenfelder.')
                    with db_connect() as con:cur=con.execute('INSERT INTO resources(name,category,quantity,unit,location,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(name,str(data.get('category','Allgemein'))[:80],qty,str(data.get('unit','Stück'))[:40],str(data.get('location',''))[:180],str(data.get('notes',''))[:10000],now,now)); row=con.execute('SELECT * FROM resources WHERE id=?',(cur.lastrowid,)).fetchone()
                    return self.send_json({'item':dict(row)},201)
                if path=='/api/assignments':
                    try: pid=int(data['project_id']); qty=float(data.get('quantity',0)); uid=int(data['unit_id']) if data.get('unit_id') is not None else None; rid=int(data['resource_id']) if data.get('resource_id') is not None else None
                    except (TypeError,ValueError,KeyError):return self.fail(400,'Ungültige Zuweisungsdaten.')
                    if (uid is None)==(rid is None) or not math.isfinite(qty) or qty<0 or qty>1e12:return self.fail(400,'Genau eine Einheit oder Ressource sowie eine endliche, nichtnegative Menge bis 1e12 angeben.')
                    with db_connect() as con:
                        if not con.execute("SELECT 1 FROM records WHERE id=? AND module='projects'",(pid,)).fetchone():return self.fail(400,'Projekt nicht gefunden.')
                        if uid is not None and not con.execute('SELECT 1 FROM units WHERE id=?',(uid,)).fetchone():return self.fail(400,'Einheit nicht gefunden.')
                        if rid is not None and not con.execute('SELECT 1 FROM resources WHERE id=?',(rid,)).fetchone():return self.fail(400,'Ressource nicht gefunden.')
                        cur=con.execute('INSERT INTO project_assignments(project_id,unit_id,resource_id,quantity,notes,created_at) VALUES(?,?,?,?,?,?)',(pid,uid,rid,qty,str(data.get('notes',''))[:10000],now))
                    return self.send_json({'id':cur.lastrowid,'project_id':pid,'unit_id':uid,'resource_id':rid,'quantity':qty},201)
                if path=='/api/backups':return self.send_json({'item':create_backup('manual')},201)
                if path=='/api/restore':
                    name=str(data.get('name',''))
                    if not re.fullmatch(r'kor-[0-9]{8}-[0-9]{6}-[a-z0-9-]{1,32}\.sqlite3',name):return self.fail(400,'Ungültiger Backupname.')
                    source=(BACKUP_DIR/name).resolve()
                    try:source.relative_to(BACKUP_DIR.resolve())
                    except ValueError:return self.fail(400,'Ungültiger Pfad.')
                    if not source.is_file():return self.fail(404,'Backup nicht gefunden.')
                    check=sqlite3.connect(f'file:{source}?mode=ro',uri=True)
                    try:
                        if check.execute('PRAGMA integrity_check').fetchone()[0]!='ok':return self.fail(400,'Backup ist beschädigt.')
                        tables={r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                        if not {'schema_migrations','tasks','records','settings','feed_items','feed_status'}.issubset(tables):return self.fail(400,'Backup stammt nicht aus KOR-NEXUS.')
                    finally:check.close()
                    # Do not prune until the selected restore point has been used:
                    # at the retention limit it may be the oldest backup.
                    safety=create_backup('before-restore',prune=False)
                    try:
                        with _db_lock:
                            # Use SQLite's online backup API instead of a raw file copy;
                            # this preserves a coherent database image even with WAL mode.
                            dst=sqlite3.connect(DB_PATH,timeout=15)
                            src=sqlite3.connect(f'file:{source}?mode=ro',uri=True,timeout=15)
                            try:
                                src.backup(dst)
                                dst.commit()
                                integrity=dst.execute('PRAGMA integrity_check').fetchone()[0]
                                if integrity!='ok': raise RuntimeError('Wiederhergestellte Datenbank ist nicht integer.')
                            finally:src.close();dst.close()
                    finally:
                        prune_backups()
                    return self.send_json({'ok':True,'restored':name,'safety_backup':safety})
                if path=='/api/import':
                    exported=data.get('data')
                    try:
                        validated=validate_portable_import(exported)
                    except (ValueError,TypeError,KeyError) as exc:
                        return self.fail(400,str(exc)[:500])
                    # Only after complete validation, make a verified safety point.
                    safety=create_backup('before-import',prune=False)
                    try:
                        with _db_lock, db_connect() as con:
                            counts=apply_portable_import(con,exported,now)
                    except (ValueError,TypeError,KeyError,sqlite3.IntegrityError) as exc:
                        return self.fail(400,'Import wurde vollständig zurückgerollt: '+str(exc)[:400])
                    except Exception:
                        return self.fail(500,'Import fehlgeschlagen und wurde zurückgerollt. Das Sicherheitsbackup bleibt erhalten.')
                    state_geo=exported.get('geodata',{}).get('germany-states',exported.get('geodata',{}).get('germany_states'))
                    if state_geo is not None:
                        try:
                            GEODATA_DIR.mkdir(parents=True,exist_ok=True);tmp=GERMANY_STATES_FILE.with_suffix('.geojson.tmp');tmp.write_text(json.dumps(state_geo,ensure_ascii=False,separators=(',',':')),encoding='utf-8');tmp.replace(GERMANY_STATES_FILE)
                        except OSError as exc:
                            return self.send_json({'ok':True,**counts,'safety_backup':safety,'warning':'SQLite-Import erfolgreich, GeoJSON-Datei konnte nicht aktualisiert werden; SQLite bleibt maßgeblich.'})
                    elif exported.get('schema_version')==2:
                        try: GERMANY_STATES_FILE.unlink(missing_ok=True)
                        except OSError: pass
                    with db_connect() as con:
                        check=con.execute('PRAGMA foreign_key_check').fetchall()
                        if check: return self.fail(500,'Fremdschlüsselprüfung nach Import fehlgeschlagen.')
                    prune_backups()
                    return self.send_json({'ok':True,**counts,'safety_backup':safety,'schema_version':exported['schema_version']})
            except sqlite3.Error as e:
                return self.fail(500,'Datenbankfehler; die lokalen Daten wurden nicht absichtlich gelöscht. Details stehen nicht im Browser.')
            except Exception as e:
                print(f'[KOR] API-Fehler: {e}',file=sys.stderr);return self.fail(500,'Interner Fehler. Siehe lokale Terminalausgabe.')
        return self.fail(404,'API-Endpunkt nicht gefunden.')
    def do_PATCH(self):
        if not self.trusted():return self.fail(403,'Nur lokale Anfragen sind erlaubt.')
        path=urllib.parse.urlsplit(self.path).path
        try:data=self.read_body()
        except ValueError as e:return self.fail(400,str(e))
        maybe_backup();now=utcnow()
        with _db_lock:
            try:
                m=re.fullmatch(r'/api/tasks/(\d+)',path)
                if m:
                    ident=int(m.group(1))
                    with db_connect() as con:
                        old=con.execute('SELECT * FROM tasks WHERE id=?',(ident,)).fetchone()
                        if not old:return self.fail(404,'Aufgabe nicht gefunden.')
                        title=str(data.get('title',old['title'])).strip();area=str(data.get('area',old['area'])).strip()[:80];done=int(bool(data.get('done',old['done'])))
                        if not title or len(title)>180:return self.fail(400,'Ungültiger Titel.')
                        con.execute('UPDATE tasks SET title=?,area=?,done=?,updated_at=? WHERE id=?',(title,area,done,now,ident));r=con.execute('SELECT * FROM tasks WHERE id=?',(ident,)).fetchone()
                    return self.send_json({'item':task_dict(r)})
                m=re.fullmatch(r'/api/records/(\d+)',path)
                if m:
                    ident=int(m.group(1))
                    with db_connect() as con:
                        old=con.execute('SELECT * FROM records WHERE id=?',(ident,)).fetchone()
                        if not old:return self.fail(404,'Datensatz nicht gefunden.')
                        module=data.get('module',old['module']);title=str(data.get('title',old['title'])).strip();body=str(data.get('body',old['body']));region=str(data.get('region',old['region']));tags=data.get('tags',json.loads(old['tags']))
                        if module not in MODULES or not title or len(title)>180 or len(body)>100000 or len(region)>180 or not isinstance(tags,list):return self.fail(400,'Ungültige Datensatzfelder.')
                        con.execute('UPDATE records SET module=?,title=?,body=?,region=?,tags=?,updated_at=? WHERE id=?',(module,title,body,region,json.dumps(tags[:50],ensure_ascii=False),now,ident));r=con.execute('SELECT * FROM records WHERE id=?',(ident,)).fetchone()
                    return self.send_json({'item':record_dict(r)})
                m=re.fullmatch(r'/api/locations/(\d+)',path)
                if m:
                    ident=int(m.group(1))
                    with db_connect() as con:
                        old=con.execute('SELECT * FROM map_locations WHERE id=?',(ident,)).fetchone()
                        if not old:return self.fail(404,'Kartenstandort nicht gefunden.')
                        title=str(data.get('title',old['title'])).strip();region=str(data.get('region',old['region'])).strip()[:180];kind=str(data.get('kind',old['kind'])).strip()[:40];notes=str(data.get('notes',old['notes']))
                        try:lat=float(data.get('latitude',old['latitude']));lon=float(data.get('longitude',old['longitude']));progress=int(data.get('progress',old['progress']))
                        except (TypeError,ValueError):return self.fail(400,'Koordinaten und Fortschritt müssen gültige Zahlen sein.')
                        status=str(data.get('status',old['status']))
                        if not title or len(title)>180 or len(notes)>10000 or not (-90<=lat<=90 and -180<=lon<=180) or not 0<=progress<=100 or status not in ('geplant','aktiv','blockiert','abgeschlossen'):return self.fail(400,'Ungültige Standortdaten, Status oder Fortschritt.')
                        refs={}
                        for field,table,extra in [('project_id','records'," AND module='projects'"),('task_id','tasks',''),('unit_id','units',''),('resource_id','resources','')]:
                            value=data.get(field,old[field]);refs[field]=None if value in ('',None) else int(value) if str(value).isdigit() else -1
                            if refs[field]==-1:return self.fail(400,'Ungültige Verknüpfungs-ID.')
                            if refs[field] is not None and not con.execute(f'SELECT 1 FROM {table} WHERE id=?{extra}',(refs[field],)).fetchone():return self.fail(400,f'Verknüpfter Datensatz für {field} wurde nicht gefunden.')
                        con.execute('UPDATE map_locations SET title=?,kind=?,region=?,latitude=?,longitude=?,project_id=?,notes=?,updated_at=?,status=?,progress=?,task_id=?,unit_id=?,resource_id=? WHERE id=?',(title,kind,region,lat,lon,refs['project_id'],notes,now,status,progress,refs['task_id'],refs['unit_id'],refs['resource_id'],ident))
                        row=con.execute('SELECT l.*,p.title AS project_title,t.title AS task_title,u.name AS unit_name,rs.name AS resource_name FROM map_locations l LEFT JOIN records p ON p.id=l.project_id LEFT JOIN tasks t ON t.id=l.task_id LEFT JOIN units u ON u.id=l.unit_id LEFT JOIN resources rs ON rs.id=l.resource_id WHERE l.id=?',(ident,)).fetchone()
                    return self.send_json({'item':dict(row)})
                if path=='/api/settings':
                    allowed={'language','backup_keep','backup_interval_minutes','unit_label_singular','unit_label_plural'}
                    if any(k not in allowed for k in data):return self.fail(400,'Unbekannte Einstellung.')
                    if 'language' in data and data['language'] not in ('de','en'):return self.fail(400,'Sprache muss de oder en sein.')
                    if any(k in data and (not str(data[k]).strip() or len(str(data[k]))>60) for k in ('unit_label_singular','unit_label_plural')):return self.fail(400,'Einheitenbezeichnung muss 1–60 Zeichen lang sein.')
                    if 'backup_keep' in data:
                        try:data['backup_keep']=str(max(3,min(50,int(data['backup_keep']))))
                        except Exception:return self.fail(400,'Backup-Aufbewahrung muss 3–50 sein.')
                    if 'backup_interval_minutes' in data:
                        try:data['backup_interval_minutes']=str(max(5,min(1440,int(data['backup_interval_minutes']))))
                        except Exception:return self.fail(400,'Backupintervall muss 5–1440 Minuten sein.')
                    with db_connect() as con:
                        for k,v in data.items():con.execute('INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',(k,str(v),now))
                    return self.send_json({'settings':get_settings()})
            except Exception as e:print(f'[KOR] PATCH-Fehler: {e}',file=sys.stderr);return self.fail(500,'Interner Fehler.')
        return self.fail(404,'Endpunkt nicht gefunden.')
    def do_DELETE(self):
        if not self.trusted():return self.fail(403,'Nur lokale Anfragen sind erlaubt.')
        path=urllib.parse.urlsplit(self.path).path
        with _db_lock:
            try:
                m=re.fullmatch(r'/api/tasks/(\d+)',path)
                if m:
                    with db_connect() as con:con.execute('DELETE FROM tasks WHERE id=?',(int(m.group(1)),))
                    return self.send_json({'ok':True})
                m=re.fullmatch(r'/api/records/(\d+)',path)
                if m:
                    with db_connect() as con:con.execute('DELETE FROM records WHERE id=?',(int(m.group(1)),))
                    return self.send_json({'ok':True})
                m=re.fullmatch(r'/api/locations/(\d+)',path)
                if m:
                    with db_connect() as con:con.execute('DELETE FROM map_locations WHERE id=?',(int(m.group(1)),))
                    return self.send_json({'ok':True})
                m=re.fullmatch(r'/api/units/(\d+)',path)
                if m:
                    with db_connect() as con:
                        ident=int(m.group(1))
                        if con.execute('SELECT 1 FROM project_assignments WHERE unit_id=?',(ident,)).fetchone():return self.fail(409,'Dieses Profil ist Projekten zugewiesen. Entferne zuerst die Zuweisungen.')
                        con.execute('DELETE FROM units WHERE id=?',(ident,))
                    return self.send_json({'ok':True})
                m=re.fullmatch(r'/api/resources/(\d+)',path)
                if m:
                    with db_connect() as con:
                        ident=int(m.group(1))
                        if con.execute('SELECT 1 FROM project_assignments WHERE resource_id=?',(ident,)).fetchone():return self.fail(409,'Diese Ressource ist Projekten zugewiesen. Entferne zuerst die Zuweisungen.')
                        con.execute('DELETE FROM resources WHERE id=?',(ident,))
                    return self.send_json({'ok':True})
                m=re.fullmatch(r'/api/assignments/(\d+)',path)
                if m:
                    with db_connect() as con:con.execute('DELETE FROM project_assignments WHERE id=?',(int(m.group(1)),))
                    return self.send_json({'ok':True})
            except sqlite3.Error:return self.fail(500,'Datenbankfehler.')
        return self.fail(404,'Endpunkt nicht gefunden.')


def open_app(url):
    import subprocess
    # Chromium/Chrome app mode gives a separate window. Other browsers still work in a tab.
    candidates=[os.environ.get('KOR_BROWSER',''), 'chromium','chromium-browser','google-chrome-stable','google-chrome','firefox']
    for c in candidates:
        if not c:continue
        exe=shutil.which(c)
        if not exe:continue
        name=Path(exe).name.lower()
        args=[exe]
        if 'chrom' in name or 'chrome' in name:args += ['--app='+url,'--no-first-run','--disable-session-crashed-bubble']
        else:args += [url]
        try:subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);return True
        except OSError:pass
    for c in ('xdg-open','gio'):
        exe=shutil.which(c)
        if exe:
            try:subprocess.Popen([exe,url] if c=='xdg-open' else [exe,'open',url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);return True
            except OSError:pass
    return False


def open_app_or_report(url):
    if open_app(url): return True
    print('[KOR] Kein unterstützter Browser gefunden. Installiere Chromium, Firefox oder xdg-utils; KOR-NEXUS läuft lokal weiter unter '+url, file=sys.stderr)
    return False


def active_instance(url):
    try:
        with urllib.request.urlopen(url.rstrip('/')+'/api/health',timeout=1.2) as response:
            status=json.loads(response.read(65536).decode('utf-8'))
        reported_data=Path(status.get('data_dir','')).resolve() if status.get('data_dir') else None
        return status.get('app')==APP_NAME and status.get('ok') is True and reported_data==DATA_HOME.resolve()
    except Exception:
        return False


def main():
    global _instance_lock_fd
    # Lock inside the Python process so every entry point (desktop, shell, direct launch) shares it.
    runtime_path=DATA_HOME/'runtime.json'
    DATA_HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        _instance_lock_fd=os.open(DATA_HOME/'launcher.lock',os.O_CREAT|os.O_RDWR,0o600)
        fcntl.flock(_instance_lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        os.environ['KOR_REUSE_ONLY']='1'
    except OSError as exc:
        print(f'KOR-NEXUS konnte die Start-Sperre nicht öffnen: {exc}',file=sys.stderr)
        return 1
    # A competing launch may only reopen the existing UI; it must never bind another server.
    if os.environ.get('KOR_REUSE_ONLY')=='1':
        for _ in range(30):
            try:
                info=json.loads(runtime_path.read_text(encoding='utf-8'))
                prior_port=int(info.get('port',0))
                if 1024<=prior_port<=65535:
                    prior_url=f'http://127.0.0.1:{prior_port}/'
                    if active_instance(prior_url):
                        if os.environ.get('KOR_NO_BROWSER')!='1': open_app_or_report(prior_url)
                        print(f'{APP_NAME} läuft bereits: {prior_url}');return 0
            except Exception:
                pass
            time.sleep(0.1)
        print(f'{APP_NAME} wird bereits gestartet. Bitte kurz warten und erneut öffnen.')
        return 0
    # Reuse the recorded instance first. This makes repeated menu clicks idempotent.
    if os.environ.get('KOR_NO_BROWSER')!='1':
        try:
            info=json.loads(runtime_path.read_text(encoding='utf-8'))
            prior_port=int(info.get('port',0))
            if 1024<=prior_port<=65535:
                prior_url=f'http://127.0.0.1:{prior_port}/'
                if active_instance(prior_url):
                    open_app_or_report(prior_url);print(f'{APP_NAME} läuft bereits: {prior_url}');return 0
        except Exception:
            pass
    port=8765
    try:
        server=ThreadingHTTPServer(('127.0.0.1',port),AppHandler);server.daemon_threads=True
    except OSError:
        default_url=f'http://127.0.0.1:{port}/'
        if active_instance(default_url):
            if os.environ.get('KOR_NO_BROWSER')!='1':open_app_or_report(default_url)
            print(f'{APP_NAME} läuft bereits: {default_url}');return 0
        # If an unrelated local service occupies the preferred port, choose a free
        # loopback port automatically rather than asking the user to troubleshoot.
        try:
            server=ThreadingHTTPServer(('127.0.0.1',0),AppHandler);server.daemon_threads=True
            print(f'Hinweis: Port 8765 war belegt; nutze automatisch Port {server.server_port}.')
        except OSError as e:
            print(f'KOR-NEXUS konnte keinen lokalen Port öffnen: {e}',file=sys.stderr);return 1
    try:
        initialize()
    except Exception as e:
        server.server_close();print(f'KOR-NEXUS konnte die lokale Datenbank nicht initialisieren: {e}',file=sys.stderr);return 1
    server.timeout=1
    port=server.server_port;url=f'http://127.0.0.1:{port}/'
    try:
        runtime_path.write_text(json.dumps({'port':port,'pid':os.getpid(),'started_at':utcnow()}),encoding='utf-8')
        os.chmod(runtime_path,0o600)
    except OSError as exc:print(f'[KOR] Hinweis: Laufzeitstatus nicht speicherbar: {exc}',file=sys.stderr)
    print(f'{APP_NAME} {VERSION}');print(f'Datenbank: {DB_PATH}');print(f'Backups: {BACKUP_DIR}');print(f'Lokale Oberfläche: {url}')
    if os.environ.get('KOR_NO_BROWSER')!='1':
        threading.Timer(0.35,lambda:open_app_or_report(url)).start()
    stop_backups=threading.Event();server.shutdown_event=threading.Event()
    def backup_loop():
        while not stop_backups.wait(30):maybe_backup()
    backup_thread=threading.Thread(target=backup_loop,name='kor-backup-scheduler',daemon=True);backup_thread.start()
    # LAN discovery powers the live HUD; beacons contain no user data.
    try: mesh.start()
    except Exception as exc: add_system_log('WARN','MESH','Netzwerkerkennung konnte nicht starten: '+str(exc))
    native_started=False
    if os.environ.get('KOR_NO_BROWSER')!='1' and os.environ.get('KOR_NATIVE_WINDOW','auto')!='0':
        try:
            from core.window import start_native_app
            def serve_http():
                try: server.serve_forever(poll_interval=0.25)
                except Exception as exc: add_system_log('ERROR','HTTP','Server-Thread beendet: '+str(exc))
            server_thread=threading.Thread(target=serve_http,name='kor-http-server',daemon=True);server_thread.start()
            try:
                start_native_app(url)
                native_started=True
            finally:
                server.shutdown()
        except (ImportError,ModuleNotFoundError) as exc:
            add_system_log('WARN','WINDOW','PyQt6 WebEngine nicht installiert; verwende Browser-Fenster. '+str(exc))
        except Exception as exc:
            add_system_log('ERROR','WINDOW','Natives Fenster konnte nicht gestartet werden; verwende Browser-Fallback. '+str(exc))
    if not native_started and not server.shutdown_event.is_set():
        if os.environ.get('KOR_NO_BROWSER')!='1':
            threading.Timer(0.35,lambda:open_app_or_report(url)).start()
        try:
            while not server.shutdown_event.is_set():server.handle_request()
        except KeyboardInterrupt:print('\nKOR-NEXUS wird beendet.')
    stop_backups.set()
    try: mesh.stop()
    except Exception: pass
    server.server_close()
    try:
        if json.loads(runtime_path.read_text(encoding='utf-8')).get('port')==port:runtime_path.unlink(missing_ok=True)
    except Exception:pass
    return 0

if __name__=='__main__': raise SystemExit(main())
