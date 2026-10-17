import contextlib, io, json, tempfile, threading, unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

from core import server as app


class FakeResponse:
    status = 200
    def __init__(self, content): self.content=content
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,n=-1): return self.content[:n] if n>0 else self.content


class CoreApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        base=Path(self.tmp.name)
        app.DATA_HOME=base/'data';app.DB_PATH=app.DATA_HOME/'kor-workstation.sqlite3';app.BACKUP_DIR=app.DATA_HOME/'backups';app.GEODATA_DIR=app.DATA_HOME/'geodata';app.GERMANY_STATES_FILE=app.GEODATA_DIR/'germany-states.geojson'
        app._last_backup_monotonic=0
        app.initialize()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),app.AppHandler);self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.tmp.cleanup()
    def req(self,path,method='GET',body=None,headers=None):
        data=None if body is None else json.dumps(body).encode()
        req=Request(self.base+path,data=data,method=method,headers={'Content-Type':'application/json',**(headers or {})})
        try:
            with urlopen(req,timeout=5) as res:return res.status,json.loads(res.read().decode())
        except HTTPError as e:return e.code,json.loads(e.read().decode())
    def test_core_engine_status_is_read_only_and_llm_optional(self):
        _,before=self.req('/api/events?since=0&snapshot=1')
        status,initial=self.req('/api/engine/status')
        self.assertEqual(status,200)
        self.assertEqual(initial['state'],'ready')
        self.assertFalse(initial['llm_required'])
        self.assertEqual(initial['ai']['provider'],'disabled')
        self.assertFalse(initial['ai']['available'])
        self.assertEqual(initial['database']['integrity'],'ok')
        self.assertEqual(initial['database']['foreign_key_violations'],0)
        self.req('/api/tasks','POST',{'title':'Engine-Status-Test'})
        status,updated=self.req('/api/engine/status')
        self.assertEqual(status,200)
        self.assertEqual(updated['counts']['open_tasks'],initial['counts']['open_tasks']+1)
        _,after=self.req('/api/events?since=0&snapshot=1')
        self.assertEqual(after['latest_event_id'],before['latest_event_id']+1)
        self.assertEqual(updated['database']['event_cursor'],after['latest_event_id'])
        status,ai=self.req('/api/ai/status')
        self.assertEqual(status,200)
        self.assertFalse(ai['enabled'])
        self.assertFalse(ai['model_loaded'])

    def test_disabled_ai_provider_refuses_generation_without_side_effects(self):
        from core.ai_provider import AIUnavailableError, DisabledAIProvider
        provider=DisabledAIProvider()
        with self.assertRaises(AIUnavailableError):
            provider.generate('This must not run')
        self.assertFalse(provider.status()['available'])

    def test_scheduled_jobs_run_due_once_and_leave_future_jobs_pending(self):
        now=app.utcnow()
        status,created=self.req('/api/engine/jobs','POST',{'job_key':'qa-evaluate-now','job_type':'engine_evaluate','due_at':now})
        self.assertEqual(status,201)
        self.assertEqual(created['item']['status'],'pending')
        self.assertEqual(self.req('/api/engine/jobs','POST',{'job_key':'qa-evaluate-now','job_type':'engine_evaluate','due_at':now})[0],409)
        status,future=self.req('/api/engine/jobs','POST',{'job_key':'qa-future-automation','job_type':'run_automations','due_at':'2099-01-01T00:00:00Z'})
        self.assertEqual(status,201)
        status,run=self.req('/api/engine/jobs/run-due','POST',{})
        self.assertEqual(status,200)
        self.assertEqual(run['result']['processed'],1)
        self.assertEqual(run['result']['completed'],1)
        status,completed=self.req('/api/engine/jobs?status=completed')
        self.assertEqual(status,200)
        self.assertEqual(completed['count'],1)
        status,pending=self.req('/api/engine/jobs?status=pending')
        self.assertEqual(status,200)
        self.assertEqual(pending['count'],1)
        status,again=self.req('/api/engine/jobs/run-due','POST',{})
        self.assertEqual(again['result']['processed'],0)

    def test_automation_rules_are_idempotent_and_critical_actions_require_approval(self):
        _,resource=self.req('/api/resources','POST',{'name':'Automation-Ressource','quantity':1,'unit':'Kisten'})
        resource_id=resource['item']['id']
        self.req(f'/api/resources/{resource_id}/policy','PATCH',{'minimum_quantity':3})
        status,safe=self.req('/api/automation/rules','POST',{'rule_key':'low-stock-task','name':'Nachbestellaufgabe','trigger_type':'resource_low_stock','action_type':'create_task','action':{'title_prefix':'Nachbestellen: ','area':'Logistik'},'enabled':True})
        self.assertEqual(status,201)
        status,critical=self.req('/api/automation/rules','POST',{'rule_key':'low-stock-adjust','name':'Bestand anpassen','trigger_type':'resource_low_stock','action_type':'adjust_resource','action':{'quantity_delta':2,'notes':'Vorgeschlagener Wareneingang'},'enabled':True})
        self.assertEqual(status,201)
        status,run=self.req('/api/automation/run','POST',{})
        self.assertEqual(status,201)
        self.assertEqual(run['result']['actions_executed'],1)
        self.assertEqual(run['result']['proposals_created'],1)
        tasks=self.req('/api/tasks')[1]['items']
        self.assertEqual(sum(1 for task in tasks if task['title']=='Nachbestellen: Automation-Ressource'),1)
        status,proposals=self.req('/api/actions/proposals?status=pending')
        self.assertEqual(status,200)
        self.assertEqual(proposals['count'],1)
        proposal=proposals['items'][0]
        self.assertEqual(proposal['risk_level'],'critical')
        self.assertEqual(self.req(f"/api/actions/proposals/{proposal['id']}/execute",'POST',{})[0],409)
        status,again=self.req('/api/automation/run','POST',{})
        self.assertEqual(status,201)
        self.assertEqual(again['result']['already_run'],2)
        self.assertEqual(sum(1 for task in self.req('/api/tasks')[1]['items'] if task['title']=='Nachbestellen: Automation-Ressource'),1)
        status,approved=self.req(f"/api/actions/proposals/{proposal['id']}/approve",'POST',{})
        self.assertEqual(status,200)
        self.assertEqual(approved['item']['status'],'approved')
        status,executed=self.req(f"/api/actions/proposals/{proposal['id']}/execute",'POST',{})
        self.assertEqual(status,200)
        self.assertEqual(executed['item']['status'],'executed')
        status,resource_after=self.req('/api/resources')
        self.assertEqual(resource_after['items'][0]['quantity'],3)
        status,replay=self.req(f"/api/actions/proposals/{proposal['id']}/execute",'POST',{})
        self.assertEqual(status,200)
        self.assertTrue(replay['idempotent_replay'])
        self.assertEqual(self.req('/api/actions/proposals?status=pending')[1]['count'],0)

    def test_automation_rules_reject_unknown_actions_and_bad_keys(self):
        self.assertEqual(self.req('/api/automation/rules','POST',{'rule_key':'unsafe','name':'Unsafe','trigger_type':'manual','action_type':'run_shell','action':{},'enabled':True})[0],400)
        self.assertEqual(self.req('/api/automation/rules','POST',{'rule_key':'bad key','name':'Bad key','trigger_type':'manual','action_type':'create_task','action':{},'enabled':True})[0],400)
        self.assertEqual(self.req('/api/automation/rules','POST',{'rule_key':'manual-adjust','name':'Manual adjust','trigger_type':'manual','action_type':'adjust_resource','action':{'quantity_delta':2},'enabled':True})[0],400)

    def test_task_dependencies_roundtrip_remaps_both_task_ids(self):
        _,first=self.req('/api/tasks','POST',{'title':'Abhängigkeit A'})
        _,second=self.req('/api/tasks','POST',{'title':'Abhängigkeit B'})
        first_id,second_id=first['item']['id'],second['item']['id']
        status,created=self.req(f'/api/tasks/{first_id}/dependencies','POST',{'depends_on_task_id':second_id})
        self.assertEqual(status,201)
        payload=self.req('/api/export')[1]
        self.assertEqual(len(payload['task_dependencies']),1)
        payload['tasks'][0]['id']=70101
        payload['tasks'][1]['id']=70102
        payload['task_dependencies'][0]['task_id']=70101
        payload['task_dependencies'][0]['depends_on_task_id']=70102
        status,result=self.req('/api/import','POST',{'data':payload})
        self.assertEqual(status,200,result)
        with app.db_connect() as con:
            tasks=con.execute('SELECT id,title FROM tasks ORDER BY id').fetchall()
            deps=con.execute('SELECT * FROM task_dependencies').fetchall()
            self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
        ids_by_title={row['title']:row['id'] for row in tasks}
        self.assertNotEqual(ids_by_title['Abhängigkeit A'],70101)
        self.assertNotEqual(ids_by_title['Abhängigkeit B'],70102)
        self.assertEqual(len(deps),1)
        self.assertEqual((deps[0]['task_id'],deps[0]['depends_on_task_id']),(ids_by_title['Abhängigkeit A'],ids_by_title['Abhängigkeit B']))

    def test_task_schedule_fields_and_dependency_cycle_protection(self):
        status,first=self.req('/api/tasks','POST',{'title':'Erste Aufgabe','due_at':'2027-01-10','priority':5,'estimated_minutes':45,'recurrence':{'frequency':'weekly','interval':2,'days_of_week':[0,3]},'blocked_reason':'Wartet auf Material'})
        self.assertEqual(status,201)
        self.assertEqual(first['item']['priority'],5)
        self.assertEqual(first['item']['recurrence']['frequency'],'weekly')
        self.assertEqual(first['item']['blocked_reason'],'Wartet auf Material')
        status,second=self.req('/api/tasks','POST',{'title':'Zweite Aufgabe'})
        self.assertEqual(status,201)
        status,third=self.req('/api/tasks','POST',{'title':'Dritte Aufgabe'})
        self.assertEqual(status,201)
        first_id,second_id,third_id=first['item']['id'],second['item']['id'],third['item']['id']
        self.assertEqual(self.req('/api/tasks','POST',{'title':'Ungültige Priorität','priority':6})[0],400)
        self.assertEqual(self.req('/api/tasks','POST',{'title':'Ungültiges Datum','due_at':'nächstes Jahr'})[0],400)
        self.assertEqual(self.req(f'/api/tasks/{first_id}/dependencies','POST',{'depends_on_task_id':second_id})[0],201)
        self.assertEqual(self.req(f'/api/tasks/{second_id}/dependencies','POST',{'depends_on_task_id':third_id})[0],201)
        self.assertEqual(self.req(f'/api/tasks/{third_id}/dependencies','POST',{'depends_on_task_id':first_id})[0],409)
        status,deps=self.req(f'/api/tasks/{first_id}/dependencies')
        self.assertEqual(status,200)
        self.assertEqual(deps['items'][0]['depends_on_task_id'],second_id)
        self.assertEqual(self.req(f'/api/tasks/{first_id}/dependencies','POST',{'depends_on_task_id':second_id})[0],409)
        status,edited=self.req(f'/api/tasks/{first_id}','PATCH',{'due_at':None,'priority':2,'actual_minutes':30,'recurrence':{}})
        self.assertEqual(status,200)
        self.assertIsNone(edited['item']['due_at'])
        self.assertEqual(edited['item']['priority'],2)
        self.assertEqual(edited['item']['actual_minutes'],30)
        self.assertEqual(edited['item']['recurrence'],{})
        dep_id=deps['items'][0]['id']
        self.assertEqual(self.req('/api/task-dependencies/'+str(dep_id),'DELETE')[0],200)
        self.assertEqual(self.req(f'/api/tasks/{first_id}/dependencies')[1]['items'],[])

    def test_resource_policy_alerts_are_idempotent_and_resolve(self):
        _,created=self.req('/api/resources','POST',{'name':'Mindestbestand-Test','quantity':2,'unit':'Kisten'})
        resource_id=created['item']['id']
        status,policy=self.req(f'/api/resources/{resource_id}/policy')
        self.assertEqual(status,200)
        self.assertEqual(policy['policy']['minimum_quantity'],0)
        status,policy=self.req(f'/api/resources/{resource_id}/policy','PATCH',{'minimum_quantity':3,'target_quantity':10})
        self.assertEqual(status,200)
        self.assertEqual(self.req(f'/api/resources/{resource_id}/policy','PATCH',{'minimum_quantity':9,'target_quantity':4})[0],400)
        status,run=self.req('/api/engine/evaluate','POST',{})
        self.assertEqual(status,201)
        self.assertEqual(run['result']['low_stock_resources'],1)
        self.assertEqual(run['result']['open_alerts'],1)
        status,alerts=self.req('/api/engine/alerts?status=open')
        self.assertEqual(status,200)
        self.assertEqual(alerts['count'],1)
        alert=alerts['items'][0]
        self.assertEqual(alert['severity'],'warning')
        self.assertIn('Mindestbestand 3',alert['message'])
        status,again=self.req('/api/engine/evaluate','POST',{})
        self.assertEqual(status,201)
        self.assertEqual(again['result']['open_alerts'],1)
        status,ack=self.req(f"/api/engine/alerts/{alert['id']}/acknowledge",'POST',{})
        self.assertEqual(status,200)
        self.assertEqual(ack['item']['status'],'acknowledged')
        status,receipt=self.req(f'/api/resources/{resource_id}/movements','POST',{'movement_type':'receipt','quantity':2,'idempotency_key':'policy-test-receipt'})
        self.assertEqual(status,201)
        status,resolved=self.req('/api/engine/evaluate','POST',{})
        self.assertEqual(status,201)
        self.assertEqual(resolved['result']['alerts_resolved'],1)
        status,items=self.req('/api/engine/alerts?status=resolved')
        self.assertEqual(status,200)
        self.assertEqual(items['count'],1)
        status,status_data=self.req('/api/engine/status')
        self.assertEqual(status,200)
        self.assertEqual(status_data['counts']['open_alerts'],0)

    def test_resource_ledger_migrates_existing_stock_without_inventing_history(self):
        _,created=self.req('/api/resources','POST',{'name':'Bestandsmigration','quantity':7,'unit':'Kisten'})
        resource_id=created['item']['id']
        with app.db_connect() as con:
            con.execute('DROP TABLE resource_movements')
            con.execute('DELETE FROM schema_migrations WHERE version=7')
            app.ensure_resource_ledger_schema(con)
            row=con.execute('SELECT * FROM resource_movements WHERE resource_id=?',(resource_id,)).fetchone()
        self.assertEqual(row['movement_type'],'opening_balance')
        self.assertEqual(row['quantity_delta'],7)
        self.assertEqual(row['quantity_after'],7)
        self.assertIn('historische Bewegungen wurden nicht rekonstruiert',row['notes'])

    def test_resource_movements_are_atomic_idempotent_and_never_negative(self):
        _,created=self.req('/api/resources','POST',{'name':'Ledger-Test','quantity':5,'unit':'Kisten'})
        resource_id=created['item']['id']
        with app.db_connect() as con:
            before_count=con.execute('SELECT COUNT(*) FROM resource_movements WHERE resource_id=?',(resource_id,)).fetchone()[0]
            app.ensure_resource_ledger_schema(con)
            after_count=con.execute('SELECT COUNT(*) FROM resource_movements WHERE resource_id=?',(resource_id,)).fetchone()[0]
        self.assertEqual(after_count,before_count,'Schema-Verifikation darf keinen zweiten Eröffnungsbestand erzeugen.')
        status,receipt=self.req(f'/api/resources/{resource_id}/movements','POST',{'movement_type':'receipt','quantity':3,'idempotency_key':'receipt-ledger-1','notes':'Lieferung'})
        self.assertEqual(status,201)
        self.assertEqual(receipt['resource']['quantity'],8)
        status,replayed=self.req(f'/api/resources/{resource_id}/movements','POST',{'movement_type':'receipt','quantity':3,'idempotency_key':'receipt-ledger-1','notes':'Lieferung'})
        self.assertEqual(status,200)
        self.assertTrue(replayed['idempotent_replay'])
        self.assertEqual(replayed['resource']['quantity'],8)
        status,consumed=self.req(f'/api/resources/{resource_id}/movements','POST',{'movement_type':'consumption','quantity':2,'idempotency_key':'consume-ledger-1'})
        self.assertEqual(status,201)
        self.assertEqual(consumed['resource']['quantity'],6)
        self.assertEqual(self.req(f'/api/resources/{resource_id}/movements','POST',{'movement_type':'consumption','quantity':7,'idempotency_key':'consume-ledger-too-much'})[0],400)
        status,adjustment=self.req(f'/api/resources/{resource_id}/movements','POST',{'movement_type':'adjustment','quantity_delta':-1,'idempotency_key':'adjust-ledger-1'})
        self.assertEqual(status,201)
        self.assertEqual(adjustment['resource']['quantity'],5)
        status,items=self.req(f'/api/resources/{resource_id}/movements')
        self.assertEqual(status,200)
        self.assertEqual([x['movement_type'] for x in reversed(items['items'])],['opening_balance','receipt','consumption','adjustment'])
        self.assertEqual(items['items'][-1]['quantity_after'],5)
        self.assertEqual(self.req(f'/api/resources/{resource_id}/movements','POST',{'movement_type':'receipt','quantity':2,'idempotency_key':'receipt-ledger-1'})[0],409)
        self.assertEqual(self.req(f'/api/resources/{resource_id}/movements','POST',{'movement_type':'receipt','quantity':1e12,'idempotency_key':'overflow-ledger'})[0],400)
        self.assertEqual(self.req('/api/resources')[1]['items'][0]['quantity'],5)

    def test_event_journal_tracks_changes_and_replays_by_cursor(self):
        _,initial=self.req('/api/events')
        cursor=initial['latest_event_id']
        status,created=self.req('/api/tasks','POST',{'title':'Journal-Test'})
        self.assertEqual(status,201)
        task_id=created['item']['id']
        self.assertEqual(self.req('/api/tasks/'+str(task_id),'PATCH',{'done':True})[0],200)
        self.assertEqual(self.req('/api/tasks/'+str(task_id),'DELETE')[0],200)
        status,batch=self.req('/api/events?since='+str(cursor)+'&limit=100')
        self.assertEqual(status,200)
        self.assertFalse(batch['reset_required'])
        changes=[event for event in batch['events'] if event['entity_type']=='task' and event['entity_id']==str(task_id)]
        self.assertEqual([event['event_type'] for event in changes],['created','updated','deleted'])
        self.assertTrue(all(event['payload']=={'id':task_id} for event in changes))
        self.assertEqual([event['event_id'] for event in changes],sorted(event['event_id'] for event in changes))
        status,first=self.req('/api/events?since='+str(cursor)+'&limit=1')
        self.assertEqual(status,200)
        self.assertEqual(len(first['events']),1)
        status,next_page=self.req('/api/events?since='+str(first['events'][0]['event_id'])+'&limit=1')
        self.assertEqual(status,200)
        self.assertEqual(len(next_page['events']),1)
        with app.db_connect() as con:
            self.assertIsNotNone(con.execute('SELECT 1 FROM schema_migrations WHERE version=6').fetchone())

    def test_event_journal_reports_replay_gap(self):
        self.req('/api/tasks','POST',{'title':'Journal-Gap-1'})
        self.req('/api/tasks','POST',{'title':'Journal-Gap-2'})
        with app.db_connect() as con:
            first=con.execute('SELECT MIN(event_id) AS id FROM event_journal').fetchone()['id']
            con.execute('DELETE FROM event_journal WHERE event_id=?',(first,))
        status,batch=self.req('/api/events?since=0')
        self.assertEqual(status,200)
        self.assertTrue(batch['reset_required'])
        self.assertEqual(batch['cursor'],batch['latest_event_id'])
        self.assertEqual(batch['events'],[])
        # A cursor newer than the restored database's latest event also requires a snapshot reset.
        status,ahead=self.req('/api/events?since='+str(batch['latest_event_id']+5))
        self.assertEqual(status,200)
        self.assertTrue(ahead['reset_required'])
        self.assertEqual(ahead['cursor'],ahead['latest_event_id'])

    def test_event_journal_retention_is_bounded_and_configurable(self):
        status,settings=self.req('/api/settings')
        self.assertEqual(status,200)
        self.assertEqual(settings['settings']['event_retention_count'],'100000')
        status,updated=self.req('/api/settings','PATCH',{'event_retention_count':'1000'})
        self.assertEqual(status,200)
        self.assertEqual(updated['settings']['event_retention_count'],'1000')
        with app.db_connect() as con:
            for i in range(1005):
                con.execute("""INSERT INTO event_journal(event_uuid,occurred_at,entity_type,entity_id,event_type,payload_json,schema_version)
                    VALUES(?,?,'test',?,'created','{}',1)""",(f'retention-test-{i}',app.utcnow(),str(i)))
            self.assertEqual(con.execute('SELECT COUNT(*) AS n FROM event_journal').fetchone()['n'],1005)
        status,updated=self.req('/api/settings','PATCH',{'event_retention_count':'1000'})
        self.assertEqual(status,200)
        self.assertEqual(updated['settings']['event_retention_count'],'1000')
        with app.db_connect() as con:
            count=con.execute('SELECT COUNT(*) AS n FROM event_journal').fetchone()['n']
            bounds=con.execute('SELECT MIN(event_id) AS first,MAX(event_id) AS last FROM event_journal').fetchone()
            self.assertLessEqual(count,1000)
            self.assertEqual(bounds['last']-bounds['first']+1,count)
            batch=app.read_event_batch(con,0)
            self.assertTrue(batch['reset_required'])
            self.assertEqual(batch['cursor'],batch['latest_event_id'])

    def test_event_retention_setting_is_range_validated(self):
        self.assertEqual(self.req('/api/settings','PATCH',{'event_retention_count':'10'})[0],200)
        self.assertEqual(self.req('/api/settings','PATCH',{'event_retention_count':'10'})[1]['settings']['event_retention_count'],'1000')
        self.assertEqual(self.req('/api/settings','PATCH',{'event_retention_count':'not-a-number'})[0],400)

    def test_restore_from_pre_journal_backup_reinstalls_additive_schema(self):
        with app.db_connect() as con:
            # Simulate a genuine pre-journal database, not a table dropped beneath live triggers.
            for trigger in con.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'event_%'").fetchall():
                con.execute('DROP TRIGGER IF EXISTS "'+trigger['name'].replace('"','""')+'"')
            con.execute('DROP TABLE event_journal')
            con.execute('DROP TABLE resource_movements')
            con.execute('DROP TABLE resource_policies')
            con.execute('DROP TABLE alerts')
            con.execute('DROP TABLE engine_runs')
            con.execute('DELETE FROM schema_migrations WHERE version IN (6,7,8)')
        legacy=app.create_backup('legacy-journal-test')
        status,result=self.req('/api/restore','POST',{'name':legacy['name']})
        self.assertEqual(status,200,result)
        status,batch=self.req('/api/events')
        self.assertEqual(status,200)
        self.assertFalse(batch['reset_required'])
        with app.db_connect() as con:
            self.assertIsNotNone(con.execute('SELECT 1 FROM schema_migrations WHERE version=6').fetchone())
            self.assertIsNotNone(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_journal'").fetchone())
            self.assertIsNotNone(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='resource_movements'").fetchone())
            self.assertIsNotNone(con.execute('SELECT 1 FROM schema_migrations WHERE version=7').fetchone())


    def test_active_instance_requires_matching_user_data_directory(self):
        health={'ok':True,'app':'KOR-NEXUS','version':'1.20.0','data_dir':str(app.DATA_HOME)}
        with patch('core.server.urllib.request.urlopen',return_value=FakeResponse(json.dumps(health).encode('utf-8'))):
            self.assertTrue(app.active_instance('http://127.0.0.1:8765/'))
        health['data_dir']=str(app.DATA_HOME/'different-profile')
        with patch('core.server.urllib.request.urlopen',return_value=FakeResponse(json.dumps(health).encode('utf-8'))):
            self.assertFalse(app.active_instance('http://127.0.0.1:8765/'))

    def test_missing_browser_reports_actionable_message(self):
        output=io.StringIO()
        with patch.object(app,'open_app',return_value=False), contextlib.redirect_stderr(output):
            self.assertFalse(app.open_app_or_report('http://127.0.0.1:8765/'))
        self.assertIn('Kein unterstützter Browser gefunden',output.getvalue())
        self.assertIn('KOR-NEXUS läuft lokal weiter',output.getvalue())

    def test_health_and_storage(self):
        status,d=self.req('/api/health');self.assertEqual(status,200);self.assertTrue(d['ok']);self.assertEqual(d['database'],'SQLite');self.assertEqual(d['version'],'1.20.0')
        status,d=self.req('/api/tasks','POST',{'title':'Projekt testen','area':'PROJEKTE'});self.assertEqual(status,201);tid=d['item']['id']
        status,d=self.req('/api/tasks/'+str(tid),'PATCH',{'done':True});self.assertEqual(status,200);self.assertTrue(d['item']['done'])
        status,d=self.req('/api/tasks');self.assertEqual(len(d['items']),1)
        status,_=self.req('/api/tasks/'+str(tid),'DELETE');self.assertEqual(status,200)
        self.assertEqual(self.req('/api/tasks')[1]['items'],[])
    def test_record_crud_tags_and_validation(self):
        status,d=self.req('/api/records','POST',{'module':'archive','title':'Grundsätze','body':'Alle für Alle','tags':['Kor','Werte']});self.assertEqual(status,201);rid=d['item']['id'];self.assertEqual(d['item']['tags'],['Kor','Werte'])
        status,d=self.req('/api/records/'+str(rid),'PATCH',{'title':'Aktualisiert','body':'Text','region':'Global','tags':['Editiert']});self.assertEqual(status,200);self.assertEqual(d['item']['title'],'Aktualisiert')
        self.assertEqual(len(self.req('/api/records?module=archive')[1]['items']),1)
        self.assertEqual(self.req('/api/records','POST',{'module':'invalid','title':'X'})[0],400)
        self.assertEqual(self.req('/api/records/'+str(rid),'DELETE')[0],200)
        self.assertEqual(self.req('/api/records?module=archive')[1]['items'],[])
    def test_backup_restore_is_integrity_checked(self):
        _,created=self.req('/api/records','POST',{'module':'database','title':'Sicherer Datensatz','body':'restore me'})
        _,backup=self.req('/api/backups','POST',{})
        name=backup['item']['name']
        self.req('/api/records/'+str(created['item']['id']),'DELETE')
        self.assertEqual(self.req('/api/records?module=database')[1]['items'],[])
        status,result=self.req('/api/restore','POST',{'name':name});self.assertEqual(status,200);self.assertTrue(result['ok'])
        recovered=self.req('/api/records?module=database')[1]['items'];self.assertEqual(len(recovered),1);self.assertEqual(recovered[0]['title'],'Sicherer Datensatz')
        self.assertTrue(Path(app.BACKUP_DIR/result['safety_backup']['name']).is_file())
    def test_settings_export_and_import(self):
        status,d=self.req('/api/settings','PATCH',{'language':'en','backup_keep':5,'backup_interval_minutes':15});self.assertEqual(status,200);self.assertEqual(d['settings']['language'],'en')
        _,exported=self.req('/api/export');self.assertEqual(exported['schema_version'],2)
        data={'schema_version':1,'tasks':[{'title':'Imported task','area':'ARCHIVE','done':False}],'records':[{'module':'projects','title':'Imported record','body':'imported'}]}
        status,d=self.req('/api/import','POST',{'data':data});self.assertEqual(status,200);self.assertEqual(d['tasks'],1);self.assertEqual(len(self.req('/api/records?module=projects')[1]['items']),1)
        self.assertGreaterEqual(len(list(app.BACKUP_DIR.glob('kor-*.sqlite3'))),2)


    def test_import_preview_is_read_only_and_reports_summary(self):
        self.req('/api/records','POST',{'module':'projects','title':'Vorschauprojekt','body':'Privater Inhalt'})
        self.req('/api/tasks','POST',{'title':'Vorschauaufgabe'})
        before_export=self.req('/api/export')[1]
        before_backups=len(list(app.BACKUP_DIR.glob('kor-*.sqlite3')))
        status,report=self.req('/api/import/preview','POST',{'data':before_export})
        self.assertEqual(status,200);self.assertTrue(report['valid']);self.assertEqual(report['summary']['schema_version'],2)
        self.assertEqual(report['summary']['tasks'],1);self.assertEqual(report['summary']['records_by_module']['projects'],1)
        self.assertEqual(len(list(app.BACKUP_DIR.glob('kor-*.sqlite3'))),before_backups)
        self.assertEqual(self.req('/api/export')[1]['tasks'],before_export['tasks'])
        self.assertEqual(self.req('/api/records?module=projects')[1]['items'][0]['body'],'Privater Inhalt')
        invalid={'schema_version':2,'tasks':[{'id':1,'title':'A'},{'id':1,'title':'B'}],'records':[],'map_locations':[],'units':[],'resources':[],'project_assignments':[],'settings':{},'geodata':{},'news':{'items':[],'sources':[]}}
        status,bad=self.req('/api/import/preview','POST',{'data':invalid})
        self.assertEqual(status,200);self.assertFalse(bad['valid']);self.assertTrue(any(x['code']=='duplicate_ids' for x in bad['issues']))
        self.assertEqual(len(list(app.BACKUP_DIR.glob('kor-*.sqlite3'))),before_backups)
        dangling={'schema_version':2,'tasks':[],'records':[],'map_locations':[{'id':'loc-x','title':'Verwaister Marker','latitude':52,'longitude':13,'project_id':'project-missing'}],'units':[],'resources':[],'project_assignments':[],'settings':{},'geodata':{},'news':{'items':[],'sources':[]}}
        _,dangling_report=self.req('/api/import/preview','POST',{'data':dangling})
        self.assertFalse(dangling_report['valid']);self.assertTrue(any(x['code']=='missing_reference' for x in dangling_report['issues']))
        self.assertEqual(len(list(app.BACKUP_DIR.glob('kor-*.sqlite3'))),before_backups)

    def test_import_preview_legacy_ambiguity_invalid_fields_and_large_payload(self):
        ambiguous={'schema_version':1,'tasks':[],'records':[{'module':'projects','title':'Doppelprojekt'},{'module':'projects','title':'Doppelprojekt'}], 'map_locations':[{'title':'Marker','latitude':52,'longitude':13,'project_title':'Doppelprojekt'}]}
        _,report=self.req('/api/import/preview','POST',{'data':ambiguous})
        self.assertFalse(report['valid']);self.assertTrue(any(x['code']=='ambiguous_legacy_mapping' for x in report['issues']))
        invalid={'schema_version':1,'tasks':[{'title':' ' }],'records':[]}
        _,report=self.req('/api/import/preview','POST',{'data':invalid})
        self.assertFalse(report['valid']);self.assertTrue(report['issues'])
        large={'schema_version':2,'tasks':[],'records':[],'map_locations':[],'units':[],'resources':[],'project_assignments':[],'settings':{},'geodata':{'opaque_payload':{'data':'x'*1024*1024}},'news':{'items':[],'sources':[]}}
        _,report=self.req('/api/import/preview','POST',{'data':large})
        self.assertTrue(report['valid']);self.assertEqual(report['summary']['geodata'],1)

    def test_local_geodata_endpoint_validates_and_persists_geojson(self):
        status,world=self.req('/api/geodata/germany-states')
        self.assertEqual(status,200);self.assertFalse(world['available'])
        feature={'type':'Feature','properties':{'name':'Berlin'},'geometry':{'type':'Polygon','coordinates':[[[13.0,52.0],[14.0,52.0],[14.0,53.0],[13.0,53.0],[13.0,52.0]]]}}
        geo={'type':'FeatureCollection','features':[feature]}
        status,result=self.req('/api/geodata/germany-states','POST',{'geojson':geo})
        self.assertEqual(status,201);self.assertEqual(result['feature_count'],1);self.assertEqual(result['recognized_state_names'],1)
        status,loaded=self.req('/api/geodata/germany-states')
        self.assertEqual(status,200);self.assertTrue(loaded['available']);self.assertEqual(loaded['geojson'],geo)
        exported=self.req('/api/export')[1]
        self.assertEqual(exported['geodata']['germany_states'],geo)
        status,restored=self.req('/api/import','POST',{'data':exported})
        self.assertEqual(status,200);self.assertEqual(restored['geodata'],1)
        self.assertEqual(self.req('/api/geodata/germany-states')[1]['geojson'],geo)
        bad={'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':{'type':'Polygon','coordinates':[[[600000,5800000],[600001,5800000],[600001,5800001],[600000,5800000]]]}}]}
        self.assertEqual(self.req('/api/geodata/germany-states','POST',{'geojson':bad})[0],400)
        self.assertEqual(self.req('/api/geodata/germany-states','POST',{'geojson':{'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':{'type':'Point','coordinates':[0,0]}}]}})[0],400)

    def test_bundled_world_geodata_is_valid_geojson(self):
        path=app.WEB/'geodata'/'world.geojson'
        self.assertTrue(path.is_file())
        geo=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(geo['type'],'FeatureCollection');self.assertGreaterEqual(len(geo['features']),150)
        self.assertTrue(any((f.get('properties') or {}).get('iso_a3')=='DEU' for f in geo['features']))
        status,served=self.req('/geodata/world.geojson')
        self.assertEqual(status,200);self.assertEqual(served['type'],'FeatureCollection');self.assertEqual(len(served['features']),len(geo['features']))

    def test_map_locations_coordinates_validation_and_project_link(self):
        status, project = self.req('/api/records', 'POST', {'module':'projects','title':'Küstenprojekt'})
        self.assertEqual(status, 201)
        status, loc = self.req('/api/locations', 'POST', {'title':'Standort Nord','kind':'Projekt','region':'Niedersachsen','latitude':53.55,'longitude':9.99,'project_id':project['item']['id'],'notes':'Testmarker'})
        self.assertEqual(status, 201); self.assertEqual(loc['item']['project_title'],'Küstenprojekt')
        self.assertEqual(self.req('/api/locations')[1]['items'][0]['latitude'],53.55)
        self.assertEqual(self.req('/api/locations','POST',{'title':'Außerhalb','latitude':120,'longitude':0})[0],400)
        exported=self.req('/api/export')[1]
        self.assertEqual(len(exported['map_locations']),1)
        status, imported=self.req('/api/import','POST',{'data':{'schema_version':1,'tasks':[],'records':[{'module':'projects','title':'Küstenprojekt'}],'map_locations':exported['map_locations']}})
        self.assertEqual(status,200); self.assertEqual(imported['map_locations'],1)
        self.assertEqual(self.req('/api/locations')[1]['items'][0]['project_title'],'Küstenprojekt')
        self.assertEqual(self.req('/api/locations/'+str(self.req('/api/locations')[1]['items'][0]['id']),'DELETE')[0],200)
        self.assertEqual(self.req('/api/locations')[1]['items'],[])


    def test_strategic_location_create_edit_and_link_references(self):
        _, project=self.req('/api/records','POST',{'module':'projects','title':'Atlas-Testprojekt'})
        _, task=self.req('/api/tasks','POST',{'title':'Koordinaten prüfen'})
        _, unit=self.req('/api/units','POST',{'name':'Atlas-Team','role':'Planung'})
        _, resource=self.req('/api/resources','POST',{'name':'Werkzeugkiste','quantity':3,'unit':'Kisten','location':'Niedersachsen'})
        payload={'title':'Regionaler Knoten','kind':'Standort','region':'Niedersachsen','latitude':52.4,'longitude':9.7,'project_id':project['item']['id'],'task_id':task['item']['id'],'unit_id':unit['item']['id'],'resource_id':resource['item']['id'],'status':'aktiv','progress':35,'notes':'Planungsnotiz'}
        status,created=self.req('/api/locations','POST',payload)
        self.assertEqual(status,201); item=created['item']; self.assertEqual(item['project_title'],'Atlas-Testprojekt');self.assertEqual(item['task_title'],'Koordinaten prüfen');self.assertEqual(item['unit_name'],'Atlas-Team');self.assertEqual(item['resource_name'],'Werkzeugkiste');self.assertEqual(item['progress'],35)
        status,edited=self.req('/api/locations/'+str(item['id']),'PATCH',{'latitude':53.1,'longitude':10.2,'status':'blockiert','progress':60})
        self.assertEqual(status,200);self.assertEqual(edited['item']['latitude'],53.1);self.assertEqual(edited['item']['status'],'blockiert');self.assertEqual(edited['item']['progress'],60);self.assertEqual(edited['item']['task_id'],task['item']['id'])
        # Coordinate-only PATCH must preserve every unrelated field and relationship.
        status,moved=self.req('/api/locations/'+str(item['id']),'PATCH',{'latitude':54.2,'longitude':11.3})
        self.assertEqual(status,200);moved_item=moved['item']
        self.assertEqual((moved_item['latitude'],moved_item['longitude']),(54.2,11.3))
        self.assertEqual(moved_item['status'],'blockiert');self.assertEqual(moved_item['progress'],60)
        self.assertEqual(moved_item['project_id'],project['item']['id']);self.assertEqual(moved_item['task_id'],task['item']['id'])
        self.assertEqual(moved_item['unit_id'],unit['item']['id']);self.assertEqual(moved_item['resource_id'],resource['item']['id'])
        self.assertEqual(moved_item['notes'],'Planungsnotiz')
        # A fresh GET/SQLite connection sees the committed coordinates and preserved fields.
        persisted=self.req('/api/locations')[1]['items'][0]
        self.assertEqual((persisted['latitude'],persisted['longitude']),(54.2,11.3))
        self.assertEqual((persisted['status'],persisted['progress']),('blockiert',60))
        self.assertEqual(persisted['resource_id'],resource['item']['id'])
        self.assertEqual(self.req('/api/locations/'+str(item['id']),'PATCH',{'latitude':91})[0],400)
        self.assertEqual(self.req('/api/locations/'+str(item['id']),'PATCH',{'longitude':181})[0],400)
        self.assertEqual(self.req('/api/locations/'+str(item['id']),'PATCH',{'progress':101})[0],400)
        self.assertEqual(self.req('/api/locations','POST',{**payload,'task_id':999999})[0],400)
        exported=self.req('/api/export')[1]; exported_item=exported['map_locations'][0]
        self.assertEqual(exported_item['status'],'blockiert');self.assertEqual(exported_item['task_title'],'Koordinaten prüfen')

    def test_schema2_roundtrip_all_data_remaps_foreign_ids_and_checks_foreign_keys(self):
        _, project=self.req('/api/records','POST',{'module':'projects','title':'Portabilitätsprojekt','body':'Projekttext','tags':['roundtrip']})
        _, task=self.req('/api/tasks','POST',{'title':'Portabilitätsaufgabe','area':'Atlas'})
        _, unit=self.req('/api/units','POST',{'name':'Mira','role':'Logistik','status':'aktiv','biography':'Profilbiografie','region':'Hessen','tags':['Erste Hilfe']})
        _, resource=self.req('/api/resources','POST',{'name':'Feldfunkgerät','category':'Kommunikation','quantity':4,'unit':'Stück','location':'Depot Nord','notes':'Funktionsfähig'})
        self.req(f"/api/resources/{resource['item']['id']}/policy",'PATCH',{'minimum_quantity':2,'target_quantity':9})
        self.req('/api/automation/rules','POST',{'rule_key':'portable-rule','name':'Portable rule','trigger_type':'resource_low_stock','action_type':'create_task','action':{'title_prefix':'Nachbestellen: '},'enabled':True})
        _, assignment=self.req('/api/assignments','POST',{'project_id':project['item']['id'],'unit_id':unit['item']['id'],'quantity':2,'notes':'Einsatzteam'})
        _, resource_assignment=self.req('/api/assignments','POST',{'project_id':project['item']['id'],'resource_id':resource['item']['id'],'quantity':1,'notes':'Materialpaket'})
        with app.db_connect() as con:
            con.execute('INSERT INTO feed_items(id,source_key,source_name,title,summary,url,published,fetched_at) VALUES(?,?,?,?,?,?,?,?)',('feed-roundtrip','qa','QA-Quelle','Testmeldung','Kurztext','https://example.invalid/item','2026-10-16',app.utcnow()))
            con.execute('INSERT INTO feed_status(source_key,source_name,last_attempt,last_success,status,item_count) VALUES(?,?,?,?,?,?)',('qa','QA-Quelle',app.utcnow(),app.utcnow(),'Aktuell',1))
        _, loc=self.req('/api/locations','POST',{'title':'Knoten Nord','latitude':52.5,'longitude':9.8,'project_id':project['item']['id'],'task_id':task['item']['id'],'unit_id':unit['item']['id'],'resource_id':resource['item']['id'],'status':'aktiv','progress':73,'notes':'Markertext'})
        self.req('/api/settings','PATCH',{'unit_label_singular':'Kor-Mitglied','unit_label_plural':'Kor-Mitglieder'})
        geo={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':'Berlin'},'geometry':{'type':'Polygon','coordinates':[[[13,52],[14,52],[14,53],[13,53],[13,52]]]}}]}
        self.req('/api/geodata/germany-states','POST',{'geojson':geo})
        exported=self.req('/api/export')[1]
        self.assertEqual(exported['schema_version'],2)
        for key in ('tasks','records','map_locations','units','resources','resource_movements','resource_policies','project_assignments','settings','geodata','news'):
            self.assertIn(key,exported)
        self.assertEqual(exported['units'][0]['biography'],'Profilbiografie')
        self.assertEqual(len(exported['project_assignments']),2)
        self.assertGreaterEqual(len(exported['resource_movements']),1)
        self.assertEqual(exported['resource_policies'][0]['minimum_quantity'],2)
        self.assertEqual(len(exported['automation_rules']),1)
        self.assertTrue(bool(exported['automation_rules'][0]['enabled']))
        self.assertEqual(len(exported['news']['items']),1)
        # Simulate IDs from an unrelated SQLite database; all foreign keys are rewritten through the export map.
        exported['records'][0]['id']=88001
        exported['tasks'][0]['id']=77001
        exported['units'][0]['id']=66001
        exported['resources'][0]['id']=55001
        for movement in exported.get('resource_movements',[]):
            if movement.get('resource_id') is not None: movement['resource_id']=55001
        for policy in exported.get('resource_policies',[]): policy['resource_id']=55001
        for item in exported['project_assignments']:
            item['project_id']=88001
            if item.get('unit_id') is not None: item['unit_id']=66001
            if item.get('resource_id') is not None: item['resource_id']=55001
        exported['map_locations'][0].update({'project_id':88001,'task_id':77001,'unit_id':66001,'resource_id':55001})
        status,result=self.req('/api/import','POST',{'data':exported})
        self.assertEqual(status,200,result)
        self.assertEqual((result['tasks'],result['records'],result['units'],result['resources'],result['project_assignments']),(1,1,1,1,2))
        with app.db_connect() as con:
            self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
            new_project=con.execute("SELECT id FROM records WHERE module='projects'").fetchone()['id']
            new_task=con.execute('SELECT id FROM tasks').fetchone()['id']
            new_unit=con.execute('SELECT id FROM units').fetchone()['id']
            new_resource=con.execute('SELECT id FROM resources').fetchone()['id']
            assignments=con.execute('SELECT * FROM project_assignments ORDER BY id').fetchall()
            new_loc=con.execute('SELECT * FROM map_locations').fetchone()
            self.assertNotEqual(new_project,88001);self.assertNotEqual(new_task,77001)
            self.assertTrue(any((a['project_id'],a['unit_id'],a['resource_id'])==(new_project,new_unit,None) for a in assignments))
            self.assertTrue(any((a['project_id'],a['unit_id'],a['resource_id'])==(new_project,None,new_resource) for a in assignments))
            self.assertEqual((new_loc['project_id'],new_loc['task_id'],new_loc['unit_id'],new_loc['resource_id']),(new_project,new_task,new_unit,new_resource))
            self.assertEqual((new_loc['status'],new_loc['progress'],new_loc['notes']),('aktiv',73,'Markertext'))
            self.assertEqual(con.execute("SELECT value FROM settings WHERE key='unit_label_plural'").fetchone()['value'],'Kor-Mitglieder')
            self.assertEqual(json.loads(con.execute("SELECT geojson FROM geodata_assets WHERE key='germany-states'").fetchone()['geojson']),geo)
            self.assertEqual(con.execute("SELECT title FROM feed_items WHERE id='feed-roundtrip'").fetchone()['title'],'Testmeldung')
            self.assertEqual(con.execute("SELECT status FROM feed_status WHERE source_key='qa'").fetchone()['status'],'Aktuell')
        # A fresh export/read after commit confirms persisted profile and assignment content.
        fresh=self.req('/api/export')[1]
        self.assertEqual(fresh['units'][0]['biography'],'Profilbiografie')
        self.assertIn('Einsatzteam',[a['notes'] for a in fresh['project_assignments']])
        self.assertIn('Materialpaket',[a['notes'] for a in fresh['project_assignments']])
        self.assertEqual(fresh['news']['items'][0]['title'],'Testmeldung')
        self.assertGreaterEqual(len(fresh['resource_movements']),1)
        self.assertEqual(fresh['resource_movements'][0]['resource_id'],new_resource)
        self.assertEqual(fresh['resource_policies'][0]['resource_id'],new_resource)
        self.assertEqual(fresh['resource_policies'][0]['minimum_quantity'],2)
        self.assertEqual(fresh['resource_policies'][0]['target_quantity'],9)
        self.assertEqual(fresh['map_locations'][0]['task_id'],new_task)
        imported_rules=self.req('/api/automation/rules')[1]['items']
        self.assertEqual(len(imported_rules),1)
        self.assertFalse(imported_rules[0]['enabled'],'Importierte Regeln müssen aus Sicherheitsgründen deaktiviert sein.')

    def test_schema2_without_optional_ledger_fields_remains_importable(self):
        _,resource=self.req('/api/resources','POST',{'name':'Altes Exportformat','quantity':6,'unit':'Kisten'})
        payload=self.req('/api/export')[1]
        payload.pop('resource_movements',None)
        payload.pop('resource_policies',None)
        payload.pop('automation_rules',None)
        self.req('/api/automation/rules','POST',{'rule_key':'keep-local-rule','name':'Lokale Regel','trigger_type':'manual','action_type':'create_task','action':{'title_prefix':'Test'},'enabled':False})
        status,result=self.req('/api/import','POST',{'data':payload})
        self.assertEqual(status,200,result)
        imported=self.req('/api/resources')[1]['items'][0]
        status,movements=self.req(f"/api/resources/{imported['id']}/movements")
        self.assertEqual(status,200)
        self.assertEqual(len(movements['items']),1)
        self.assertEqual(movements['items'][0]['movement_type'],'import_snapshot')
        status,policy=self.req(f"/api/resources/{imported['id']}/policy")
        self.assertEqual(status,200)
        self.assertEqual(policy['policy']['minimum_quantity'],0)
        self.assertIsNone(policy['policy']['target_quantity'])
        self.assertEqual(self.req('/api/automation/rules')[1]['count'],1,'Alte Schema-2-Dateien ohne Regelfeld dürfen lokale Regeln nicht löschen.')

    def test_portable_import_rejects_unsafe_news_links(self):
        self.req('/api/tasks','POST',{'title':'Bleibt erhalten'})
        payload=self.req('/api/export')[1]
        payload['news']['items']=[{
            'id':'unsafe-link','source_key':'imported','source_name':'Imported source',
            'title':'Unsafe link test','summary':'','url':'javascript:alert(1)',
            'published':'','fetched_at':app.utcnow()
        }]
        before=self.req('/api/export')[1]
        backups_before=len(list(app.BACKUP_DIR.glob('kor-*.sqlite3')))
        status,preview=self.req('/api/import/preview','POST',{'data':payload})
        self.assertEqual(status,200)
        self.assertFalse(preview['valid'])
        status,result=self.req('/api/import','POST',{'data':payload})
        self.assertEqual(status,400)
        self.assertIn('HTTP(S)',result['error'])
        after=self.req('/api/export')[1]
        self.assertEqual(after['tasks'],before['tasks'])
        self.assertEqual(after['news']['items'],before['news']['items'])
        self.assertEqual(len(list(app.BACKUP_DIR.glob('kor-*.sqlite3'))),backups_before)

    def test_invalid_portable_reference_is_rejected_before_backup_or_mutation(self):
        self.req('/api/tasks','POST',{'title':'Bleibt erhalten'})
        before=self.req('/api/export')[1]
        backups_before=len(list(app.BACKUP_DIR.glob('kor-*.sqlite3')))
        bad={'schema_version':2,'tasks':[{'id':1,'title':'T'}],'records':[{'id':2,'module':'projects','title':'P'}],
             'map_locations':[{'id':3,'title':'M','latitude':1,'longitude':2,'task_id':999,'project_id':2}],
             'units':[],'resources':[],'project_assignments':[],'settings':{},'geodata':{},'news':{'items':[],'sources':[]}}
        status,result=self.req('/api/import','POST',{'data':bad})
        self.assertEqual(status,400);self.assertIn('Referenz',result['error'])
        after=self.req('/api/export')[1]
        self.assertEqual(after['tasks'],before['tasks'])
        self.assertEqual(len(list(app.BACKUP_DIR.glob('kor-*.sqlite3'))),backups_before)

    def test_legacy_v1_duplicate_title_fallback_is_rejected_as_ambiguous(self):
        bad={'schema_version':1,'tasks':[],'records':[{'module':'projects','title':'Doppelt'},{'module':'projects','title':'Doppelt'}],
             'map_locations':[{'title':'Marker','latitude':1,'longitude':2,'project_title':'Doppelt'}]}
        status,result=self.req('/api/import','POST',{'data':bad})
        self.assertEqual(status,400);self.assertIn('Mehrdeutige',result['error'])

    def test_untrusted_origin_rejected(self):
        status,_=self.req('/api/tasks','POST',{'title':'blocked'},headers={'Origin':'https://evil.example'})
        self.assertEqual(status,403)
    def test_rss_atom_parser(self):
        xml=b'''<?xml version="1.0"?><rss version="2.0"><channel><item><title>Lokaler RSS Test</title><link>https://news.example/item/1</link><description><![CDATA[<b>Klarer</b> Teaser &amp; Inhalt]]></description><pubDate>Tue, 15 Oct 2024 12:00:00 GMT</pubDate></item><item><title>Duplikat</title><link>https://news.example/item/1#abschnitt</link></item></channel></rss>'''
        with patch.object(app.urllib.request,'urlopen',return_value=FakeResponse(xml)):
            items=app.fetch_one_feed(app.FEEDS[0])
        self.assertEqual(len(items),1);self.assertEqual(items[0]['title'],'Lokaler RSS Test');self.assertNotIn('<b>',items[0]['summary']);self.assertIn('news.example',items[0]['url'])
        atom=b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom-Test</title><link href="https://news.example/atom/1" rel="alternate"/><summary>Atom Kurzmeldung</summary><updated>2026-10-16T10:00:00Z</updated></entry></feed>'''
        with patch.object(app.urllib.request,'urlopen',return_value=FakeResponse(atom)):
            atom_items=app.fetch_one_feed(app.FEEDS[0])
        self.assertEqual(len(atom_items),1);self.assertEqual(atom_items[0]['title'],'Atom-Test');self.assertIn('/atom/1',atom_items[0]['url'])

    def test_rss_rejects_empty_malformed_and_dtd_xml(self):
        feed=app.FEEDS[0]
        for payload in (b'',b'<rss><channel>',b'<!DOCTYPE rss [<!ENTITY x "boom">]><rss><channel/></rss>'):
            with self.subTest(payload=payload), patch.object(app.urllib.request,'urlopen',return_value=FakeResponse(payload)):
                with self.assertRaises(Exception):
                    app.fetch_one_feed(feed)

    def test_rss_timeout_is_reported_and_cache_is_preserved(self):
        feed={'key':'test','name':'Testfeed','url':'https://feed.example/rss'}
        old={'id':'old-item','source_key':'test','source_name':'Testfeed','title':'Gecachte Meldung','summary':'alt','url':'https://news.example/old','published':'','fetched_at':app.utcnow()}
        with app.db_connect() as con:
            con.execute('INSERT INTO feed_items(id,source_key,source_name,title,summary,url,published,fetched_at) VALUES(:id,:source_key,:source_name,:title,:summary,:url,:published,:fetched_at)',old)
        with patch.object(app,'FEEDS',[feed]), patch.object(app,'fetch_one_feed',side_effect=TimeoutError('Zeitlimit')):
            result=app.refresh_feeds()
        self.assertEqual(len(result['errors']),1)
        with app.db_connect() as con:
            row=con.execute('SELECT * FROM feed_items WHERE id=?',('old-item',)).fetchone()
            status=con.execute('SELECT * FROM feed_status WHERE source_key=?',('test',)).fetchone()
        self.assertIsNotNone(row);self.assertIn('TimeoutError',status['status']);self.assertEqual(status['item_count'],1);self.assertIsNone(status['last_success'])

    def test_rss_valid_empty_feed_does_not_delete_stale_cache(self):
        feed={'key':'test','name':'Testfeed','url':'https://feed.example/rss'}
        old={'id':'old-item','source_key':'test','source_name':'Testfeed','title':'Gecachte Meldung','summary':'alt','url':'https://news.example/old','published':'','fetched_at':app.utcnow()}
        with app.db_connect() as con:
            con.execute('INSERT INTO feed_items(id,source_key,source_name,title,summary,url,published,fetched_at) VALUES(:id,:source_key,:source_name,:title,:summary,:url,:published,:fetched_at)',old)
        with patch.object(app,'FEEDS',[feed]), patch.object(app,'fetch_one_feed',return_value=[]):
            result=app.refresh_feeds()
        self.assertEqual(result['errors'],[])
        with app.db_connect() as con:
            self.assertIsNotNone(con.execute('SELECT 1 FROM feed_items WHERE id=?',('old-item',)).fetchone())
            status=con.execute('SELECT * FROM feed_status WHERE source_key=?',('test',)).fetchone()
        self.assertIn('Cache beibehalten',status['status']);self.assertEqual(status['item_count'],1);self.assertTrue(status['last_success'])

    def test_rss_success_replaces_cache_deduplicates_and_persists(self):
        feed={'key':'test','name':'Testfeed','url':'https://feed.example/rss'}
        old={'id':'old-item','source_key':'test','source_name':'Testfeed','title':'Alt','summary':'','url':'https://news.example/old','published':'','fetched_at':app.utcnow()}
        new={'id':'new-item','source_key':'test','source_name':'Testfeed','title':'Neue Meldung','summary':'Kurz','url':'https://news.example/new','published':'','fetched_at':app.utcnow()}
        duplicate={**new,'id':'new-item-duplicate','title':'Doppelte URL-Quelle'}
        with app.db_connect() as con:
            con.execute('INSERT INTO feed_items(id,source_key,source_name,title,summary,url,published,fetched_at) VALUES(:id,:source_key,:source_name,:title,:summary,:url,:published,:fetched_at)',old)
        with patch.object(app,'FEEDS',[feed]), patch.object(app,'fetch_one_feed',return_value=[new,duplicate]):
            result=app.refresh_feeds()
        self.assertEqual(result['items'],1)
        with app.db_connect() as con:
            rows=con.execute('SELECT * FROM feed_items WHERE source_key=?',('test',)).fetchall()
            status=con.execute('SELECT * FROM feed_status WHERE source_key=?',('test',)).fetchone()
        self.assertEqual(len(rows),1);self.assertFalse(any(r['id']=='old-item' for r in rows));self.assertEqual(status['status'],'Aktuell');self.assertEqual(status['item_count'],1);self.assertTrue(status['last_success'])
        self.assertEqual(self.req('/api/news')[0],200)

    def test_rss_rejects_unsafe_article_links_and_non_https_feed_source(self):
        xml=b'<rss><channel><item><title>unsafe</title><link>javascript:alert(1)</link></item><item><title>safe</title><link>https://news.example/good</link></item></channel></rss>'
        with patch.object(app.urllib.request,'urlopen',return_value=FakeResponse(xml)):
            items=app.fetch_one_feed(app.FEEDS[0])
        self.assertEqual(len(items),1);self.assertEqual(items[0]['title'],'safe')
        with self.assertRaises(ValueError): app.fetch_one_feed({'key':'x','name':'bad','url':'http://example.com/rss'})

    def test_static_assets_and_security_headers(self):
        req=Request(self.base+'/',headers={'Accept':'text/html'})
        with urlopen(req,timeout=3) as res:
            html=res.read().decode('utf-8')
            self.assertEqual(res.status,200)
            self.assertIn('KOR-NEXUS',html)
            self.assertIn("default-src 'self'",res.headers.get('Content-Security-Policy',''))
            self.assertEqual(res.headers.get('X-Content-Type-Options'),'nosniff')
        for asset,marker in (('/app.js','function init()'),('/styles.css','.workspace')):
            with urlopen(self.base+asset,timeout=3) as res:
                self.assertEqual(res.status,200)
                self.assertIn(marker,res.read().decode('utf-8'))

    def test_invalid_import_preserves_existing_records(self):
        self.req('/api/tasks','POST',{'title':'Darf nicht verschwinden','area':'QA'})
        status,_=self.req('/api/import','POST',{'data':{'schema_version':1,'tasks':[],'records':[{'module':'not-a-module','title':'Invalid'}]}})
        self.assertEqual(status,400)
        tasks=self.req('/api/tasks')[1]['items']
        self.assertEqual(len(tasks),1)
        self.assertEqual(tasks[0]['title'],'Darf nicht verschwinden')

    def test_backup_retention_and_path_validation(self):
        self.req('/api/settings','PATCH',{'backup_keep':3})
        for _ in range(6):
            self.req('/api/backups','POST',{})
        names=sorted(Path(app.BACKUP_DIR).glob('kor-*.sqlite3'),key=lambda p:p.stat().st_mtime)
        self.assertLessEqual(len(names),3)
        status,_=self.req('/api/restore','POST',{'name':'../../outside.sqlite3'})
        self.assertEqual(status,400)
        # At the retention limit, restoring the oldest still-listed point must
        # work even though the safety backup would otherwise evict it too early.
        status,result=self.req('/api/restore','POST',{'name':names[0].name})
        self.assertEqual(status,200)
        self.assertTrue(result['ok'])

    def test_units_resources_and_project_assignments(self):
        status,u=self.req('/api/units','POST',{'name':'Alex Beispiel','role':'Logistik','biography':'Kennt Lager und Inventur.','region':'Nord','tags':['Logistik']})
        self.assertEqual(status,201); uid=u['item']['id']; self.assertEqual(u['item']['biography'],'Kennt Lager und Inventur.')
        status,r=self.req('/api/resources','POST',{'name':'Erste-Hilfe-Sets','category':'Medizin','quantity':12,'unit':'Sets','location':'Depot Nord'})
        self.assertEqual(status,201); rid=r['item']['id']; self.assertEqual(r['item']['quantity'],12)
        status,p=self.req('/api/records','POST',{'module':'projects','title':'Basislager Nord'})
        self.assertEqual(status,201); pid=p['item']['id']
        status,a=self.req('/api/assignments','POST',{'project_id':pid,'unit_id':uid,'quantity':1,'notes':'Leitung'})
        self.assertEqual(status,201)
        status,b=self.req('/api/assignments','POST',{'project_id':pid,'resource_id':rid,'quantity':4})
        self.assertEqual(status,201)
        self.assertEqual(len(self.req('/api/assignments')[1]['items']),2)
        self.assertEqual(self.req('/api/assignments/'+str(b['id']),'DELETE')[0],200)
        self.assertEqual(len(self.req('/api/assignments')[1]['items']),1)
        self.assertEqual(self.req('/api/resources/'+str(rid),'DELETE')[0],200)
        self.assertEqual(self.req('/api/units/'+str(uid),'DELETE')[0],409)
        self.assertEqual(self.req('/api/assignments/'+str(a['id']),'DELETE')[0],200)
        self.assertEqual(self.req('/api/units/'+str(uid),'DELETE')[0],200)
        self.assertEqual(self.req('/api/units')[1]['items'],[])
        self.assertEqual(self.req('/api/resources')[1]['items'],[])
        assignments=self.req('/api/assignments')[1]['items']; self.assertEqual(len(assignments),0)
        self.assertEqual(self.req('/api/assignments','POST',{'project_id':pid,'unit_id':uid,'resource_id':rid})[0],400)
        status,settings=self.req('/api/settings','PATCH',{'unit_label_singular':'Mitglied','unit_label_plural':'Mitglieder'})
        self.assertEqual(status,200); self.assertEqual(settings['settings']['unit_label_plural'],'Mitglieder')
        self.assertEqual(self.req('/api/settings','PATCH',{'unit_label_plural':''})[0],400)

    def test_resource_and_assignment_quantities_reject_non_finite_values(self):
        _,project=self.req('/api/records','POST',{'module':'projects','title':'Mengenvalidierung'})
        _,unit=self.req('/api/units','POST',{'name':'Testmitglied'})
        for value in (float('nan'),float('inf'),float('-inf')):
            status,_=self.req('/api/resources','POST',{'name':'Ungültige Menge','quantity':value})
            self.assertEqual(status,400, f'Resource quantity {value!r} must be rejected as client input')
            status,_=self.req('/api/assignments','POST',{'project_id':project['item']['id'],'unit_id':unit['item']['id'],'quantity':value})
            self.assertEqual(status,400, f'Assignment quantity {value!r} must be rejected as client input')
        with app.db_connect() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM resources WHERE name='Ungültige Menge'").fetchone()[0],0)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM project_assignments').fetchone()[0],0)

    def test_project_dashboard_joins_by_id_filters_and_persists(self):
        _,project=self.req('/api/records','POST',{'module':'projects','title':'Doppelname','region':'Nord'})
        pid=project['item']['id']
        _,unit1=self.req('/api/units','POST',{'name':'Alex','role':'Logistik','region':'Nord'})
        _,unit2=self.req('/api/units','POST',{'name':'Alex','role':'Sanität','region':'Süd'})
        _,resource1=self.req('/api/resources','POST',{'name':'Wasser','quantity':20,'unit':'Liter'})
        _,resource2=self.req('/api/resources','POST',{'name':'Wasser','quantity':5,'unit':'Kanister'})
        _,task=self.req('/api/tasks','POST',{'title':'Offene Aufgabe','area':'Nord'})
        _,loc=self.req('/api/locations','POST',{'title':'Nordknoten','region':'Nord','latitude':53.0,'longitude':9.0,'project_id':pid,'task_id':task['item']['id'],'status':'aktiv','progress':40})
        _,assignment=self.req('/api/assignments','POST',{'project_id':pid,'unit_id':unit2['item']['id'],'quantity':1})
        self.req('/api/assignments','POST',{'project_id':pid,'resource_id':resource2['item']['id'],'quantity':2})
        status,data=self.req('/api/dashboard/projects')
        self.assertEqual(status,200);self.assertEqual(data['total'],1)
        item=data['items'][0];self.assertEqual(item['id'],pid);self.assertEqual(item['status'],'aktiv');self.assertEqual(item['progress'],40)
        self.assertEqual([x['id'] for x in item['members']],[unit2['item']['id']]);self.assertEqual(item['members'][0]['role'],'Sanität')
        self.assertEqual(item['resources'][0]['id'],resource2['item']['id']);self.assertEqual(item['resources'][0]['unit'],'Kanister')
        self.assertEqual(item['open_tasks'][0]['id'],task['item']['id']);self.assertEqual(item['locations'][0]['id'],loc['item']['id'])
        self.assertEqual(self.req('/api/dashboard/projects?region=S%C3%BCd')[1]['total'],0)
        self.assertEqual(self.req('/api/dashboard/projects?region=Nord')[1]['total'],1)
        self.assertEqual(self.req('/api/dashboard/projects?project_id='+str(pid))[1]['total'],1)
        self.assertEqual(self.req('/api/dashboard/projects?status=aktiv')[1]['total'],1)
        self.assertEqual(self.req('/api/dashboard/projects?status=blockiert')[1]['total'],0)
        self.assertEqual(self.req('/api/dashboard/projects?project_id=bad')[0],400)
        self.assertEqual(self.req('/api/dashboard/projects?status=made-up')[0],400)
        # A separate request reads the same committed relationships, not name-based guesses.
        persisted=self.req('/api/dashboard/projects')[1]['items'][0]
        self.assertEqual(persisted['members'][0]['id'],unit2['item']['id'])
        self.assertEqual(persisted['resources'][0]['id'],resource2['item']['id'])

    def test_project_dashboard_unknown_values_and_empty_filters(self):
        self.assertEqual(self.req('/api/dashboard/projects')[1]['items'],[])
        _,project=self.req('/api/records','POST',{'module':'projects','title':'Ohne Lage','region':''})
        status,data=self.req('/api/dashboard/projects')
        self.assertEqual(status,200);item=data['items'][0]
        self.assertEqual(item['status'],'unbekannt');self.assertIsNone(item['progress'])
        self.assertEqual(item['counts'],{'locations':0,'open_tasks':0,'members':0,'resources':0})
        self.assertEqual(self.req('/api/dashboard/projects?region=Nichtvorhanden')[1]['items'],[])
        self.assertEqual(self.req('/api/dashboard/projects?status=unbekannt')[1]['total'],1)
        self.assertIn('null bedeutet keine Werte',self.req('/api/dashboard/projects')[1]['semantics']['progress'])

    def test_host_header_and_cross_origin_mutations_are_rejected(self):
        req=Request(self.base+'/api/health',headers={'Host':'evil.example'})
        with self.assertRaises(HTTPError) as caught: urlopen(req,timeout=3)
        self.assertEqual(caught.exception.code,403)
        status,_=self.req('/api/tasks','POST',{'title':'blocked'},headers={'Origin':'http://127.0.0.1:1'})
        self.assertEqual(status,403)

if __name__=='__main__':unittest.main()
