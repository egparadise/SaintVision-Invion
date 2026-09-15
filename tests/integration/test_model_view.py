"""Historical model observations with real JWT, PostgreSQL and byte commitment."""
from copy import deepcopy
import hashlib

import psycopg
from psycopg.types.json import Jsonb
import pytest
from fastapi.testclient import TestClient

from inv.app import create_app
from inv.approvals import Principal
from inv.contracts import validate_contract
from inv.errors import DomainError
from inv.identity import public_subject
from inv.model_manifest import canonical
from inv.model_view import ModelCommitObservation
from jwt_support import jwt_fixture
from test_model_commit import model, commit, count
from test_storage_commit import sample

pytestmark = pytest.mark.postgres


@pytest.fixture
def storage_subject():
    return public_subject('https://synthetic-idp.invalid/realm', 'requester')


@pytest.fixture
def view(model, tmp_path):
    a = model
    a.receipt = commit(a)
    a.jwt = jwt_fixture(tmp_path, a.e.tenant)
    assert a.jwt.subject('requester') == a.principal.subject_id
    a.url = f'/v1/projects/{a.e.project}/models/{a.body["modelId"]}/versions/{a.body["version"]}/commitment'
    a.headers = {'Authorization': 'Bearer ' + a.jwt.token()}
    with TestClient(create_app(a.e.db, a.jwt.auth), raise_server_exceptions=False) as http:
        a.http = http
        yield a


def get(a):
    return a.http.get(a.url, headers=a.headers)


def test_committed_summary_is_read_only_and_never_revalidates_bytes(view, monkeypatch):
    a = view
    before = a.e.runs.get(a.e.tenant, a.run)
    response = get(a)
    assert response.status_code == 200
    result = response.json()
    validate_contract('ModelCommitObservation', result)
    assert result['manifestHash'] == a.receipt['manifestHash']
    assert result['modelId'] == a.body['modelId'] and result['sourceRunId'] == a.run
    assert result['totalBytes'] == len(b'actual bytes') and result['shardCount'] == 1
    assert result['committed'] and result['requiresExecutionRevalidation']
    assert result['currentAvailability'] == 'unknown'
    assert response.headers['cache-control'] == 'no-store'
    for private in ('keyRef', 'nodeId', 'locationId', 'data.bin', str(a.root)):
        assert private not in response.text
    (a.root / 'data.bin').write_bytes(b'changed bytes')

    def forbidden(*args, **kwargs):
        pytest.fail('Historical GET must not invoke a bytes verifier')

    monkeypatch.setattr(type(a.verifier), 'verify', forbidden)
    assert get(a).json() == result
    assert count(a) == 1 and a.e.runs.get(a.e.tenant, a.run) == before


@pytest.mark.parametrize('change', [
    'UPDATE inv.project_grants SET enabled=false',
    'UPDATE inv.business_projects SET enabled=false',
    'UPDATE inv.business_subjects SET enabled=false',
    "UPDATE public.project_members SET role_code='viewer'",
    "UPDATE public.users SET status='suspended'",
    "UPDATE public.projects SET status='archived'",
])
def test_current_project_permission_revocation_hides_summary(view, change):
    a = view
    with psycopg.connect(a.e.owner) as c:
        c.execute(change + ' WHERE tenant_id=%s', (a.e.tenant,))
    assert get(a).status_code == 403


def test_unlinked_project_is_not_legacy_kernel_grant_fallback(view):
    a = view
    with psycopg.connect(a.e.owner) as c:
        # Simulate a legacy/incomplete restore with a missing business link.
        # Ordinary runtime writes cannot remove this immutable mapping.
        c.execute('ALTER TABLE inv.business_projects DISABLE TRIGGER USER')
        c.execute('DELETE FROM inv.business_projects WHERE project_id=%s', (a.e.project,))
        c.execute('ALTER TABLE inv.business_projects ENABLE TRIGGER USER')
    assert get(a).status_code == 403


def test_same_subject_in_another_tenant_cannot_observe_commitment(view):
    a = view
    with pytest.raises(DomainError) as error:
        ModelCommitObservation(a.e.db).get(
            Principal(a.e.other, a.principal.subject_id), a.e.project,
            a.body['modelId'], a.body['version'],
        )
    assert error.value.status == 403


def test_identity_scope_missing_version_and_write_methods(view):
    a = view
    for headers in ({}, {'Authorization': 'Bearer forged'}):
        assert a.http.get(a.url, headers=headers).status_code == 401
    assert a.http.get(a.url, headers={'Authorization': 'Bearer ' + a.jwt.token('outsider')}).status_code == 403
    assert a.http.get(a.url.replace('/versions/1.0.0/', '/versions/absent/'), headers=a.headers).status_code == 404
    assert a.http.get(a.url.replace(a.e.project, 'prj_' + '0' * 26), headers=a.headers).status_code == 403
    for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        assert a.http.request(method, a.url, headers=a.headers, json={}).status_code == 405
    assert count(a) == 1


@pytest.mark.parametrize('fault', ['hash', 'schema'])
def test_corrupt_stored_manifest_is_rejected_without_reflection(view, fault):
    a = view
    body = deepcopy(a.body)
    body['licensePolicy'] = 'private-corruption-marker'
    if fault == 'schema':
        body['totalBytes'] += 1
    digest = hashlib.sha256(canonical(body)).hexdigest() if fault == 'schema' else '0' * 64
    with psycopg.connect(a.e.owner) as c:
        # Only the disposable owner injects corruption; runtime cannot do this.
        c.execute('ALTER TABLE inv.model_manifests DISABLE TRIGGER USER')
        c.execute('UPDATE inv.model_manifests SET manifest=%s,manifest_sha256=%s WHERE tenant_id=%s',
                  (Jsonb(body), digest, a.e.tenant))
        c.execute('ALTER TABLE inv.model_manifests ENABLE TRIGGER USER')
    response = get(a)
    assert response.status_code == 409
    assert response.json()['code'] == 'MODEL-0001'
    assert 'private-corruption-marker' not in response.text


@pytest.mark.parametrize('version', ['latest', 'head', 'current', 'x' * 65])
def test_mutable_or_unbounded_version_is_refused(view, version):
    response = view.http.get(view.url.replace('/versions/1.0.0/', f'/versions/{version}/'), headers=view.headers)
    assert response.status_code == 422 and version not in response.text
