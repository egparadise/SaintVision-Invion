"""Python contract units use explicitly synthetic floor signatures, never runtime evidence.

Actual journal/process/TLS acceptance is the separate CI native fixed proof.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

import pytest
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

from test_lan_leaf_rotation import _legacy_fixture as _fixture, fingerprint, lan_pilot, rotation
import peer_policy_phase as phase
from worker_config import no_rotation_mutation, rotation_mutation_guard


def synthetic_floor(root, scope, key, *, nonce="a" * 64):
    raw = (root / "peer-policy.json").read_bytes()
    value = dict(schemaVersion="saintvision-node-peer-policy-floor:2", tenantId=scope["tenantId"], nodeId=scope["nodeId"],
                 recoveryEpoch=scope["recoveryEpoch"], nonce=nonce, observedAt=int(datetime.now(timezone.utc).timestamp()),
                 certificateDER_SHA256=fingerprint(x509.load_pem_x509_certificate((root / "node-cert.pem").read_bytes())),
                 peerPolicyVersion=phase.strict(raw)["version"], peerPolicySHA256=phase.digest(raw),
                 floorSHA256=phase.digest(b"synthetic unit floor"), journalIdentitySHA256=phase.digest(b"synthetic unit identity"),
                 journalUID=0, servingPID=1, servingProcessSHA256=phase.digest(b"synthetic unit process"), servingExecutableSHA256=phase.digest(b"SYNTHETIC UNIT EXECUTABLE BYTES"), plainServingProcess=True)
    return {**value, "nodeSignature": key.sign(phase.DOMAIN + phase.floor_canonical(value)).hex()}


def candidate(tmp_path, *, peer_version=7):
    f = _fixture(tmp_path, now=datetime.now(timezone.utc).replace(microsecond=0))
    raw = (f.worker / "peer-policy.json").read_bytes()
    policy = phase.strict(raw)
    policy["version"] = peer_version
    (f.worker / "peer-policy.json").write_bytes(phase.canonical(policy))
    scope = {"tenantId": f.manifest["tenantId"], "nodeId": f.manifest["nodeId"], "recoveryEpoch": f.manifest["recoveryEpoch"]}
    observation = synthetic_floor(f.worker, scope, f.node_key)
    kwargs = dict(state={"tenantId": scope["tenantId"], "epoch": scope["recoveryEpoch"]},
                  node={"nodeId": scope["nodeId"], "nodeIP": f.manifest["nodeIP"]},
                  current_node=f.current_node, current_control=f.current_control, control_key=f.control_key,
                  public_key=f.node_key.public_key(), ca_key=f.issuer_key, intermediate=f.issuer, chain_raw=f.chain,
                  revocations=set(), now=f.now, current_version=3, overlap_seconds=3600, leaf_valid_seconds=21600,
                  rotation_id="b" * 32, peer_floor_observation=observation, peer_floor_nonce=observation["nonce"],
                  current_policy_raw=(f.worker / "peer-policy.json").read_bytes(), current_node_raw=(f.worker / "node-cert.pem").read_bytes())
    return f, kwargs


def test_normal_generator_uses_independent_peer_and_channel_generations(tmp_path):
    f, kwargs = candidate(tmp_path)
    raw, manifest, files = lan_pilot._write_rotation_public_material(tmp_path / "normal", **kwargs)
    assert manifest["schemaVersion"] == phase.SCHEMA
    assert [manifest[k] for k in ("currentChannelVersion", "targetChannelVersion")] == [3, 4]
    assert [manifest[k] for k in ("currentPeerPolicyVersion", "overlapPeerPolicyVersion", "finalPeerPolicyVersion")] == [7, 8, 9]
    assert files["previous-peer-policy.json"] == kwargs["current_policy_raw"]
    assert set(files) == set(rotation.FILE_NAMES) | set(phase.EXTRA_FILES)
    assert rotation.validate_bundle(tmp_path / "normal", f.worker, now=f.now)["proposalDigest"] == phase.digest(raw)
    from jsonschema import Draft202012Validator
    schema = json.loads((Path(__file__).resolve().parents[1] / "deploy/lan/plain-peer-phase-v3.schema.json").read_bytes())
    Draft202012Validator({**schema, "$ref": "#/$defs/Proposal"}).validate(manifest)
    Draft202012Validator({**schema, "$ref": "#/$defs/FloorObservation"}).validate(kwargs["peer_floor_observation"])


@pytest.mark.parametrize("fault", ["nonce", "signature", "stale", "cp-hash", "overflow", "expired-current"])
def test_preparation_refuses_unknown_actual_floor_before_any_output(tmp_path, fault):
    f, kwargs = candidate(tmp_path, peer_version=phase.MAX_VERSION - 1 if fault == "overflow" else 7)
    if fault == "nonce": kwargs["peer_floor_nonce"] = "b" * 64
    elif fault == "signature": kwargs["peer_floor_observation"]["nodeSignature"] = "0" * 128
    elif fault == "stale": kwargs["now"] = datetime.fromtimestamp(kwargs["peer_floor_observation"]["observedAt"] + 121, timezone.utc)
    elif fault == "cp-hash": kwargs["current_policy_raw"] += b" "
    elif fault == "expired-current":
        kwargs["now"] = f.current_control.not_valid_after_utc + timedelta(seconds=1)
    with pytest.raises((ValueError, InvalidSignature)):
        lan_pilot._write_rotation_public_material(tmp_path / "rejected", **kwargs)
    assert not (tmp_path / "rejected").exists()
    assert not (f.worker / "leaf-rotation.json").exists()


@pytest.mark.parametrize("operation", [rotation.install, rotation.rollback])
def test_legacy_live_mutation_is_refused_without_restart_or_old_bytes(tmp_path, operation):
    f = _fixture(tmp_path)
    before = {p.name: p.read_bytes() for p in f.worker.iterdir()}
    with pytest.raises(ValueError, match="Legacy"):
        operation(f.bundle, f.worker, now=f.now, restart=lambda _: pytest.fail("legacy restart"))
    assert {p.name: p.read_bytes() for p in f.worker.iterdir()} == before


@pytest.mark.parametrize("state", ["installing", "installed", "restarted", "finalizing", "finalized", "unknown"])
def test_generic_installer_and_rollback_guard_preserves_every_leaf_state(tmp_path, state):
    path = tmp_path / "leaf-rotation.json"
    raw = phase.canonical(dict(phase=state, publicationIntent=True))
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="forward-only"):
        no_rotation_mutation(tmp_path)
    assert path.read_bytes() == raw


def test_native_fixed_mode_is_early_failing_gate_with_two_real_cycles():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/core.yml").read_text("utf-8")
    assert workflow.index("name: FLEET5 fixed native Go two-cycle proof") < workflow.index("name: Start digest-pinned product")
    source = (root / "tests/proofs/run_fleet5_peer_phase_fixed_probe.py").read_text("utf-8")
    assert "completedNormalCycles\"] == 2" in source
    assert "[7, 8, 9, 10, 11]" in source
    assert "productionDockerOwnershipAssessed=False" in source
    assert "actualPostgresCASAssessed=False" in source


def test_actual_native_heartbeat_request_matches_shared_contract_and_base64_is_rejected():
    import base64
    import importlib.util
    from jsonschema import Draft202012Validator
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('fixed_native_request_producer', root / 'tests/proofs/run_fleet5_peer_phase_fixed_probe.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    schema = json.loads((root / 'contracts/v1alpha1/core.schema.json').read_bytes())
    validator = Draft202012Validator({**schema, '$ref':'#/$defs/NodeProbeInput'})
    actual = json.loads(module.heartbeat_request())
    validator.validate(actual)
    assert len(actual['nonce']) == 64
    invalid = {'nonce':base64.b64encode(bytes(range(32))).decode()}
    assert list(validator.iter_errors(invalid))


def test_generic_mutation_guard_serializes_with_leaf_writer_and_keeps_stale_lock(tmp_path):
    with rotation_mutation_guard(tmp_path):
        with rotation_mutation_guard(tmp_path):
            assert (tmp_path / "leaf-rotation.lock").exists()
        with pytest.raises(ValueError, match="Node lock"):
            with rotation._exclusive(tmp_path / "leaf-rotation.lock"):
                pytest.fail("concurrent leaf writer admitted")
    lock = tmp_path / "leaf-rotation.lock"
    lock.write_bytes(b"unknown prior owner")
    with pytest.raises(ValueError, match="Node lock"):
        with rotation_mutation_guard(tmp_path):
            pytest.fail("stale lock stolen")
    assert lock.read_bytes() == b"unknown prior owner"


@pytest.mark.parametrize("fault", ["missing-member", "unknown-member", "nonce", "cp-policy", "storage", "stale"])
def test_complete_cohort_floor_preflight_blocks_before_any_proposal_or_cas(tmp_path, monkeypatch, fault):
    from test_lan_leaf_rotation import _batch_inputs, NODE_ID_2
    from peer_phase_unit_fixtures import install_unit_adapters
    f, key2, _cert2, _rows, args = _batch_inputs(tmp_path, monkeypatch)
    adapter = install_unit_adapters(monkeypatch, tmp_path)
    adapter['refresh'](args)
    del args._unit_keys  # frozen independently supplied synthetic observations
    path = args.peer_floor_observations / (NODE_ID_2 + '.json')
    if fault == 'missing-member': path.unlink()
    elif fault == 'unknown-member': (args.peer_floor_observations / 'unconfigured.json').write_bytes(path.read_bytes())
    elif fault == 'nonce': args.peer_floor_nonce = 'f' * 64
    elif fault == 'cp-policy':
        cp = args.state / 'nodes' / NODE_ID_2 / 'peer-policy.json'
        cp.write_bytes(cp.read_bytes() + b' ')
    else:
        value = phase.strict(path.read_bytes())
        value['plainServingProcess' if fault == 'storage' else 'observedAt'] = False if fault == 'storage' else value['observedAt'] - 121
        body = {k:v for k,v in value.items() if k != 'nodeSignature'}
        value['nodeSignature'] = key2.sign(phase.DOMAIN + phase.floor_canonical(body)).hex()
        path.write_bytes(phase.canonical(value))
    before = {str(p.relative_to(args.state)):p.read_bytes() for p in args.state.rglob('*') if p.is_file()}
    monkeypatch.setattr(lan_pilot,'provision_channel',lambda *a,**k: pytest.fail('CAS before complete preflight'))
    with pytest.raises((ValueError,InvalidSignature)):
        lan_pilot.prepare_leaf_rotation_batch(args)
    assert not args.output.exists()
    assert {str(p.relative_to(args.state)):p.read_bytes() for p in args.state.rglob('*') if p.is_file()} == before
