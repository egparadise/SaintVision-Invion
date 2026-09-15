"""VF-CX-01 regression at the configured deployment boundary."""
import base64
import hashlib
import json
from pathlib import Path

import pytest
from jwt_support import jwt_fixture
from test_configured_server import running_server
from test_server_container import business_login

pytestmark = pytest.mark.postgres


def test_configured_factory_cannot_mint_fixture_administrator(env, tmp_path):
    identity = jwt_fixture(tmp_path, env.tenant)
    verifier = 'attacker-chosen-verifier-' * 3
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    with running_server(env, tmp_path, identity) as client:
        response = client.post('/v1/auth/token', json={
            'grant_type': 'authorization_code', 'code': 'attacker-chosen-code',
            'code_verifier': verifier, 'code_challenge': challenge,
            'code_challenge_method': 'S256', 'client_id': 'saintvision-web', 'idp': 'internal-keycloak',
        })
        assert response.status_code == 404
        for path in ('/v1/projects', '/v1/nodes', '/v1/runs'):
            response = client.get(path, headers={'Authorization': 'Bearer attacker-admin'})
            assert response.status_code in (401, 404)
            assert 'cluster:admin' not in response.text
        assert client.get('/v1/auth/userinfo', headers={'Authorization': 'Bearer attacker-admin'}).status_code == 404


def test_factory_route_measurement_is_not_fixture_union(env, tmp_path, monkeypatch, business_login):
    import sys
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / 'tools'))
    from route_coverage import configured_routes, scan_client
    identity = jwt_fixture(tmp_path, env.tenant)
    config = tmp_path / 'api.json'
    config.write_text(json.dumps({'identity': {
        'tenant_id': env.tenant, 'issuer': identity.issuer, 'audience': identity.audience,
        'client_ids': ['synthetic-web'], 'jwks_file': str(identity.path),
    }}), encoding='utf-8')
    config.chmod(0o600)
    monkeypatch.setenv('INV_API_CONFIG', str(config))
    monkeypatch.setenv('INV_RUNTIME_DSN', env.runtime)
    monkeypatch.setenv('INV_RECOVERY_EPOCH', env.epoch)
    served = configured_routes()
    assert '/v1/projects' in served
    assert '/v1/auth/token' not in served
    assert '/v1/session' in served
    assert '/v1/storage/resolve' not in served
    wanted = scan_client(root / 'apps/web/src')
    (root / '.work/vf-route-gap.json').write_text(json.dumps({
        'measurement': 'configured-factory, synthetic issuer, isolated PostgreSQL, workspace/business disabled',
        'served': sorted(served), 'clientPaths': sorted(wanted), 'unserved': sorted(wanted-served),
        'payloadCompatibilityAssessed': False, 'operationalAcceptance': False,
    }, indent=2)+'\n', encoding='utf-8')

    from psycopg.conninfo import conninfo_to_dict
    from sqlalchemy.engine import URL
    info = conninfo_to_dict(env.runtime)
    role, password = business_login
    business_dsn = URL.create('postgresql+psycopg', username=role, password=password,
                             host=info['host'], port=int(info['port']), database=info['dbname'])
    monkeypatch.setenv('INV_BUSINESS_DSN', business_dsn.render_as_string(hide_password=False))
    body = json.loads(config.read_text(encoding='utf-8'))
    body['business'] = True
    config.write_text(json.dumps(body), encoding='utf-8')
    from inv.app import create_configured_app
    from inv.business_surface import BusinessDispatch
    from route_coverage import registered_routes
    from fastapi.testclient import TestClient
    api = create_configured_app()
    try:
        composed = registered_routes(api)
        assert '/v1/projects/{}/workspaces' in composed
        assert '/v1/workspaces/{}/execution-readiness' in composed
        assert '/v1/storage/resolve' in composed
        assert '/v1/storage/contributions' in composed
        assert '/v1/storage/locations' in composed
        assert '/v1/auth/token' not in composed
        with TestClient(api) as client:
            assert client.get('/v1/projects/'+env.project+'/workspaces', headers={'Authorization': 'Bearer attacker-admin'}).status_code == 401
        (root / '.work/vf-composed-route-gap.json').write_text(json.dumps({
            'measurement': 'configured-factory; business enabled with separate non-owner role; workspace runtime disabled',
            'served': sorted(composed), 'clientPaths': sorted(wanted), 'unserved': sorted(wanted-composed),
            'payloadCompatibilityAssessed': False, 'operationalAcceptance': False,
        }, indent=2)+'\n', encoding='utf-8')
    finally:
        for item in api.user_middleware:
            if item.cls is BusinessDispatch:
                item.kwargs['business'].state.engine.dispose()
