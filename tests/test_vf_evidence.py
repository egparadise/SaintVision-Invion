"""Actual VF runner with synthetic external boundaries; no Docker/DB access."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import run_vf_security_tests as runner

PASS = '<testsuites><testsuite><testcase name="current"/></testsuite></testsuites>'
EMPTY = '<testsuites><testsuite tests="0"/></testsuites>'
FAILED = '<testsuites><testsuite><testcase classname="tests.browser.SafeJourney" name="case[param-private]"><failure>private failure detail</failure></testcase></testsuite></testsuites>'


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'dependents', lambda: [])
    monkeypatch.setenv('VF_EVIDENCE_PREFIX', 'same-prefix')
    monkeypatch.setattr(sys, 'argv', ['runner', 'tests/synthetic.py'])
    state = {'calls': [], 'xml': PASS, 'rc': 0}

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, *args): pass

    def docker(args, **kwargs):
        state['calls'].append(args)
        if args[1] == 'run':
            state['name'] = args[args.index('--name') + 1]
            out = 'owned-container-id'
        elif args[1] == 'inspect' and '--format' not in args:
            out = json.dumps([{'NetworkSettings': {'Ports': {'5432/tcp': [{'HostPort': '1'}]}, 'IPAddress': '127.0.0.1'}}])
        elif args[1] == 'inspect': out = state['name']
        else: out = 'ok'
        return subprocess.CompletedProcess(args, 0, out, '')

    def child(args, **kwargs):
        xml = Path(next(a.split('=', 1)[1] for a in args if a.startswith('--junitxml=')))
        if state['xml'] is not None: xml.write_text(state['xml'])
        if state['rc'] == 124: raise subprocess.TimeoutExpired(args, 1800)
        return subprocess.CompletedProcess(args, state['rc'])

    monkeypatch.setattr(runner.docker_diag, 'run', docker)
    monkeypatch.setattr(runner.psycopg, 'connect', lambda *a, **kw: Connection())
    monkeypatch.setattr(runner.subprocess, 'run', child)

    def invoke():
        code = runner.main()
        proof = json.loads((tmp_path / '.work/same-prefix.json').read_text())
        assert json.loads((tmp_path / proof['evidencePath']).read_text()) == proof
        assert proof['exitCode'] == code
        return code, proof
    return state, invoke, tmp_path


@pytest.mark.parametrize('xml,rc,status,exit_code', [
    (PASS, 0, 'complete', 0),
    (None, 0, 'missing', 2),
    (EMPTY, 0, 'empty', 2),
    ('<broken', 0, 'invalid', 2),
    ('<unrelated/>', 0, 'invalid', 2),
    (PASS.replace('/>', '><skipped/></testcase>'), 0, 'no-executed-tests', 2),
    (PASS.replace('/>', '><failure/></testcase>'), 0, 'inconsistent', 2),
    (PASS.replace('/>', '><error/></testcase>'), 1, 'partial', 1),
    (PASS, 124, 'partial', 124),
    (None, 124, 'missing', 124),
    (EMPTY, 5, 'empty', 5),
])
def test_exit_and_evidence_are_independent(harness, xml, rc, status, exit_code):
    state, invoke, _ = harness
    state.update(xml=xml, rc=rc)
    code, proof = invoke()
    assert code == exit_code
    assert proof['subprocessExitCode'] == rc
    assert proof['evidenceStatus'] == status
    assert proof['isolatedContainerRemoved']


@pytest.mark.parametrize('rc', [0, 1, 124])
def test_prefix_reuse_never_reads_previous_report(harness, rc):
    state, invoke, root = harness
    _, first = invoke()
    (root / '.work/same-prefix-tests.xml').write_text(PASS)
    state.update(xml=None, rc=rc)
    code, second = invoke()
    assert first['runId'] != second['runId']
    assert first['xmlPath'] != second['xmlPath']
    assert (root / first['xmlPath']).is_file()
    assert second['evidenceStatus'] == 'missing' and 'tests' not in second
    assert code == (2 if rc == 0 else rc)


def test_safe_failure_summary_exposes_only_owning_class(harness):
    state, invoke, root = harness
    state.update(xml=FAILED, rc=1)
    code, proof = invoke()
    assert code == 1
    assert proof['failedTestClasses'] == ['tests.browser.SafeJourney']
    assert proof['failedCaseIds'] == ['tests.browser.SafeJourney::case']
    public = (root / '.work/same-prefix.json').read_text()
    assert 'param-private' not in public
    assert 'private failure detail' not in public


@pytest.mark.parametrize('arg', ['--co', '--collect-only'])
def test_collection_rejected_before_docker(harness, monkeypatch, arg):
    state, invoke, _ = harness
    monkeypatch.setattr(sys, 'argv', ['runner', arg])
    code, proof = invoke()
    assert code == 2 and proof['evidenceStatus'] == 'rejected-mode'
    assert proof['subprocessExitCode'] is None
    assert state['calls'] == []


def test_pre_test_infrastructure_failure_keeps_not_run(harness, monkeypatch):
    _, invoke, root = harness
    def unavailable(*args, **kwargs):
        raise runner._HarnessUnavailable('synthetic pre-test timeout')
    monkeypatch.setattr(runner.docker_diag, 'run', unavailable)
    code, proof = invoke()
    assert code == 125 and proof['subprocessExitCode'] is None
    assert proof['evidenceStatus'] == 'not-run' and 'tests' not in proof
    assert not (root / proof['xmlPath']).exists()


@pytest.mark.parametrize('source', ['cli', 'env', 'config', 'execute'])
def test_real_pytest_execution_guard(tmp_path, source):
    # A failing body distinguishes execution from successful collection.
    (tmp_path / 'test_body.py').write_text('def test_body():\n    assert False\n')
    (tmp_path / 'pytest.ini').write_text('[pytest]\n' + ('addopts = --collect-only\n' if source == 'config' else ''))
    env = {**os.environ, 'PYTHONPATH': str(ROOT), 'PYTEST_ADDOPTS': '--co' if source == 'env' else '', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
    command = [sys.executable, '-m', 'pytest', '-p', 'tools.vf_execution_guard', '-q', 'test_body.py']
    if source == 'cli': command.append('--collect-only')
    result = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    if source == 'execute':
        assert result.returncode == 1 and '1 failed' in result.stdout
    else:
        assert result.returncode != 0
        assert 'collect-only is not allowed' in result.stderr
