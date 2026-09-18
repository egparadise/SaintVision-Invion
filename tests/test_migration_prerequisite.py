"""Missing test infrastructure must not masquerade as migration corruption."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASE = 'tests/test_account_integration.py::test_published_migration_heads_upgrade_without_rewriting'


def run(arguments, *, dsn=None, ci=False):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('INV_', 'CX01_', 'VF_')) and k != 'CI'}
    if dsn is not None:
        env['INV_TEST_ADMIN_DSN'] = dsn
    if ci:
        env['CI'] = 'true'
    return subprocess.run([sys.executable, *arguments], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize('dsn', [None, ''])
def test_cli_missing_admin_is_not_a_migration_failure(dsn):
    result = run(['tools/check_migration_upgrade.py'], dsn=dsn)
    assert result.returncode == 2
    assert 'not run: INV_TEST_ADMIN_DSN is absent' in result.stderr
    assert 'validation failed' not in result.stderr
    assert 'Traceback' not in result.stderr


def test_present_invalid_dsn_still_fails_without_echoing_credentials():
    secret = 'synthetic-secret-must-not-appear'
    result = run(['tools/check_migration_upgrade.py'], dsn='invalid-' + secret)
    assert result.returncode == 1
    assert 'credential-bearing diagnostics suppressed' in result.stderr
    assert secret not in result.stdout + result.stderr


@pytest.mark.parametrize('ci', [False, True])
def test_account_migration_uses_shared_local_skip_and_ci_failure(ci):
    result = run(['-m', 'pytest', '-q', '-rs', CASE], ci=ci)
    output = result.stdout + result.stderr
    assert 'Disposable migration paths failed' not in output
    if ci:
        assert result.returncode == 1
        assert 'CI requires INV_TEST_ADMIN_DSN' in output
    else:
        assert result.returncode == 0
        assert '1 skipped' in output
        assert 'PostgreSQL tests not run' in output
