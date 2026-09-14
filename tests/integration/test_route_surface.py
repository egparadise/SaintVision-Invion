"""Configured-factory measurement with real PostgreSQL and synthetic trust."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from jwt_support import jwt_fixture

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def test_configured_cli_counts_only_registered_routes(env, tmp_path):
    identity = jwt_fixture(tmp_path, env.tenant)
    config = tmp_path / 'api.json'
    config.write_text(json.dumps({'identity': {
        'tenant_id': env.tenant, 'issuer': identity.issuer,
        'audience': identity.audience, 'client_ids': ['synthetic-web'],
        'jwks_file': str(identity.path),
    }}))
    config.chmod(0o600)
    client = tmp_path / 'client'
    client.mkdir()
    (client / 'calls.ts').write_text('''
        api('/v1/projects/${project}/approvals');
        api('/v1/projects/${project}/runs/${run}/shards');
        api('/v1/fixture-only');
    ''')
    # A dormant fixture in the same input tree must not enter the served set.
    (client / 'demo.py').write_text('@app.get("/v1/fixture-only")\ndef demo(): pass\n')
    result = subprocess.run(
        [sys.executable, 'tools/route_coverage.py', '--configured-surface', '--client', str(client), '--json'],
        cwd=ROOT, env={**os.environ, 'INV_API_CONFIG': str(config),
                      'INV_RUNTIME_DSN': env.runtime, 'INV_RECOVERY_EPOCH': env.epoch,
                      'PYTHONPATH': os.pathsep.join(str(ROOT / p) for p in ('src', 'services/control-plane/src'))},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 1, 'Configured measurement failed; diagnostics suppressed'
    output = json.loads(result.stdout)
    assert output['measurement'] == 'configured-factory'
    assert output['operationalAcceptanceAssessed'] is False
    assert '/v1/fixture-only' in output['unserved']
    served = output['servedByTree']['configured-factory']
    assert '/v1/fixture-only' not in served
    assert '/v1/projects/{}/approvals' in served
    assert '/v1/projects/{}/runs/{}/shards' in served
    assert '/v1/workspaces/{}/terminals/{}' in served
