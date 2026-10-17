"""Deterministic, read-only status calculations for KOR-NEXUS."""
from __future__ import annotations

ENGINE_VERSION = '0.1.0'
MODULES = ('atlas', 'projects', 'archive', 'simulation', 'database')


def _count(con, sql, params=()):
    row = con.execute(sql, params).fetchone()
    return int(row[0] or 0)


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
