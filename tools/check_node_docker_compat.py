"""Explicit local Docker acceptance for the Go Node; no production DB/PKI.

The test runner alone receives the local Docker socket. Synthetic workloads
retain the Node's normal isolation, bounded resources and cleanup protocol.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def command(args, **kwargs):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=kwargs.pop('timeout', 180), **kwargs)


def checked(args, **kwargs):
    result = command(args, **kwargs)
    if result.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} exit {result.returncode}: {result.stdout[-4000:]} {result.stderr[-4000:]}')
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--go', required=True)
    parser.add_argument('--image', required=True, help='local pinned synthetic probe image ID')
    args = parser.parse_args()
    image = json.loads(checked(['docker', 'image', 'inspect', args.image]))[0]
    if image['Id'] != args.image or image['Config'].get('Labels', {}).get('ai.saintvision.supervisor') != 'deadline-v1':
        raise ValueError('Pinned synthetic supervisor image required')
    name = 'saintvision-compat-' + uuid4().hex[:12]
    work = ROOT / '.work' / name
    work.mkdir(parents=True)
    environment = dict(os.environ, GOOS='linux', GOARCH='amd64', CGO_ENABLED='0', GOMAXPROCS='2')
    checked([args.go, 'test', '-p', '1', '-c', '-o', work / 'runtime.test', './runtime'],
            cwd=ROOT / 'services/node-agent', env=environment)
    (work / 'Dockerfile').write_text('FROM scratch\nCOPY --chmod=0755 runtime.test /runtime-test\nENTRYPOINT ["/runtime-test"]\n', encoding='ascii')
    checked(['docker', 'build', '--network=none', '--pull=false', '-t', name, work])
    test_image = checked(['docker', 'image', 'inspect', '--format', '{{.Id}}', name])
    # Pass argv directly, including dotted Go flags, on Windows and Linux.
    result = command(['docker', 'run', '--name', name, '--label', 'ai.saintvision.acceptance='+name,
                      '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                      '--cpus', '0.5', '--memory', '256m', '--pids-limit', '128',
                      '--tmpfs', '/tmp:rw,nosuid,nodev,size=33554432',
                      '--mount', 'type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock',
                      '-e', 'INV_RUN_DOCKER_COMPAT=1', '-e', 'INV_NODE_IMAGE='+args.image,
                      test_image, '-test.v', '-test.timeout=90s'])
    log = result.stdout + result.stderr
    (work / 'tests.log').write_text(log, encoding='utf-8')
    actual = json.loads(checked(['docker', 'inspect', name]))[0]
    stopped = not actual['State']['Running'] and actual['State']['Pid'] == 0
    # Keep this stopped test runner and its evidence for review. Never remove a
    # container selected by name prefix or touch an existing workload/DB.
    cases = [line.strip() for line in log.splitlines() if 'api=v1.' in line and 'outputSHA256=' in line]
    passed = result.returncode == 0 and stopped and len(cases) == 4
    evidence = dict(at=datetime.now(timezone.utc).isoformat(), passed=passed,
                    scope='local-node-component-acceptance-not-production-run',
                    codeSHA=checked(['git', 'rev-parse', 'HEAD'], cwd=ROOT),
                    dirty=bool(checked(['git', 'status', '--porcelain'], cwd=ROOT)),
                    binarySHA256=hashlib.sha256((work/'runtime.test').read_bytes()).hexdigest(),
                    probeImage=args.image, testImage=test_image, testContainer=name,
                    exitCode=result.returncode, stopped=stopped, cases=cases,
                    passedTests=sum(line.startswith('--- PASS:') for line in log.splitlines()),
                    logSHA256=hashlib.sha256(log.encode()).hexdigest(), log=str(work/'tests.log'))
    (work / 'evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence, indent=2))
    if not passed:
        print(log[-8000:])
        raise SystemExit(1)


if __name__ == '__main__':
    main()
