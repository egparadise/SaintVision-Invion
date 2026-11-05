"""A verified predecessor must be settled before advancing its active generation."""

from argparse import Namespace
from datetime import timedelta
import json
import os

import pytest

from test_lan_leaf_rotation_consecutive import _normal_cycles
from test_lan_leaf_rotation_batch_successor import _completed, _snapshot, lan_pilot, rotation


def _crash_after_link(monkeypatch, action):
    real_link = os.link

    def link_then_crash(source, target, *args, **kwargs):
        real_link(source, target, *args, **kwargs)
        raise RuntimeError("crash after verified archive link")

    with monkeypatch.context() as patch:
        patch.setattr(rotation.os, "link", link_then_crash)
        with pytest.raises(RuntimeError, match="verified archive link"):
            action()


def test_node_successor_requires_verified_predecessor_replay(tmp_path, monkeypatch):
    case = _normal_cycles(tmp_path, monkeypatch)
    first = json.loads((case.first / "rotation.json").read_bytes())
    archive = case.worker / "leaf-rotation-finalized" / f'{first["rotationId"]}.json'
    canonical = archive.read_bytes()
    archive.rename(archive.with_suffix(".preserved"))  # supported legacy finalized journal
    key_raw = (case.worker / "node-key.pem").read_bytes()

    def replay():
        rotation.finalize(
            case.first,
            case.worker,
            case.first_commit,
            now=case.now(),
            restart=lambda _root: pytest.fail("finalized replay restarted"),
        )

    _crash_after_link(monkeypatch, replay)
    temporary = archive.with_name(archive.name + ".next")
    assert archive.read_bytes() == temporary.read_bytes() == canonical
    before = _snapshot(case.worker)
    with pytest.raises(ValueError, match="predecessor.*replay"):
        case.install(case.second)
    assert _snapshot(case.worker) == before
    replay()
    assert not temporary.exists()
    assert archive.read_bytes() == canonical
    case.finish(case.second, case.install(case.second))
    third = case.prepare(2)  # fixture clock only, next normal renewal window
    case.finish(third, case.install(third))
    assert (
        json.loads((case.worker / "leaf-rotation.json").read_bytes())["targetChannelVersion"] == 10
    )
    assert (case.worker / "node-key.pem").read_bytes() == key_raw
    assert archive.read_bytes() == canonical
    assert len(list(archive.parent.glob("*.json"))) == 3
    assert not list(archive.parent.glob("*.next"))


def test_cp_successor_requires_verified_predecessor_replay(tmp_path, monkeypatch):
    case = _completed(tmp_path, monkeypatch)
    _, first, _ = lan_pilot._batch_material(case.args.output)
    archive = lan_pilot._batch_archive_path(case.args.state, first)
    _crash_after_link(monkeypatch, lambda: lan_pilot.retire_leaf_rotation_batch(case.retirement))
    temporary = archive.with_name(archive.name + ".next")
    canonical = archive.read_bytes()
    assert temporary.read_bytes() == canonical

    # Reproduce the supported legacy8b replay: the complete archive was validated,
    # but the old publisher returned without unlinking its equal staging link.
    def legacy_existing_publication(path, raw, *, publish):
        assert path == archive
        assert rotation._history_bytes(path, limit=max(65536, len(raw))) == raw

    with monkeypatch.context() as patch:
        patch.setattr(rotation, "_immutable", legacy_existing_publication)
        lan_pilot.retire_leaf_rotation_batch(case.retirement)
    assert lan_pilot._load_batch_journal(case.args.state)["phase"] == "finalized"
    assert temporary.exists()
    case.clock[0] += timedelta(days=4)
    second = Namespace(**{**vars(case.args), "output": tmp_path / "second-after-residue"})
    before = _snapshot(case.args.state)
    with pytest.raises(ValueError, match="predecessor.*replay"):
        lan_pilot.prepare_leaf_rotation_batch(second)
    assert _snapshot(case.args.state) == before
    assert not second.output.exists()
    lan_pilot.retire_leaf_rotation_batch(case.retirement)
    assert not temporary.exists()
    assert archive.read_bytes() == canonical
    lan_pilot.prepare_leaf_rotation_batch(second)
    case.complete(second.output, 1)
    case.retire(second.output, 1)
    case.clock[0] += timedelta(days=4)
    third = Namespace(**{**vars(case.args), "output": tmp_path / "third-after-residue"})
    lan_pilot.prepare_leaf_rotation_batch(third)
    case.complete(third.output, 2)
    case.retire(third.output, 2)
    assert archive.read_bytes() == canonical
    assert len(list(archive.parent.glob("*.json"))) == 3
    assert not list(archive.parent.glob("*.next"))
    assert sorted(row[0] for row in case.rows.values()) == [10, 14]
