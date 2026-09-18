"""Offline calls to original fixtures, fake SQL boundary; never connects to DB."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import pytest

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
for rel in ['src', 'services/control-plane/src', 'tests', 'tests/integration']:
    sys.path.insert(0, str(ROOT / rel))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


integration = module('audited_integration_fixture', 'tests/integration/conftest.py')
backend = module('audited_credential_fixture', 'tests/integration/test_credential_backend.py')
base = module('audited_root_fixture', 'tests/conftest.py')
results = []


class SQLConnection:
    def __init__(self, calls, fail_role=False):
        self.calls, self.fail_role = calls, fail_role
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, statement, params=None):
        sql = statement if isinstance(statement, str) else statement.as_string()
        self.calls.append(sql)
        if self.fail_role and sql.startswith('CREATE ROLE'):
            raise RuntimeError('injected CREATE ROLE failure after committed CREATE DATABASE')


# Execute the real integration yield fixture until its first yield.
with pytest.MonkeyPatch.context() as patch:
    calls = []
    patch.setenv('INV_TEST_ADMIN_DSN', 'synthetic-not-used')
    patch.setattr(integration.psycopg, 'connect', lambda *a, **k: SQLConnection(calls, True))
    generator = integration.postgres.__wrapped__()
    try:
        next(generator)
        raise AssertionError('failure injection was not reached')
    except RuntimeError:
        pass
    finally:
        generator.close()
    result = {'case': 'role-setup-failure', 'createdDatabase': any(s.startswith('CREATE DATABASE') for s in calls),
              'dropDatabaseAttempted': any(s.startswith('DROP DATABASE') for s in calls),
              'outcome': 'setup error, not PASS', 'sqlOperations': [s.split()[0:2] for s in calls]}
    assert result['createdDatabase'] and not result['dropDatabaseAttempted']
    results.append(result)

# Invoke the real credential fixture and its real mutate closure (no AST copy).
with pytest.MonkeyPatch.context() as patch, tempfile.TemporaryDirectory() as folder:
    calls = []
    patch.setattr(backend.psycopg, 'connect', lambda *a, **k: SQLConnection(calls))
    patch.setattr(backend, 'planned', lambda e: {'runId': 'synthetic-run'})
    patch.setattr(backend, 'PostgresCredentialRegistry', lambda db: object())
    patch.setattr(backend, 'LinuxFileCredentials', lambda *a: SimpleNamespace())
    env = SimpleNamespace(owner='unused', tenant='tenant', project='project', other='other', epoch='epoch', db=None)
    h = backend.credential_harness.__wrapped__(env, Path(folder), patch)
    for action in ['remove_version', 'rebind_destination', 'disable', 'revoke']:
        calls.clear()
        h.mutate(action)
        results.append({'case': action, 'executedSQL': list(calls)})
    by_case = {r['case']: r for r in results}
    assert by_case['remove_version']['executedSQL'] == ['DELETE FROM inv.credential_grants WHERE credential_id=%s']
    assert by_case['rebind_destination']['executedSQL'] == by_case['disable']['executedSQL']
    assert 'revoked_at' in by_case['revoke']['executedSQL'][0]

# Existing prerequisite semantics: absence never returns a passing dummy DB.
for ci in [False, True]:
    with pytest.MonkeyPatch.context() as patch:
        patch.delenv('INV_TEST_ADMIN_DSN', raising=False)
        patch.delenv('CI', raising=False)
        if ci: patch.setenv('CI', '1')
        for label, fixture in [('root', base.test_admin_dsn), ('integration', integration.postgres)]:
            try:
                value = fixture.__wrapped__()
                if label == 'integration': next(value)
                raise AssertionError('prerequisite unexpectedly returned')
            except (pytest.skip.Exception, pytest.fail.Exception) as exc:
                outcome = 'skip' if isinstance(exc, pytest.skip.Exception) else 'fail'
                assert outcome == ('fail' if ci else 'skip')
                results.append({'case': label + '-missing-dsn', 'CI': ci, 'outcome': outcome})

# Actual context-manager cleanup: a disposal error prevents role cleanup.
import db_login
from contextlib import contextmanager
calls = []
class Owner:
    @contextmanager
    def begin(self):
        yield SimpleNamespace(connection=SimpleNamespace(driver_connection=SQLConnection(calls)))
class Engine:
    def dispose(self):
        raise RuntimeError('injected dispose failure')
with pytest.MonkeyPatch.context() as patch:
    patch.setattr(db_login, 'create_engine', lambda *a, **k: Engine())
    try:
        with db_login.application_test_engine('postgresql+psycopg://fixture@localhost/unused', Owner()):
            raise AssertionError('original body failure')
    except RuntimeError as exc:
        context_preserved = isinstance(exc.__context__, AssertionError)
    assert context_preserved
    assert not any(s.startswith('DROP ROLE') for s in calls)
    results.append({'case': 'dispose-failure', 'dropRoleAttempted': False,
                    'originalAssertionInExceptionContext': context_preserved,
                    'outcome': 'RuntimeError, not PASS',
                    'scope': 'synthetic disposal fault, not a real driver failure'})

# Mutation errors occur outside the denial assertion and must propagate.
from credential_conformance import CredentialConformance
from test_credential_conformance import ModelHarness
from saintvision.credentials.contract import CredentialDenied
h = ModelHarness()
def broken_mutation(action):
    raise CredentialDenied()
h.mutate = broken_mutation
try:
    CredentialConformance().test_authority_rechecked_at_use(h, 'revoke')
    raise AssertionError('fixture exception was swallowed')
except CredentialDenied:
    results.append({'case': 'mutation-error-before-raises', 'outcome': 'propagates; not accepted as denial'})

OUT.write_text(json.dumps({'scope': 'original fixtures with synthetic external DB/provider boundaries, no live PostgreSQL/Docker', 'results': results}, indent=2) + '\n')
print(json.dumps(results, indent=2))

