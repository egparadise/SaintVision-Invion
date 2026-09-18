"""Real PG binding identity, current authorization, immutability and row locks."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import hashlib
import json
from pathlib import Path

import psycopg
import pytest
from inv.approvals import Principal
from inv.errors import DomainError
from inv.model_registry_binding import ModelRegistryBindingStore, RegistryBindingPolicy
from saintvision.ids import new_id
from test_model_commit import model, commit
from test_storage_commit import sample, storage_subject

pytestmark = pytest.mark.postgres


@pytest.fixture
def registered(model):
    a = model
    a.committed = commit(a)
    a.registry_model, a.registry_version = new_id('model'), new_id('model_version')
    with psycopg.connect(a.e.owner) as c:
        c.execute("INSERT INTO public.models(tenant_id,project_id,model_id,name) VALUES(%s,%s,%s,%s)",
                  (a.e.tenant, a.e.project, a.registry_model, uuid4().hex))
        c.execute('''INSERT INTO public.model_versions(tenant_id,model_id,model_version_id,version,
            stage,content_sha256,byte_size,uri,verified_at,retention_pinned_until)
            VALUES(%s,%s,%s,'registry-distinct-version','released',%s,%s,'inv://synthetic',
            clock_timestamp()-interval '1 second',clock_timestamp()+interval '1 hour')''',
            (a.e.tenant, a.registry_model, a.registry_version, a.body['contentHash'], a.body['totalBytes']))
    a.binding_policy = RegistryBindingPolicy('synthetic-policy:1', frozenset({
        (a.body['licensePolicy'], a.body['classification'])}))
    a.bindings = ModelRegistryBindingStore(a.e.db, a.binding_policy)
    return a


def bind(a, **kwargs):
    return a.bindings.bind(kwargs.pop('principal', a.principal), a.e.project,
        kwargs.pop('registry_version_id', a.registry_version), a.body['modelId'],
        a.body['version'], manifest_hash=kwargs.pop('manifest_hash', a.committed['manifestHash']), **kwargs)


def test_explicit_distinct_registry_identity_is_durable_and_not_a_permit(registered):
    a = registered
    result = bind(a)
    assert result == bind(a)
    assert result['registryModelId'] != result['modelId']
    assert result['registryVersionId'] == a.registry_version
    assert result['manifestHash'] == a.committed['manifestHash']
    assert not result['executionAuthorized'] and result['requiresExecutionRevalidation']
    with a.e.db.transaction(a.e.tenant) as c:
        assert c.execute('SELECT count(*) AS n FROM inv.model_registry_bindings').fetchone()['n'] == 1


@pytest.mark.parametrize('assignment', [
    "stage='retired'", "stage='draft'", "content_sha256=repeat('0',64)",
    'byte_size=1', "verified_at=clock_timestamp()+interval '1 hour'",
    "retention_pinned_until=clock_timestamp()-interval '1 second'",
])
def test_registry_mismatch_or_invalid_lifecycle_is_refused(registered, assignment):
    a = registered
    with psycopg.connect(a.e.owner) as c:
        c.execute('UPDATE public.model_versions SET '+assignment+' WHERE model_version_id=%s', (a.registry_version,))
    with pytest.raises(DomainError):
        bind(a)


def test_replay_checks_revoked_project_permission(registered):
    a = registered
    bind(a)
    with psycopg.connect(a.e.owner) as c:
        c.execute('UPDATE inv.project_grants SET can_request=false WHERE project_id=%s', (a.e.project,))
    with pytest.raises(DomainError):
        bind(a)


def test_no_hash_or_version_name_fallback(registered):
    a = registered
    for kwargs in [dict(registry_version_id=new_id('model_version')), dict(manifest_hash='0'*64),
                   dict(principal=Principal(a.e.other, a.principal.subject_id))]:
        with pytest.raises(DomainError):
            bind(a, **kwargs)


def test_changed_policy_cannot_rewrite_binding(registered):
    a = registered
    bind(a)
    a.bindings = ModelRegistryBindingStore(a.e.db, RegistryBindingPolicy('new', a.binding_policy.allowed))
    with pytest.raises(DomainError, match='bound differently'):
        bind(a)


def test_disallowed_manifest_policy_cannot_bind(registered):
    a = registered
    a.bindings = ModelRegistryBindingStore(a.e.db, RegistryBindingPolicy('deny', frozenset({('other','other')})))
    with pytest.raises(DomainError):
        bind(a)


def test_concurrent_duplicate_has_one_immutable_result(registered):
    a = registered
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: bind(a), range(2)))
    assert results[0] == results[1]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with a.e.db.transaction(a.e.tenant) as c:
            c.execute('DELETE FROM inv.model_registry_bindings')
    with a.e.db.transaction(a.e.other) as c:
        assert c.execute('SELECT count(*) AS n FROM inv.model_registry_bindings').fetchone()['n'] == 0


def test_snapshot_locks_registry_until_transaction_end(registered):
    a = registered
    with a.e.db.transaction(a.e.tenant) as c:
        c.execute('SELECT * FROM public.model_registry_snapshot(%s,%s,%s)',
                  (a.e.tenant, a.e.project, a.registry_version)).fetchone()
        with pytest.raises(psycopg.errors.LockNotAvailable):
            with psycopg.connect(a.e.owner) as other:
                other.execute("SET LOCAL lock_timeout='100ms'")
                other.execute("UPDATE public.model_versions SET stage='retired' WHERE model_version_id=%s",
                              (a.registry_version,))


def test_definer_scope_and_privileges(registered):
    a = registered
    with a.e.db.transaction(a.e.other) as c:
        assert c.execute('SELECT * FROM public.model_registry_snapshot(%s,%s,%s)',
                         (a.e.tenant, a.e.project, a.registry_version)).fetchone() is None
    with a.e.db.transaction(a.e.tenant) as c:
        assert c.execute('SELECT * FROM public.model_registry_snapshot(%s,%s,%s)',
                         (a.e.tenant, 'other-project', a.registry_version)).fetchone() is None
    with psycopg.connect(a.e.owner) as c:
        signature = 'public.model_registry_snapshot(uuid,text,text)'
        assert c.execute("SELECT has_function_privilege('inv_app',%s,'EXECUTE')", (signature,)).fetchone() == (False,)
        definition = c.execute('SELECT pg_get_functiondef(%s::regprocedure)', (signature,)).fetchone()[0]
        digest = hashlib.sha256(definition.encode()).hexdigest()
        policy = json.loads((Path(__file__).parents[2]/'tools/definer-policy.json').read_text())
        expected = policy['functions']['public.model_registry_snapshot(uuid, text, text)']['definitionSHA256']
        assert digest == expected


def test_retirement_invalidates_a_previously_successful_binding(registered):
    a = registered
    bind(a)
    with psycopg.connect(a.e.owner) as c:
        c.execute("UPDATE public.model_versions SET stage='retired' WHERE model_version_id=%s", (a.registry_version,))
    with pytest.raises(DomainError):
        bind(a)


def test_same_content_cannot_rebind_to_a_different_kernel_version(registered):
    a = registered
    bind(a)
    from copy import deepcopy
    body = deepcopy(a.body)
    body['version'] = 'different-version'
    second = commit(a, key=uuid4().hex, body=body)
    with pytest.raises(DomainError, match='bound differently'):
        a.bindings.bind(a.principal, a.e.project, a.registry_version,
                       body['modelId'], body['version'], manifest_hash=second['manifestHash'])
