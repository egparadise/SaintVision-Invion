"""VF regression runner: disposable PostgreSQL only, secret-safe evidence.

No operational DSN, provider credential or remote Node setting is inherited.
Node-dependent suites stay in the explicit Node acceptance lane. Skips are counted.
"""
import json
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

ROOT = Path(__file__).resolve().parents[1]


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
    name = 'sv-container-' + uuid4().hex
    password = secrets.token_urlsafe(32)
    container = None
    proof = {'exitCode': 1, 'postgres': 'isolated tmpfs PostgreSQL 16; loopback ephemeral port',
             'identity': 'synthetic issuer; no operational SSO acceptance',
             'operationalAcceptance': False, 'browserOptIn': browser_tests == '1', 'serverImage': server_image, 'nodeDependentSuitesExcluded': dependents()}
    code = 1
    try:
        container = subprocess.check_output([
            'docker', 'run', '-d', '--name', name,
            '--label', 'ai.saintvision.configured=' + name,
            '--label', 'ai.saintvision.cx01=' + name,
            '--memory', '768m', '--cpus', '1', '--pids-limit', '256',
            '--tmpfs', '/var/lib/postgresql/data', '--publish', '127.0.0.1::5432',
            '--env', 'POSTGRES_PASSWORD', 'postgres:16',
        ], env={**base_env, 'POSTGRES_PASSWORD': password}, text=True).strip()
        info = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
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
        xml = output / (prefix + '-tests.xml')
        command = [sys.executable, '-m', 'pytest', '-q', *(sys.argv[1:] or ['tests']),
                   *['--ignore=' + p for p in dependents()], '--junitxml=' + str(xml)]
        proof['command'] = command
        with (output / (prefix + '-private.log')).open('w', encoding='utf-8') as log:
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
        proof['exitCode'] = code
        if xml.exists():
            try:
                cases = ET.parse(xml).findall('.//testcase')
                counts = {tag: sum(c.find(tag) is not None for c in cases)
                          for tag in ('failure', 'error', 'skipped')}
                counts['passed'] = len(cases) - sum(counts.values())
                proof['tests'] = counts
            except ET.ParseError:
                proof['testReport'] = 'incomplete'
    finally:
        if container:
            label = subprocess.check_output(['docker', 'inspect', container, '--format',
                        '{{index .Config.Labels "ai.saintvision.configured"}}'], text=True).strip()
            if label != name:
                raise RuntimeError('Container ownership changed; cleanup refused')
            subprocess.run(['docker', 'rm', '-f', container], check=True, stdout=subprocess.DEVNULL)
            proof['isolatedContainerRemoved'] = True
        (output / (prefix + '.json')).write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'exitCode': code, 'tests': proof.get('tests'),
                      'evidence': '.work/' + prefix + '.json'}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
