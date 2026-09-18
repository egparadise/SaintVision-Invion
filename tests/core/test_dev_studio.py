"""Boundaries that protect the operator's files and durable development intent."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from dev_studio import Studio, snapshot, relative, sha, encode


@pytest.fixture
def studio(tmp_path):
    return Studio.init(tmp_path / 'studio')


def test_login_is_single_use_and_kind_bound(studio):
    token = studio.token()
    assert not studio.authenticate(token)
    assert studio.authenticate(token, 'login', consume=True)
    assert not studio.authenticate(token, 'login', consume=True)
    session = studio.token('session')
    assert studio.authenticate(session)
    assert not studio.authenticate(session, 'login')
    with studio.db() as conn:
        conn.execute('UPDATE tokens SET expires=0')
    assert not studio.authenticate(session)


@pytest.mark.parametrize('path', ['../key', '/root/key', 'C:/key', 'src\\key', 'src/../key', './src', 'src//x'])
def test_paths_cannot_leave_workspace(path):
    with pytest.raises(ValueError):
        relative(path)


def test_snapshot_only_explicit_sources_and_no_credentials(tmp_path):
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src/app.py').write_text('print(42)')
    (tmp_path / 'src/.env').write_text('PRIVATE=value')
    (tmp_path / 'src/credentials.json').write_text('PRIVATE')
    (tmp_path / 'private.txt').write_text('PRIVATE')
    captured = snapshot(tmp_path, ['src'])
    assert [f['path'] for f in captured] == ['src/app.py']
    assert captured[0]['sha256'] == sha(b'print(42)')
    (tmp_path / 'src/app.py').write_text('-----BEGIN PRIVATE KEY-----')
    with pytest.raises(ValueError, match='Private key'):
        snapshot(tmp_path, ['src'])


def test_oversized_source_rejected(tmp_path):
    (tmp_path / 'app.py').write_bytes(b'x' * (512 * 1024 + 1))
    with pytest.raises(ValueError, match='512 KiB'):
        snapshot(tmp_path, ['app.py'])


def test_budget_fails_closed_during_unresolved_recovery(studio):
    assert studio.budget({'cpuMillis': 250, 'memoryMiB': 128, 'timeoutSeconds': 5})['cpuMillis'] == 250
    for value in [True, 10000, -1]:
        with pytest.raises(ValueError):
            studio.budget({'cpuMillis': value, 'memoryMiB': 128, 'timeoutSeconds': 5})
    with studio.db() as conn:
        conn.execute("INSERT INTO projects VALUES('p','p','path','existing','{}','[]')")
        conn.execute("INSERT INTO jobs VALUES('j','p','w','t','recovery_required',0,NULL,'{}','abcdefgh','hash')")
    with pytest.raises(ValueError, match='recovery'):
        studio.budget({'cpuMillis': 500, 'memoryMiB': 256, 'timeoutSeconds': 60})


def test_restart_recovery_preserves_input_and_does_not_replay(studio, monkeypatch):
    with studio.db() as conn:
        conn.execute("INSERT INTO projects VALUES('p','p','path','existing','{}','[]')")
        conn.execute("INSERT INTO jobs VALUES('j','p','w','t','running',0,NULL,?,'abcdefgh','hash')", (json.dumps({'container': 'owned'}),))
    stopped = []
    monkeypatch.setattr(studio, 'stop_owned', stopped.append)
    assert studio.recover() == [{'id': 'j', 'status': 'interrupted'}]
    assert stopped == ['owned']
    assert studio.recover() == []
    assert studio.job('j')['record']['stopped']


def test_recovery_failure_keeps_slot_reserved(studio, monkeypatch):
    with studio.db() as conn:
        conn.execute("INSERT INTO projects VALUES('p','p','path','existing','{}','[]')")
        conn.execute("INSERT INTO jobs VALUES('j','p','w','t','running',0,NULL,?,'abcdefgh','hash')", (json.dumps({'container': 'foreign'}),))
    def deny(_):
        raise ValueError('Different owner')
    monkeypatch.setattr(studio, 'stop_owned', deny)
    assert studio.recover()[0]['status'] == 'recovery_required'
    assert not studio.job('j')['record']['stopped']


def test_submission_idempotency_rejects_changed_content(studio):
    with studio.db() as conn:
        conn.execute("INSERT INTO projects VALUES('p','p','path','existing','{}','[]')")
        conn.execute("INSERT INTO jobs VALUES('j','p','w','test','succeeded',0,1,'{}','abcdefgh',?)", (sha(encode(['p', 'w', 'test'])),))
    assert studio.submit('p', 'w', 'test', 'abcdefgh') == 'j'
    with pytest.raises(ValueError, match='different intent'):
        studio.submit('p', 'w', 'train', 'abcdefgh')


def test_shared_context_binds_actual_workspace_without_initializing_git(studio, tmp_path):
    path = tmp_path / "plain project"
    path.mkdir()
    project = studio.register('plain', path, tasks={'test': {'argv': ['python', 'test.py']}})
    assert studio.configure_tools() == {'configuredWorkspaces': 1}
    text = (path / '.saintvision/README.md').read_text('utf-8')
    workspace = studio.status()['projects'][0]['workspaces'][0]['id']
    assert "--project '" + project + "'" in text
    assert "--workspace '" + workspace + "'" in text
    assert not (path / '.git').exists()
    assert studio.configure_tools() == {'configuredWorkspaces': 1}


def test_shared_context_does_not_overwrite_user_file(studio, tmp_path):
    path = tmp_path / 'project'
    (path / '.saintvision').mkdir(parents=True)
    target = path / '.saintvision/README.md'
    target.write_text('My existing context', encoding='utf-8')
    studio.register('existing', path)
    with pytest.raises(ValueError, match='unmanaged'):
        studio.configure_tools()
    assert target.read_text() == 'My existing context'
