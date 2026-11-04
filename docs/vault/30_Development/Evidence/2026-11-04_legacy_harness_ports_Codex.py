"""Record bounded harness checks; --pg uses one new labeled tmpfs-only server."""
import datetime as dt
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).parent
LOG = EVIDENCE / '2026-11-04_legacy_harness_ports_Codex.jsonl'
KST = dt.timezone(dt.timedelta(hours=9))
TASK = 'task_2944648d1e21'
PYTHON = 'D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe'


def emit(record):
    with LOG.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')


def run(argv, environment=None, redactions=()):
    env = dict(os.environ if environment is None else environment)
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
               PYTHONPATH=os.pathsep.join(map(str, (ROOT, ROOT / 'src', ROOT / 'services/control-plane/src', ROOT / 'tests'))))
    started = dt.datetime.now(KST).isoformat()
    result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    stdout, stderr = result.stdout, result.stderr
    for value in redactions:
        stdout, stderr = stdout.replace(value, '<redacted>'), stderr.replace(value, '<redacted>')
    record = {'argv': argv, 'cwd': str(ROOT), 'startedKst': started,
              'endedKst': dt.datetime.now(KST).isoformat(), 'exitCode': result.returncode,
              'sourceHead': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'trackedDiffPaths': subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], cwd=ROOT, text=True).splitlines(),
              'testDsnPresent': bool(env.get('INV_TEST_ADMIN_DSN')), 'stdout': stdout, 'stderr': stderr}
    emit(record)
    print(stdout, end='')
    print(stderr, end='', file=sys.stderr)
    print('DIRECT EXIT:', result.returncode, flush=True)
    return result.returncode


def postgres_checks():
    import psycopg
    password = secrets.token_urlsafe(32)
    environment = dict(os.environ, POSTGRES_PASSWORD=password)
    name = 'sv-legacy-harness-' + secrets.token_hex(6)
    argv = ['docker', 'run', '--detach', '--rm', '--name', name,
            '--label', 'inv.test.owner=codex', '--label', 'inv.test.task=' + TASK,
            '--tmpfs', '/var/lib/postgresql/data:rw', '--env', 'POSTGRES_PASSWORD',
            '--publish', '127.0.0.1::5432', 'pgvector/pgvector:pg16']
    created = subprocess.run(argv, env=environment, capture_output=True, text=True)
    if created.returncode:
        raise RuntimeError('Owned PostgreSQL server creation failed')
    container_id = created.stdout.strip()
    try:
        inspected = json.loads(subprocess.check_output(['docker', 'inspect', container_id], text=True))[0]
        assert inspected['Config']['Labels'].get('inv.test.task') == TASK
        # Older Engines list tmpfs in HostConfig instead of Mounts.
        assert '/var/lib/postgresql/data' in inspected['HostConfig']['Tmpfs']
        assert all(mount['Type'] == 'tmpfs' for mount in inspected['Mounts'])
        port = inspected['NetworkSettings']['Ports']['5432/tcp'][0]
        assert port['HostIp'] == '127.0.0.1'
        dsn = psycopg.conninfo.make_conninfo(host='127.0.0.1', port=port['HostPort'], user='postgres', password=password, dbname='postgres')
        environment['INV_TEST_ADMIN_DSN'] = dsn
        for attempt in range(60):
            try:
                with psycopg.connect(dsn, connect_timeout=1):
                    break
            except psycopg.Error:
                if attempt == 59:
                    raise RuntimeError('Owned PostgreSQL did not become ready') from None
                time.sleep(0.25)
        emit({'kind': 'disposablePostgres', 'containerId': container_id, 'imageId': inspected['Image'],
              'port': port, 'mounts': inspected['Mounts'], 'tmpfs': inspected['HostConfig']['Tmpfs'], 'labels': inspected['Config']['Labels'],
              'syntheticTestServer': True, 'liveResourcesUsed': False})
        commands = [
            [PYTHON, 'tools/run_s04_db_evidence.py', '--json-out', str(EVIDENCE / '2026-11-04_legacy_harness_ports_Codex.s04.json'), '--junit-out', str(EVIDENCE / '2026-11-04_legacy_harness_ports_Codex.s04.xml')],
            [PYTHON, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', 'tests/integration/test_five_node_lab_preflight.py', '--junitxml=' + str(EVIDENCE / '2026-11-04_legacy_harness_ports_Codex.s07.xml')],
            [PYTHON, 'tools/measure_s07_recovery.py', '--nodes', '3', '--repetitions', '1', '--liveness-timeout-seconds', '0.05', '--poll-interval-seconds', '0.02', '--max-detection-seconds', '0.5', '--json-out', str(EVIDENCE / '2026-11-04_legacy_harness_ports_Codex.synthetic.json'), '--junit-out', str(EVIDENCE / '2026-11-04_legacy_harness_ports_Codex.synthetic.xml')],
        ]
        exits = [run(command, environment, (dsn, password)) for command in commands]
        with psycopg.connect(dsn) as conn:
            databases = conn.execute("SELECT count(*) FROM pg_database WHERE datname LIKE 'inv_test_%'").fetchone()[0]
            roles = conn.execute("SELECT count(*) FROM pg_roles WHERE rolcanlogin AND rolname LIKE 'inv_app_%'").fetchone()[0]
        emit({'kind': 'disposableResidue', 'databases': databases, 'loginRoles': roles})
        assert databases == roles == 0
        return max(exits)
    finally:
        observed = subprocess.run(['docker', 'inspect', container_id], capture_output=True, text=True)
        if observed.returncode == 0:
            owned = json.loads(observed.stdout)[0]
            assert owned['Id'] == container_id
            assert owned['Config']['Labels'].get('inv.test.owner') == 'codex'
            assert owned['Config']['Labels'].get('inv.test.task') == TASK
            removed = subprocess.run(['docker', 'rm', '--force', container_id], capture_output=True, text=True)
            assert removed.returncode == 0
            check = subprocess.run(['docker', 'inspect', container_id], capture_output=True)
            assert check.returncode != 0
            emit({'kind': 'ownedContainerCleanup', 'containerId': container_id, 'removeExit': removed.returncode,
                  'absentAfterRemoval': True, 'oldResourcesTouched': False})


if __name__ == '__main__':
    if sys.argv[1] == '--pg':
        raise SystemExit(postgres_checks())
    raise SystemExit(run(sys.argv[1:]))
