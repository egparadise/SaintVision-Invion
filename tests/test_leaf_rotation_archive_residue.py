"""Crash after link publication must not leave a classifier-blocking orphan."""

import json
import os
from pathlib import Path

import pytest

from test_lan_leaf_rotation_batch_successor import _completed, lan_pilot, rotation, NODE_ID


@pytest.mark.parametrize("role", ["node", "control"])
def test_link_publication_crash_replay_removes_only_equal_owned_residue(
    tmp_path, monkeypatch, role
):
    case = _completed(tmp_path, monkeypatch)
    if role == "node":
        worker = case.workers[NODE_ID]
        bundle = case.args.output / f"nodes/{NODE_ID}"
        manifest = json.loads((bundle / "rotation.json").read_bytes())
        archive = worker / "leaf-rotation-finalized" / f'{manifest["rotationId"]}.json'
        original = archive.read_bytes()
        archive.rename(archive.with_suffix(".preserved"))
        journal = json.loads((worker / "leaf-rotation.json").read_bytes())
        journal["phase"] = "restarted"
        (worker / "leaf-rotation.json").write_bytes(rotation._canonical(journal))
        (worker / "peer-policy.json").write_bytes(
            (bundle / "peer-policy-overlap.json").read_bytes()
        )

        def publish():
            rotation.finalize(
                bundle,
                worker,
                tmp_path / "commits-0" / f"{NODE_ID}.json",
                now=case.clock[0],
                restart=lambda _root: None,
            )

    else:
        _, batch, _ = lan_pilot._batch_material(case.args.output)
        archive = lan_pilot._batch_archive_path(case.args.state, batch)
        original = None

        def publish():
            lan_pilot.retire_leaf_rotation_batch(case.retirement)

    real_link = os.link

    def link_then_crash(source, target, *args, **kwargs):
        real_link(source, target, *args, **kwargs)
        raise RuntimeError("crash after complete link publication")

    with monkeypatch.context() as patch:
        patch.setattr(rotation.os, "link", link_then_crash)
        with pytest.raises(RuntimeError, match="complete link publication"):
            publish()
    temporary = archive.with_name(archive.name + ".next")
    published = archive.read_bytes()
    if original is not None:
        assert published == original
    assert temporary.read_bytes() == published
    inode = archive.stat().st_ino
    publish()
    assert archive.read_bytes() == published
    assert archive.stat().st_ino == inode
    assert not temporary.exists()
    # The F5 orphan classifier needs no exception for a verified replay.
    assert not list(archive.parent.glob("*.next"))
    publish()  # exact replay remains idempotent, without creating residue
    assert archive.read_bytes() == published


@pytest.mark.parametrize("publish", [False, True])
@pytest.mark.parametrize("residue", [b"different evidence", b"", b"partial"])
def test_existing_archive_never_hides_unknown_or_partial_staging_residue(
    tmp_path, publish, residue
):
    archive = tmp_path / "history.json"
    canonical = b"canonical immutable evidence\n"
    archive.write_bytes(canonical)
    temporary = archive.with_name(archive.name + ".next")
    temporary.write_bytes(residue)
    with pytest.raises(ValueError):
        rotation._immutable(archive, canonical, publish=publish)
    assert archive.read_bytes() == canonical
    assert temporary.read_bytes() == residue


def test_equal_residue_is_not_removed_by_a_preflight(tmp_path):
    archive = tmp_path / "history.json"
    archive.write_bytes(b"canonical evidence\n")
    temporary = archive.with_name(archive.name + ".next")
    temporary.write_bytes(archive.read_bytes())
    rotation._immutable(archive, archive.read_bytes(), publish=False)
    assert temporary.exists()
    rotation._immutable(archive, archive.read_bytes(), publish=True)
    assert not temporary.exists()


def test_verified_terminal_cp_replay_cleans_equal_residue_from_prior_source(tmp_path, monkeypatch):
    case = _completed(tmp_path, monkeypatch)
    lan_pilot.retire_leaf_rotation_batch(case.retirement)
    _, batch, _ = lan_pilot._batch_material(case.args.output)
    archive = lan_pilot._batch_archive_path(case.args.state, batch)
    canonical = archive.read_bytes()
    journal_raw = (case.args.state / "leaf-rotation-batch.json").read_bytes()
    temporary = archive.with_name(archive.name + ".next")
    os.link(archive, temporary)  # exact legacy link/unlink residue, already terminal
    lan_pilot.retire_leaf_rotation_batch(case.retirement)
    assert not temporary.exists()
    assert archive.read_bytes() == canonical
    assert (case.args.state / "leaf-rotation-batch.json").read_bytes() == journal_raw


@pytest.mark.skipif(os.name == "nt", reason="POSIX ownership/mode guard")
def test_group_writable_equal_residue_is_preserved_and_refused(tmp_path):
    archive = tmp_path / "history.json"
    archive.write_bytes(b"canonical evidence\n")
    temporary = archive.with_name(archive.name + ".next")
    temporary.write_bytes(archive.read_bytes())
    temporary.chmod(0o666)
    with pytest.raises(ValueError, match="ownership or mode"):
        rotation._immutable(archive, archive.read_bytes(), publish=True)
    assert temporary.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX file-owner guard")
@pytest.mark.parametrize("foreign", ["archive", "temporary"])
def test_foreign_owned_evidence_is_not_removed(tmp_path, monkeypatch, foreign):
    archive = tmp_path / "history.json"
    archive.write_bytes(b"canonical evidence\n")
    temporary = archive.with_name(archive.name + ".next")
    temporary.write_bytes(archive.read_bytes())
    target = archive if foreign == "archive" else temporary
    real_lstat = Path.lstat

    def foreign_lstat(path, *args, **kwargs):
        info = real_lstat(path, *args, **kwargs)
        if path == target:
            values = list(info)
            values[4] = os.geteuid() + 1
            return os.stat_result(values)
        return info

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", foreign_lstat)
        with pytest.raises(ValueError, match="ownership or mode"):
            rotation._immutable(archive, b"canonical evidence\n", publish=True)
    assert temporary.exists()
    assert archive.read_bytes() == b"canonical evidence\n"


def test_symlink_equal_residue_is_preserved_and_refused(tmp_path):
    archive = tmp_path / "history.json"
    archive.write_bytes(b"canonical evidence\n")
    temporary = archive.with_name(archive.name + ".next")
    try:
        temporary.symlink_to(archive)
    except OSError:
        pytest.skip("OS cannot create test symlinks")
    with pytest.raises(ValueError):
        rotation._immutable(archive, archive.read_bytes(), publish=True)
    assert temporary.is_symlink()
    assert archive.read_bytes() == b"canonical evidence\n"
