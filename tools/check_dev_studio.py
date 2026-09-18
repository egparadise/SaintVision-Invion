"""Opt-in real Docker acceptance in a NEW private test Studio, never user jobs."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from dev_studio import Studio, command, ROOT


def until(check, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.1)
    raise AssertionError('Timed out waiting for observed condition')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = ROOT / '.work' / ('studio-acceptance-' + uuid4().hex[:10])
    studio = Studio.init(root)
    studio.set_config('image', args.image)
    project_path = root / 'project'
    (project_path / 'src').mkdir(parents=True)
    (project_path / 'src/check.py').write_text('''import os, sys, time
from pathlib import Path
mode=sys.argv[1]
if mode == 'sleep':
    print('started',flush=True)
    time.sleep(60)
elif mode == 'fail':
    print('expected-failure',file=sys.stderr)
    sys.exit(7)
else:
    assert os.getuid() == 65532
    status=Path('/proc/self/status').read_text()
    assert 'CapEff:\\t0000000000000000' in status
    assert sorted(Path('/sys/class/net').iterdir()) == [Path('/sys/class/net/lo')]
    assert not Path('/var/run/docker.sock').exists()
    try:
        Path('/should-not-write').write_text('x')
        raise AssertionError('Writable root')
    except PermissionError:
        pass
    except OSError as error:
        assert error.errno == 30
    print('isolation-ok')
''')
    command(['git', 'init', str(project_path)])
    command(['git', '-C', str(project_path), 'add', '.'])
    command(['git', '-C', str(project_path), '-c', 'user.name=Studio Acceptance', '-c', 'user.email=acceptance@localhost', 'commit', '-m', 'Isolated acceptance input'])
    tasks = {key: {'label': key, 'argv': ['python', 'src/check.py', key]} for key in ('success', 'fail', 'sleep')}
    project = studio.register('acceptance', project_path, 'acceptance', tasks, ['src'])
    workspace = studio.status()['projects'][0]['workspaces'][0]['id']
    results = []
    def record(case, job):
        results.append({'case': case, 'id': job['id'], 'status': job['status'], 'record': job['record']})
    try:
        studio.budget({'cpuMillis': 250, 'memoryMiB': 128, 'timeoutSeconds': 10})
        identity = studio.submit(project, workspace, 'success', 'success-key', background=False)
        job = studio.job(identity)
        assert job['status'] == 'succeeded', job
        assert job['record']['stdout'].strip() == 'isolation-ok'
        assert studio.submit(project, workspace, 'success', 'success-key') == identity
        record('isolation-and-idempotency', job)
        identity = studio.submit(project, workspace, 'fail', 'failure-key', background=False)
        job = studio.job(identity)
        assert job['status'] == 'failed' and job['record']['exitCode'] == 7, job
        record('failure-exit', job)
        studio.budget({'cpuMillis': 250, 'memoryMiB': 128, 'timeoutSeconds': 1})
        identity = studio.submit(project, workspace, 'sleep', 'timeout-key', background=False)
        job = studio.job(identity)
        assert job['status'] == 'failed' and job['record']['exitCode'] == 124 and job['record']['stopped'], job
        record('deadline', job)
        studio.budget({'cpuMillis': 250, 'memoryMiB': 128, 'timeoutSeconds': 60})
        identity = studio.submit(project, workspace, 'sleep', 'cancel-key')
        until(lambda: studio.job(identity)['status'] == 'running')
        until(lambda: studio.inspect(studio.job(identity)['record']['container'])['State']['Running'])
        studio.cancel(identity)
        until(lambda: studio.job(identity)['status'] not in ('queued', 'running', 'stopping'))
        job = studio.job(identity)
        assert job['status'] == 'cancelled' and job['record']['stopped'], job
        record('cancel-running', job)
        # Kill the actual Python runner (not the venv launcher). Docker's worker remains bounded.
        child = subprocess.Popen([sys._base_executable, str(ROOT / 'tools/dev_studio.py'), '--root', str(root), 'run',
                                  '--project', project, '--workspace', workspace, '--task', 'sleep', '--request-id', 'crash-key'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            identity = until(lambda: next((j['id'] for j in studio.status()['jobs'] if j['status'] == 'running'), None))
            name = studio.job(identity)['record']['container']
            until(lambda: studio.inspect(name)['State']['Running'])
            before = (studio.state / 'jobs' / identity / 'input.json').read_bytes()
            child.kill()
            child.wait(timeout=5)
            assert child.returncode != 0
            fresh = Studio(root)
            assert fresh.recover() == [{'id': identity, 'status': 'interrupted'}]
            assert not fresh.inspect(name)['State']['Running']
            assert before == (studio.state / 'jobs' / identity / 'input.json').read_bytes()
            assert fresh.recover() == []
            record('process-crash-recovery-no-replay', fresh.job(identity))
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
        assert all(not studio.inspect(j['record']['container'])['State']['Running'] for j in results)
        report = {'passed': True, 'scope': 'local-developer-container-acceptance', 'at': time.time(), 'root': str(root), 'tests': results}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print('PASS: real Docker isolation, idempotency, exit 7, timeout, cancellation, killed-runner recovery; all owned containers stopped.')
    finally:
        studio.recover()


if __name__ == '__main__':
    main()
