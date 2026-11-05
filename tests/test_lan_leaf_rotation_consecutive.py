"""Consecutive normal renewals with real issuer/CSR/receipt cryptography.

Only the channel persistence/restart seams and fixture clock are substituted.
No live CA, socket, Docker daemon, system clock or operator receipt is used.
"""

from argparse import Namespace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.exceptions import InvalidSignature

from test_lan_leaf_rotation import (
    _plain_unit_transport,
    NODE_ID,
    _BatchConnection,
    _batch_worker,
    _prepare_inputs,
    fingerprint,
    lan_pilot,
    rotation,
)


def _normal_cycles(tmp_path, monkeypatch):
    instant = datetime(2026, 11, 5, 0, 0, tzinfo=timezone.utc)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(lan_pilot, "datetime", Clock)
    fixture, _state, row, args = _prepare_inputs(tmp_path, monkeypatch, now=instant)
    rows = {NODE_ID: row}
    monkeypatch.setattr(lan_pilot.psycopg, "connect", lambda _dsn: _BatchConnection(rows))

    def provision(_conn, principal, *, epoch, endpoint, certificate_der, expected_version):
        assert rows[principal.node_id][0] == expected_version
        cert = x509.load_der_x509_certificate(certificate_der)
        rows[principal.node_id] = (
            expected_version + 1,
            fingerprint(cert),
            cert.not_valid_after_utc,
            True,
            endpoint,
        )
        return expected_version + 1

    monkeypatch.setattr(lan_pilot, "provision_channel", provision)
    worker = _batch_worker(
        tmp_path,
        "consecutive-worker",
        chain=fixture.chain,
        key=fixture.node_key,
        certificate=fixture.current_node,
        policy=json.loads((args.state / "peer-policy.json").read_bytes()),
        node_id=NODE_ID,
    )
    args.safety_window_hours = 48
    args.leaf_valid_seconds = 6 * 86400
    args.overlap_seconds = 3600
    restarts = []

    def prepare(cycle):
        nonlocal instant
        instant += timedelta(days=4) if cycle else timedelta()
        proposal = Namespace(**{**vars(args), "output": tmp_path / f"normal-{cycle}"})
        lan_pilot.prepare_leaf_rotation(proposal)
        return proposal.output

    def install(bundle, **kwargs):
        return rotation.install(
            bundle,
            worker,
            now=instant,
            restart=lambda root: restarts.append(root),
            **kwargs,
        )

    def finish(bundle, receipt):
        receipt_path = tmp_path / f"{bundle.name}-node-receipt.json"
        receipt_path.write_bytes(rotation._canonical(receipt))
        commit_path = tmp_path / f"{bundle.name}-commit.json"
        lan_pilot.commit_leaf_rotation(
            Namespace(
                state=args.state,
                bundle=bundle,
                node_receipt=receipt_path,
                output=commit_path,
            )
        )
        result = rotation.finalize(
            bundle,
            worker,
            commit_path,
            now=instant,
            restart=lambda root: restarts.append(root),
        )
        return result, commit_path

    first = prepare(0)
    receipt = install(first)
    finish(first, receipt)
    journal_raw = (worker / "leaf-rotation.json").read_bytes()
    second = prepare(1)
    return Namespace(
        worker=worker,
        first=first,
        second=second,
        install=install,
        finish=finish,
        journal_raw=journal_raw,
        restarts=restarts,
        now=lambda: instant,
        first_commit=tmp_path / f"{first.name}-commit.json",
        prepare=prepare,
    )


def test_two_server_issued_normal_cycles_keep_generation_and_immutable_history(
    tmp_path, monkeypatch
):
    case = _normal_cycles(tmp_path, monkeypatch)
    old = json.loads((case.first / "rotation.json").read_bytes())
    new = json.loads((case.second / "rotation.json").read_bytes())
    assert json.loads(case.journal_raw)["phase"] == "finalized"
    assert old["rotationId"] != new["rotationId"]
    assert old["schemaVersion"] == new["schemaVersion"] == "saintvision-lan-leaf-rotation:3"
    assert old["targetChannelVersion"] == new["currentChannelVersion"] == 8
    assert new["targetChannelVersion"] == 9
    assert old["nextNodeCertificateSHA256"] == new["currentNodeCertificateSHA256"]
    assert old["nextControlCertificateSHA256"] == new["currentControlCertificateSHA256"]
    assert old["nextNodeCertificateSHA256"] != new["nextNodeCertificateSHA256"]
    key_raw = (case.worker / "node-key.pem").read_bytes()
    backup = case.worker / "leaf-rotation-backup" / old["rotationId"]
    backup_raw = {p.name: p.read_bytes() for p in backup.iterdir()}
    receipt = case.install(case.second)
    assert case.install(case.second) == receipt  # same-generation restart replay
    case.finish(case.second, receipt)
    assert (case.worker / "node-key.pem").read_bytes() == key_raw
    assert {p.name: p.read_bytes() for p in backup.iterdir()} == backup_raw
    assert (
        fingerprint(x509.load_pem_x509_certificate((case.worker / "node-cert.pem").read_bytes()))
        == new["nextNodeCertificateSHA256"]
    )
    assert len(case.restarts) == 4
    archive = case.worker / "leaf-rotation-finalized" / f'{old["rotationId"]}.json'
    historical = json.loads(archive.read_bytes())
    assert historical["journal"] == json.loads(case.journal_raw)
    assert historical["journalRaw"].encode() == case.journal_raw
    assert historical["rotationManifest"] == (case.first / "rotation.json").read_text("utf-8")
    assert historical["journal"]["receipt"]["nodeSignature"]
    assert json.loads(historical["commitReceipt"])["controlSignature"]
    assert len(list(archive.parent.glob("*.json"))) == 2
    evidence_path = os.environ.get("INV_CONSECUTIVE_ROTATION_EVIDENCE")
    if evidence_path:
        Path(evidence_path).write_text(
            json.dumps(
                {
                    "schema": "fleet5-consecutive-normal-rotation-proof:1",
                    "fixtureOnly": True,
                    "systemClockChanged": False,
                    "channelStore": "CAS fixture",
                    "nodeId": NODE_ID,
                    "first": old,
                    "second": new,
                    "priorFinalizedJournalSHA256": hashlib.sha256(case.journal_raw).hexdigest(),
                    "preservedArchiveSHA256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                    "restartCount": len(case.restarts),
                    "nodeKeyUnchanged": True,
                    "priorBackupUnchanged": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def _snapshot(worker):
    return {str(p.relative_to(worker)): p.read_bytes() for p in worker.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "phase",
    [
        "installing",
        "installed",
        "restarted",
        "rolled-back",
        "prepared",
        "staged",
        "switched",
        "unknown",
        None,
    ],
)
def test_distinct_normal_cycle_refuses_every_unfinalized_or_unknown_state(
    tmp_path, monkeypatch, phase
):
    case = _normal_cycles(tmp_path, monkeypatch)
    journal = {**json.loads(case.journal_raw), "phase": phase}
    (case.worker / "leaf-rotation.json").write_bytes(rotation._canonical(journal))
    before = _snapshot(case.worker)
    with pytest.raises(ValueError):
        case.install(case.second)
    assert _snapshot(case.worker) == before
    assert len(case.restarts) == 2


@pytest.mark.parametrize(
    "fault",
    [
        "policy",
        "current-leaf",
        "generation",
        "tenant",
        "epoch",
        "control-hash",
        "archive-collision",
        "archive-journal",
        "archive-signature",
        "missing-archive",
        "backup-collision",
    ],
)
def test_successor_refuses_inconsistent_authority_and_history_without_mutation(
    tmp_path, monkeypatch, fault
):
    case = _normal_cycles(tmp_path, monkeypatch)
    old = json.loads((case.first / "rotation.json").read_bytes())
    new = json.loads((case.second / "rotation.json").read_bytes())
    archive = case.worker / "leaf-rotation-finalized" / f'{old["rotationId"]}.json'
    if fault == "policy":
        (case.worker / "peer-policy.json").write_bytes(
            (case.first / "peer-policy-overlap.json").read_bytes()
        )
    elif fault == "current-leaf":
        (case.worker / "node-cert.pem").write_bytes((case.second / "node-cert.pem").read_bytes())
    elif fault in {"generation", "tenant", "epoch", "control-hash"}:
        field, value = {
            "generation": ("currentChannelVersion", 42),
            "tenant": ("tenantId", "wrong-tenant"),
            "epoch": ("recoveryEpoch", "wrong-epoch"),
            "control-hash": ("currentControlCertificateSHA256", "0" * 64),
        }[fault]
        new[field] = value
        (case.second / "rotation.json").write_bytes(rotation._canonical(new))
    elif fault == "archive-collision":
        (archive.parent / f'{new["rotationId"]}.json').write_bytes(b"unrelated immutable evidence")
    elif fault in {"archive-journal", "archive-signature"}:
        proof = json.loads(archive.read_bytes())
        if fault == "archive-journal":
            proof["journal"]["phase"] = "restarted"
        else:
            commit = json.loads(proof["commitReceipt"])
            commit["controlSignature"] = "0" * 128
            proof["commitReceipt"] = json.dumps(commit)
        archive.write_bytes(rotation._canonical(proof))
    elif fault == "missing-archive":
        archive.rename(archive.with_suffix(".preserved"))  # model a legacy finalization
    else:
        backup = case.worker / "leaf-rotation-backup" / new["rotationId"]
        backup.mkdir()
        (backup / "node-cert.pem").write_bytes(b"unrelated old backup")
    before = _snapshot(case.worker)
    with pytest.raises((ValueError, FileNotFoundError, InvalidSignature)):
        case.install(case.second)
    assert _snapshot(case.worker) == before
    assert len(case.restarts) == 2


def test_legacy_finalized_replay_archives_exact_evidence_after_overlap_without_restart(
    tmp_path, monkeypatch
):
    case = _normal_cycles(tmp_path, monkeypatch)
    old = json.loads((case.first / "rotation.json").read_bytes())
    archive = case.worker / "leaf-rotation-finalized" / f'{old["rotationId"]}.json'
    archive.rename(archive.with_suffix(".preserved"))
    result = rotation.finalize(
        case.first,
        case.worker,
        case.first_commit,
        now=case.now(),
        restart=lambda _root: pytest.fail("legacy replay restarted"),
    )
    assert result["finalized"] is True
    assert archive.read_bytes() == archive.with_suffix(".preserved").read_bytes()
    assert (case.worker / "leaf-rotation.json").read_bytes() == case.journal_raw
    case.finish(case.second, case.install(case.second))


def test_finalize_archive_collision_fails_before_republishing_policy_or_restart(
    tmp_path, monkeypatch
):
    case = _normal_cycles(tmp_path, monkeypatch)
    old = json.loads((case.first / "rotation.json").read_bytes())
    archive = case.worker / "leaf-rotation-finalized" / f'{old["rotationId"]}.json'
    archive.write_bytes(b"preserve foreign proof")
    before = _snapshot(case.worker)
    with pytest.raises(ValueError, match="collision"):
        rotation.finalize(
            case.first,
            case.worker,
            case.first_commit,
            now=case.now(),
            restart=lambda _root: pytest.fail("collision restarted"),
        )
    assert _snapshot(case.worker) == before


def test_legacy_formatted_journal_bytes_are_preserved_exactly(tmp_path, monkeypatch):
    case = _normal_cycles(tmp_path, monkeypatch)
    old = json.loads((case.first / "rotation.json").read_bytes())
    archive = case.worker / "leaf-rotation-finalized" / f'{old["rotationId"]}.json'
    archive.rename(archive.with_suffix(".preserved"))
    raw = json.dumps(json.loads(case.journal_raw), indent=4).encode() + b"\n\n"
    (case.worker / "leaf-rotation.json").write_bytes(raw)
    rotation.finalize(
        case.first,
        case.worker,
        case.first_commit,
        now=case.now(),
        restart=lambda _root: pytest.fail("replay restarted"),
    )
    case.finish(case.second, case.install(case.second))
    assert json.loads(archive.read_bytes())["journalRaw"].encode() == raw


@pytest.mark.parametrize("where", ["before-archive", "after-archive"])
def test_finalize_publication_crash_is_replayable_without_overwriting_evidence(
    tmp_path, monkeypatch, where
):
    case = _normal_cycles(tmp_path, monkeypatch)
    old = json.loads((case.first / "rotation.json").read_bytes())
    archive = case.worker / "leaf-rotation-finalized" / f'{old["rotationId"]}.json'
    original_archive = archive.read_bytes()
    archive.rename(archive.with_suffix(".preserved"))
    # Model a crash after policy restart but before durable finalized journal.
    journal = {**json.loads(case.journal_raw), "phase": "restarted"}
    (case.worker / "leaf-rotation.json").write_bytes(rotation._canonical(journal))
    original_immutable = rotation._immutable
    original_atomic = rotation._atomic

    def immutable(path, raw, *, publish):
        if publish and where == "before-archive":
            raise RuntimeError("archive crash")
        return original_immutable(path, raw, publish=publish)

    def atomic(path, raw):
        if path.name == "leaf-rotation.json" and where == "after-archive":
            raise RuntimeError("archive crash")
        return original_atomic(path, raw)

    with monkeypatch.context() as patch:
        patch.setattr(rotation, "_immutable", immutable)
        patch.setattr(rotation, "_atomic", atomic)
        with pytest.raises(RuntimeError, match="archive crash"):
            rotation.finalize(
                case.first,
                case.worker,
                case.first_commit,
                now=case.now() - timedelta(days=4),
                restart=lambda _root: None,
            )
    rotation.finalize(
        case.first,
        case.worker,
        case.first_commit,
        now=case.now() - timedelta(days=4),
        restart=lambda _root: None,
    )
    assert archive.read_bytes() == original_archive
    case.finish(case.second, case.install(case.second))


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory ownership/mode boundary")
def test_successor_refuses_group_writable_archive_directory(tmp_path, monkeypatch):
    case = _normal_cycles(tmp_path, monkeypatch)
    archive = case.worker / "leaf-rotation-finalized"
    archive.chmod(0o770)
    with pytest.raises(ValueError, match="unsafe"):
        case.install(case.second)


@pytest.mark.parametrize(
    "point",
    ["before-install", "after-publication-intent", "after-overlap-publication", "after-restart-before-ack", "before-restart"],
)
def test_successor_crash_resume_keeps_prior_archive_and_backup(tmp_path, monkeypatch, point):
    case = _normal_cycles(tmp_path, monkeypatch)
    archive = case.worker / "leaf-rotation-finalized"
    before = {p.name: p.read_bytes() for p in archive.iterdir()}

    def crash(actual):
        if actual == point:
            raise RuntimeError("fixture crash")

    with pytest.raises(RuntimeError, match="fixture crash"):
        case.install(case.second, kill=crash)
    case.finish(case.second, case.install(case.second))
    assert all((archive / name).read_bytes() == raw for name, raw in before.items())


def test_successor_lock_refuses_concurrent_writer(tmp_path, monkeypatch):
    case = _normal_cycles(tmp_path, monkeypatch)
    with rotation._exclusive(case.worker / "leaf-rotation.lock"):
        with pytest.raises(ValueError, match="Node lock"):
            case.install(case.second)


def test_successor_publication_rollback_is_refused_and_preserves_prior_archive(tmp_path, monkeypatch):
    case = _normal_cycles(tmp_path, monkeypatch)
    case.install(case.second)
    before = _snapshot(case.worker)
    with pytest.raises(ValueError, match="forward-only"):
        rotation.rollback(case.second, case.worker, now=case.now(), restart=lambda _: pytest.fail("old restart"))
    assert _snapshot(case.worker) == before


def test_unfinalized_overlap_and_expired_legacy_finalize_remain_refused(tmp_path, monkeypatch):
    case = _normal_cycles(tmp_path, monkeypatch)
    before = _snapshot(case.worker)
    with pytest.raises(ValueError):
        rotation.finalize(
            case.first,
            case.worker,
            case.first_commit,
            now=case.now() + timedelta(days=3),
            restart=lambda _root: pytest.fail("expired replay restarted"),
        )
    assert _snapshot(case.worker) == before
    journal = {**json.loads(case.journal_raw), "phase": "restarted"}
    (case.worker / "leaf-rotation.json").write_bytes(rotation._canonical(journal))
    before = _snapshot(case.worker)
    with pytest.raises(ValueError, match="window"):
        rotation.finalize(
            case.first,
            case.worker,
            case.first_commit,
            now=case.now(),
            restart=lambda _root: pytest.fail("late first finalize restarted"),
        )
    assert _snapshot(case.worker) == before


@pytest.mark.parametrize("value", [None, {}, [], "finalized"])
def test_successor_refuses_ambiguous_journal_shapes(tmp_path, monkeypatch, value):
    case = _normal_cycles(tmp_path, monkeypatch)
    (case.worker / "leaf-rotation.json").write_bytes(rotation._canonical(value))
    before = _snapshot(case.worker)
    with pytest.raises(ValueError, match="journal state"):
        case.install(case.second)
    assert _snapshot(case.worker) == before


@pytest.mark.parametrize(
    "target", ["archive-directory", "archive-file", "backup-directory", "journal"]
)
def test_successor_refuses_symlink_paths(tmp_path, monkeypatch, target):
    case = _normal_cycles(tmp_path, monkeypatch)
    old = json.loads((case.first / "rotation.json").read_bytes())
    path = {
        "archive-directory": case.worker / "leaf-rotation-finalized",
        "archive-file": case.worker / "leaf-rotation-finalized" / f'{old["rotationId"]}.json',
        "backup-directory": case.worker / "leaf-rotation-backup",
        "journal": case.worker / "leaf-rotation.json",
    }[target]
    preserved = path.with_name(path.name + ".preserved")
    path.rename(preserved)
    try:
        path.symlink_to(preserved, target_is_directory=preserved.is_dir())
    except OSError as error:
        pytest.skip(
            f"symlink capability unavailable: {error.winerror if os.name == 'nt' else error.errno}"
        )
    before = _snapshot(case.worker)
    with pytest.raises(ValueError):
        case.install(case.second)
    assert _snapshot(case.worker) == before
