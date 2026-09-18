"""Bounded developer-container worker. No sockets, host mounts or credentials."""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import signal
import subprocess
import sys
import threading
import time

LIMIT = 256 * 1024


def relative(value):
    parts = PurePosixPath(value).parts
    if not parts or value.startswith('/') or any(p in ('..', '.') for p in parts) or '\\' in value or ':' in value:
        raise ValueError('Invalid relative path')
    return value


def main():
    request = json.loads(sys.stdin.buffer.read(4 * 1024 * 1024 + 1))
    if not 1 <= request['timeout'] <= 300 or len(request['files']) > 500:
        raise ValueError('Limits exceeded')
    total = 0
    for item in request['files']:
        path = Path('/workspace') / relative(item['path'])
        data = base64.b64decode(item['data'], validate=True)
        total += len(data)
        if total > 2 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Input integrity failed')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    argv = request['argv']
    if not isinstance(argv, list) or not argv or argv[0] != 'python' or len(argv) > 32:
        raise ValueError('Python task required')
    started = time.monotonic()
    child = subprocess.Popen(argv, cwd='/workspace', stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
                             env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/tmp',
                                  'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1',
                                  'SV_OUTPUT_DIR': '/output', 'OMP_NUM_THREADS': '1'})
    streams = {'stdout': bytearray(), 'stderr': bytearray()}
    overflow = threading.Event()

    def drain(name, pipe):
        while chunk := pipe.read(4096):
            remaining = LIMIT - len(streams[name])
            streams[name].extend(chunk[:max(0, remaining)])
            if len(chunk) > remaining:
                overflow.set()

    threads = [threading.Thread(target=drain, args=(name, getattr(child, name)), daemon=True)
               for name in streams]
    for thread in threads:
        thread.start()
    reason = 'exited'
    try:
        while child.poll() is None:
            if overflow.is_set():
                reason = 'output_limit'
                break
            if time.monotonic() - started >= request['timeout']:
                reason = 'timeout'
                break
            time.sleep(0.05)
    finally:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()
        for thread in threads:
            thread.join(timeout=2)
    if overflow.is_set():
        reason = 'output_limit'
    artifacts = []
    size = 0
    for path in sorted(Path('/output').rglob('*')):
        if path.is_symlink():
            raise ValueError('Output links rejected')
        if not path.is_file():
            continue
        size += path.stat().st_size
        if size > 2 * 1024 * 1024 or len(artifacts) >= 50:
            raise ValueError('Output files exceed limit')
        data = path.read_bytes()
        artifacts.append({'path': relative(path.relative_to('/output').as_posix()),
                          'data': base64.b64encode(data).decode(), 'sha256': hashlib.sha256(data).hexdigest()})
    print(json.dumps({'exitCode': child.returncode if reason == 'exited' else 124 if reason == 'timeout' else 125,
                      'reason': reason, 'durationSeconds': round(time.monotonic() - started, 3),
                      'stdout': base64.b64encode(streams['stdout']).decode(),
                      'stderr': base64.b64encode(streams['stderr']).decode(), 'artifacts': artifacts}))


if __name__ == '__main__':
    main()
