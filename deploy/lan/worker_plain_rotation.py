"""Normal :3 plain renewal; actual floors and publication intent are mandatory."""
from datetime import datetime, timezone
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization

import peer_policy_phase as phase


def _legacy():
    import worker_leaf_rotation
    return worker_leaf_rotation


def identity(manifest, raw):
    return dict(rotationId=manifest["rotationId"], proposalDigest=phase.digest(raw),
                targetChannelVersion=manifest["targetChannelVersion"])


def _sign(root, body):
    legacy = _legacy()
    private = serialization.load_pem_private_key(legacy._regular(root / "node-key.pem"), password=None)
    return {**body, "nodeSignature": private.sign(phase.canonical(body)).hex()}


def _floor(root, manifest, files):
    legacy = _legacy()
    value = legacy.observe_actual_floor(root, manifest, files)
    certificate = (files["previous-node-cert.pem"] if value.get("certificateDER_SHA256") == manifest["currentNodeCertificateSHA256"]
                   else files["node-cert.pem"])
    phase.verify_floor(value, certificate, manifest)
    return value


def _target(root, record=None):
    value = _legacy().floor_target_context(root)
    if record is not None and value != record["targetContext"]:
        raise ValueError("Plain renewal container/volume ownership changed; preserve state")
    return value


def _record(root):
    legacy = _legacy()
    path = root / "leaf-rotation.json"
    return phase.strict(legacy._regular(path)) if path.exists() or path.is_symlink() else None


def install(bundle, worker_root, *, restart, now=None, kill=lambda point: None, superseded_bundle=None):
    legacy = _legacy()
    now = now or datetime.now(timezone.utc)
    root = Path(worker_root)
    if root.is_symlink() or not root.is_dir() or superseded_bundle is not None:
        raise ValueError("Normal :3 requires existing owned state; partial/offline supersession is blocked")
    with legacy._exclusive(root / "leaf-rotation.lock"):
        record = _record(root)
        raw = legacy._regular(Path(bundle) / "rotation.json")
        proposed = phase.strict(raw)
        if record and record.get("rotationId") != proposed["rotationId"]:
            validated = legacy.validate_bundle(bundle, root, now=now, installed=False)
            legacy._finalized_successor(root, record, validated, now=now)
            record = None
        if record and record.get("phase") in {"finalizing", "finalized"}:
            raise ValueError("Final phase is owned by exact finalize replay; overlap reinstall refused")
        validated = legacy.validate_bundle(bundle, root, now=now, installed=None if record else False)
        manifest, files = validated["manifest"], validated["files"]
        frozen = identity(manifest, raw)
        if record and (record.get("peerSchemaVersion") != 3 or any(record.get(k) != v for k, v in frozen.items())):
            raise ValueError("Only the exact normal :3 proposal may resume")
        phase.validate_policy(files["peer-policy-overlap.json"], manifest, "overlap", now=now, before_write=True)
        phase.validate_policy(files["peer-policy-final.json"], manifest, "final", now=now, before_write=True)
        target = _target(root, record)
        observed = _floor(root, manifest, files)  # missing/mismatch/unsupported image BLOCKS before mutation
        observed_phase = next((name for name in ("current", "overlap", "final")
                               if (observed["peerPolicyVersion"], observed["peerPolicySHA256"]) ==
                               (manifest[name + "PeerPolicyVersion"], manifest[name + "PeerPolicySHA256"])), None)
        if observed_phase is None or observed_phase == "final":
            raise ValueError("Actual floor is outside this install phase; do not recompute generations")
        if record is None:
            if observed_phase != "current" or observed["certificateDER_SHA256"] != manifest["currentNodeCertificateSHA256"]:
                raise ValueError("Initial actual pre-floor/current DER differs")
            backup = root / "leaf-rotation-backup" / manifest["rotationId"]
            legacy._owned_directory(backup.parent)
            legacy._owned_directory(backup)
            for name in ("node-cert.pem", "peer-policy.json"):
                body = legacy._regular(root / name)
                if (backup / name).exists() and legacy._regular(backup / name) != body:
                    raise ValueError("Prior public material backup collision")
                if not (backup / name).exists():
                    legacy._atomic(backup / name, body)
            # This conservative durable barrier PRECEDES every host/live policy
            # exposure. Never infer rollback permission from a later old floor.
            record = {**frozen, "phase": "installing", "restartRequired": True,
                      "peerSchemaVersion": 3, "publicationIntent": True,
                      "peerPhaseBinding": phase.binding(manifest),
                      "prePeerFloor": observed, "targetContext": target}
            legacy._atomic(root / "leaf-rotation.json", phase.canonical(record))
            kill("after-publication-intent")
        if (record.get("publicationIntent") is not True or record.get("peerSchemaVersion") != 3
                or record.get("peerPhaseBinding") != phase.binding(manifest)):
            raise ValueError("Frozen publication intent differs; unknown state is blocked")
        phase.verify_floor(record["prePeerFloor"], files["previous-node-cert.pem"], manifest, fresh=False)
        phase.match_floor(record["prePeerFloor"], manifest, "current")
        if record.get("phase") == "restarted":
            phase.match_floor(observed, manifest, "overlap")
            return record["receipt"]
        if record.get("phase") not in {"installing", "installed"}:
            raise ValueError("Unknown normal :3 state is blocked")
        _target(root, record)
        kill("before-install")
        legacy._atomic(root / "node-cert.pem", files["node-cert.pem"])
        kill("after-node-certificate")
        legacy._atomic(root / "peer-policy.json", files["peer-policy-overlap.json"])
        kill("after-overlap-publication")
        record = {**record, "phase": "installed"}
        legacy._atomic(root / "leaf-rotation.json", phase.canonical(record))
        kill("before-restart")
        restart(root)
        kill("after-restart-before-ack")
        _target(root, record)
        post = _floor(root, manifest, files)
        phase.match_floor(post, manifest, "overlap")
        if post["certificateDER_SHA256"] != manifest["nextNodeCertificateSHA256"]:
            raise ValueError("Actual restarted Node DER differs")
        body = {"schemaVersion": phase.SCHEMA, **frozen, "nodeId": manifest["nodeId"],
                "installedNodeCertificateSHA256": manifest["nextNodeCertificateSHA256"],
                "installedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "restartObserved": True,
                **phase.binding(manifest), "prePeerFloor": record["prePeerFloor"], "postPeerFloor": post}
        receipt = _sign(root, body)
        record = {**record, "phase": "restarted", "restartRequired": False, "receipt": receipt}
        legacy._atomic(root / "leaf-rotation.json", phase.canonical(record))
        return receipt


def finalize(bundle, worker_root, commit_receipt, *, restart, now=None):
    legacy = _legacy()
    now = now or datetime.now(timezone.utc)
    root = Path(worker_root)
    with legacy._exclusive(root / "leaf-rotation.lock"):
        record = _record(root)
        if not record or record.get("peerSchemaVersion") != 3 or record.get("phase") not in {"restarted", "finalizing", "finalized"}:
            raise ValueError("Exact normal :3 overlap/final state required")
        validated = legacy.validate_bundle(bundle, root, now=now, installed=True, finalized=record["phase"] == "finalized")
        manifest, files = validated["manifest"], validated["files"]
        raw = legacy._regular(Path(bundle) / "rotation.json")
        expected = phase.commit_body(manifest, raw)
        receipt_raw = legacy._regular(Path(commit_receipt))
        receipt = phase.strict(receipt_raw)
        if set(receipt) != {*expected, "controlSignature"} or any(receipt[k] != v for k, v in expected.items()):
            raise ValueError("CP commit does not bind exact final peer P+2/hash")
        from cryptography import x509
        x509.load_pem_x509_certificate(files["control-cert.pem"]).public_key().verify(bytes.fromhex(receipt["controlSignature"]), phase.canonical(expected))
        if any(record.get(k) != v for k, v in identity(manifest, raw).items()):
            raise ValueError("Finalization proposal differs")
        _target(root, record)
        observed = _floor(root, manifest, files)
        overlap = (manifest["overlapPeerPolicyVersion"], manifest["overlapPeerPolicySHA256"])
        final = (manifest["finalPeerPolicyVersion"], manifest["finalPeerPolicySHA256"])
        actual = (observed["peerPolicyVersion"], observed["peerPolicySHA256"])
        if actual not in {overlap, final}:
            raise ValueError("Actual floor is outside exact overlap/final phases")
        if record["phase"] == "finalized" and actual != final:
            raise ValueError("Finalized journal disagrees with actual final floor")
        if actual == overlap:
            phase.validate_policy(files["peer-policy-final.json"], manifest, "final", now=now, before_write=True)
            record = {**record, "phase": "finalizing", "restartRequired": True}
            legacy._atomic(root / "leaf-rotation.json", phase.canonical(record))
            legacy._atomic(root / "peer-policy.json", files["peer-policy-final.json"])
            restart(root)
            _target(root, record)
            observed = _floor(root, manifest, files)
            phase.match_floor(observed, manifest, "final")
        if legacy._regular(root / "peer-policy.json") != files["peer-policy-final.json"]:
            raise ValueError("Exact final bytes differ; never reinstall overlap")
        record = {**record, "phase": "finalized", "restartRequired": False, "finalPeerFloor": observed}
        raw_record = (legacy._regular(root / "leaf-rotation.json") if _record(root).get("phase") == "finalized"
                      else phase.canonical(record))
        if phase.strict(raw_record) != record:
            # Exact replay retains the first final observation and original bytes.
            prior = phase.strict(raw_record)
            if prior.get("phase") == "finalized":
                phase.match_floor(prior["finalPeerFloor"], manifest, "final")
                record = prior
            else:
                raise ValueError("Final journal differs")
        archive_dir = root / "leaf-rotation-finalized"
        legacy._owned_directory(archive_dir)
        evidence = legacy._finalized_evidence(validated, raw, receipt_raw, record, raw_record)
        legacy._immutable(archive_dir / (manifest["rotationId"] + ".json"), evidence, publish=True)
        if _record(root).get("phase") != "finalized":
            legacy._atomic(root / "leaf-rotation.json", raw_record)
        return dict(rotationId=manifest["rotationId"], finalized=True, channelVersion=manifest["targetChannelVersion"],
                    finalPeerPolicyVersion=manifest["finalPeerPolicyVersion"], finalPeerPolicySHA256=manifest["finalPeerPolicySHA256"])


def rollback(*args, **kwargs):
    raise ValueError("Normal :3 publication intent is forward-only; old restoration is not authorized by a failed start, phase flag or old certificate")
