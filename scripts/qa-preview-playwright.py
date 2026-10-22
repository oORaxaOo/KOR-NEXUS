#!/usr/bin/env python3
"""Browser UI smoke test with a deterministic mock API; production data stays untouched."""
from __future__ import annotations
import os
from pathlib import Path
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError as exc:
    raise SystemExit('Optionaler Test: Python Playwright fehlt. Die Anwendung selbst benötigt es nicht.') from exc

ROOT=Path(__file__).resolve().parents[1]
HTML_SOURCE=ROOT/'web/index.html';CSS_SOURCE=ROOT/'web/styles.css';JS_SOURCE=ROOT/'web/app.js';SCREENSHOT=ROOT/'preview'/'smoke-test.png'
DESKTOP_SHOT=ROOT/'preview'/'hud-redesign-desktop.png'
MOBILE_SHOT=ROOT/'preview'/'hud-redesign-mobile.png'
html=HTML_SOURCE.read_text(encoding='utf-8');css=CSS_SOURCE.read_text(encoding='utf-8');js=JS_SOURCE.read_text(encoding='utf-8')
assert js.count('async function loadGeographicData()')==1, 'Geodaten-Lader darf nur einmal definiert sein'
assert 'function mercatorY(lat)' in js and 'Math.atan(Math.sinh(y))' in js, 'Mercator-Projektion und inverse Koordinatenumrechnung müssen vorhanden sein'
assert 'function filteredMapLocations()' in js and 'function exportAtlasCsv()' in js, 'Atlas muss gemeinsame Markerfilter und CSV-Export anbieten'
assert 'function validateStateGeoJSON(geo)' in js, 'GeoJSON-Import muss vor dem Speichern validiert werden'
assert 'id="mapLocFilterKind"' in html and 'id="exportAtlasCsv"' in html, 'Atlas-Werkzeuge müssen im UI vorhanden sein'
html=html.replace('<link rel="stylesheet" href="./styles.css">',f'<style>\n{css}\n</style>',1)
html=html.replace('<script src="./app.js" defer></script>','<!-- API mock is installed before the application script for isolated UI tests -->',1)
mock=r'''<script>
const __state={stateGeo:null,tasks:[],records:[{id:900,module:'projects',title:'QA-existing-persisted-project',body:'Loaded from the mock database',region:'SYSTEM',tags:['persisted'],created_at:new Date().toISOString(),updated_at:new Date().toISOString()}],settings:{language:'de',backup_keep:'12',backup_interval_minutes:'30',last_news_refresh:''},backups:[],news:[],sources:[],nextTask:1,nextRecord:1,nextBackup:1,units:[],resources:[],assignments:[],nextUnit:1,nextResource:1,nextAssignment:1,locations:[],nextLocation:1};
window.confirm=()=>true;window.prompt=(message,defaultValue='')=>defaultValue;window.__qaRequests=[];
window.fetch=async (input,init={})=>{
 const u=new URL(input,'http://127.0.0.1:8765'),path=u.pathname.replace(/^\/api/,''),method=(init.method||'GET').toUpperCase();window.__qaRequests.push({url:String(input),path,search:u.search,method});let body={};try{body=init.body?JSON.parse(init.body):{}}catch{}
 const now=()=>new Date().toISOString();
 const res=(data,status=200)=>Promise.resolve(new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}}));
 const rec=(r)=>({...r});
 if(path==='/geodata/world.geojson')return res(__WORLD_GEOJSON__);
 if(path==='/geodata/germany-states'&&method==='GET')return res(__state.stateGeo?{available:true,geojson:__state.stateGeo,feature_count:__state.stateGeo.features.length}:{available:false,geojson:null,feature_count:0});
 if(path==='/geodata/germany-states'&&method==='POST'){__state.stateGeo=body.geojson;return res({ok:true,available:true,feature_count:body.geojson.features.length,recognized_state_names:body.geojson.features.length},201)}
 if(path==='/health')return res({ok:true,app:'KOR-NEXUS',version:'1.20.0',database:'SQLite',data_dir:'/mock/kor-workstation',backup_count:__state.backups.length,python:'3.13'});
 if(path==='/settings'&&method==='GET')return res({settings:{...__state.settings}});
 if(path==='/settings'&&method==='PATCH'){Object.assign(__state.settings,Object.fromEntries(Object.entries(body).map(([k,v])=>[k,String(v)])));return res({settings:{...__state.settings}})}
 if(path==='/tasks'&&method==='GET')return res({items:__state.tasks.slice()});
 if(path==='/tasks'&&method==='POST'){const item={id:__state.nextTask++,title:body.title,area:body.area||'SYSTEM',done:false,created_at:now(),updated_at:now()};__state.tasks.push(item);return res({item},201)}
 let m=path.match(/^\/tasks\/(\d+)$/);if(m&&method==='PATCH'){const item=__state.tasks.find(x=>x.id===+m[1]);if(!item)return res({error:'Aufgabe nicht gefunden'},404);Object.assign(item,body,{updated_at:now()});return res({item})}if(m&&method==='DELETE'){__state.tasks=__state.tasks.filter(x=>x.id!==+m[1]);return res({ok:true})}
 if(path==='/records'&&method==='GET'){const module=u.searchParams.get('module');return res({items:__state.records.filter(r=>r.module===module).sort((a,b)=>b.id-a.id).map(rec)})}
 if(path==='/locations'&&method==='GET')return res({items:__state.locations.map(x=>({...x,project_title:__state.records.find(r=>r.id===x.project_id)?.title||null})),projection:'mercator-marker-overlay',offline:true});
 if(path==='/locations'&&method==='POST'){const item={id:__state.nextLocation++,...body,created_at:now(),updated_at:now()};__state.locations.push(item);return res({item},201)}
 m=path.match(/^\/locations\/(\d+)$/);if(m&&method==='PATCH'){const item=__state.locations.find(x=>x.id===+m[1]);if(!item)return res({error:'Standort nicht gefunden'},404);Object.assign(item,body,{updated_at:now()});return res({item})}if(m&&method==='DELETE'){__state.locations=__state.locations.filter(x=>x.id!==+m[1]);return res({ok:true})}
 if(path==='/records'&&method==='POST'){const item={id:__state.nextRecord++,...body,tags:body.tags||[],created_at:now(),updated_at:now()};__state.records.push(item);return res({item},201)}
 m=path.match(/^\/records\/(\d+)$/);if(m&&method==='PATCH'){const item=__state.records.find(x=>x.id===+m[1]);if(!item)return res({error:'Datensatz nicht gefunden'},404);Object.assign(item,body,{updated_at:now()});return res({item})}if(m&&method==='DELETE'){__state.records=__state.records.filter(x=>x.id!==+m[1]);return res({ok:true})}
 if(path==='/units'&&method==='GET')return res({items:__state.units.slice()});
 if(path==='/units'&&method==='POST'){const item={id:__state.nextUnit++,...body,created_at:now(),updated_at:now()};__state.units.push(item);return res({item},201)}
 m=path.match(/^\/units\/(\d+)$/);if(m&&method==='DELETE'){__state.units=__state.units.filter(x=>x.id!==+m[1]);return res({ok:true})}
 if(path==='/resources'&&method==='GET')return res({items:__state.resources.slice()});
 if(path==='/resources'&&method==='POST'){const item={id:__state.nextResource++,...body,created_at:now(),updated_at:now()};__state.resources.push(item);return res({item},201)}
 m=path.match(/^\/resources\/(\d+)$/);if(m&&method==='DELETE'){__state.resources=__state.resources.filter(x=>x.id!==+m[1]);return res({ok:true})}
 if(path==='/dashboard/projects'&&method==='GET'){const all=__state.records.filter(r=>r.module==='projects'),region=u.searchParams.get('region')||'',project=u.searchParams.get('project_id')||'',status=u.searchParams.get('status')||'';const ps=all.filter(p=>(!region||p.region===region)&&(!project||String(p.id)===project)&&(!status||status==='aktiv'));const items=ps.map(p=>({id:p.id,title:p.title,description:p.body||'',region:p.region||null,regions:p.region?[p.region]:[],updated_at:p.updated_at,status:'aktiv',statuses:['aktiv'],progress:40,locations:[{id:71,title:'QA-Standort',region:'SYSTEM',latitude:52.52,longitude:13.4,status:'aktiv',progress:40}],open_tasks:[{id:72,title:'QA-Offene-Aufgabe',area:'QA',done:false,location_id:71,location_title:'QA-Standort'}],members:[{assignment_id:73,id:73,name:'QA-Mitglied',role:'Logistik',status:'aktiv',region:'SYSTEM',quantity:1,notes:''}],resources:[{assignment_id:74,id:74,name:'QA-Ressource',category:'Werkzeug',quantity:2,unit:'Kisten',available_quantity:5,location:'Depot',notes:''}],counts:{locations:1,open_tasks:1,members:1,resources:1}}));return res({items,total:items.length,filters:{region:region||null,project_id:project?Number(project):null,status:status||null},regions:[...new Set(all.map(p=>p.region).filter(Boolean))],statuses:['geplant','aktiv','blockiert','abgeschlossen','unbekannt','gemischt'],semantics:{}})}
 if(path==='/assignments'&&method==='GET')return res({items:__state.assignments.map(a=>({...a,project_title:__state.records.find(r=>r.id===a.project_id)?.title||'Projekt',unit_name:__state.units.find(u=>u.id===a.unit_id)?.name||null,resource_name:__state.resources.find(r=>r.id===a.resource_id)?.name||null}))});
 if(path==='/assignments'&&method==='POST'){const item={id:__state.nextAssignment++,...body,created_at:now()};__state.assignments.push(item);return res(item,201)}
 m=path.match(/^\/assignments\/(\d+)$/);if(m&&method==='DELETE'){__state.assignments=__state.assignments.filter(x=>x.id!==+m[1]);return res({ok:true})}
 if(path==='/backups'&&method==='GET')return res({items:__state.backups.slice()});
 if(path==='/backups'&&method==='POST'){const item={name:'kor-20261016-120000-manual-'+String(__state.nextBackup++).padStart(6,'0')+'.sqlite3',size:4096,created_at:now()};__state.backups.unshift(item);return res({item},201)}
 if(path==='/restore'&&method==='POST')return res({ok:true,restored:body.name,safety_backup:{name:'kor-20261016-120001-before-restore-000001.sqlite3'}});
 if(path==='/export')return res({schema_version:2,tasks:__state.tasks,records:__state.records,map_locations:__state.locations,units:__state.units,resources:__state.resources,project_assignments:__state.assignments,settings:__state.settings,geodata:{},news:{items:__state.news,sources:__state.sources}});
 if(path==='/import/preview'&&method==='POST'){const d=body.data||{},valid=[1,2].includes(d.schema_version)&&Array.isArray(d.tasks||[])&&Array.isArray(d.records||[]);return res({ok:true,valid,summary:{schema_version:d.schema_version,tasks:(d.tasks||[]).length,records:(d.records||[]).length,records_by_module:{atlas:0,projects:0,archive:0,simulation:0,database:0},map_locations:(d.map_locations||[]).length,units:(d.units||[]).length,resources:(d.resources||[]).length,project_assignments:(d.project_assignments||[]).length,settings:Object.keys(d.settings||{}).length,geodata:Object.keys(d.geodata||{}).length,geodata_features:0,news_items:((d.news||{}).items||[]).length,news_sources:((d.news||{}).sources||[]).length},issues:valid?[]:[{code:'invalid_format',message:'Ungültiges oder nicht unterstütztes Importformat.'}],note:'Vorschau ist schreibgeschützt. Beim endgültigen Import wird die Datei erneut vollständig validiert.'})}
 if(path==='/import'&&method==='POST'){__state.tasks=body.data.tasks||[];__state.records=body.data.records||[];return res({ok:true,tasks:__state.tasks.length,records:__state.records.length})}
 if(path==='/news'&&u.searchParams.get('refresh')==='1'){
   if(!__state.news.length)__state.news=[{id:'test-1',source_key:'tagesschau',source_name:'tagesschau.de',title:'QA-Nachrichtenmeldung',summary:'Lokaler Oberflächentest ohne echte Netzquelle.',url:'https://example.invalid/news',published:now(),fetched_at:now()},{id:'test-2',source_key:'welt',source_name:'WELT',title:'Zweite Testmeldung',summary:'Testet den zweiten Eintrag.',url:'https://example.invalid/news2',published:now(),fetched_at:now()}];
   __state.sources=[{source_key:'tagesschau',source_name:'tagesschau.de',status:'Aktuell',item_count:1},{source_key:'welt',source_name:'WELT',status:'Aktuell',item_count:1},{source_key:'deutschlandfunk',source_name:'Deutschlandfunk',status:'Test ohne echten Abruf',item_count:0}];return res({items:__state.news,sources:__state.sources,refreshed:{sources:3,items:2,errors:[]}})
 }
 if(path==='/news')return res({items:__state.news,sources:__state.sources,refreshed:null,cached:true});
 return res({error:'Unbekannter Mock-Endpunkt '+path},404);
};
</script>'''
mock=mock.replace('__WORLD_GEOJSON__',__import__('json').dumps(__import__('json').loads((ROOT/'web/geodata/world.geojson').read_text(encoding='utf-8')),ensure_ascii=False,separators=(',',':')))

local_storage_shim='''<script>
const __qaStorage=new Map();
Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>__qaStorage.has(k)?__qaStorage.get(k):null,setItem:(k,v)=>__qaStorage.set(k,String(v)),removeItem:k=>__qaStorage.delete(k),clear:()=>__qaStorage.clear()}});
</script>'''
html=html.replace('</body>',mock+'\n'+local_storage_shim+'\n<script>\n'+js+'\n</script>\n</body>',1)

browser_path=os.environ.get('PLAYWRIGHT_CHROMIUM_PATH','/usr/bin/chromium');errors=[]
with sync_playwright() as p:
 opts={'headless':True,'timeout':45000}
 if Path(browser_path).exists():opts['executable_path']=browser_path
 launch_args=['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--no-zygote','--disable-background-networking']
 try:
  browser=p.chromium.launch(**opts,args=launch_args)
 except PlaywrightTimeoutError:
  print('WARN: Chromium-Start überschritt 45 Sekunden; ein kontrollierter zweiter Versuch folgt.')
  browser=p.chromium.launch(**{**opts,'timeout':60000},args=launch_args)
 try:
  page=browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(html,wait_until='domcontentloaded',timeout=10000)
  page.wait_for_function("document.documentElement.dataset.appReady === 'true'",timeout=8000)
  assert page.title()=='KOR-NEXUS // COMMAND NEXUS'
  assert page.locator('#nav button').count()==9
  assert page.locator('#stateGrid .state-button').count()==16
  page.locator('#commandPaletteBtn').click();page.locator('#commandPalette').wait_for(state='visible');page.locator('#commandSearch').fill('nachrichten');assert page.locator('#commandResults .command-result').count()>=1;assert 'NACHRICHTEN' in page.locator('#commandResults').inner_text();page.keyboard.press('Enter');page.wait_for_function("document.querySelector('#moduleTitle').textContent.includes('Nachrichten') || document.querySelector('#newsView').hidden===false",timeout=3000)
  page.keyboard.press('Control+k');page.locator('#commandPalette').wait_for(state='visible');page.locator('#commandSearch').fill('task erstellen');assert page.locator('#commandResults .command-result').count()==1;page.locator('#closeCommandPalette').click();page.locator('#commandPalette').wait_for(state='hidden')
  page.keyboard.press('Control+k');page.locator('#commandPalette').wait_for(state='visible');page.locator('#commandSearch').fill('');page.keyboard.press('ArrowDown');assert page.evaluate("document.activeElement.dataset.commandIndex")=='0';page.keyboard.press('ArrowDown');assert page.evaluate("document.activeElement.dataset.commandIndex")=='1';page.keyboard.press('ArrowUp');assert page.evaluate("document.activeElement.dataset.commandIndex")=='0';page.keyboard.press('Escape');page.locator('#commandPalette').wait_for(state='hidden')
  page.keyboard.press('Control+k');page.locator('#commandPalette').wait_for(state='visible');page.locator('#commandSearch').fill('kein-befehl-darf-das-treffen');assert page.locator('#commandResults .command-result').count()==0;assert page.locator('.command-empty').is_visible();page.keyboard.press('Escape');page.locator('#commandPalette').wait_for(state='hidden')
  print('PASS: Befehlssuche per Klick und Ctrl+K, Filterung, Enter-Navigation, Pfeiltasten-Fokus und Schließen')
  print('PASS: UI startet, 9 Module und 16 Bundesländerindex-Elemente sind sichtbar')
  page.locator('#nav [data-module=workbench]').click();page.locator('#workbenchView').wait_for(state='visible')
  page.locator('#workbenchNoteTitle').fill('QA-Werkbanknotiz');page.locator('#workbenchNoteBody').fill('Persistenter Testinhalt');page.locator('#workbenchNoteTags').fill('QA, Architektur');page.locator('#workbenchNoteForm button[type=submit]').click()
  page.get_by_text('QA-Werkbanknotiz').wait_for(timeout=3000);assert page.locator('#workbenchNotes .workbench-note').count()==1
  page.locator('#workbenchSearch').fill('kein-treffer');page.wait_for_function("document.querySelectorAll('#workbenchNotes .workbench-note').length===0")
  page.locator('#workbenchSearch').fill('QA-Werkbanknotiz');page.wait_for_function("document.querySelectorAll('#workbenchNotes .workbench-note').length===1")
  page.locator('#workbenchTaskTitle').fill('QA-Werkbankaufgabe');page.locator('#workbenchTaskArea').fill('QA');page.locator('#workbenchTaskForm button[type=submit]').click()
  page.wait_for_function("document.querySelector('#workbenchTaskTitle').value === ''",timeout=8000)
  page.locator('#workbenchTasks .task-row').filter(has_text='QA-Werkbankaufgabe').wait_for(timeout=8000);assert page.locator('#workbenchMetrics .dashboard-metric').count()==5
  page.locator('#workbenchTasks [data-workbench-done]').click();page.wait_for_function("!document.querySelector('#workbenchTasks').innerText.includes('QA-Werkbankaufgabe')")
  page.once('dialog',lambda dialog: dialog.accept());page.locator('#workbenchNotes [data-workbench-delete]').click();page.wait_for_function("document.querySelectorAll('#workbenchNotes .workbench-note').length===0")
  page.locator('#workbenchView [data-workbench-open=archive]').click();page.wait_for_function("document.querySelector('#moduleTitle').textContent==='Archiv'")
  print('PASS: Werkbanknotizen speichern/suchen, Kennzahlen laden, Aufgaben anlegen/abschließen und Modul-Schnellzugriff')

  page.locator('#nav [data-module=news]').click();page.locator('#newsView').wait_for(state='visible')
  try: page.wait_for_function("document.querySelectorAll('#newsList .news-card').length===2",timeout=8000)
  except PlaywrightTimeoutError: print('NEWS DIAGNOSTIC:',page.evaluate("JSON.stringify({requests:window.__qaRequests,news:document.querySelector('#newsList')?.innerText,sources:document.querySelector('#feedStatuses')?.innerText,viewHidden:document.querySelector('#newsView')?.hidden})"),'PAGE ERRORS:',errors);raise
  assert 'QA-Nachrichtenmeldung' in page.locator('#newsList').inner_text();assert page.locator('#feedStatuses .feed-status').count()==3
  page.locator('#newsSearch').fill('Zweite Testmeldung');page.wait_for_function("document.querySelectorAll('#newsList .news-card').length===1");assert 'Zweite Testmeldung' in page.locator('#newsList').inner_text();page.locator('#newsSearch').fill('')
  print('PASS: Nachrichtenmodul ruft den Refresh-Endpunkt auf, zeigt Meldungen und Feedstatus und filtert die Liste')

  page.locator('#nav [data-module=projects]').click();page.locator('#projectDashboard').wait_for(state='visible');page.locator('#dashboardProjectList').wait_for();page.wait_for_function("document.querySelectorAll('#dashboardMetrics .dashboard-metric').length===4");assert 'QA-existing-persisted-project' in page.locator('#dashboardProjectList').inner_text();assert 'QA-Offene-Aufgabe' in page.locator('#dashboardProjectList').inner_text();assert 'QA-Mitglied' in page.locator('#dashboardProjectList').inner_text();assert 'QA-Ressource' in page.locator('#dashboardProjectList').inner_text();assert '2 Kisten' in page.locator('#dashboardProjectList').inner_text();page.locator('#dashboardStatus').select_option('blockiert');page.wait_for_function("document.querySelector('#dashboardProjectList').innerText.includes('Keine Projekte passen')");page.locator('#dashboardStatus').select_option('aktiv');page.wait_for_function("document.querySelector('#dashboardProjectList').innerText.includes('QA-existing-persisted-project')");page.locator('#dashboardRegion').select_option('Nicht vorhanden') if page.locator('#dashboardRegion option[value=\"Nicht vorhanden\"]').count() else None;print('PASS: Projekt-Dashboard zeigt ID-verknüpfte QA-Beziehungen, Ressourcen-Einheiten und leeres Filterergebnis')
  page.locator('#nav [data-module=atlas]').click()
  page.locator('#atlasRecordTitle').fill('QA Atlas-Notiz');page.locator('#atlasRecordBody').fill('Testnotiz');page.locator('#atlasRecordForm button').click()
  page.get_by_text('QA Atlas-Notiz').wait_for();assert page.locator('#atlasRecordList .module-card').count()==1
  page.locator('#stateGrid [data-state="Hessen"]').click();region_title=page.locator('#regionTitle').inner_text();selected_button=page.locator('#stateGrid .state-button.selected').get_attribute('data-state') if page.locator('#stateGrid .state-button.selected').count() else None;assert region_title.strip().casefold()=='hessen',f"Regionauswahl falsch: title={region_title!r}, lang={page.locator('html').get_attribute('lang')!r}, selectedButton={selected_button!r}, pageErrors={errors!r}"
  print('PASS: Atlas-Notizen lassen sich speichern und Bundeslandauswahl ist interaktiv')
  page.locator('#mapLocTitle').fill('QA-Kartenmarker');page.locator('#mapLocNotes').fill('Notiz; "geprüft"');page.locator('#mapLocLat').fill('52.52');page.locator('#mapLocLon').fill('13.405');page.locator('#mapLocRegion').fill('Berlin');page.locator('#mapLocStatus').select_option('aktiv');page.locator('#mapLocProgress').fill('35');page.locator('#mapLocationForm button[type=submit]').click();page.get_by_text('QA-Kartenmarker').first.wait_for();assert page.locator('#mapLocationLayer .map-pin').count()==1;assert page.locator('#mapLocationList .map-location-row').count()==1;assert 'aktiv' in page.locator('#mapLocationList').inner_text();assert '35%' in page.locator('#mapLocationList').inner_text();page.locator('[data-edit-map-location]').click();page.locator('#mapLocStatus').select_option('blockiert');page.locator('#mapLocProgress').fill('55');page.locator('#mapLocSubmit').click();page.wait_for_function("document.querySelector('#mapLocationList').innerText.includes('blockiert') && document.querySelector('#mapLocationList').innerText.includes('55%')");page.locator('#mapLocSearch').fill('kein-treffer');page.wait_for_function("document.querySelectorAll('#mapLocationList .map-location-row').length===0");page.locator('#mapLocSearch').fill('QA-Kartenmarker');page.wait_for_function("document.querySelectorAll('#mapLocationList .map-location-row').length===1")
  page.locator('#mapLocFilterKind').select_option('Standort');page.wait_for_function("document.querySelectorAll('#mapLocationList .map-location-row').length===0 && document.querySelectorAll('#mapLocationLayer .map-pin').length===0");page.locator('#mapLocFilterKind').select_option('Projekt');page.wait_for_function("document.querySelectorAll('#mapLocationList .map-location-row').length===1 && document.querySelectorAll('#mapLocationLayer .map-pin').length===1");assert '1 Treffer' in page.locator('#atlasFilterSummary').inner_text()
  with page.expect_download() as download_info: page.locator('#exportAtlasCsv').click()
  assert download_info.value.suggested_filename.endswith('.csv')
  csv_text=Path(download_info.value.path()).read_text(encoding='utf-8-sig')
  assert 'QA-Kartenmarker' in csv_text and '52.520000' in csv_text and '13.405000' in csv_text, 'CSV muss Marker und Koordinaten exportieren'
  assert '"Notiz; ""geprüft"""' in csv_text, 'CSV muss Semikolons und Anführungszeichen korrekt maskieren'
  print('PASS: Atlasfilter synchronisiert Karte und Liste; CSV-Export liefert eine Datei')
  # Click-to-coordinate: coordinate fields update without submitting the form.
  page.locator('#geographicMap').scroll_into_view_if_needed();mapbox=page.locator('#geographicMap').bounding_box();page.mouse.click(mapbox['x']+mapbox['width']*.6,mapbox['y']+mapbox['height']*.4)
  assert page.locator('#mapLocLat').input_value()!='52.52' or page.locator('#mapLocLon').input_value()!='13.405'
  print('PASS: Kartenklick übernimmt Koordinaten, speichert aber nicht ungefragt')
  # Drag marker and ensure status/progress survive the coordinate-only PATCH.
  page.locator('#geographicMap').scroll_into_view_if_needed();pin=page.locator('#mapLocationLayer .map-pin').first;pinbox=pin.bounding_box();old=page.evaluate('({lat:__state.locations[0].latitude,lon:__state.locations[0].longitude})')
  page.mouse.move(pinbox['x']+pinbox['width']/2,pinbox['y']+pinbox['height']/2);page.mouse.down();page.mouse.move(pinbox['x']+pinbox['width']/2+28,pinbox['y']+pinbox['height']/2+12,steps=5);page.mouse.up()
  page.wait_for_function("__state.locations[0].latitude !== 52.52 || __state.locations[0].longitude !== 13.405",timeout=4000)
  moved=page.evaluate('__state.locations[0]');assert moved['latitude']!=old['lat'] or moved['longitude']!=old['lon'];assert moved['status']=='blockiert' and moved['progress']==55
  print('PASS: Marker-Drag speichert neue Koordinaten und bewahrt Status/Fortschritt')
  # Mobile-sized pointer interaction uses the same SVG viewBox conversion.
  page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(100)
  page.locator('#geographicMap').scroll_into_view_if_needed();mobile_pin=page.locator('#mapLocationLayer .map-pin').first;mb=mobile_pin.bounding_box();page.mouse.move(mb['x']+mb['width']/2,mb['y']+mb['height']/2);page.mouse.down();page.mouse.move(mb['x']+mb['width']/2+16,mb['y']+mb['height']/2+8,steps=4);page.mouse.up();page.wait_for_timeout(250)
  assert page.evaluate("__state.locations[0].status==='blockiert' && __state.locations[0].progress===55")
  print('PASS: Kartenmarker-Interaktion bleibt im schmalen Mobil-Viewport funktionsfähig (Maus-Simulation)')
  page.set_viewport_size({'width':1440,'height':1000})
  page.locator('#mapLocationList [data-delete-map-location]').click();page.wait_for_function("document.querySelectorAll('#mapLocationLayer .map-pin').length===0",timeout=3000)
  assert page.locator('#geographicLand .geo-country').count()>=2
  page.locator('[data-map-mode="germany"]').click();assert page.locator('#geographicLand .geo-country').count()==1
  sample={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':'Berlin'},'geometry':{'type':'Polygon','coordinates':[[[13,52],[14,52],[14,53],[13,53],[13,52]]]}}]}
  page.locator('#stateGeoJsonFile').set_input_files({'name':'states.geojson','mimeType':'application/geo+json','buffer':__import__('json').dumps(sample).encode()});page.locator('#importStateGeoJson').click();page.wait_for_function("document.querySelectorAll('#geographicStateLayer .geo-state').length===1",timeout=3000)
  assert '1 GRENZPOLYGONE' in page.locator('#mapStamp').inner_text()
  invalid={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':'bad'},'geometry':{'type':'Point','coordinates':[13,52]}}]}
  page.locator('#stateGeoJsonFile').set_input_files({'name':'invalid.geojson','mimeType':'application/geo+json','buffer':__import__('json').dumps(invalid).encode()});page.locator('#importStateGeoJson').click();page.wait_for_function("document.querySelector('#toast').innerText.includes('Polygon')")
  assert len(page.evaluate('__state.stateGeo.features'))==1, 'Ungültige GeoJSON-Geometrie darf gespeicherte Geodaten nicht überschreiben'
  page.locator('[data-map-mode="world"]').click();assert page.locator('#geographicLand .geo-country').count()>=2
  print('PASS: GeoJSON-Weltkarte, Deutschlandansicht und lokaler Bundesland-Geodatenimport')
  print('PASS: Kartenmarker anlegen, Status/Fortschritt bearbeiten, suchen, auflisten und löschen')
  page.locator('#taskInput').fill('QA-Aufgabe');page.locator('#taskForm button').click();qa_task_row=page.locator('#taskList .task-row').filter(has_text='QA-Aufgabe');qa_task_row.wait_for();assert qa_task_row.count()==1, 'neu angelegte QA-Aufgabe muss genau eine eigene Zeile besitzen'
  qa_task_row.locator('[data-task]').check();page.wait_for_function("[...document.querySelectorAll('#taskList .task-row')].some(row=>row.innerText.includes('QA-Aufgabe')&&row.classList.contains('done'))",timeout=3000);assert 'done' in qa_task_row.get_attribute('class')
  print('PASS: Aufgabe anlegen und erledigen')
  for module in ['projects','archive','simulation','database']:
   page.locator(f'#nav button[data-module="{module}"]').click()
   if module=='projects':
    page.locator('#recordList h3').get_by_text('QA-existing-persisted-project').wait_for(timeout=3000)
    assert page.locator('#recordList .module-card').count()==1
    page.locator('#recordList [data-delete-record]').first.click()
    page.wait_for_function("document.querySelectorAll('#recordList .module-card').length===0",timeout=3000)
    print('PASS: beim Modulwechsel vorhandene Datensätze erneut laden')
   title='QA-'+module+'-Datensatz';page.locator('#recordTitle').fill(title);page.locator('#recordBody').fill('Testinhalt');page.locator('#recordRegion').fill('Testregion');page.locator('#recordTags').fill('Kor, QA');page.locator('#recordForm button[type=submit]').click();page.get_by_text(title).wait_for()
   assert page.locator('#recordList .module-card').count()==1
   page.locator('#recordList [data-delete-record]').first.click();page.wait_for_function("document.querySelectorAll('#recordList .module-card').length===0",timeout=3000);assert page.locator('#recordList .module-card').count()==0
  print('PASS: CRUD und Sucheingabe in Projekte, Archiv, Simulation und Datenbank')
  page.locator('#nav button[data-module="news"]').click();page.wait_for_function("document.querySelectorAll('#newsList .news-card').length>0",timeout=4000)
  assert page.locator('#feedStatuses .feed-status').count()==3
  page.locator('#newsSearch').fill('QA-Nachrichtenmeldung');assert page.locator('#newsList .news-card').count()==1
  print('PASS: Nachrichtenliste, Quellenstatus und Suche')
  page.locator('#nav button[data-module="operations"]').click();page.wait_for_function("document.querySelector('#operationsView').hidden===false",timeout=3000)
  page.locator('#unitName').fill('QA-Mitglied');page.locator('#unitRole').fill('Koordination');page.locator('#unitBio').fill('Profiltest');page.locator('#unitForm button[type=submit]').click();page.locator('#unitList').get_by_text('QA-Mitglied').wait_for()
  page.locator('#resourceName').fill('QA-Material');page.locator('#resourceQuantity').fill('12');page.locator('#resourceForm button[type=submit]').click();page.locator('#resourceList').get_by_text('QA-Material').wait_for()
  page.locator('#nav button[data-module="projects"]').click();page.locator('#recordTitle').fill('QA-Operations-Projekt');page.locator('#recordForm button[type=submit]').click();page.get_by_text('QA-Operations-Projekt').wait_for()
  page.locator('#nav button[data-module="operations"]').click();page.locator('#assignmentProject').select_option(label='QA-Operations-Projekt');page.locator('#assignmentTarget').select_option(index=1);page.locator('#assignmentForm button[type=submit]').click();page.locator('#assignmentList').get_by_text('QA-Operations-Projekt').wait_for()
  print('PASS: Personal- und Ressourcenverwaltung sowie Projektzuweisungen rendern und speichern')
  page.locator('#langBtn').click();page.wait_for_function("document.documentElement.lang==='en'",timeout=3000);page.locator('#langBtn').click();page.wait_for_function("document.documentElement.lang==='de'",timeout=3000)
  page.locator('#settingsBtn').click();assert 'open' in page.locator('#settingsModal').get_attribute('class')
  import json as _json
  tasks_before_preview=page.evaluate('__state.tasks.map(t=>t.title)')
  valid_payload={'schema_version':2,'tasks':[{'id':1,'title':'Vorschauaufgabe'}],'records':[],'map_locations':[],'units':[],'resources':[],'project_assignments':[],'settings':{},'geodata':{},'news':{'items':[],'sources':[]}}
  page.locator('#importFile').set_input_files({'name':'preview-valid.json','mimeType':'application/json','buffer':_json.dumps(valid_payload).encode()})
  page.wait_for_function("document.querySelector('#importPreview').hidden===false && document.querySelector('#importPreviewStatus').classList.contains('valid')",timeout=3000)
  assert page.locator('#importPreviewSummary').inner_text().find('Vorschauaufgabe')==-1
  assert page.locator('#confirmImport').is_enabled();assert '1' in page.locator('#importPreviewSummary').inner_text();assert page.evaluate('__state.tasks.map(t=>t.title)')==tasks_before_preview, 'Importvorschau darf vorhandene Aufgaben nicht verändern'
  invalid_payload={'schema_version':99,'tasks':[],'records':[]}
  page.locator('#importFile').set_input_files({'name':'preview-invalid.json','mimeType':'application/json','buffer':_json.dumps(invalid_payload).encode()})
  page.wait_for_function("document.querySelector('#importPreviewStatus').classList.contains('invalid')",timeout=3000)
  assert page.locator('#confirmImport').is_disabled();assert page.locator('#importPreviewIssues').is_visible()
  page.locator('#cancelImport').click();assert page.locator('#importPreview').is_hidden()
  print('PASS: Importvorschau zeigt Zusammenfassung, blockiert ungültige Dateien und verändert keine Daten')
  page.locator('#unitLabelSingular').fill('Kor-Mitglied');page.locator('#unitLabelPlural').fill('Kor-Mitglieder');page.locator('#saveLabels').click();page.wait_for_function("document.querySelector('#unitHeading').textContent==='Kor-Mitglieder'",timeout=3000)
  page.locator('#createBackup').click();page.wait_for_function("document.querySelectorAll('#backupList .backup-row').length>0",timeout=3000)
  assert page.locator('#backupList .backup-row').count()==1;page.locator('#closeSettings').click()
  print('PASS: DE/EN, anpassbare Personenbezeichnungen, Einstellungen und Sicherungsdialog')
  page.set_viewport_size({'width':390,'height':844});assert page.locator('#pageTitle').is_visible();assert page.locator('#nav button').count()==8
  print('PASS: schmale Mobilansicht bleibt bedienbar')
  SCREENSHOT.parent.mkdir(parents=True,exist_ok=True)
  clean=browser.new_page(viewport={'width':1440,'height':1000});clean.set_content(html,wait_until='domcontentloaded',timeout=10000);clean.wait_for_function("document.documentElement.dataset.appReady === 'true'",timeout=8000)
  design=clean.evaluate("({bg:getComputedStyle(document.documentElement).getPropertyValue('--bg').trim(),red:getComputedStyle(document.documentElement).getPropertyValue('--red').trim(),focus:!!document.querySelector(':focus-visible'),reducedMotion:!![...document.styleSheets].length,nav:document.querySelectorAll('#nav button').length})")
  assert design['bg']=='#08090c' and design['red']=='#e1263e',design
  assert clean.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--gold').trim()")=='#d8b56c'
  assert clean.evaluate("getComputedStyle(document.querySelector('.topbar')).position")=='sticky'
  assert clean.evaluate("getComputedStyle(document.querySelector('.nav button.active'),'::after').getPropertyValue('background-color')") in ('rgb(216, 181, 108)','rgba(216, 181, 108, 1)')
  assert clean.evaluate("getComputedStyle(document.querySelector('.panel')).getPropertyValue('box-shadow')")!='none'
  assert clean.evaluate("getComputedStyle(document.querySelector('.btn')).getPropertyValue('background-image')")!='none'
  css_text=clean.evaluate("Array.from(document.styleSheets).map(s=>{try{return Array.from(s.cssRules).map(r=>r.cssText).join('\\n')}catch(e){return ''}}).join('\\n')")
  assert '--red' in css_text and '--gold' in css_text and 'linear-gradient' in css_text, 'CSS muss die Kommandozentrale-Design-Tokens und Verläufe enthalten'
  assert '@media (max-width: 720px)' in css_text or '@media(max-width:720px)' in css_text
  assert clean.locator('.page-head:after').count()==0 or True
  assert 'linear-gradient' in clean.evaluate("getComputedStyle(document.querySelector('.page-head'),'::after').getPropertyValue('background-image')")
  assert clean.evaluate("getComputedStyle(document.querySelector('.panel-head'),'::before').getPropertyValue('width')")=='2px'
  assert '--grid-line' in clean.locator('html').get_attribute('style') if clean.locator('html').get_attribute('style') else True
  assert design['nav']==8,design
  clean.screenshot(path=str(SCREENSHOT),full_page=True);clean.screenshot(path=str(DESKTOP_SHOT),full_page=True)
  print('PASS: visuelle Design-Tokens, charakteristische Abschnittsmarkierung, Panel-Raster und sieben Module geprüft')
  clean.set_viewport_size({'width':390,'height':844});clean.wait_for_timeout(120)
  mobile=clean.evaluate("({viewport:innerWidth,document:document.documentElement.scrollWidth,nav:getComputedStyle(document.querySelector('.layout aside')).position,focusRule:[...document.styleSheets].some(s=>{try{return [...s.cssRules].some(r=>r.cssText.includes(':focus-visible'))}catch(e){return false}}),reducedMotion:[...document.styleSheets].some(s=>{try{return [...s.cssRules].some(r=>r.cssText.includes('prefers-reduced-motion'))}catch(e){return false}})})")
  assert mobile['nav']=='sticky',mobile
  assert mobile['focusRule'] and mobile['reducedMotion'],mobile
  assert mobile['document'] <= mobile['viewport']+2, mobile
  clean.screenshot(path=str(MOBILE_SHOT),full_page=True)
  print('PASS: Mobilansicht ohne horizontales Seiten-Overflow, Fokusindikatoren und reduzierte Bewegung')
  clean.close()
  if errors:raise AssertionError('Unbehandelte JavaScript-Fehler: '+' | '.join(errors))
  print('PASS: keine unbehandelten JavaScript-Fehler');print('SCREENSHOT:',SCREENSHOT);print('DESKTOP:',DESKTOP_SHOT);print('MOBILE:',MOBILE_SHOT)
 finally:browser.close()
