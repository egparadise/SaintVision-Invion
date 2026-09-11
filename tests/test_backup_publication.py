"""Actual private Linux files: publication, interruption and replacement."""

import concurrent.futures
import importlib.util
import os
from pathlib import Path
import stat
import sys

import pytest

SPEC = importlib.util.spec_from_file_location(
    "backup_drill", Path(__file__).resolve().parents[1] / "tools/recovery_drill.py"
)
drill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drill)
pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux publication contract")


def test_private_publication_reads_back_and_rechecks_bytes(tmp_path):
    path = tmp_path / "backup.dump"
    value, report = drill._save_backup(path, b"synthetic dump")
    report.update(backupBytes=len(value), backupSha256=report["savedBackupSha256"])
    assert value == path.read_bytes() == b"synthetic dump"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert path.stat().st_nlink == 1
    assert report["localBackupSynced"] and not report["offSiteVerified"]
    drill._recheck_saved_backup(report)
    assert report["savedBackupIntact"]
    path.write_bytes(b"changed")
    drill._recheck_saved_backup(report)
    assert not report["savedBackupIntact"]


@pytest.mark.parametrize("existing", ["file", "symlink", "directory"])
def test_existing_destination_is_preserved(tmp_path, existing):
    path = tmp_path / "backup.dump"
    target = tmp_path / "original"
    target.write_bytes(b"do not overwrite")
    if existing == "file":
        path.write_bytes(b"prior dump")
    elif existing == "symlink":
        path.symlink_to(target)
    else:
        path.mkdir()
    with pytest.raises(FileExistsError):
        drill._save_backup(path, b"new")
    assert target.read_bytes() == b"do not overwrite"
    if existing == "file":
        assert path.read_bytes() == b"prior dump"
    if existing == "symlink":
        assert path.is_symlink()
    if existing == "directory":
        assert path.is_dir()
    assert not list(tmp_path.glob(".inv-backup-*"))


@pytest.mark.parametrize("fault", ["file", "directory"])
def test_sync_failure_never_returns_verified_receipt(tmp_path, monkeypatch, fault):
    original = os.fsync

    def fail(fd):
        directory = stat.S_ISDIR(os.fstat(fd).st_mode)
        if directory == (fault == "directory"):
            raise OSError("injected sync failure")
        return original(fd)

    monkeypatch.setattr(drill.os, "fsync", fail)
    path = tmp_path / "backup.dump"
    with pytest.raises(OSError):
        drill._save_backup(path, b"synthetic")
    assert path.exists() == (fault == "directory")
    assert not list(tmp_path.glob(".inv-backup-*"))
    if path.exists():
        assert path.read_bytes() == b"synthetic"


def test_concurrent_publications_have_one_winner(tmp_path):
    path = tmp_path / "backup.dump"

    def attempt(value):
        try:
            return drill._save_backup(path, value)[0]
        except FileExistsError:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [b"first", b"second"]))
    assert results.count(None) == 1
    assert path.read_bytes() == next(r for r in results if r is not None)
    assert not list(tmp_path.glob(".inv-backup-*"))


@pytest.mark.parametrize(
    "replacement", ["same-bytes", "symlink", "hardlink", "public-mode", "missing"]
)
def test_changed_identity_or_boundary_invalidates_receipt(tmp_path, replacement):
    path = tmp_path / "backup.dump"
    value, report = drill._save_backup(path, b"synthetic")
    report.update(backupBytes=len(value), backupSha256=report["savedBackupSha256"])
    other = tmp_path / "other"
    other.write_bytes(value)
    other.chmod(0o600)
    if replacement == "same-bytes":
        os.replace(other, path)
    elif replacement == "symlink":
        path.unlink()
        path.symlink_to(other)
    elif replacement == "hardlink":
        os.link(path, other.with_name("extra-link"))
    elif replacement == "public-mode":
        path.chmod(0o644)
    else:
        path.unlink()
    drill._recheck_saved_backup(report)
    assert report["savedBackupIntact"] is False


def test_symlink_parent_and_shared_directory_are_refused(tmp_path):
    real = tmp_path / "private"
    real.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(OSError):
        drill._save_backup(link / "dump", b"synthetic")
    real.chmod(0o755)
    with pytest.raises(ValueError):
        drill._save_backup(real / "dump", b"synthetic")
    assert not list(real.iterdir())
