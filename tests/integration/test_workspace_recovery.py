from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys
from uuid import uuid4
import pytest
from inv.errors import DomainError
from inv.ids import new_id
from inv.workspace_files import PrivateTree, RestoreGenerations, decode_snapshot
from inv.workspace_recovery import WorkspaceRecovery
from test_approvals import approval, count
from test_tool_admission import gateway
from test_snapshots import storage
from test_results import result, stopped

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux scoped handles"),
]


@pytest.fixture
def workspace(result, tmp_path):
    a = result
    root = tmp_path / "working"
    root.mkdir(mode=0o700)
    (root / "src").mkdir(mode=0o700)
    (root / "empty").mkdir(mode=0o700)
    (root / "src/main.py").write_bytes(b"print('checkpoint')\n")
    (root / "src/main.py").chmod(0o600)
    (root / "binary").write_bytes(bytes(range(256)))
    (root / "binary").chmod(0o600)
    (root / "run").write_bytes(b"#!/bin/sh\nexit 0\n")
    (root / "run").chmod(0o700)
    a.source = PrivateTree(root)
    destination = tmp_path / "restores"
    destination.mkdir(mode=0o700)
    a.generations = RestoreGenerations(destination)
    a.workspace_id = new_id("wsp")
    a.recovery = WorkspaceRecovery(a.storage, a.generations)
    a.restore_id = str(uuid4())
    a.recovery.checkpoint(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        a.workspace_id,
        "files-v1",
        a.source,
        proofs=a.proofs,
    )
    return a


def recovering(a, *, physical=True):
    if physical:
        stopped(a)
    a.run = a.e.runs.transition(
        a.e.tenant, a.run["runId"], "recovering", expected_version=a.run["version"]
    )


def restore(a, **changes):
    return a.recovery.restore(
        changes.get("tenant", a.e.tenant),
        changes.get("project", a.e.project),
        a.run["runId"],
        changes.get("workspace", a.workspace_id),
        1,
        "files-v1",
        a.restore_id,
        expected_version=a.run["version"],
    )


def test_actual_files_restore_and_concurrent_replay_publish_only_one_generation(
    workspace,
):
    a = workspace
    recovering(a)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: restore(a), range(4)))
    assert (
        sum(not r["replayed"] for r in results) == 1
        and count(a, "workspace_restores") == 1
    )
    generation = a.generations.root / results[0]["generation"] / "files"
    for path in ["src/main.py", "binary", "run"]:
        assert (generation / path).read_bytes() == (a.source.root / path).read_bytes()
    assert (generation / "empty").is_dir()
    assert (generation / "run").stat().st_mode & 0o777 == 0o500
    assert (generation / "src/main.py").stat().st_mode & 0o777 == 0o400
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "recovering"
    assert not list(a.generations.root.glob("stage-*"))


def test_restore_does_not_overwrite_working_tree_and_rejects_wrong_scope(workspace):
    a = workspace
    recovering(a)
    (a.source.root / "src/main.py").write_bytes(b"later user edit")
    for changes in [
        {"workspace": new_id("wsp")},
        {"tenant": a.e.other},
        {"project": new_id("prj")},
    ]:
        with pytest.raises(DomainError):
            restore(a, **changes)
    r = restore(a)
    assert (
        a.generations.root / r["generation"] / "files/src/main.py"
    ).read_bytes() == b"print('checkpoint')\n"
    assert (a.source.root / "src/main.py").read_bytes() == b"later user edit"


def test_physical_release_is_required_before_restore(workspace):
    a = workspace
    recovering(a, physical=False)
    with pytest.raises(DomainError, match="LEASE-0003"):
        restore(a)
    assert (
        not list(a.generations.root.iterdir()) and count(a, "workspace_restores") == 0
    )


def test_generation_fsync_before_db_failure_is_reused_without_overwrite(
    workspace, monkeypatch
):
    import inv.workspace_recovery as module

    a = workspace
    recovering(a)
    original = module.event

    def crash(*args):
        raise RuntimeError("synthetic restore commit failure")

    monkeypatch.setattr(module, "event", crash)
    with pytest.raises(RuntimeError):
        restore(a)
    assert count(a, "workspace_restores") == 0
    generation = next(a.generations.root.glob("generation-*"))
    inode = generation.stat().st_ino
    monkeypatch.setattr(module, "event", original)
    assert not restore(a)["replayed"]
    assert generation.stat().st_ino == inode and count(a, "workspace_restores") == 1


def test_cancel_between_failed_commit_and_retry_does_not_resume(workspace, monkeypatch):
    import inv.workspace_recovery as module

    a = workspace
    recovering(a)

    def crash(*args):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(module, "event", crash)
    with pytest.raises(RuntimeError):
        restore(a)
    a.e.runs.transition(
        a.e.tenant, a.run["runId"], "cancelled", expected_version=a.run["version"]
    )
    with pytest.raises(DomainError, match="GRAPH-0003"):
        restore(a)
    assert count(a, "workspace_restores") == 0


def test_generation_corruption_or_missing_data_cannot_be_silently_repaired(workspace):
    a = workspace
    recovering(a)
    r = restore(a)
    file = a.generations.root / r["generation"] / "files/binary"
    file.unlink()
    with pytest.raises(DomainError, match="VERIFY-0023"):
        restore(a)
    assert not file.exists() and count(a, "workspace_restores") == 1


@pytest.mark.parametrize("attack", ["symlink", "hardlink", "directory-link", "fifo"])
def test_capture_refuses_link_and_special_file_escape(workspace, tmp_path, attack):
    a = workspace
    outside = tmp_path / "outside"
    outside.write_bytes(b"must not be read")
    outside.chmod(0o600)
    link = a.source.root / "escape"
    if attack == "symlink":
        link.symlink_to(outside)
    if attack == "hardlink":
        os.link(outside, link)
    if attack == "directory-link":
        link.symlink_to(tmp_path, target_is_directory=True)
    if attack == "fifo":
        os.mkfifo(link, 0o600)
    with pytest.raises((DomainError, OSError)):
        a.source.capture(a.workspace_id)
    assert outside.read_bytes() == b"must not be read"


def test_root_replacement_is_rejected(workspace):
    a = workspace
    a.source.root.rename(a.source.root.with_name("original"))
    a.source.root.mkdir(mode=0o700)
    with pytest.raises(DomainError, match="SEC-0021"):
        a.source.capture(a.workspace_id)


def test_partial_file_write_has_no_published_generation(workspace, monkeypatch):
    a = workspace
    recovering(a)
    original = os.fsync

    def crash(fd):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(os, "fsync", crash)
    with pytest.raises(OSError):
        restore(a)
    assert (
        not list(a.generations.root.glob("generation-*"))
        and count(a, "workspace_restores") == 0
    )
    monkeypatch.setattr(os, "fsync", original)
    assert not restore(a)["replayed"]
