"""Local Windows developer workbench. Distinct from production Node Run admission.

Browser mutations require a short-lived, single-use Windows-issued login link.
Container jobs have fixed images, bounded snapshots, durable identity and no host mounts.
"""
import argparse
import base64
from contextlib import contextmanager
import hashlib
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit, parse_qs
from uuid import uuid4

from studio_templates import template

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = Path('C:/Project/SaintVision-Workspaces')
ORIGIN = 'http://127.0.0.1:18100'
LABEL = 'ai.saintvision.developer-studio'
ACTIVE = ('queued', 'running', 'stopping', 'recovery_required')
HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
SAFE_SUFFIX = {'.py', '.json', '.csv', '.txt', '.md', '.toml', '.yaml', '.yml', '.js', '.ts', '.html', '.css'}


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def command(args, *, cwd=None, timeout=30, data=None):
    process = subprocess.run([str(x) for x in args], cwd=cwd, input=data, capture_output=True,
                             timeout=timeout, creationflags=HIDDEN)
    if process.returncode:
        raise ValueError(f'{Path(str(args[0])).stem} command failed (exit {process.returncode})')
    return process.stdout.decode('utf-8-sig', errors='replace').strip()


def relative(value):
    if not isinstance(value, str) or not value or len(value) > 240 or '\\' in value or ':' in value:
        raise ValueError('Invalid file path')
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ('..', '.', '') for p in value.split('/')):
        raise ValueError('Invalid file path')
    return value


def safe_file(root, name):
    path = root / relative(name)
    for part in [path, *path.parents]:
        if part == root:
            break
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Links and junctions are not inputs')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path leaves Workspace')
    return path


def snapshot(root, inputs):
    files, total = [], 0
    for name in inputs:
        source = safe_file(root, name)
        if not source.exists():
            continue
        candidates = sorted(source.rglob('*')) if source.is_dir() else [source]
        for path in candidates:
            rel = path.relative_to(root).as_posix()
            safe_file(root, rel)
            if path.is_dir():
                continue
            if path.suffix not in SAFE_SUFFIX or path.name.startswith('.') or any(
                x.lower() in {'.git', '.venv', '__pycache__', 'node_modules', '.studio'} for x in path.relative_to(root).parts
            ) or any(word in path.name.lower() for word in ('secret', 'credential', 'private-key', 'node-key')):
                continue
            before = path.stat()
            if before.st_size > 512 * 1024:
                raise ValueError('One source file exceeds 512 KiB')
            data = path.read_bytes()
            after = path.stat()
            if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                raise ValueError('Source changed during snapshot; submit again')
            if b'-----BEGIN PRIVATE KEY-----' in data or b'-----BEGIN RSA PRIVATE KEY-----' in data:
                raise ValueError('Private key in source input')
            total += len(data)
            if total > 2 * 1024 * 1024 or len(files) >= 500:
                raise ValueError('Workspace input exceeds 2 MiB / 500 files')
            files.append({'path': rel, 'data': base64.b64encode(data).decode(), 'sha256': sha(data)})
    if not files:
        raise ValueError('No configured source inputs')
    return files


class Studio:
    def __init__(self, root=DEFAULT):
        self.root = Path(root).resolve()
        self.state = self.root / '.studio'
        if not (self.state / 'studio.sqlite').exists():
            raise ValueError('Run init from the Windows launcher first')
        self.guard = threading.RLock()
        self.implementation = {
            'implementationSHA': command(['git', '-C', ROOT, 'rev-parse', 'HEAD']),
            'implementationDirty': bool(command(['git', '-C', ROOT, 'status', '--porcelain'])),
            'implementationFiles': {name: sha((ROOT / name).read_bytes()) for name in
                ('tools/dev_studio.py', 'tools/studio_templates.py', 'deploy/studio/container_worker.py')},
        }

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.state / 'studio.sqlite', timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        try:
            conn.execute('BEGIN IMMEDIATE')
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @classmethod
    def init(cls, root):
        root = Path(root).resolve()
        state = root / '.studio'
        state.mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            sid = command(['powershell.exe', '-NoProfile', '-Command',
                           '[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value'])
            if not re.fullmatch(r'S-1-[0-9-]+', sid):
                raise ValueError('Windows user identity unavailable')
            command(['icacls.exe', str(state), '/inheritance:r', '/grant:r',
                     f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'])
        conn = sqlite3.connect(state / 'studio.sqlite')
        conn.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,path TEXT UNIQUE NOT NULL,kind TEXT NOT NULL,tasks TEXT NOT NULL,inputs TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY,project TEXT NOT NULL REFERENCES projects(id),role TEXT NOT NULL,path TEXT UNIQUE NOT NULL,UNIQUE(project,role));
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project TEXT NOT NULL REFERENCES projects(id),workspace TEXT NOT NULL,task TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,finished REAL,record TEXT NOT NULL,idempotency TEXT UNIQUE NOT NULL,request_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tokens(hash TEXT PRIMARY KEY,expires REAL NOT NULL,kind TEXT NOT NULL);
        ''')
        for key, value in {'id': str(uuid4()), 'budget': {'cpuMillis': 500, 'memoryMiB': 256, 'timeoutSeconds': 120}, 'image': None}.items():
            conn.execute('INSERT OR IGNORE INTO config VALUES(?,?)', (key, json.dumps(value)))
        conn.commit()
        conn.close()
        return cls(root)

    def config(self, key):
        with self.db() as conn:
            return json.loads(conn.execute('SELECT value FROM config WHERE key=?', (key,)).fetchone()[0])

    def set_config(self, key, value):
        with self.db() as conn:
            conn.execute('UPDATE config SET value=? WHERE key=?', (json.dumps(value), key))

    def token(self, kind='login'):
        value = secrets.token_urlsafe(32)
        with self.db() as conn:
            conn.execute('DELETE FROM tokens WHERE expires<?', (time.time(),))
            conn.execute('INSERT INTO tokens VALUES(?,?,?)', (sha(value.encode()), time.time() + (120 if kind == 'login' else 28800), kind))
        return value

    def authenticate(self, value, kind='session', consume=False):
        if not isinstance(value, str) or len(value) > 100:
            return False
        with self.db() as conn:
            row = conn.execute('SELECT * FROM tokens WHERE hash=? AND kind=? AND expires>?', (sha(value.encode()), kind, time.time())).fetchone()
            if row and consume:
                conn.execute('DELETE FROM tokens WHERE hash=?', (row['hash'],))
            return bool(row)

    def register(self, name, path, kind='existing', tasks=None, inputs=None):
        path = Path(path).resolve()
        if not path.is_dir():
            raise ValueError('Project directory unavailable')
        with self.db() as conn:
            prior = conn.execute('SELECT id FROM projects WHERE path=?', (str(path),)).fetchone()
            if prior:
                return prior['id']
            project = str(uuid4())
            conn.execute('INSERT INTO projects VALUES(?,?,?,?,?,?)', (project, name[:80], str(path), kind, json.dumps(tasks or {}), json.dumps(inputs or [])))
            conn.execute('INSERT INTO workspaces VALUES(?,?,?,?)', (str(uuid4()), project, 'main', str(path)))
        return project

    def create(self, name, kind):
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]{2,39}', name):
            raise ValueError('Use a project name with 3–40 lowercase letters, digits or hyphens')
        files, tasks = template(kind)
        path = self.root / 'Projects' / name
        path.mkdir(parents=True, exist_ok=False)
        for name, content in files.items():
            target = path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
        command(['git', 'init', '--initial-branch=main', str(path)])
        command(['git', '-C', str(path), 'add', '.'])
        command(['git', '-C', str(path), '-c', 'user.name=SaintVision Workspace Setup', '-c', 'user.email=workspace@localhost',
                 'commit', '-m', 'Initialize editable development workspace'])
        command([sys.executable, '-m', 'venv', str(path / '.venv')], timeout=90)
        project = self.register(path.name, path, kind, tasks, ['src', 'tests', 'data'])
        self.configure_tools()
        return project

    def workspace(self, project, workspace):
        with self.db() as conn:
            row = conn.execute('SELECT w.*,p.tasks,p.inputs,p.name FROM workspaces w JOIN projects p ON p.id=w.project WHERE w.id=? AND w.project=?', (workspace, project)).fetchone()
        if not row:
            raise ValueError('Workspace unavailable')
        return dict(row)

    def configure_tools(self):
        count = 0
        for project in self.status()['projects']:
            for workspace in project['workspaces']:
                path = Path(workspace['path'])
                directory = safe_file(path, '.saintvision')
                directory.mkdir(exist_ok=True)
                target = safe_file(path, '.saintvision/README.md')
                marker = '<!-- SaintVision managed development context v1 -->'
                if target.exists() and not target.read_text('utf-8').startswith(marker):
                    raise ValueError('Existing unmanaged tool context preserved')
                def quote(value):
                    return "'" + str(value).replace("'", "''") + "'"
                prefix = '& ' + quote(sys.executable) + ' ' + quote(ROOT / 'tools/dev_studio.py') + ' --root ' + quote(self.root)
                lines = [marker, '# SaintVision development context', '',
                         'Read AGENTS.md and README.md. Work only in the selected Workspace.',
                         'Use these registered commands for bounded CPU tests/training. Do not invent Run/Evidence IDs or bypass production approvals.',
                         'GPU and remote Node execution are not enabled in this developer environment.', '',
                         f'Project: {project["name"]}', f'Workspace role: {workspace["role"]}', f'Workspace path: {path}', '', '```powershell']
                for task in project['tasks']:
                    lines.append(prefix + ' run --project ' + quote(project['id']) + ' --workspace ' + quote(workspace['id']) + ' --task ' + quote(task))
                if not project['tasks']:
                    lines.append('# No container task registered. Use the repository development instructions.')
                lines += ['```', '', 'Report the returned job ID, actual status, exit code and artifact hashes. Credentials stay in the tool account; never copy them into source inputs.', '']
                target.write_text('\n'.join(lines), encoding='utf-8')
                try:
                    common = Path(command(['git', '-C', path, 'rev-parse', '--git-common-dir']))
                except ValueError:
                    count += 1
                    continue  # A plain folder can be opened without initializing Git.
                if not common.is_absolute():
                    common = (path / common).resolve()
                exclude = common / 'info/exclude'
                current = exclude.read_text('utf-8') if exclude.exists() else ''
                if '.saintvision/' not in current.splitlines():
                    exclude.parent.mkdir(parents=True, exist_ok=True)
                    with exclude.open('a', encoding='utf-8') as stream:
                        stream.write('\n.saintvision/\n')
                count += 1
        return {'configuredWorkspaces': count}

    def add_workspace(self, project, role):
        if role not in ('codex', 'claude', 'gemini', 'antigravity'):
            raise ValueError('Unknown development tool')
        with self.guard:
            with self.db() as conn:
                prior = conn.execute('SELECT * FROM workspaces WHERE project=? AND role=?', (project, role)).fetchone()
                base = conn.execute('SELECT * FROM projects WHERE id=?', (project,)).fetchone()
            if prior:
                return dict(prior)
            if not base:
                raise ValueError('Project unavailable')
            command(['orca', 'repo', 'add', '--path', base['path'], '--json'], timeout=45)
            head = command(['git', '-C', base['path'], 'rev-parse', 'HEAD'])
            result = json.loads(command(['orca', 'worktree', 'create', '--repo', 'path:' + base['path'],
                      '--name', 'studio-' + role, '--base-branch', head, '--setup', 'skip', '--no-parent', '--json'], timeout=60))
            if not result.get('ok'):
                raise ValueError('Orca Workspace creation failed')
            path = result['result']['worktree']['path']
            if base['kind'] in ('ai', 'python'):
                command([sys.executable, '-m', 'venv', str(Path(path) / '.venv')], timeout=90)
            row = {'id': str(uuid4()), 'project': project, 'role': role, 'path': str(Path(path).resolve())}
            with self.db() as conn:
                conn.execute('INSERT INTO workspaces VALUES(:id,:project,:role,:path)', row)
            self.configure_tools()
            return row

    def open_tool(self, project, workspace, tool):
        if tool not in ('orca', 'codex', 'claude', 'gemini', 'antigravity', 'folder', 'terminal'):
            raise ValueError('Unknown tool')
        row = self.workspace(project, workspace)
        if os.name != 'nt':
            raise ValueError('Desktop tools require Windows')
        # File arguments never become PowerShell code; the script has a fixed switch.
        command(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                 str(ROOT / 'deploy/studio/Open-Tool.ps1'), '-Workspace', row['path'], '-Tool', tool], timeout=40)
        return {'opened': tool, 'workspace': row['path'], 'authentication': 'existing-tool-account'}

    def budget(self, value):
        if not isinstance(value, dict) or set(value) != {'cpuMillis', 'memoryMiB', 'timeoutSeconds'} or any(type(x) is not int for x in value.values()):
            raise ValueError('Integer resource limits required')
        if not 250 <= value['cpuMillis'] <= 1000 or not 128 <= value['memoryMiB'] <= 512 or not 1 <= value['timeoutSeconds'] <= 300:
            raise ValueError('CPU 0.25–1, memory 128–512 MiB, timeout 1–300 seconds')
        with self.db() as conn:
            if conn.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running','stopping','recovery_required')").fetchone():
                raise ValueError('Wait for the current job or finish recovery before changing limits')
            conn.execute('UPDATE config SET value=? WHERE key=?', (json.dumps(value), 'budget'))
        return value

    def status(self):
        with self.db() as conn:
            projects = [dict(row) for row in conn.execute('SELECT * FROM projects ORDER BY name')]
            workspaces = [dict(row) for row in conn.execute('SELECT * FROM workspaces ORDER BY role')]
            jobs = [dict(row) for row in conn.execute('SELECT * FROM jobs ORDER BY created DESC LIMIT 50')]
        for row in projects:
            row['tasks'] = json.loads(row['tasks'])
            row['inputs'] = json.loads(row['inputs'])
            row['workspaces'] = [w for w in workspaces if w['project'] == row['id']]
        for row in jobs:
            row['record'] = json.loads(row['record'])
            row.pop('idempotency')
            row.pop('request_hash')
        return {'scope': 'local-developer-studio', 'projects': projects, 'jobs': jobs,
                'budget': self.config('budget'), 'imageConfigured': bool(self.config('image')),
                'tools': {tool: bool(shutil.which(exe)) for tool, exe in {'orca': 'orca', 'codex': 'codex.cmd', 'claude': 'claude', 'gemini': 'gemini.cmd', 'antigravity': 'agy'}.items()},
                'remoteExecution': False, 'gpuExecution': False, 'generatedAt': time.time()}

    def submit(self, project, workspace, task, key, *, background=True):
        if not isinstance(key, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}', key):
            raise ValueError('Idempotency key required')
        request_hash = sha(encode([project, workspace, task]))
        with self.guard:
            with self.db() as conn:
                prior = conn.execute('SELECT * FROM jobs WHERE idempotency=?', (key,)).fetchone()
            if prior:
                if prior['request_hash'] != request_hash:
                    raise ValueError('Idempotency key has different intent')
                return prior['id']
            row = self.workspace(project, workspace)
            tasks = json.loads(row['tasks'])
            if task not in tasks:
                raise ValueError('Task is not configured for this project')
            image = self.config('image')
            if not image or not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
                raise ValueError('Build the pinned execution image first')
            files = snapshot(Path(row['path']), json.loads(row['inputs']))
            budget = self.config('budget')
            argv = tasks[task]['argv']
            if not argv or argv[0] != 'python' or not all(isinstance(s, str) and len(s) < 300 for s in argv):
                raise ValueError('Configured Python task required')
            identity = 'dev_' + uuid4().hex
            record = {'scope': 'developer-container', 'machine': 'server-local-docker', 'container': 'svdev-' + identity,
                      'image': image, 'budget': budget, 'argv': argv, 'workspacePath': row['path'],
                      'inputSha256': sha(encode(files)), 'inputFiles': [{k: f[k] for k in ('path', 'sha256')} for f in files],
                      'gitCommit': command(['git', '-C', row['path'], 'rev-parse', 'HEAD']),
                      **self.implementation,
                      'artifacts': []}
            target = self.state / 'jobs' / identity
            target.mkdir(parents=True)
            (target / 'input.json').write_bytes(encode({'files': files, 'argv': argv, 'timeout': budget['timeoutSeconds']}))
            with self.db() as conn:
                if conn.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running','stopping','recovery_required')").fetchone():
                    raise ValueError('One job is already active; wait for completion')
                current_budget = json.loads(conn.execute("SELECT value FROM config WHERE key='budget'").fetchone()[0])
                if budget != current_budget:
                    raise ValueError('Budget changed while freezing source; submit again')
                conn.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,NULL,?,?,?)',
                             (identity, project, workspace, task, 'queued', time.time(), json.dumps(record), key, request_hash))
            if background:
                threading.Thread(target=self.execute, args=(identity,), daemon=True).start()
            else:
                self.execute(identity)
            return identity

    def job(self, identity):
        with self.db() as conn:
            row = conn.execute('SELECT * FROM jobs WHERE id=?', (identity,)).fetchone()
        if not row:
            raise ValueError('Job unavailable')
        result = dict(row)
        result['record'] = json.loads(result['record'])
        return result

    def inspect(self, name):
        # Distinguish daemon failure from absence. Absence is proven by an owned list response.
        ids = command(['docker', 'ps', '-aq', '--filter', 'name=^/' + name + '$'])
        if not ids:
            return None
        if len(ids.splitlines()) != 1:
            raise ValueError('Container name is ambiguous')
        item = json.loads(command(['docker', 'inspect', ids]))[0]
        if item['Config'].get('Labels', {}).get(LABEL) != self.config('id'):
            raise ValueError('Container ownership differs; preserved')
        return item

    def stop_owned(self, name):
        item = self.inspect(name)
        if item and item['State']['Running']:
            command(['docker', 'stop', '--time', '2', item['Id']], timeout=20)
            if self.inspect(name)['State']['Running']:
                raise ValueError('Container stop unverified')

    def execute(self, identity):
        job = self.job(identity)
        record, terminal = job['record'], 'failed'
        name, budget = record['container'], record['budget']
        target = self.state / 'jobs' / identity
        try:
            with self.guard:
                if self.job(identity)['status'] != 'queued':
                    return
                command(['docker', 'create', '--name', name, '--label', LABEL + '=' + self.config('id'),
                         '--cpus', str(budget['cpuMillis'] / 1000), '--memory', str(budget['memoryMiB']) + 'm',
                         '--memory-swap', str(budget['memoryMiB']) + 'm', '--pids-limit', '64', '--network', 'none',
                         '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                         '--user', '65532:65532', '--init', '--restart', 'no', '--log-driver', 'json-file',
                         '--log-opt', 'max-size=4m', '--log-opt', 'max-file=1',
                         '--tmpfs', '/workspace:rw,noexec,nosuid,nodev,size=16m,uid=65532,gid=65532,mode=700',
                         '--tmpfs', '/output:rw,noexec,nosuid,nodev,size=8m,uid=65532,gid=65532,mode=700',
                         '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=16m,uid=65532,gid=65532,mode=700', '-i', record['image']])
                actual = self.inspect(name)
                host = actual['HostConfig']
                if (actual['Image'] != record['image'] or host['NanoCpus'] != budget['cpuMillis'] * 1000000
                    or host['Memory'] != budget['memoryMiB'] * 1024**2 or host['MemorySwap'] != host['Memory']
                    or host['NetworkMode'] != 'none' or not host['ReadonlyRootfs'] or host.get('Binds')
                    or host['PidsLimit'] != 64 or host['Privileged'] or host.get('CapAdd')
                    or {x.upper() for x in host['CapDrop']} != {'ALL'}
                    or 'no-new-privileges' not in host['SecurityOpt'] or actual['Config']['User'] != '65532:65532'
                    or actual['Config'].get('Volumes') or host['RestartPolicy']['Name'] != 'no'
                    or any(m['Type'] in ('bind','volume') for m in actual.get('Mounts', []))):
                    raise ValueError('Actual container limits differ')
                record['enforced'] = {'cpuMillis': host['NanoCpus'] // 1000000, 'memoryBytes': host['Memory'],
                                      'network': host['NetworkMode'], 'readonlyRoot': host['ReadonlyRootfs'], 'pids': host['PidsLimit']}
                with self.db() as conn:
                    conn.execute('UPDATE jobs SET status=?,record=? WHERE id=?', ('running', json.dumps(record), identity))
                process = subprocess.Popen(['docker', 'start', '-ai', name], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, creationflags=HIDDEN)
            try:
                output, errors = process.communicate((target / 'input.json').read_bytes(), timeout=budget['timeoutSeconds'] + 20)
            except subprocess.TimeoutExpired:
                self.stop_owned(name)
                process.kill()
                process.communicate()
                raise ValueError('Container transport timed out') from None
            # Drain first, then require observed termination; a disconnected attach is not success.
            actual = self.inspect(name)
            if not actual or actual['State']['Running']:
                raise ValueError('Container completion not observed')
            if process.returncode or actual['State']['ExitCode'] or len(output) > 4 * 1024 * 1024:
                raise ValueError('Container worker failed; inspect its retained job container')
            result = json.loads(output)
            (target / 'receipt.json').write_bytes(output)
            record['receiptSha256'] = sha(output)
            record['exitCode'], record['reason'] = result['exitCode'], result['reason']
            record['durationSeconds'] = result['durationSeconds']
            for stream in ('stdout', 'stderr'):
                data = base64.b64decode(result[stream], validate=True)
                if len(data) > 256 * 1024:
                    raise ValueError('Stream exceeds limit')
                (target / (stream + '.txt')).write_bytes(data)
                record[stream] = data.decode('utf-8', errors='replace')[:16000]
                record[stream + 'Sha256'] = sha(data)
            total = 0
            for artifact in result['artifacts']:
                data = base64.b64decode(artifact['data'], validate=True)
                total += len(data)
                if total > 2 * 1024 * 1024 or len(record['artifacts']) >= 50 or sha(data) != artifact['sha256']:
                    raise ValueError('Artifact integrity failed')
                dest = safe_file(target / 'artifacts', artifact['path'])
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                record['artifacts'].append({'path': artifact['path'], 'sha256': sha(data), 'sizeBytes': len(data)})
            terminal = 'succeeded' if result['exitCode'] == 0 and result['reason'] == 'exited' else 'failed'
        except Exception as error:
            record['error'] = str(error)[:240] if isinstance(error, ValueError) else 'Execution failed; journal preserved'
        finally:
            with self.guard:
                current = self.job(identity)['status']
                try:
                    self.stop_owned(name)
                    record['stopped'] = True
                except Exception:
                    terminal = 'recovery_required'
                    record['stopped'] = False
                if current == 'stopping' and terminal != 'recovery_required':
                    terminal = 'cancelled'
                if current in ACTIVE:
                    with self.db() as conn:
                        conn.execute('UPDATE jobs SET status=?,finished=?,record=? WHERE id=?', (terminal, time.time(), json.dumps(record), identity))

    def cancel(self, identity):
        with self.guard:
            job = self.job(identity)
            if job['status'] not in ACTIVE:
                return {'status': job['status']}
            with self.db() as conn:
                conn.execute('UPDATE jobs SET status=? WHERE id=?', ('stopping', identity))
            try:
                self.stop_owned(job['record']['container'])
            except Exception:
                with self.db() as conn:
                    conn.execute('UPDATE jobs SET status=? WHERE id=?', ('recovery_required', identity))
                raise
            if job['status'] == 'queued':
                with self.db() as conn:
                    conn.execute('UPDATE jobs SET status=?,finished=? WHERE id=?', ('cancelled', time.time(), identity))
            return {'status': self.job(identity)['status']}

    def recover(self):
        with self.guard:
            with self.db() as conn:
                rows = conn.execute("SELECT * FROM jobs WHERE status IN ('queued','running','stopping','recovery_required')").fetchall()
            result = []
            for row in rows:
                record = json.loads(row['record'])
                try:
                    self.stop_owned(record['container'])
                    status = 'interrupted'
                    record['stopped'], record['recovery'] = True, 'owned container stopped; input preserved; no automatic replay'
                except Exception:
                    status = 'recovery_required'
                    record['stopped'] = False
                with self.db() as conn:
                    conn.execute('UPDATE jobs SET status=?,finished=?,record=? WHERE id=?', (status, time.time(), json.dumps(record), row['id']))
                result.append({'id': row['id'], 'status': status})
            return result


def serve(studio):
    # The TCP bind is acquired before recovery: a second launcher cannot interrupt active jobs.
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, data, mime='application/json; charset=utf-8', cookie=None):
            raw = data if isinstance(data, bytes) else encode(data)
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if cookie:
                self.send_header('Set-Cookie', cookie)
            self.end_headers()
            self.wfile.write(raw)

        def boundary(self, mutation=False, login=False):
            if any(len(self.headers.get_all(key, [])) > 1 for key in ('Host', 'Origin', 'Cookie', 'Content-Length', 'Content-Type', 'Idempotency-Key')):
                self.reply(400, {'error': 'Ambiguous request headers'})
                return False
            if self.client_address[0] != '127.0.0.1' or self.headers.get('Host') != '127.0.0.1:18100':
                self.reply(403, {'error': 'Local Windows Studio only'})
                return False
            if mutation and (self.headers.get('Origin') != ORIGIN or self.headers.get('Content-Type') != 'application/json'):
                self.reply(403, {'error': 'Same-origin JSON request required'})
                return False
            if not login:
                cookie = SimpleCookie(self.headers.get('Cookie', ''))
                token = cookie.get('svstudio')
                if not token or not studio.authenticate(token.value):
                    self.reply(401, {'error': 'Windows의 SaintVision 개발 시작 바로가기로 로그인해 주세요.'})
                    return False
            return True

        def do_GET(self):
            path = urlsplit(self.path)
            if path.path in ('/', '/studio.js', '/studio.css', '/healthz'):
                if not self.boundary(login=True):
                    return
                if path.path == '/healthz':
                    self.reply(200, {'service': 'saintvision-developer-studio', 'root': str(studio.root)})
                else:
                    name = 'index.html' if path.path == '/' else path.path[1:]
                    mime = 'text/html' if name.endswith('.html') else 'text/javascript' if name.endswith('.js') else 'text/css'
                    self.reply(200, (ROOT / 'apps/studio' / name).read_bytes(), mime + '; charset=utf-8')
                return
            if not self.boundary():
                return
            try:
                if path.path == '/api/status':
                    self.reply(200, studio.status())
                elif path.path == '/api/remote':
                    import urllib.request
                    with urllib.request.urlopen('http://127.0.0.1:18082/pilot/v1/overview', timeout=3) as response:
                        self.reply(200, response.read(512 * 1024))
                elif path.path == '/api/artifact':
                    query = parse_qs(path.query)
                    row = studio.job(query['job'][0])
                    name = query['path'][0]
                    item = next((a for a in row['record']['artifacts'] if a['path'] == name), None)
                    if not item:
                        raise ValueError('Artifact unavailable')
                    data = safe_file(studio.state / 'jobs' / row['id'] / 'artifacts', name).read_bytes()
                    if sha(data) != item['sha256']:
                        raise ValueError('Stored artifact hash differs')
                    self.reply(200, data, 'application/octet-stream')
                else:
                    self.reply(404, {'error': 'Not found'})
            except Exception:
                self.reply(503, {'error': '데이터를 읽지 못했습니다. 연결 및 실행 기록을 확인해 주세요.'})

        def do_POST(self):
            if not self.boundary(mutation=True, login=self.path == '/api/login'):
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192 or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Request exceeds limit')
                self.connection.settimeout(5)
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('JSON object required')
                if self.path == '/api/login':
                    if not studio.authenticate(data.get('token'), 'login', consume=True):
                        self.reply(401, {'error': '로그인 링크가 만료되었거나 이미 사용됐습니다. 시작 바로가기를 다시 여세요.'})
                    else:
                        self.reply(200, {'authenticated': True}, cookie='svstudio=' + studio.token('session') + '; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
                    return
                if self.path == '/api/projects':
                    result = {'id': studio.create(data['name'], data['kind'])}
                elif self.path == '/api/workspaces':
                    result = studio.add_workspace(data['project'], data['role'])
                elif self.path == '/api/open':
                    result = studio.open_tool(data['project'], data['workspace'], data['tool'])
                elif self.path == '/api/budget':
                    result = studio.budget(data)
                elif self.path == '/api/jobs':
                    result = {'id': studio.submit(data['project'], data['workspace'], data['task'], self.headers.get('Idempotency-Key'))}
                elif self.path == '/api/cancel':
                    result = studio.cancel(data['id'])
                else:
                    self.reply(404, {'error': 'Not found'})
                    return
                self.reply(200, result)
            except (ValueError, KeyError, FileExistsError) as error:
                self.reply(409, {'error': str(error)[:240]})
            except Exception:
                self.reply(503, {'error': '작업을 수행하지 못했습니다. 기존 파일과 실행 기록은 보존했습니다.'})

    server = ThreadingHTTPServer(('127.0.0.1', 18100), Handler)
    server.daemon_threads = True
    studio.recover()
    print('SaintVision developer Studio: ' + ORIGIN, flush=True)
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT)
    subs = parser.add_subparsers(dest='action', required=True)
    for name in ('init', 'status', 'serve', 'login-link', 'recover', 'configure-tools'):
        subs.add_parser(name)
    create = subs.add_parser('create')
    create.add_argument('name')
    create.add_argument('--kind', choices=['ai', 'python'], default='python')
    register = subs.add_parser('register')
    register.add_argument('name')
    register.add_argument('path', type=Path)
    run = subs.add_parser('run')
    run.add_argument('--project', required=True)
    run.add_argument('--workspace', required=True)
    run.add_argument('--task', required=True)
    run.add_argument('--request-id', default=None)
    build = subs.add_parser('build-image')
    build.add_argument('--base-image', default='python:3.11-slim')
    args = parser.parse_args()
    studio = Studio.init(args.root) if args.action == 'init' else Studio(args.root)
    if args.action == 'init':
        print('Initialized local developer Studio; no Node identity or production DB changed.')
    elif args.action == 'serve':
        serve(studio)
    elif args.action == 'login-link':
        print(ORIGIN + '/#login=' + studio.token())
    elif args.action == 'status':
        print(json.dumps(studio.status(), ensure_ascii=False))
    elif args.action == 'create':
        print(studio.create(args.name, args.kind))
    elif args.action == 'register':
        print(studio.register(args.name, args.path))
        studio.configure_tools()
    elif args.action == 'configure-tools':
        print(json.dumps(studio.configure_tools()))
    elif args.action == 'run':
        identity = studio.submit(args.project, args.workspace, args.task, args.request_id or uuid4().hex, background=False)
        job = studio.job(identity)
        print(json.dumps({'id': identity, 'status': job['status'], 'record': job['record']}, ensure_ascii=False))
        if job['status'] != 'succeeded':
            sys.exit(1)
    elif args.action == 'recover':
        # Recovery from CLI is only allowed while no service owns the port.
        import socket
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1', 18100)) == 0:
                raise ValueError('Stop the Studio service before offline recovery')
        print(json.dumps(studio.recover()))
    elif args.action == 'build-image':
        base = json.loads(command(['docker', 'image', 'inspect', args.base_image]))[0]
        if base['Os'] != 'linux' or base['Architecture'] != 'amd64' or base['Config'].get('Volumes'):
            raise ValueError('Linux amd64 image without automatic volumes required')
        tag = 'saintvision-dev-python:' + studio.config('id')[:8]
        base_tag = 'saintvision-dev-base:' + base['Id'].split(':')[1]
        command(['docker', 'tag', base['Id'], base_tag])
        command(['docker', 'build', '--pull=false', '--network=none', '--build-arg', 'BASE_IMAGE=' + base_tag, '-t', tag,
                 str(ROOT / 'deploy/studio')], timeout=180)
        built = json.loads(command(['docker', 'image', 'inspect', tag]))[0]
        if built['RootFS']['Layers'][:len(base['RootFS']['Layers'])] != base['RootFS']['Layers']:
            raise ValueError('Built image base layers differ')
        image = built['Id']
        studio.set_config('image', image)
        print(json.dumps({'image': image, 'baseImage': base['Id']}))


if __name__ == '__main__':
    main()
