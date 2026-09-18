from concurrent.futures import ThreadPoolExecutor
import os
import sys
from uuid import uuid4
import pytest
from inv.errors import DomainError
from inv.workspace_files import WorkingGenerations
from test_approvals import approval, count
from test_tool_admission import gateway
from test_snapshots import storage
from test_results import result
from test_workspace_recovery import workspace, recovering, restore

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux private working tree"),
]


@pytest.fixture
def checkout(workspace, tmp_path):
    a = workspace
    recovering(a)
    a.restored = restore(a)
    root = tmp_path / "checkouts"
    root.mkdir(mode=0o700)
    a.working = WorkingGenerations(root)
    a.checkout_id = str(uuid4())
    return a


def publish(a):
    return a.recovery.checkout(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        a.restore_id,
        a.checkout_id,
        a.working,
        expected_version=a.run["version"],
    )


def test_writable_checkout_and_resume_cursor_preserve_immutable_restore(checkout):
    a = checkout
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: publish(a), range(4)))
    assert sum(not x["replayed"] for x in results) == 1
    r = results[0]
    assert r["stepId"] == "files-v1" and r["sourceAttempt"] == 1
    files = a.working.root / r["generation"] / "files"
    assert (files / "src/main.py").stat().st_mode & 0o777 == 0o600
    assert (files / "run").stat().st_mode & 0o777 == 0o700
    (files / "src/main.py").write_bytes(b"resumed edit")
    (files / "new.txt").write_bytes(b"new work")
    assert publish(a)["replayed"]
    assert (files / "src/main.py").read_bytes() == b"resumed edit"
    original = a.generations.root / a.restored["generation"] / "files/src/main.py"
    assert (
        original.read_bytes() == b"print('checkpoint')\n"
        and original.stat().st_mode & 0o777 == 0o400
    )
    assert count(a, "workspace_checkouts") == 1
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "recovering"


def test_checkout_commit_failure_reuses_verified_generation(checkout, monkeypatch):
    import inv.workspace_recovery as module

    a = checkout
    original = module.event
    monkeypatch.setattr(
        module,
        "event",
        lambda *args: (_ for _ in ()).throw(RuntimeError("synthetic failed commit")),
    )
    with pytest.raises(RuntimeError):
        publish(a)
    assert count(a, "workspace_checkouts") == 0
    directory = next(a.working.root.glob("generation-*"))
    inode = directory.stat().st_ino
    monkeypatch.setattr(module, "event", original)
    assert not publish(a)["replayed"] and directory.stat().st_ino == inode


def test_dirty_uncommitted_checkout_cannot_be_adopted_as_verified(checkout, monkeypatch):
    import inv.workspace_recovery as module

    a = checkout
    original = module.event
    monkeypatch.setattr(
        module,
        "event",
        lambda *args: (_ for _ in ()).throw(RuntimeError("synthetic failed commit")),
    )
    with pytest.raises(RuntimeError):
        publish(a)
    directory = next(a.working.root.glob("generation-*"))
    (directory / "files/src/main.py").write_bytes(b"uncommitted edit")
    monkeypatch.setattr(module, "event", original)
    with pytest.raises(DomainError):
        publish(a)
    assert (directory / "files/src/main.py").read_bytes() == b"uncommitted edit"
    assert count(a, "workspace_checkouts") == 0


def test_cancel_before_checkout_does_not_create_writable_files(checkout):
    a = checkout
    a.e.runs.transition(a.e.tenant, a.run["runId"], "cancelled", expected_version=a.run["version"])
    with pytest.raises(DomainError, match="GRAPH-0003"):
        publish(a)
    assert not list(a.working.root.glob("generation-*"))


def test_checkout_replay_rejects_replaced_directory_identity(checkout):
    a = checkout
    r = publish(a)
    directory = a.working.root / r["generation"]
    files = directory / "files"
    os.rename(files, directory / "old-files")
    files.mkdir(mode=0o700)
    # Restore the allowed metadata shape while changing only the files inode.
    os.rename(directory / "old-files", a.working.root / "preserved-files")
    with pytest.raises(DomainError, match="STORE-0022"):
        publish(a)
