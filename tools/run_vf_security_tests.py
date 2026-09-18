"""VF regression runner: disposable PostgreSQL only, secret-safe evidence.

No operational DSN, provider credential or remote Node setting is inherited.
Node-dependent suites stay in the explicit Node acceptance lane. Skips are counted.
"""
import json
import hashlib
from datetime import datetime, timezone
import os
import re
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import uuid4
import xml.etree.ElementTree as ET

import psycopg
from psycopg.conninfo import make_conninfo
from node_dependent_tests import dependents
import docker_diag

ROOT = Path(__file__).resolve().parents[1]


class _HarnessUnavailable(RuntimeError):
    """The host could not start the harness container -- a process-creation failure or
    a timeout, not a docker/product error. The run is *unverified*, distinct from a
    product/test failure, so it must be recorded as such rather than reported as one."""


def assess_evidence(xml, subprocess_code):
    """Validate this run's report; completeness of a requested suite is a separate gate."""
    if not xml.is_file():
        return {'evidenceStatus': 'missing'}
    raw = xml.read_bytes()
    result = {'xmlSha256': hashlib.sha256(raw).hexdigest()}
    try:
        root = ET.fromstring(raw)
        if root.tag not in ('testsuites', 'testsuite'):
            raise ValueError('not JUnit')
        cases = root.findall('.//testcase')
        counts = {tag: sum(c.find(tag) is not None for c in cases)
                  for tag in ('failure', 'error', 'skipped')}
        counts['passed'] = sum(not any(c.find(tag) is not None for tag in counts)
                               for c in cases)
    except (ET.ParseError, ValueError):
        return {**result, 'evidenceStatus': 'invalid'}
    # Parameterized case IDs may contain sensitive input: keep identities private.
    identities = json.dumps([{'classname': c.get('classname'), 'name': c.get('name')}
                             for c in cases], ensure_ascii=True).encode('utf-8')
    xml.with_name('case-identities-private.json').write_bytes(identities)
    result['caseIdentitiesSha256'] = hashlib.sha256(identities).hexdigest()
    result['tests'] = counts
    if not cases:
        status = 'empty'
    elif subprocess_code != 0:
        status = 'partial'
    elif counts['failure'] or counts['error']:
        status = 'inconsistent'
    elif not counts['passed']:
        status = 'no-executed-tests'
    else:
        status = 'complete'
    return {**result, 'evidenceStatus': status}


def main():
    os.chdir(ROOT)
    output = ROOT / '.work'
    output.mkdir(exist_ok=True)
    prefix = os.environ.get('VF_EVIDENCE_PREFIX', 'vf-security')
    if not prefix.replace('-', '').isalnum():
        raise ValueError('Invalid evidence prefix')
    server_image = os.environ.get('VF_TEST_IMAGE', 'saintvision-backend-candidate:vf-cx-01')
    if re.fullmatch(r'(?:sha256:[0-9a-f]{64}|saintvision-backend-candidate:vf-cx-[0-9]{2})', server_image) is None:
        raise ValueError('Explicit local VF candidate image required')
    browser_tests = os.environ.get('VF_BROWSER_TEST', '0')
    if browser_tests not in ('0', '1'):
        raise ValueError('VF_BROWSER_TEST must be 0 or 1')
    base_env = {k: v for k, v in os.environ.items()
                if not k.startswith(('INV_', 'CX01_', 'VF_'))}
    run_id = uuid4().hex
    run_dir = output / 'vf-runs' / (prefix + '-' + run_id)
    run_dir.mkdir(parents=True, exist_ok=False)
    xml = run_dir / 'tests.xml'
    name = 'sv-container-' + run_id
    password = secrets.token_urlsafe(32)
    container = None
    proof = {'exitCode': 1, 'subprocessExitCode': None, 'evidenceStatus': 'not-run',
             'runId': run_id, 'startedAt': datetime.now(timezone.utc).isoformat(),
             'evidencePath': str((run_dir / 'proof.json').relative_to(ROOT)),
             'xmlPath': str(xml.relative_to(ROOT)),
             'evidenceScope': 'current invocation JUnit; not expected-suite or operational acceptance', 'postgres': 'isolated tmpfs PostgreSQL 16; loopback ephemeral port',
             'identity': 'synthetic issuer; no operational SSO acceptance',
             'operationalAcceptance': False, 'browserOptIn': browser_tests == '1', 'serverImage': server_image, 'nodeDependentSuitesExcluded': dependents()}
    code = 1
    try:
        if any(arg.split('=', 1)[0] in ('--collect-only', '--co') for arg in sys.argv[1:]):
            proof['evidenceStatus'] = 'rejected-mode'
            code = 2
            return code
        # Pre-run host check (image-lane finding, 2026-09-18): if the host cannot even
        # start a trivial docker process right now, the security assertions cannot be
        # reached, and retrying under sustained pressure only adds load. Record the run
        # as unverified rather than reporting a false product/test failure.
        probe = docker_diag.run(['docker', 'version', '--format', '{{.Server.Version}}'], text=True)
        if docker_diag.is_infrastructure_failure(probe):
            raise _HarnessUnavailable('pre-run host check: ' + docker_diag.describe(probe))
        # docker_diag.run classifies a Windows host process-creation failure
        # (STATUS_DLL_INIT_FAILED under host handle/RAM pressure -- the intermittent
        # VF-CL-R-001 root cause) and a timeout apart from a real docker error, and
        # never raises TimeoutExpired out unclassified.
        created = docker_diag.run([
            'docker', 'run', '-d', '--name', name,
            '--label', 'ai.saintvision.configured=' + name,
            '--label', 'ai.saintvision.cx01=' + name,
            '--memory', '768m', '--cpus', '1', '--pids-limit', '256',
            '--tmpfs', '/var/lib/postgresql/data', '--publish', '127.0.0.1::5432',
            '--env', 'POSTGRES_PASSWORD', 'postgres:16',
        ], env={**base_env, 'POSTGRES_PASSWORD': password}, text=True)
        if created.returncode:
            if docker_diag.is_infrastructure_failure(created):
                raise _HarnessUnavailable('container create: ' + docker_diag.describe(created))
            raise RuntimeError('container create failed: ' + docker_diag.describe(created))
        container = created.stdout.strip()
        inspected = docker_diag.run(['docker', 'inspect', container], text=True)
        if inspected.returncode:
            if docker_diag.is_infrastructure_failure(inspected):
                raise _HarnessUnavailable('container inspect: ' + docker_diag.describe(inspected))
            raise RuntimeError('container inspect failed: ' + docker_diag.describe(inspected))
        info = json.loads(inspected.stdout)[0]
        port = info['NetworkSettings']['Ports']['5432/tcp'][0]['HostPort']
        dsn = make_conninfo(host='127.0.0.1', port=port, dbname='postgres',
                           user='postgres', password=password, connect_timeout=2)
        for _ in range(100):
            try:
                with psycopg.connect(dsn) as conn:
                    conn.execute('SELECT 1')
                break
            except psycopg.OperationalError:
                time.sleep(.2)
        else:
            raise RuntimeError('Isolated PostgreSQL unavailable')
        command = [sys.executable, '-m', 'pytest', '-p', 'tools.vf_execution_guard', '-q', *(sys.argv[1:] or ['tests']),
                   *['--ignore=' + p for p in dependents()], '--junitxml=' + str(xml)]
        proof['command'] = command
        with (run_dir / 'private.log').open('w', encoding='utf-8') as log:
            try:
                result = subprocess.run(command, env={
                    **base_env, 'INV_TEST_ADMIN_DSN': dsn, 'CX01_CONTAINER': name,
                    'INV_BROWSER_TEST': browser_tests,
                    'INV_TEST_SERVER_IMAGE': server_image,
                    'INV_CONTAINER_TEST_DB_HOST': info['NetworkSettings']['IPAddress'],
                }, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
        proof['subprocessExitCode'] = code
        proof.update(assess_evidence(xml, code))
        if code == 0 and proof['evidenceStatus'] != 'complete':
            code = 2  # execution evidence unavailable/inconsistent, not a product assertion
    except _HarnessUnavailable as exc:
        # Unverified, not failed: the host could not start the harness. Kept distinct
        # from a test failure (exit 1) and a test-run timeout (exit 124); 125 = the
        # harness itself could not start, so the assertions were never reached.
        proof['unverified'] = str(exc)
        code = 125
    finally:
        proof['exitCode'] = code
        # Best-effort, classified (VF-CL-R-001): cleanup must never stop the secret-free
        # evidence JSON from being written. docker_diag.run classifies a host-init
        # failure or timeout rather than raising, but subprocess can still raise OSError
        # (e.g. it cannot spawn under the very pressure this addresses), so the whole
        # cleanup is guarded and its failure is recorded (masked), not propagated
        # (Codex, 2026-09-18). Ownership is checked when it can be; removal targets this
        # run's unique id, and the outcome is recorded so cleanup is falsifiable.
        try:
            if container:
                inspected = docker_diag.run(['docker', 'inspect', container, '--format',
                            '{{index .Config.Labels "ai.saintvision.configured"}}'], text=True)
                if inspected.returncode == 0 and inspected.stdout.strip() != name:
                    proof['cleanup'] = 'ownership mismatch; container preserved'
                else:
                    removed = docker_diag.run(['docker', 'rm', '-f', container])
                    proof['isolatedContainerRemoved'] = removed.returncode == 0
                    if removed.returncode:
                        proof['cleanup'] = docker_diag.describe(removed)
        except Exception as exc:
            proof['cleanup'] = 'cleanup error (container preserved): ' + docker_diag.masked_stderr(str(exc))
        proof['finishedAt'] = datetime.now(timezone.utc).isoformat()
        # Always the last statement in finally: a secret-free result JSON is written
        # even when cleanup failed above.
        encoded = json.dumps(proof, indent=2) + '\n'
        (run_dir / 'proof.json').write_text(encoded, encoding='utf-8')
        # Compatibility summary: atomic last-finisher publication, never an XML input.
        latest_temp = output / (prefix + '-' + run_id + '.tmp')
        latest_temp.write_text(encoded, encoding='utf-8')
        latest_temp.replace(output / (prefix + '.json'))
    print(json.dumps({'exitCode': code, 'tests': proof.get('tests'),
                      'unverified': proof.get('unverified'),
                      'evidence': '.work/' + prefix + '.json'}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
