"""Deterministic, read-only status calculations for KOR-NEXUS."""
from __future__ import annotations

import json

ENGINE_VERSION = '0.1.0'
MODULES = ('atlas', 'projects', 'archive', 'simulation', 'database')


def _count(con, sql, params=()):
    row = con.execute(sql, params).fetchone()
    return int(row[0] or 0)





def run_due_scheduled_jobs(con, now):
    """Run due one-shot jobs atomically; failed jobs are audited and never partially applied."""
    jobs=con.execute("SELECT * FROM scheduled_jobs WHERE status='pending' AND due_at<=? ORDER BY due_at,id",(now,)).fetchall()
    summary={'processed':0,'completed':0,'failed':0,'llm_used':False}
    for job in jobs:
        con.execute("UPDATE scheduled_jobs SET status='running',attempts=attempts+1,updated_at=? WHERE id=?",(now,job['id']))
        con.execute('SAVEPOINT scheduled_job')
        try:
            if job['job_type']=='engine_evaluate':
                result=evaluate_engine(con,now)
            elif job['job_type']=='run_automations':
                result=run_automations(con,now)
            else:
                raise ValueError('Unbekannter Jobtyp.')
            result_json=json.dumps(result,ensure_ascii=False,separators=(',',':'))
        except Exception as exc:
            con.execute('ROLLBACK TO SAVEPOINT scheduled_job')
            con.execute('RELEASE SAVEPOINT scheduled_job')
            con.execute("UPDATE scheduled_jobs SET status='failed',last_error=?,result_json=?,updated_at=? WHERE id=?",(f'{type(exc).__name__}: {exc}'[:500],'{}',now,job['id']))
            summary['failed']+=1
        else:
            con.execute('RELEASE SAVEPOINT scheduled_job')
            con.execute("UPDATE scheduled_jobs SET status='completed',last_error=NULL,result_json=?,updated_at=? WHERE id=?",(result_json,now,job['id']))
            summary['completed']+=1
        summary['processed']+=1
    return summary


def run_automations(con, now):
    """Run enabled allowlisted rules once per entity per UTC day; critical actions only create proposals."""
    today=str(now)[:10]
    rules=con.execute('SELECT * FROM automation_rules WHERE enabled=1 ORDER BY id').fetchall()
    summary={'rules_evaluated':len(rules),'actions_executed':0,'proposals_created':0,'already_run':0,'llm_used':False}
    for rule in rules:
        action=json.loads(rule['action_json'] or '{}')
        trigger=rule['trigger_type']
        if trigger=='manual':
            candidates=[{'entity_type':'system','entity_id':'manual','name':'System'}]
        elif trigger=='resource_low_stock':
            candidates=[{'entity_type':'resource','entity_id':str(r['id']),'name':r['name']} for r in con.execute('SELECT r.id,r.name FROM resources r JOIN resource_policies p ON p.resource_id=r.id WHERE r.quantity<p.minimum_quantity ORDER BY r.id')]
        elif trigger=='task_overdue':
            candidates=[{'entity_type':'task','entity_id':str(r['id']),'name':r['title']} for r in con.execute('SELECT id,title FROM tasks WHERE done=0 AND due_at IS NOT NULL AND due_at<? ORDER BY id',(today,))]
        else:
            candidates=[{'entity_type':'task','entity_id':str(r['id']),'name':r['title']} for r in con.execute("""SELECT t.id,t.title FROM tasks t WHERE t.done=0 AND EXISTS (
                SELECT 1 FROM task_dependencies d JOIN tasks parent ON parent.id=d.depends_on_task_id
                WHERE d.task_id=t.id AND parent.done=0) ORDER BY t.id""")]
        for candidate in candidates:
            key=f"rule:{rule['id']}:{candidate['entity_type']}:{candidate['entity_id']}:{today}"
            if con.execute('SELECT 1 FROM automation_runs WHERE idempotency_key=?',(key,)).fetchone():
                summary['already_run']+=1
                continue
            if rule['action_type']=='create_task':
                prefix=str(action.get('title_prefix') or (rule['name']+': '))
                title=(prefix+candidate['name'])[:180]
                area=str(action.get('area','Logistik'))[:80] or 'SYSTEM'
                blocked=str(action.get('blocked_reason',''))[:1000]
                cur=con.execute('INSERT INTO tasks(title,area,done,created_at,updated_at,blocked_reason) VALUES(?,?,0,?,?,?)',(title,area,now,now,blocked))
                result={'task_id':cur.lastrowid,'title':title}
                status='executed'
                summary['actions_executed']+=1
            else:
                payload={'resource_id':int(candidate['entity_id']),'quantity_delta':float(action['quantity_delta']),'notes':str(action.get('notes') or (rule['name']+' — ausdrücklich zu bestätigen'))[:1000]}
                con.execute('INSERT OR IGNORE INTO action_proposals(idempotency_key,action_type,payload_json,risk_level,status,rationale,created_at) VALUES(?,?,?,?,?,?,?)',(key,'adjust_resource',json.dumps(payload,ensure_ascii=False,separators=(',',':')),'critical','pending',rule['name'],now))
                proposal=con.execute('SELECT id FROM action_proposals WHERE idempotency_key=?',(key,)).fetchone()
                result={'proposal_id':proposal['id'],'requires_confirmation':True}
                status='proposal_created'
                summary['proposals_created']+=1
            con.execute('INSERT INTO automation_runs(rule_id,idempotency_key,trigger_entity_type,trigger_entity_id,status,result_json,created_at) VALUES(?,?,?,?,?,?,?)',(rule['id'],key,candidate['entity_type'],candidate['entity_id'],status,json.dumps(result,ensure_ascii=False,separators=(',',':')),now))
    return summary


def evaluate_engine(con, now):
    """Run deterministic stock-policy rules without AI, network access, or destructive actions."""
    run=con.execute("INSERT INTO engine_runs(started_at,status,summary_json) VALUES(?,'running','{}')",(now,))
    run_id=run.lastrowid
    low_resources=set()
    affected=0
    rows=con.execute("""SELECT r.id,r.name,r.quantity,r.unit,p.minimum_quantity
        FROM resources r JOIN resource_policies p ON p.resource_id=r.id ORDER BY r.id""").fetchall()
    for row in rows:
        quantity=float(row['quantity']); minimum=float(row['minimum_quantity'])
        if quantity >= minimum: continue
        resource_id=int(row['id']); low_resources.add(str(resource_id))
        key='resource-low:'+str(resource_id)
        severity='critical' if quantity<=0 else 'warning'
        message=f"{row['name']}: Bestand {quantity:g} {row['unit']}; Mindestbestand {minimum:g}."
        existing=con.execute('SELECT * FROM alerts WHERE alert_key=?',(key,)).fetchone()
        if existing:
            status='acknowledged' if existing['status']=='acknowledged' else 'open'
            con.execute('UPDATE alerts SET severity=?,message=?,status=?,updated_at=?,resolved_at=NULL WHERE id=?',(severity,message,status,now,existing['id']))
        else:
            con.execute('INSERT INTO alerts(alert_key,severity,category,title,message,entity_type,entity_id,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (key,severity,'resource_stock_low','Bestand unter Mindestbestand',message,'resource',str(resource_id),'open',now,now))
        affected+=1
    resolved=0
    for alert in con.execute("SELECT id,entity_id FROM alerts WHERE category='resource_stock_low' AND status IN ('open','acknowledged')").fetchall():
        if str(alert['entity_id']) not in low_resources:
            con.execute("UPDATE alerts SET status='resolved',resolved_at=?,updated_at=? WHERE id=?",(now,now,alert['id']))
            resolved+=1
    open_count=con.execute("SELECT COUNT(*) FROM alerts WHERE status='open'").fetchone()[0]
    acknowledged_count=con.execute("SELECT COUNT(*) FROM alerts WHERE status='acknowledged'").fetchone()[0]
    summary={'run_id':run_id,'low_stock_resources':len(low_resources),'alerts_created_or_updated':affected,'alerts_resolved':resolved,'open_alerts':int(open_count),'acknowledged_alerts':int(acknowledged_count),'llm_used':False}
    con.execute("UPDATE engine_runs SET completed_at=?,status='completed',summary_json=? WHERE id=?",(now,json.dumps(summary,ensure_ascii=False,separators=(',',':')),run_id))
    return summary


def build_engine_status(con, ai_status):
    """Build a reproducible health snapshot without writing to the database."""
    tables = {row['name'] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    integrity = str(con.execute('PRAGMA integrity_check').fetchone()[0])
    foreign_key_violations = len(con.execute('PRAGMA foreign_key_check').fetchall())
    migration_version = _count(con, 'SELECT COALESCE(MAX(version),0) FROM schema_migrations')
    event_cursor = _count(con, 'SELECT COALESCE(MAX(event_id),0) FROM event_journal') if 'event_journal' in tables else 0
    module_counts = {module: 0 for module in MODULES}
    for row in con.execute('SELECT module,COUNT(*) AS count FROM records GROUP BY module'):
        module_counts[row['module']] = int(row['count'])
    counts = {
        'open_tasks': _count(con, 'SELECT COUNT(*) FROM tasks WHERE done=0'),
        'completed_tasks': _count(con, 'SELECT COUNT(*) FROM tasks WHERE done=1'),
        'records': _count(con, 'SELECT COUNT(*) FROM records'),
        'records_by_module': module_counts,
        'locations': _count(con, 'SELECT COUNT(*) FROM map_locations'),
        'blocked_locations': _count(con, "SELECT COUNT(*) FROM map_locations WHERE status='blockiert'"),
        'active_locations': _count(con, "SELECT COUNT(*) FROM map_locations WHERE status='aktiv'"),
        'units': _count(con, 'SELECT COUNT(*) FROM units'),
        'resources': _count(con, 'SELECT COUNT(*) FROM resources'),
        'assignments': _count(con, 'SELECT COUNT(*) FROM project_assignments'),
        'resource_policies': _count(con, 'SELECT COUNT(*) FROM resource_policies') if 'resource_policies' in tables else 0,
        'open_alerts': _count(con, "SELECT COUNT(*) FROM alerts WHERE status IN ('open','acknowledged')") if 'alerts' in tables else 0,
        'enabled_automation_rules': _count(con, 'SELECT COUNT(*) FROM automation_rules WHERE enabled=1') if 'automation_rules' in tables else 0,
        'pending_action_proposals': _count(con, "SELECT COUNT(*) FROM action_proposals WHERE status='pending'") if 'action_proposals' in tables else 0,
        'pending_scheduled_jobs': _count(con, "SELECT COUNT(*) FROM scheduled_jobs WHERE status='pending'") if 'scheduled_jobs' in tables else 0,
    }
    checks = [
        {'name': 'sqlite_integrity', 'ok': integrity == 'ok', 'detail': integrity},
        {'name': 'foreign_keys', 'ok': foreign_key_violations == 0, 'detail': foreign_key_violations},
        {'name': 'llm_independence', 'ok': True, 'detail': 'Core functionality does not require an LLM.'},
    ]
    return {
        'engine': 'KOR-NEXUS Core Engine',
        'engine_version': ENGINE_VERSION,
        'state': 'ready' if integrity == 'ok' and foreign_key_violations == 0 else 'degraded',
        'llm_required': False,
        'ai': dict(ai_status),
        'database': {
            'integrity': integrity,
            'foreign_key_violations': foreign_key_violations,
            'schema_version': migration_version,
            'event_cursor': event_cursor,
        },
        'counts': counts,
        'checks': checks,
    }
