"""Retained backup boundaries; the actual restore evidence is a separate drill."""
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from rehearse_independent_restore import pinned_snapshot, rehearse, main


@pytest.fixture
def backup(tmp_path):
    archive = b'synthetic-backup-bytes-not-a-postgres-archive'
    pin = hashlib.sha256(archive).hexdigest()
    (tmp_path / 'snapshot.dump').write_bytes(archive)
    (tmp_path / 'manifest.json').write_text(json.dumps({'archiveSha256': pin, 'archiveBytes': len(archive)}))
    return tmp_path, archive, pin


def test_pinned_backup_is_read_without_rewriting(backup):
    directory, archive, pin = backup
    paths = [directory / name for name in ('snapshot.dump', 'manifest.json')]
    before = [(p.stat().st_mtime_ns, p.read_bytes()) for p in paths]
    assert pinned_snapshot(directory, pin)[0] == archive
    assert before == [(p.stat().st_mtime_ns, p.read_bytes()) for p in paths]


@pytest.mark.parametrize('change', ['archive', 'manifest-pin', 'manifest-size', 'hardlink'])
def test_changed_or_aliased_backup_is_rejected_before_docker(backup, change, monkeypatch):
    import rehearse_independent_restore as subject
    directory, archive, pin = backup
    if change == 'archive':
        (directory / 'snapshot.dump').write_bytes(archive + b'changed')
    elif change == 'manifest-pin':
        (directory / 'manifest.json').write_text(json.dumps({'archiveSha256': '0' * 64, 'archiveBytes': len(archive)}))
    elif change == 'manifest-size':
        (directory / 'manifest.json').write_text(json.dumps({'archiveSha256': pin, 'archiveBytes': len(archive) + 1}))
    else:
        os.link(directory / 'snapshot.dump', directory / 'alias.dump')
    def forbidden(*args, **kwargs):
        pytest.fail('Invalid backup reached Docker')
    monkeypatch.setattr(subject, 'docker', forbidden)
    with pytest.raises(ValueError):
        rehearse(directory, pin, 'postgres:16')


@pytest.mark.parametrize('pin', ['', 'A' * 64, '0' * 63, '../archive'])
def test_explicit_canonical_pin_required(backup, pin):
    with pytest.raises(ValueError):
        pinned_snapshot(backup[0], pin)


def test_existing_report_is_preserved_before_any_restore(backup, monkeypatch):
    directory, _, pin = backup
    report = directory / 'report.json'
    report.write_text('existing-evidence')
    monkeypatch.setattr(sys, 'argv', ['rehearse_independent_restore.py', '--backup', str(directory),
                                    '--expected-sha256', pin, '--output', str(report)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2 and report.read_text() == 'existing-evidence'


def test_alias_created_after_initial_stat_is_rejected(backup, monkeypatch):
    from contextlib import contextmanager
    import rehearse_independent_restore as subject
    directory, _, pin = backup
    original = subject.ReadRoot.open

    @contextmanager
    def raced_open(root, path):
        if path.name == 'snapshot.dump':
            os.link(path, directory / 'late-alias.dump')
        with original(root, path) as opened:
            yield opened

    monkeypatch.setattr(subject.ReadRoot, 'open', raced_open)
    with pytest.raises(ValueError, match='pinned root'):
        pinned_snapshot(directory, pin)


def test_opened_file_limit_is_enforced(backup, monkeypatch):
    import rehearse_lan_upgrade as shared
    directory, archive, pin = backup
    monkeypatch.setitem(shared.SNAPSHOT_LIMITS, 'snapshot.dump', len(archive) - 1)
    with pytest.raises(ValueError, match='size limit'):
        pinned_snapshot(directory, pin)


def test_same_size_changed_reread_is_rejected(backup, monkeypatch):
    from contextlib import contextmanager
    import io
    import rehearse_lan_upgrade as shared
    directory, archive, _ = backup

    class ChangingStream(io.BytesIO):
        def seek(self, offset, whence=0):
            self.getbuffer()[0] ^= 1
            return super().seek(offset, whence)

    @contextmanager
    def changed_bytes(root, path):
        yield ChangingStream(archive), len(archive)

    root = shared.ReadRoot(directory)
    monkeypatch.setattr(shared.ReadRoot, 'open', changed_bytes)
    with pytest.raises(ValueError, match='bytes changed'):
        shared.read_backup_file(root, 'snapshot.dump')
