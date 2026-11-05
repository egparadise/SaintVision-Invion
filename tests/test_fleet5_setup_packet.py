"""Exercise the nonexecuting packet's settlement gate on disposable fixtures only.

No live state, transport, database, key, Docker or operator environment is used.
The canonical CP verifier and Node proof verifier run against the lifecycle
fixture's temporary files and channel store; results never accept real PCs.
"""

import json
from pathlib import Path

import pytest

from test_lan_leaf_rotation_batch_successor import _batch_case, lan_pilot, rotation


def _unique_json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate proof/archive key")
            value[key] = item
        return value

    return json.loads(raw, object_pairs_hook=unique)


def _snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _fixture(tmp_path, monkeypatch, count=2):
    case = _batch_case(tmp_path, monkeypatch, node_count=count)
    lan_pilot.prepare_leaf_rotation_batch(case.args)
    case.complete(case.args.output, 0)
    case.retire(case.args.output, 0)
    return case


def _settlement(case):
    """Packet algorithm, intentionally limited to the temporary lifecycle fixture.

    Reject orphan/staging artifacts before canonical verification, including
    equal .next bytes. Cleanup requires a separate authorized verified replay.
    The real packet also requires a complete private catalog, current read-only
    channel snapshot, lock/writer exclusion and fresh source/host observations;
    none of those live prerequisites is asserted by this fixture.
    """
    state = lan_pilot.load(case.args.state)
    raw, batch, bundles = lan_pilot._batch_material(case.args.output)
    journal = lan_pilot._load_batch_journal(case.args.state)
    cp_archive = lan_pilot._batch_archive_path(case.args.state, batch)
    expected = {cp_archive}
    roots = [case.args.state, case.args.output, *case.workers.values()]
    if any(list(root.rglob("*.next")) for root in roots):
        raise ValueError("Staging/orphan material blocks settlement, even if byte-equal")
    node_archives = {}
    for node_id, (proposal_raw, _proposal, _files) in bundles.items():
        proposal = _unique_json(proposal_raw)
        archive = case.workers[node_id] / "leaf-rotation-finalized" / (proposal["rotationId"] + ".json")
        node_archives[node_id] = archive
        expected.add(archive)
    found = set()
    for root in [case.args.state, *case.workers.values()]:
        directory = root / "leaf-rotation-finalized"
        for item in directory.iterdir():
            if item.is_symlink() or not item.is_file():
                raise ValueError("Redirected/unknown archive blocks settlement")
            found.add(item)
    if found != expected:
        raise ValueError("Missing/unknown archive blocks settlement")
    archive = _unique_json(cp_archive.read_bytes())
    for name in ("journalRaw", "terminalJournalRaw", "batchManifest"):
        _unique_json(archive[name])
    for value in archive["nodeFinalizations"].values():
        attestation = _unique_json(value)
        proof = _unique_json(attestation["evidence"])
        _unique_json(proof["commitReceipt"])
        _unique_json(proof["journalRaw"])
    # Uses the canonical CP archive shape, original journal/batch bytes,
    # CP signature, every distinct Node signature, current CA/CP/Node public
    # files and the exact enabled channel cohort. psycopg is the fixture store.
    with lan_pilot.psycopg.connect(state["adminDSN"]) as connection:
        verified = lan_pilot._verify_batch_archive(
            case.args.state, state, journal, raw, batch, bundles, connection
        )
    assert verified == cp_archive.read_bytes()
    for node_id, (proposal_raw, _proposal, files) in bundles.items():
        value = _unique_json(archive["nodeFinalizations"][node_id])
        proof = rotation.verify_finalized_attestation(value, proposal_raw, files)
        worker = case.workers[node_id]
        original_receipt = case.args.state.parent / "commits-0" / (node_id + ".json")
        if (
            node_archives[node_id].read_bytes() != value["evidence"].encode()
            or (worker / "leaf-rotation.json").read_bytes() != proof["journalRaw"].encode()
            or (worker / "peer-policy.json").read_bytes() != files["peer-policy-final.json"]
            or (worker / "node-cert.pem").read_bytes() != files["node-cert.pem"]
            or original_receipt.read_bytes() != proof["commitReceipt"].encode()
        ):
            raise ValueError("Current Node files or original byte-bound receipt differ")
    return {"fixtureProofVerified": True, "physicalAcceptance": False, "nodeCount": len(bundles)}


@pytest.mark.parametrize("count", [2, 5])
def test_packet_uses_canonical_signed_finalization_without_mutating_fixture(tmp_path, monkeypatch, count):
    case = _fixture(tmp_path, monkeypatch, count)
    before = _snapshot(tmp_path)
    assert _settlement(case) == {"fixtureProofVerified": True, "physicalAcceptance": False, "nodeCount": count}
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("fault", [
    "missing-cp-archive", "partial-cp-archive", "tampered-cp-signature",
    "duplicate-proof-key", "missing-node-proof", "unknown-node-proof",
    "tampered-node-signature", "missing-node-archive", "unknown-cp-archive",
    "unknown-node-archive", "equal-cp-next", "equal-node-next", "partial-next",
    "bare-finalized", "receipt-byte-change", "current-node-policy", "current-channel",
])
def test_packet_rejects_partial_unknown_tampered_or_unsettled_fixture_without_cleanup(tmp_path, monkeypatch, fault):
    case = _fixture(tmp_path, monkeypatch)
    raw, batch, bundles = lan_pilot._batch_material(case.args.output)
    cp = lan_pilot._batch_archive_path(case.args.state, batch)
    archive = json.loads(cp.read_bytes())
    node = next(iter(bundles))
    worker = case.workers[node]
    node_archive = worker / "leaf-rotation-finalized" / (batch["batchId"] + ".json")
    if fault == "missing-cp-archive":
        cp.unlink()
    elif fault == "partial-cp-archive":
        cp.write_bytes(b'{"schemaVersion":')
    elif fault == "tampered-cp-signature":
        archive["controlSignature"] = "0" * 128
    elif fault == "duplicate-proof-key":
        value = archive["nodeFinalizations"][node]
        archive["nodeFinalizations"][node] = '{"nodeId":"duplicate",' + value[1:]
    elif fault == "missing-node-proof":
        del archive["nodeFinalizations"][node]
    elif fault == "unknown-node-proof":
        archive["nodeFinalizations"]["unknown"] = archive["nodeFinalizations"][node]
    elif fault == "tampered-node-signature":
        value = json.loads(archive["nodeFinalizations"][node])
        value["nodeSignature"] = "0" * 128
        archive["nodeFinalizations"][node] = rotation._canonical(value).decode()
    elif fault == "missing-node-archive":
        node_archive.unlink()
    elif fault.startswith("unknown-"):
        target = cp if fault == "unknown-cp-archive" else node_archive
        target.with_name("unknown.json").write_bytes(target.read_bytes())
    elif fault in {"equal-cp-next", "equal-node-next", "partial-next"}:
        target = node_archive if fault == "equal-node-next" else cp
        target.with_name(target.name + ".next").write_bytes(b"partial" if fault == "partial-next" else target.read_bytes())
    elif fault == "bare-finalized":
        archive = {"phase": "finalized"}
    elif fault == "receipt-byte-change":
        receipt = case.args.state.parent / "commits-0" / (node + ".json")
        receipt.write_bytes(receipt.read_bytes() + b"\n")
    elif fault == "current-node-policy":
        (worker / "peer-policy.json").write_text("{}", encoding="utf-8")
    elif fault == "current-channel":
        old = case.rows[node]
        case.rows[node] = (old[0] + 1, *old[1:])
    if fault in {"tampered-cp-signature", "duplicate-proof-key", "missing-node-proof", "unknown-node-proof", "tampered-node-signature", "bare-finalized"}:
        cp.write_bytes(lan_pilot._canonical_json(archive))
    before = _snapshot(tmp_path)
    # InvalidSignature/KeyError are explicit refusal too, never a successful gate.
    from cryptography.exceptions import InvalidSignature
    with pytest.raises((ValueError, KeyError, InvalidSignature)):
        _settlement(case)
    assert _snapshot(tmp_path) == before


def test_public_nonexecuting_plan_never_fabricates_live_query_counts():
    path = Path(__file__).resolve().parents[1] / "docs/vault/30_Development/Evidence/fleet5-setup-integration-20261105-codex/setup-plan.json"
    plan = json.loads(path.read_bytes())
    assert plan["executed"] is False
    assert plan["actualF5"]["queryExecuted"] is False
    assert all(value is None for value in plan["actualF5"]["counts"].values())
    assert plan["actualF5"]["settlement"] == "UNKNOWN_NO_F5_STATE"
    assert plan["cohort"]["initialization"] == "ALL_FIVE_TOGETHER_AFTER_READY"
    assert plan["cohort"]["arbitraryExpansionAccepted"] is False
    assert plan["topology"]["selectedProposal"] == "FOUR_PLAIN_WORKSPACE_NODES_NO_SHARED_STORAGE_MOUNT"
    assert plan["topology"]["simultaneousComputeAndSharedStorageSupported"] is False
