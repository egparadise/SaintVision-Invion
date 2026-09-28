"""S11-ST CAP-02/BAK-02 exact failure and crash-resume boundaries.

PG-free except for the Linux-only real LocalObjects fsync seams.  The public
object failure is the existing ProblemDetails code; retention uses a closed
operator receipt and never invents a public error code.
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pitr_archive_retention as retention  # noqa: E402
from inv.errors import DomainError  # noqa: E402
from inv.object_store import (  # noqa: E402
    LocalObjectStore,
    LocalObjects,
    ObjectHandle,
    object_store_session,
)

NOW = datetime(2026, 9, 28, 8, 0, tzinfo=timezone.utc)
CAP_02 = {"code": "STORE-0001", "status": 503, "retryable": True}
BAK_02 = {"failureClass": "RETENTION_APPLY_PARTIAL", "exit": 4}


class FaultFiles:
    def __init__(self, operation: str, error: OSError):
        self.operation = operation
        self.error = error

    def _call(self, operation: str, value=None):
        if operation == self.operation:
            raise self.error
        return value

    def exists(self, _locator):
        return self._call("exists", False)

    def hash(self, _locator):
        return self._call("hash")

    def read(self, _locator, _digest, _size):
        return self._call("get", b"x")

    def put(self, _locator, _body, _digest):
        return self._call("put")

    def remove(self, _locator):
        return self._call("delete")


class FakeLocal:
    def __init__(self, files):
        self.files = files

    @contextlib.contextmanager
    def locked(self):
        yield self.files


def _assert_store_unavailable(error: DomainError) -> None:
    assert {"code": error.code, "status": error.status, "retryable": error.retryable} == CAP_02
    assert error.detail == "Object provider unavailable"


@pytest.mark.parametrize("error_number", [errno.ENOSPC, errno.EDQUOT])
def test_cap02_local_capacity_errors_have_the_exact_existing_public_surface(error_number):
    provider = LocalObjectStore(
        FakeLocal(FaultFiles("put", OSError(error_number, "private host detail")))
    )
    with pytest.raises(DomainError) as raised:
        provider.put("obj-" + "a" * 32, b"x", hashlib.sha256(b"x").hexdigest())
    _assert_store_unavailable(raised.value)
    assert "private host detail" not in str(raised.value)


@pytest.mark.parametrize("operation", ["put", "get", "exists", "hash", "delete"])
def test_every_local_provider_operation_translates_oserror(operation):
    provider = LocalObjectStore(FakeLocal(FaultFiles(operation, OSError(errno.EIO, "device path"))))
    locator = "obj-" + "b" * 32
    digest = hashlib.sha256(b"x").hexdigest()
    calls = {
        "put": lambda: provider.put(locator, b"x", digest),
        "get": lambda: provider.get(locator, digest, 1),
        "exists": lambda: provider.exists(locator),
        "hash": lambda: provider.hash(locator),
        "delete": lambda: provider.delete(locator),
    }
    with pytest.raises(DomainError) as raised:
        calls[operation]()
    _assert_store_unavailable(raised.value)


def test_a_missing_local_object_remains_not_found_not_provider_unavailable():
    provider = LocalObjectStore(FakeLocal(FaultFiles("get", FileNotFoundError())))
    with pytest.raises(FileNotFoundError):
        provider.get("obj-" + "c" * 32, "0" * 64, 1)


@pytest.mark.parametrize("operation", ["put", "get", "exists", "hash", "delete"])
def test_cap02_legacy_session_provider_calls_translate_oserror(operation):
    provider = LocalObjectStore(
        FakeLocal(FaultFiles(operation, OSError(errno.EIO, "private session path")))
    )
    locator = "obj-" + "f" * 32
    digest = hashlib.sha256(b"x").hexdigest()
    with object_store_session(provider) as files:
        calls = {
            "put": lambda: files.put(locator, b"x", digest),
            "get": lambda: files.get(locator, digest, 1),
            "exists": lambda: files.exists(locator),
            "hash": lambda: files.hash(locator),
            "delete": lambda: files.delete(locator),
        }
        with pytest.raises(DomainError) as raised:
            calls[operation]()
    _assert_store_unavailable(raised.value)


@pytest.mark.parametrize("operation", ["put", "delete"])
def test_cap02_legacy_session_mutations_translate_filenotfound(operation):
    provider = LocalObjectStore(FakeLocal(FaultFiles(operation, FileNotFoundError())))
    locator = "obj-" + "1" * 32
    digest = hashlib.sha256(b"x").hexdigest()
    with object_store_session(provider) as files:
        with pytest.raises(DomainError) as raised:
            if operation == "put":
                files.put(locator, b"x", digest)
            else:
                files.delete(locator)
    _assert_store_unavailable(raised.value)


@pytest.mark.skipif(sys.platform != "linux", reason="real LocalObjects flock requires Linux")
def test_cap02_real_locked_scope_does_not_relabel_unrelated_consumer_oserror(tmp_path):
    root = tmp_path / "objects"
    root.mkdir(mode=0o700)
    provider = LocalObjects(root)
    with pytest.raises(OSError, match="workspace disk") as raised:
        with provider.locked():
            raise OSError(errno.EIO, "workspace disk")
    assert not isinstance(raised.value, DomainError)


@pytest.mark.skipif(sys.platform != "linux", reason="real LocalObjects flock requires Linux")
@pytest.mark.parametrize(
    "operation,handle_method", [("put", "put"), ("get", "read"), ("delete", "remove")]
)
def test_cap02_real_object_store_session_translates_provider_oserror(
    tmp_path, monkeypatch, operation, handle_method
):
    root = tmp_path / "objects"
    root.mkdir(mode=0o700)
    provider = LocalObjects(root)

    def fail(*_args, **_kwargs):
        raise OSError(errno.EIO, "private provider path")

    monkeypatch.setattr(ObjectHandle, handle_method, fail)
    locator = "obj-" + "2" * 32
    digest = hashlib.sha256(b"x").hexdigest()
    with object_store_session(provider) as files:
        with pytest.raises(DomainError) as raised:
            if operation == "put":
                files.put(locator, b"x", digest)
            elif operation == "get":
                files.get(locator, digest, 1)
            else:
                files.delete(locator)
    _assert_store_unavailable(raised.value)


@pytest.mark.skipif(sys.platform != "linux", reason="real LocalObjects handle checks require Linux")
@pytest.mark.parametrize("error_number", [errno.ENOSPC, errno.EDQUOT])
def test_cap02_real_local_file_fsync_failure_leaves_no_canonical_or_temp_and_retry_succeeds(
    tmp_path, monkeypatch, error_number
):
    root = tmp_path / "objects"
    root.mkdir(mode=0o700)
    provider = LocalObjectStore(LocalObjects(root))
    locator = "obj-" + "d" * 32
    body = b"capacity boundary"
    digest = hashlib.sha256(body).hexdigest()
    real_fsync = os.fsync
    calls = 0

    def fail_first(fd):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError(error_number, "private mount")
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_first)
    with pytest.raises(DomainError) as raised:
        provider.put(locator, body, digest)
    _assert_store_unavailable(raised.value)
    assert not (root / locator).exists() and list(root.glob("tmp-*")) == []

    monkeypatch.setattr(os, "fsync", real_fsync)
    provider.put(locator, body, digest)
    assert provider.get(locator, digest, len(body)) == body


@pytest.mark.skipif(sys.platform != "linux", reason="real LocalObjects handle checks require Linux")
def test_obj04_directory_fsync_failure_is_503_then_exact_byte_retry_is_quiet(tmp_path, monkeypatch):
    root = tmp_path / "objects"
    root.mkdir(mode=0o700)
    provider = LocalObjectStore(LocalObjects(root))
    locator = "obj-" + "e" * 32
    body = b"renamed before directory fsync"
    digest = hashlib.sha256(body).hexdigest()
    real_fsync = os.fsync
    calls = 0

    def fail_directory(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError(errno.EIO, "private directory")
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_directory)
    with pytest.raises(DomainError) as raised:
        provider.put(locator, body, digest)
    _assert_store_unavailable(raised.value)
    assert (root / locator).read_bytes() == body and list(root.glob("tmp-*")) == []

    monkeypatch.setattr(os, "fsync", real_fsync)
    provider.put(locator, body, digest)
    assert provider.get(locator, digest, len(body)) == body


def seg(index: int) -> str:
    return f"0000000100000000{index:08X}"


def _write_backup(root: Path, name: str, start: str, when: datetime) -> None:
    target = root / name
    target.mkdir(parents=True)
    (target / "backup_label").write_text(
        f"START WAL LOCATION: 0/3000028 (file {start})\nSTART TIME: {when:%Y-%m-%d %H:%M:%S} UTC\n",
        encoding="utf-8",
    )


def _retention_world(tmp_path):
    archive = tmp_path / "archive"
    backups = tmp_path / "backups"
    archive.mkdir()
    backups.mkdir()
    for index in range(1, 8):
        (archive / seg(index)).write_bytes(bytes([index]))
    (archive / "00000001.history").write_bytes(b"history")
    (archive / f"{seg(4)}.partial").write_bytes(b"partial")
    _write_backup(backups, "old", seg(2), NOW - timedelta(days=20))
    _write_backup(backups, "recent", seg(5), NOW - timedelta(days=1))
    planned = retention.plan(
        retention.load_archive(archive),
        retention.load_backups(backups),
        retention_days=7,
        now=NOW,
    )
    return archive, backups, planned, backups / "receipt.json"


def test_bak02_partial_unlink_records_exact_failure_and_resume_does_not_repeat_completed_delete(
    tmp_path, monkeypatch
):
    archive, backups, planned, journal = _retention_world(tmp_path)
    real_delete = retention._delete_candidate
    failed = False
    delete_calls: list[str] = []

    def fail_second(target, archive_dir, backups_dir):
        nonlocal failed
        delete_calls.append(target["name"])
        if target["name"] == seg(2) and not failed:
            failed = True
            raise OSError(errno.ENOSPC, "private retention mount")
        return real_delete(target, archive_dir, backups_dir)

    monkeypatch.setattr(retention, "_delete_candidate", fail_second)
    with pytest.raises(retention.RetentionApplyPartial) as raised:
        retention.apply(planned, archive, backups, journal_path=journal)
    receipt = raised.value.receipt
    assert receipt["failureClass"] == BAK_02["failureClass"] and receipt["status"] == "partial"
    assert receipt["removed"]["archive"] == [seg(1)]
    assert {item["name"] for item in receipt["incompleteCandidates"]} == {
        seg(2),
        seg(3),
        seg(4),
        "old",
    }
    assert not (archive / seg(1)).exists() and (archive / seg(2)).exists()
    assert (archive / "00000001.history").exists() and (archive / f"{seg(4)}.partial").exists()
    assert (backups / "recent").is_dir()

    monkeypatch.setattr(retention, "_delete_candidate", real_delete)
    current = retention.plan(
        retention.load_archive(archive), retention.load_backups(backups), retention_days=7, now=NOW
    )
    removed = retention.apply(current, archive, backups, journal_path=journal)
    final = retention.load_apply_receipt(journal)
    assert seg(1) not in removed["archive"] and delete_calls.count(seg(1)) == 1
    assert final["status"] == "completed" and final["failureClass"] is None
    assert final["incompleteCandidates"] == [] and final["attemptCount"] == 2
    assert set(final["removed"]["archive"]) == {seg(1), seg(2), seg(3), seg(4)}
    assert final["removed"]["backups"] == ["old"]
    assert (backups / "recent").is_dir()


def test_bak02_process_interruption_after_unlink_resumes_as_already_absent_without_second_delete(
    tmp_path, monkeypatch
):
    archive, backups, planned, journal = _retention_world(tmp_path)
    real_delete = retention._delete_candidate
    interrupted = False

    def interrupt_after_delete(target, archive_dir, backups_dir):
        nonlocal interrupted
        removed = real_delete(target, archive_dir, backups_dir)
        if not interrupted:
            interrupted = True
            raise KeyboardInterrupt
        return removed

    monkeypatch.setattr(retention, "_delete_candidate", interrupt_after_delete)
    with pytest.raises(KeyboardInterrupt):
        retention.apply(planned, archive, backups, journal_path=journal)
    assert not (archive / seg(1)).exists()
    assert retention.load_apply_receipt(journal)["incompleteCandidates"][0]["name"] == seg(1)

    unlink_calls: list[str] = []
    real_unlink = Path.unlink

    def count_unlink(path, *args, **kwargs):
        if path.name == seg(1):
            unlink_calls.append(path.name)
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(retention, "_delete_candidate", real_delete)
    monkeypatch.setattr(Path, "unlink", count_unlink)
    current = retention.plan(
        retention.load_archive(archive), retention.load_backups(backups), retention_days=7, now=NOW
    )
    retention.apply(current, archive, backups, journal_path=journal)
    final = retention.load_apply_receipt(journal)
    assert unlink_calls == []
    assert final["alreadyAbsent"]["archive"] == [seg(1)]
    assert final["status"] == "completed" and final["attemptCount"] == 2


def test_bak02_partial_backup_rmtree_resumes_only_the_same_directory_inode(tmp_path, monkeypatch):
    archive, backups, planned, journal = _retention_world(tmp_path)
    real_rmtree = retention.shutil.rmtree
    interrupted = False

    def remove_label_then_fail(path):
        nonlocal interrupted
        if path.name == "old" and not interrupted:
            interrupted = True
            (path / "backup_label").unlink()
            raise OSError(errno.ENOSPC, "private retention mount")
        return real_rmtree(path)

    monkeypatch.setattr(retention.shutil, "rmtree", remove_label_then_fail)
    with pytest.raises(retention.RetentionApplyPartial) as raised:
        retention.apply(planned, archive, backups, journal_path=journal)
    assert raised.value.receipt["failureClass"] == BAK_02["failureClass"]
    assert (backups / "old").is_dir() and not (backups / "old" / "backup_label").exists()

    monkeypatch.setattr(retention.shutil, "rmtree", real_rmtree)
    current = retention.plan(
        retention.load_archive(archive),
        retention.load_backups(backups),
        retention_days=7,
        now=NOW,
    )
    retention.apply(current, archive, backups, journal_path=journal)
    receipt = retention.load_apply_receipt(journal)
    assert not (backups / "old").exists()
    assert receipt["removed"]["backups"] == ["old"]
    assert receipt["status"] == "completed" and receipt["attemptCount"] == 2


def test_bak02_replaced_candidate_directory_is_refused_before_delete(tmp_path, monkeypatch):
    archive, backups, planned, journal = _retention_world(tmp_path)

    def stop_before_delete(*_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(retention, "_delete_candidate", stop_before_delete)
    with pytest.raises(KeyboardInterrupt):
        retention.apply(planned, archive, backups, journal_path=journal)
    retention.shutil.rmtree(backups / "old")
    _write_backup(backups, "old", seg(2), NOW - timedelta(days=20))
    monkeypatch.undo()
    current = retention.plan(
        retention.load_archive(archive),
        retention.load_backups(backups),
        retention_days=7,
        now=NOW,
    )
    with pytest.raises(retention.RetentionApplyRefused, match="candidate identity changed"):
        retention.apply(current, archive, backups, journal_path=journal)
    assert (backups / "old").is_dir()


def _interrupt_before_first_delete(retention_world, monkeypatch):
    archive, backups, planned, journal = retention_world

    def stop_before_delete(*_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(retention, "_delete_candidate", stop_before_delete)
    with pytest.raises(KeyboardInterrupt):
        retention.apply(planned, archive, backups, journal_path=journal)
    monkeypatch.undo()
    return archive, backups, planned, journal


def test_bak02_self_consistent_journal_cannot_add_retained_wal(tmp_path, monkeypatch):
    archive, backups, planned, journal = _interrupt_before_first_delete(
        _retention_world(tmp_path), monkeypatch
    )
    document = json.loads(journal.read_text(encoding="utf-8"))
    retained = seg(6)
    document["plan"]["deleteArchive"].append(retained)
    document["plan"]["deleteArchive"].sort()
    document["planSha256"] = retention._digest(document["plan"])
    target = {
        "kind": "archive",
        "name": retained,
        "state": "pending",
        "identity": retention._candidate_identity(archive, retained, "archive"),
    }
    first_backup = next(
        index for index, value in enumerate(document["targets"]) if value["kind"] == "backups"
    )
    document["targets"].insert(first_backup, target)
    retention._refresh_incomplete(document)
    journal.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(retention.RetentionApplyRefused, match="no longer deletable"):
        retention.apply(planned, archive, backups, journal_path=journal)
    assert (archive / retained).is_file()
    assert all((archive / seg(index)).exists() for index in range(1, 8))


def test_bak02_self_consistent_journal_cannot_target_retained_backup(tmp_path, monkeypatch):
    archive, backups, planned, journal = _interrupt_before_first_delete(
        _retention_world(tmp_path), monkeypatch
    )
    document = json.loads(journal.read_text(encoding="utf-8"))
    retained = "recent"
    document["plan"]["deleteBackups"].append(retained)
    document["plan"]["deleteBackups"].sort()
    document["planSha256"] = retention._digest(document["plan"])
    document["candidateBackupLabelSha256"][retained] = retention._label_sha256(backups, retained)
    document["targets"].append(
        {
            "kind": "backups",
            "name": retained,
            "state": "pending",
            "identity": retention._candidate_identity(backups, retained, "backups"),
        }
    )
    retention._refresh_incomplete(document)
    journal.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(retention.RetentionApplyRefused, match="now retained"):
        retention.apply(planned, archive, backups, journal_path=journal)
    assert (backups / retained / "backup_label").is_file()
    assert all((archive / seg(index)).exists() for index in range(1, 8))


def test_bak02_rechecks_the_live_boundary_immediately_before_delete(tmp_path, monkeypatch):
    archive, backups, planned, journal = _retention_world(tmp_path)
    real_write = retention._write_journal
    changed = False

    def write_then_change_boundary(path, document):
        nonlocal changed
        real_write(path, document)
        if not changed:
            changed = True
            _write_backup(backups, "new-boundary", seg(1), NOW - timedelta(hours=1))

    monkeypatch.setattr(retention, "_write_journal", write_then_change_boundary)
    with pytest.raises(retention.RetentionApplyPartial) as raised:
        retention.apply(planned, archive, backups, journal_path=journal)
    assert raised.value.receipt["removed"] == {"archive": [], "backups": []}
    assert all((archive / seg(index)).exists() for index in range(1, 8))


def test_bak02_completed_receipt_is_archived_and_next_cycle_runs(tmp_path):
    archive, backups, planned, journal = _retention_world(tmp_path)
    retention.apply(planned, archive, backups, journal_path=journal)
    first = retention.load_apply_receipt(journal)
    assert first["status"] == "completed"

    later = NOW + timedelta(days=10)
    _write_backup(backups, "newest", seg(7), later - timedelta(hours=1))
    current = retention.plan(
        retention.load_archive(archive),
        retention.load_backups(backups),
        retention_days=7,
        now=later,
    )
    removed = retention.apply(current, archive, backups, journal_path=journal)
    archived = list(journal.parent.glob(f"{journal.stem}.completed-{first['planSha256']}-*.json"))
    assert len(archived) == 1
    assert retention.load_apply_receipt(archived[0]) == first
    assert removed["backups"] == ["recent"]
    assert retention.load_apply_receipt(journal)["status"] == "completed"


def test_bak02_delete_flushes_parent_before_returning(tmp_path, monkeypatch):
    archive, backups, planned, _journal = _retention_world(tmp_path)
    target = {
        "kind": "archive",
        "name": planned.delete_archive[0],
        "state": "pending",
        "identity": retention._candidate_identity(archive, planned.delete_archive[0], "archive"),
    }
    flushed: list[Path] = []
    monkeypatch.setattr(retention, "_fsync_directory", lambda path: flushed.append(path))
    assert retention._delete_candidate(target, archive, backups) is True
    assert flushed == [archive]
    assert not (archive / target["name"]).exists()


def test_bak02_changed_retained_label_refuses_before_another_delete(tmp_path, monkeypatch):
    archive, backups, planned, journal = _retention_world(tmp_path)

    def stop_before_delete(*_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(retention, "_delete_candidate", stop_before_delete)
    with pytest.raises(KeyboardInterrupt):
        retention.apply(planned, archive, backups, journal_path=journal)
    retained = backups / "recent" / "backup_label"
    retained.write_text(retained.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    monkeypatch.undo()
    current = retention.plan(
        retention.load_archive(archive), retention.load_backups(backups), retention_days=7, now=NOW
    )
    with pytest.raises(retention.RetentionApplyRefused, match="retained backup label changed"):
        retention.apply(current, archive, backups, journal_path=journal)
    assert all((archive / seg(index)).exists() for index in range(1, 8))
    assert (backups / "old").is_dir() and (backups / "recent").is_dir()


def test_bak02_tampered_nested_receipt_refuses_before_another_delete(tmp_path, monkeypatch):
    archive, backups, planned, journal = _retention_world(tmp_path)

    def stop_before_delete(*_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(retention, "_delete_candidate", stop_before_delete)
    with pytest.raises(KeyboardInterrupt):
        retention.apply(planned, archive, backups, journal_path=journal)
    document = json.loads(journal.read_text(encoding="utf-8"))
    document["receipt"]["incompleteCandidates"][0]["unexpected"] = True
    journal.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.undo()
    current = retention.plan(
        retention.load_archive(archive), retention.load_backups(backups), retention_days=7, now=NOW
    )
    with pytest.raises(
        retention.RetentionApplyRefused, match="receipt does not match target state"
    ):
        retention.apply(current, archive, backups, journal_path=journal)
    assert all((archive / seg(index)).exists() for index in range(1, 8))


def test_bak02_cli_uses_closed_failure_class_and_nonzero_exit(tmp_path, monkeypatch, capsys):
    archive, backups, _planned, journal = _retention_world(tmp_path)

    def fail(*_args):
        raise OSError(errno.EDQUOT, "private retention mount")

    monkeypatch.setattr(retention, "_delete_candidate", fail)
    code = retention.main(
        [
            "--archive",
            str(archive),
            "--backups",
            str(backups),
            "--days",
            "7",
            "--now",
            NOW.isoformat(),
            "--journal",
            str(journal),
            "--apply",
        ]
    )
    output = capsys.readouterr().out
    assert code == BAK_02["exit"]
    assert f'"failureClass": "{BAK_02["failureClass"]}"' in output
    assert '"status": "partial"' in output
    assert (archive / seg(1)).exists() and (backups / "old").is_dir()
