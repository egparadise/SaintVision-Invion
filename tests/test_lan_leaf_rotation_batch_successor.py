"""Public normal batch lifecycle, with real crypto and a fixture channel store."""

from argparse import Namespace
from datetime import datetime, timedelta, timezone
import json
import hashlib
import os
import sys
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID

from test_lan_leaf_rotation import (
    NODE_ID,
    NODE_ID_2,
    _batch_inputs,
    _batch_worker,
    fingerprint,
    lan_pilot,
    rotation,
)


def _batch_case(tmp_path, monkeypatch, *, node_count=2):
    clock = [datetime(2026, 11, 5, 0, 0, tzinfo=timezone.utc)]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0].astimezone(tz) if tz else clock[0].replace(tzinfo=None)

    monkeypatch.setattr(lan_pilot, "datetime", Clock)
    fixture, key2, cert2, rows, args = _batch_inputs(tmp_path, monkeypatch, now=clock[0])
    args.leaf_valid_seconds = 6 * 86400
    args.safety_window_hours = 48
    identities = [(NODE_ID, fixture.node_key, fixture.current_node), (NODE_ID_2, key2, cert2)]
    state = lan_pilot.load(args.state)
    for index in range(2, node_count):
        node_id = "nod_01H" + ("XWV"[index - 2] * 23)
        address = f"192.168.45.{81 + index}"
        key = Ed25519PrivateKey.generate()
        cert = lan_pilot.issue(
            fixture.issuer_key,
            fixture.issuer,
            key.public_key(),
            lan_pilot.node_uri(lan_pilot.NodePrincipal(state["tenantId"], node_id), state["epoch"]),
            address=address,
            now=clock[0] - timedelta(minutes=1),
            valid_for=timedelta(minutes=5),
        )
        node = {
            "nodeId": node_id,
            "nodeIP": address,
            "nodePort": 18443,
            "provisioned": True,
            "coLocatedWithControlPlane": False,
        }
        state["nodes"].append(node)
        policy_dir = args.state / "nodes" / node_id
        policy_dir.mkdir(parents=True)
        public_dir = args.state / "public" / "nodes" / node_id
        public_dir.mkdir(parents=True)
        (public_dir / "node-cert.pem").write_bytes(lan_pilot.pem(cert))
        version = 7 + 4 * index
        (policy_dir / "peer-policy.json").write_text(
            json.dumps(
                {
                    "version": version,
                    "tenantId": state["tenantId"],
                    "nodeId": node_id,
                    "recoveryEpoch": state["epoch"],
                    "expiresAt": fixture.current_control.not_valid_after_utc.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "clientFingerprints": [fingerprint(fixture.current_control)],
                }
            ),
            encoding="utf-8",
        )
        rows[node_id] = (
            version,
            fingerprint(cert),
            cert.not_valid_after_utc,
            True,
            f"https://{address}:18443",
        )
        csr_path = tmp_path / f"{node_id}.csr"
        csr_path.write_bytes(
            x509.CertificateSigningRequestBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, node_id)]))
            .sign(key, None)
            .public_bytes(serialization.Encoding.PEM)
        )
        args.csr.append(csr_path)
        identities.append((node_id, key, cert))
    (args.state / "private-state.json").write_text(json.dumps(state), encoding="utf-8")
    workers = {}
    for node_id, key, cert in identities:
        state = lan_pilot.load(args.state)
        node = lan_pilot.node_by_id(state, node_id)
        policy = json.loads(lan_pilot.node_policy_path(args.state, state, node).read_bytes())
        workers[node_id] = _batch_worker(
            tmp_path,
            node_id,
            chain=fixture.chain,
            key=key,
            certificate=cert,
            policy=policy,
            node_id=node_id,
        )

    def complete(bundle, cycle):
        for node_id, worker in workers.items():
            receipt = rotation.install(
                bundle / f"nodes/{node_id}", worker, now=clock[0], restart=lambda _root: None
            )
            receipt_path = tmp_path / f"{cycle}-{node_id}-installed.json"
            receipt_path.write_bytes(rotation._canonical(receipt))
            lan_pilot.stage_leaf_rotation_batch(
                Namespace(state=args.state, bundle=bundle, node_receipt=receipt_path)
            )
        commits = tmp_path / f"commits-{cycle}"
        lan_pilot.commit_leaf_rotation_batch(
            Namespace(state=args.state, bundle=bundle, output=commits)
        )
        for node_id, worker in workers.items():
            rotation.finalize(
                bundle / f"nodes/{node_id}",
                worker,
                commits / f"{node_id}.json",
                now=clock[0],
                restart=lambda _root: None,
            )

    def proofs(bundle, cycle):
        receipts = []
        for node_id, worker in workers.items():
            value = rotation.attest_finalized(bundle / f"nodes/{node_id}", worker, now=clock[0])
            target = tmp_path / f"{cycle}-{node_id}-finalized.json"
            target.write_bytes(rotation._canonical(value))
            receipts.append(target)
        retirement = Namespace(state=args.state, bundle=bundle, finalized_receipt=receipts)
        return retirement

    def retire(bundle, cycle):
        retirement = proofs(bundle, cycle)
        lan_pilot.retire_leaf_rotation_batch(retirement)
        return retirement

    return Namespace(
        args=args,
        clock=clock,
        workers=workers,
        rows=rows,
        complete=complete,
        retire=retire,
        proofs=proofs,
        fixture=fixture,
    )


@pytest.mark.parametrize("node_count", [2, 5])
def test_two_distinct_normal_multi_node_batches_preserve_prior_generation(
    tmp_path, monkeypatch, node_count
):
    case = _batch_case(tmp_path, monkeypatch, node_count=node_count)
    keys = {
        node_id: (worker / "node-key.pem").read_bytes() for node_id, worker in case.workers.items()
    }
    lan_pilot.prepare_leaf_rotation_batch(case.args)
    case.complete(case.args.output, 0)
    first_raw, first, old_bundles = lan_pilot._batch_material(case.args.output)
    prior_journal = (case.args.state / "leaf-rotation-batch.json").read_bytes()
    assert json.loads(prior_journal)["phase"] == "switched"
    retirement = case.retire(case.args.output, 0)
    prior_worker_history = {
        node_id: {
            str(p.relative_to(worker)): p.read_bytes()
            for directory in (worker / "leaf-rotation-backup", worker / "leaf-rotation-finalized")
            for p in directory.rglob("*")
            if p.is_file()
        }
        for node_id, worker in case.workers.items()
    }
    archive = case.args.state / "leaf-rotation-finalized" / f'{first["batchId"]}.json'
    prior_archive = archive.read_bytes()
    assert json.loads(prior_archive)["journalRaw"].encode() == prior_journal
    lan_pilot.retire_leaf_rotation_batch(retirement)
    assert archive.read_bytes() == prior_archive
    # Old same-batch public replays keep the verified terminal generation.
    lan_pilot.prepare_leaf_rotation_batch(case.args)
    lan_pilot.commit_leaf_rotation_batch(
        Namespace(state=case.args.state, bundle=case.args.output, output=tmp_path / "commits-0")
    )
    assert lan_pilot._load_batch_journal(case.args.state)["phase"] == "finalized"
    case.clock[0] += timedelta(days=4)
    second_args = Namespace(**{**vars(case.args), "output": tmp_path / "second-normal-batch"})
    lan_pilot.prepare_leaf_rotation_batch(second_args)
    _, second, new_bundles = lan_pilot._batch_material(second_args.output)
    assert first["batchId"] != second["batchId"]
    assert first["nextControlCertificateSHA256"] == second["currentControlCertificateSHA256"]
    for node_id in case.workers:
        old, new = old_bundles[node_id][1], new_bundles[node_id][1]
        assert old["targetChannelVersion"] == new["currentChannelVersion"]
        assert old["nextNodeCertificateSHA256"] == new["currentNodeCertificateSHA256"]
    case.complete(second_args.output, 1)
    case.retire(second_args.output, 1)
    assert archive.read_bytes() == prior_archive
    assert len(list(archive.parent.glob("*.json"))) == 2
    for node_id, worker in case.workers.items():
        assert all(
            (worker / name).read_bytes() == raw
            for name, raw in prior_worker_history[node_id].items()
        )
        assert (worker / "node-key.pem").read_bytes() == keys[node_id]
        assert (
            fingerprint(x509.load_pem_x509_certificate((worker / "node-cert.pem").read_bytes()))
            == new_bundles[node_id][1]["nextNodeCertificateSHA256"]
        )
        assert (worker / "leaf-rotation-backup" / first["batchId"] / "node-cert.pem").exists()
        assert len(list((worker / "leaf-rotation-finalized").glob("*.json"))) == 2
    destination = os.environ.get("INV_CONSECUTIVE_BATCH_EVIDENCE_DIR")
    if destination:
        Path(destination, f"two-normal-batches-{node_count}-nodes.json").write_text(
            json.dumps(
                {
                    "schema": "fleet5-consecutive-normal-batch-proof:1",
                    "fixtureOnly": True,
                    "physicalClockChanged": False,
                    "nodeCount": node_count,
                    "first": first,
                    "second": second,
                    "firstProposals": {n: b[1] for n, b in old_bundles.items()},
                    "secondProposals": {n: b[1] for n, b in new_bundles.items()},
                    "priorSwitchedJournalSHA256": hashlib.sha256(prior_journal).hexdigest(),
                    "priorArchiveSHA256": hashlib.sha256(prior_archive).hexdigest(),
                    "oldArchiveUnchanged": True,
                    "keysUnchanged": True,
                    "allNodeFinalizedArchivesPreserved": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def _completed(tmp_path, monkeypatch):
    case = _batch_case(tmp_path, monkeypatch)
    lan_pilot.prepare_leaf_rotation_batch(case.args)
    case.complete(case.args.output, 0)
    case.retirement = case.proofs(case.args.output, 0)
    return case


def _snapshot(path):
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}


def test_public_attestation_and_retirement_cli_accept_only_signed_current_proofs(
    tmp_path, monkeypatch, capsys
):
    case = _completed(tmp_path, monkeypatch)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return case.clock[0].astimezone(tz) if tz else case.clock[0].replace(tzinfo=None)

    monkeypatch.setattr(rotation, "datetime", Clock)
    capsys.readouterr()
    for node_id, worker in case.workers.items():
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "worker_leaf_rotation.py",
                "attest-finalized",
                "--bundle",
                str(case.args.output / f"nodes/{node_id}"),
                "--worker-root",
                str(worker),
            ],
        )
        rotation.main()
        value = json.loads(capsys.readouterr().out)
        assert value["nodeId"] == node_id
        assert value["nodeSignature"]
    command = [
        "lan_pilot.py",
        "--state",
        str(case.args.state),
        "retire-leaf-rotation-batch",
        "--bundle",
        str(case.args.output),
    ]
    for path in case.retirement.finalized_receipt:
        command.extend(["--finalized-receipt", str(path)])
    monkeypatch.setattr(sys, "argv", command)
    lan_pilot.main()
    result = json.loads(capsys.readouterr().out)
    assert result["phase"] == "finalized"
    assert result["nodeCount"] == 2


@pytest.mark.parametrize("phase", ["prepared", "staging", "staged", "unknown", None])
def test_retirement_refuses_uncommitted_partial_or_unknown_batch(tmp_path, monkeypatch, phase):
    case = _completed(tmp_path, monkeypatch)
    journal_path = case.args.state / "leaf-rotation-batch.json"
    journal = json.loads(journal_path.read_bytes())
    journal["phase"] = phase
    journal_path.write_bytes(rotation._canonical(journal))
    before = _snapshot(case.args.state)
    with pytest.raises(ValueError):
        lan_pilot.retire_leaf_rotation_batch(case.retirement)
    assert _snapshot(case.args.state) == before


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "duplicate",
        "unsigned-boolean",
        "wrong-node",
        "signature",
        "proof-phase",
        "cp-not-switched",
        "cp-key",
        "node-leaf",
        "node-policy",
        "ca-pin",
        "epoch",
        "members",
        "version",
        "disabled",
        "endpoint",
        "expiry",
        "archive",
        "archive-next",
    ],
)
def test_retirement_refuses_ambiguous_or_tampered_proof_and_current_authority(
    tmp_path, monkeypatch, fault
):
    case = _completed(tmp_path, monkeypatch)
    _, batch, bundles = lan_pilot._batch_material(case.args.output)
    target = case.retirement.finalized_receipt[0]
    value = json.loads(target.read_bytes())
    state = lan_pilot.load(case.args.state)
    if fault == "missing":
        case.retirement.finalized_receipt.pop()
    elif fault == "duplicate":
        case.retirement.finalized_receipt.append(target)
    elif fault in {"unsigned-boolean", "wrong-node", "signature", "proof-phase"}:
        if fault == "unsigned-boolean":
            value = {"nodeId": value["nodeId"], "finalized": True}
        elif fault == "wrong-node":
            value["nodeId"] = NODE_ID_2
        elif fault == "signature":
            value["nodeSignature"] = "0" * 128
        else:
            proof = json.loads(value["evidence"])
            proof["journal"]["phase"] = "restarted"
            value["evidence"] = json.dumps(proof)
        target.write_bytes(rotation._canonical(value))
    elif fault == "cp-not-switched":
        (case.args.state / "control-cert.pem").write_bytes(
            lan_pilot.pem(case.fixture.current_control)
        )
    elif fault == "cp-key":
        (case.args.state / "control-key.pem").write_bytes(
            lan_pilot.private_pem(Ed25519PrivateKey.generate())
        )
    elif fault in {"node-leaf", "node-policy"}:
        node = lan_pilot.node_by_id(state, NODE_ID)
        if fault == "node-leaf":
            lan_pilot.node_certificate_path(case.args.state, state, node).write_bytes(
                lan_pilot.pem(case.fixture.current_node)
            )
        else:
            lan_pilot.node_policy_path(case.args.state, state, node).write_bytes(
                bundles[NODE_ID][2]["peer-policy-overlap.json"]
            )
    elif fault in {"ca-pin", "epoch", "members"}:
        if fault == "ca-pin":
            state["caBundleSHA256"] = "0" * 64
        elif fault == "epoch":
            state["epoch"] = "wrong-epoch"
        else:
            state["nodes"] = state["nodes"][:1]
        (case.args.state / "private-state.json").write_text(json.dumps(state), encoding="utf-8")
    elif fault in {"version", "disabled", "endpoint", "expiry"}:
        row = list(case.rows[NODE_ID])
        field, changed = {
            "version": (0, row[0] + 1),
            "disabled": (3, False),
            "endpoint": (4, "https://192.168.45.99:18443"),
            "expiry": (2, row[2] - timedelta(seconds=1)),
        }[fault]
        row[field] = changed
        case.rows[NODE_ID] = tuple(row)
    else:
        archive = lan_pilot._batch_archive_path(case.args.state, batch)
        if fault == "archive-next":
            archive = archive.with_name(archive.name + ".next")
        archive.write_bytes(b"preserve colliding immutable evidence")
    before = _snapshot(case.args.state)
    with pytest.raises((ValueError, KeyError, InvalidSignature)):
        lan_pilot.retire_leaf_rotation_batch(case.retirement)
    assert _snapshot(case.args.state) == before


@pytest.mark.parametrize("fault", ["phase", "policy", "leaf", "key", "missing-proof"])
def test_worker_attestation_never_promotes_unfinalized_or_inconsistent_state(
    tmp_path, monkeypatch, fault
):
    case = _completed(tmp_path, monkeypatch)
    worker = case.workers[NODE_ID]
    bundle = case.args.output / f"nodes/{NODE_ID}"
    if fault == "phase":
        journal = json.loads((worker / "leaf-rotation.json").read_bytes())
        journal["phase"] = "restarted"
        (worker / "leaf-rotation.json").write_bytes(rotation._canonical(journal))
    elif fault == "policy":
        (worker / "peer-policy.json").write_bytes(
            (bundle / "peer-policy-overlap.json").read_bytes()
        )
    elif fault == "leaf":
        (worker / "node-cert.pem").write_bytes(lan_pilot.pem(case.fixture.current_node))
    elif fault == "key":
        (worker / "node-key.pem").write_bytes(lan_pilot.private_pem(Ed25519PrivateKey.generate()))
    else:
        archive = (
            worker
            / "leaf-rotation-finalized"
            / f'{json.loads((bundle / "rotation.json").read_bytes())["rotationId"]}.json'
        )
        archive.rename(archive.with_suffix(".preserved"))
    before = _snapshot(worker)
    with pytest.raises((ValueError, FileNotFoundError)):
        rotation.attest_finalized(bundle, worker, now=case.clock[0])
    assert _snapshot(worker) == before


def test_retirement_archive_crash_replays_without_reset_or_overwrite(tmp_path, monkeypatch):
    case = _completed(tmp_path, monkeypatch)
    _, batch, _ = lan_pilot._batch_material(case.args.output)
    archive = lan_pilot._batch_archive_path(case.args.state, batch)

    def crash(_point):
        raise RuntimeError("retirement publication crash")

    with pytest.raises(RuntimeError, match="retirement publication"):
        lan_pilot.retire_leaf_rotation_batch(Namespace(**vars(case.retirement), _kill=crash))
    archived_raw = archive.read_bytes()
    assert lan_pilot._load_batch_journal(case.args.state)["phase"] == "switched"
    lan_pilot.retire_leaf_rotation_batch(case.retirement)
    assert archive.read_bytes() == archived_raw
    assert lan_pilot._load_batch_journal(case.args.state)["phase"] == "finalized"


def test_complete_successor_publication_crash_uses_verified_terminal_predecessor(
    tmp_path, monkeypatch
):
    case = _completed(tmp_path, monkeypatch)
    lan_pilot.retire_leaf_rotation_batch(case.retirement)
    terminal_raw = (case.args.state / "leaf-rotation-batch.json").read_bytes()
    case.clock[0] += timedelta(days=4)
    args = Namespace(**{**vars(case.args), "output": tmp_path / "successor-after-crash"})

    def crash(_point):
        raise RuntimeError("successor publication crash")

    with pytest.raises(RuntimeError, match="successor publication"):
        lan_pilot.prepare_leaf_rotation_batch(Namespace(**vars(args), _kill=crash))
    assert (args.output / "batch.json").is_file()
    assert (case.args.state / "leaf-rotation-batch.json").read_bytes() == terminal_raw
    lan_pilot.prepare_leaf_rotation_batch(args)
    assert lan_pilot._load_batch_journal(case.args.state)["phase"] == "prepared"
    case.complete(args.output, 1)
    case.retire(args.output, 1)
    before = _snapshot(case.args.state)
    with pytest.raises(ValueError):
        lan_pilot.retire_leaf_rotation_batch(case.retirement)
    assert _snapshot(case.args.state) == before


def test_retirement_and_successor_refuse_existing_writer_lock(tmp_path, monkeypatch):
    case = _completed(tmp_path, monkeypatch)
    with lan_pilot.exclusive_file(case.args.state / "leaf-rotation.lock"):
        with pytest.raises(ValueError, match="state lock"):
            lan_pilot.retire_leaf_rotation_batch(case.retirement)


@pytest.mark.parametrize(
    "fault", ["archive", "archive-format", "terminal", "terminal-format", "current-node", "members"]
)
def test_successor_refuses_stale_terminal_or_tampered_archive(tmp_path, monkeypatch, fault):
    case = _completed(tmp_path, monkeypatch)
    lan_pilot.retire_leaf_rotation_batch(case.retirement)
    _, batch, _ = lan_pilot._batch_material(case.args.output)
    if fault in {"archive", "archive-format"}:
        archive = lan_pilot._batch_archive_path(case.args.state, batch)
        value = json.loads(archive.read_bytes())
        if fault == "archive":
            value["controlSignature"] = "0" * 128
            archive.write_bytes(rotation._canonical(value))
        else:
            archive.write_text(json.dumps(value, indent=4), encoding="utf-8")
    elif fault in {"terminal", "terminal-format"}:
        journal_path = case.args.state / "leaf-rotation-batch.json"
        value = json.loads(journal_path.read_bytes())
        if fault == "terminal":
            value["batchDigest"] = "0" * 64
            journal_path.write_bytes(rotation._canonical(value))
        else:
            journal_path.write_text(json.dumps(value, indent=4), encoding="utf-8")
    elif fault == "current-node":
        case.rows[NODE_ID] = (42, *case.rows[NODE_ID][1:])
    else:
        state = lan_pilot.load(case.args.state)
        state["nodes"] = state["nodes"][:1]
        (case.args.state / "private-state.json").write_text(json.dumps(state), encoding="utf-8")
    case.clock[0] += timedelta(days=4)
    before = _snapshot(case.args.state)
    with pytest.raises((ValueError, InvalidSignature)):
        lan_pilot.prepare_leaf_rotation_batch(
            Namespace(**{**vars(case.args), "output": tmp_path / "refused-successor"})
        )
    assert _snapshot(case.args.state) == before


@pytest.mark.parametrize(
    "target", ["journal", "archive-directory", "archive-file", "receipt", "bundle-node-directory"]
)
def test_retirement_refuses_redirected_paths(tmp_path, monkeypatch, target):
    case = _completed(tmp_path, monkeypatch)
    _, batch, _ = lan_pilot._batch_material(case.args.output)
    if target in {"archive-file", "archive-directory"}:
        lan_pilot.retire_leaf_rotation_batch(case.retirement)
    path = {
        "journal": case.args.state / "leaf-rotation-batch.json",
        "archive-directory": case.args.state / "leaf-rotation-finalized",
        "archive-file": lan_pilot._batch_archive_path(case.args.state, batch),
        "receipt": case.retirement.finalized_receipt[0],
        "bundle-node-directory": case.args.output / "nodes" / NODE_ID,
    }[target]
    preserved = path.with_name(path.name + ".preserved")
    path.rename(preserved)
    try:
        path.symlink_to(preserved, target_is_directory=preserved.is_dir())
    except OSError:
        pytest.skip("OS cannot create test symlinks")
    before = _snapshot(case.args.state)
    with pytest.raises(ValueError):
        lan_pilot.retire_leaf_rotation_batch(case.retirement)
    assert _snapshot(case.args.state) == before
