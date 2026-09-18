"""Caller-transaction registry authorization prerequisite; real PostgreSQL."""
import psycopg
import pytest
from inv.errors import DomainError
from inv.model_registry_binding import ModelRegistryBindingStore, RegistryBindingPolicy
from test_model_registry_binding import registered, bind, model, sample, storage_subject

pytestmark = pytest.mark.postgres


def recheck(a, c):
    return a.bindings.revalidate(c, a.principal, a.e.project, a.registry_version,
        a.body['modelId'], a.body['version'], manifest_hash=a.committed['manifestHash'])


def test_revalidation_does_not_create_missing_binding(registered):
    a = registered
    with a.e.db.transaction(a.e.tenant) as c:
        with pytest.raises(DomainError, match='Current registry binding required'):
            recheck(a, c)
        assert c.execute('SELECT count(*) AS n FROM inv.model_registry_bindings').fetchone()['n'] == 0


def test_revalidation_retains_lifecycle_lock_until_caller_commit(registered):
    a = registered
    expected = bind(a)
    with a.e.db.transaction(a.e.tenant) as c:
        assert recheck(a, c) == expected
        with pytest.raises(psycopg.errors.LockNotAvailable):
            with psycopg.connect(a.e.owner) as other:
                other.execute("SET LOCAL lock_timeout='100ms'")
                other.execute("UPDATE public.model_versions SET stage='retired' WHERE model_version_id=%s",
                              (a.registry_version,))
    with psycopg.connect(a.e.owner) as other:
        other.execute("SET LOCAL lock_timeout='1s'")
        other.execute("UPDATE public.model_versions SET stage='retired' WHERE model_version_id=%s",
                      (a.registry_version,))
    with a.e.db.transaction(a.e.tenant) as c:
        with pytest.raises(DomainError):
            recheck(a, c)


@pytest.mark.parametrize('change', ['permission', 'policy', 'pin', 'content', 'identity'])
def test_revalidation_refuses_stale_authority_or_identity(registered, change):
    a = registered
    bind(a)
    if change == 'policy':
        a.bindings = ModelRegistryBindingStore(a.e.db, RegistryBindingPolicy('new', a.binding_policy.allowed))
    elif change == 'identity':
        a.committed['manifestHash'] = '0' * 64
    else:
        with psycopg.connect(a.e.owner) as c:
            if change == 'permission':
                c.execute('UPDATE inv.project_grants SET can_request=false WHERE project_id=%s', (a.e.project,))
            else:
                assignment = ("retention_pinned_until=clock_timestamp()-interval '1 second'"
                              if change == 'pin' else "content_sha256=repeat('0',64)")
                c.execute('UPDATE public.model_versions SET '+assignment+' WHERE model_version_id=%s',
                          (a.registry_version,))
    # Per-cause codes confirmed against real PostgreSQL: a revoked grant is refused as
    # AUTH-0030, a changed binding policy as MODEL-0008, and pin/content/identity drift as
    # MODEL-0001. Pinning each stops a case being refused for another case's reason.
    expected = {'permission': 'AUTH-0030', 'policy': 'MODEL-0008',
                'pin': 'MODEL-0001', 'content': 'MODEL-0001', 'identity': 'MODEL-0001'}
    with a.e.db.transaction(a.e.tenant) as c:
        with pytest.raises(DomainError, match=expected[change]):
            recheck(a, c)
