"""Normal :3 plain renewal; actual floors and publication intent are mandatory."""
from datetime import datetime, timezone
import json
from pathlib import Path
import os
import re
import stat

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
    return {**body, "nodeSignature": private.sign(legacy._canonical(body)).hex()}


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
    if not (path.exists() or path.is_symlink()):
        return None
    value = phase.strict(legacy._regular(path))
    if not isinstance(value, dict) or value.get("phase") not in {"installing", "installed", "restarted", "finalizing", "finalized", "rolled-back"}:
        raise ValueError("Unknown or ambiguous rotation journal state is blocked")
    if 'peerSchemaVersion' in value and (type(value['peerSchemaVersion']) is not int or value['peerSchemaVersion'] != 3):
        raise ValueError('Unknown normal peer schema in journal')
    if value.get("peerSchemaVersion") == 3:
        base = {"rotationId", "proposalDigest", "targetChannelVersion", "phase", "restartRequired", "peerSchemaVersion", "publicationIntent", "peerPhaseBinding", "prePeerFloor", "targetContext"}
        optional = {"receipt", "finalPeerFloor"}
        if (not base <= set(value) <= base | optional or type(value["restartRequired"]) is not bool
                or value["publicationIntent"] is not True
                or (value["phase"] in {"restarted", "finalizing", "finalized"} and "receipt" not in value)
                or (value["phase"] == "finalized" and "finalPeerFloor" not in value)):
            raise ValueError("Unknown normal :3 journal state is blocked")
    return value


def _verify_record(record, manifest, files, raw):
    legacy = _legacy()
    if (any(record.get(k) != v for k, v in identity(manifest, raw).items())
            or record.get("peerPhaseBinding") != phase.binding(manifest)):
        raise ValueError("Frozen publication record differs")
    phase.verify_floor(record["prePeerFloor"], files["previous-node-cert.pem"], manifest, fresh=False)
    phase.match_floor(record["prePeerFloor"], manifest, "current")
    if "receipt" in record:
        receipt = record["receipt"]
        body = {"schemaVersion": phase.SCHEMA, **identity(manifest, raw), "nodeId": manifest["nodeId"],
                "installedNodeCertificateSHA256": manifest["nextNodeCertificateSHA256"],
                "installedAt": receipt.get("installedAt"), "restartObserved": True,
                **phase.binding(manifest), "prePeerFloor": record["prePeerFloor"], "postPeerFloor": receipt.get("postPeerFloor")}
        if not phase.signed_shape(receipt, body, "nodeSignature"):
            raise ValueError("Stored actual installation receipt differs")
        from cryptography import x509
        x509.load_pem_x509_certificate(files["node-cert.pem"]).public_key().verify(bytes.fromhex(receipt["nodeSignature"]), legacy._canonical(body))
        phase.verify_floor(body["postPeerFloor"], files["node-cert.pem"], manifest, fresh=False)
        phase.match_floor(body["postPeerFloor"], manifest, "overlap")
        if body['postPeerFloor']['servingExecutableSHA256'] != record['prePeerFloor']['servingExecutableSHA256']:
            raise ValueError('Stored installation acknowledgement changed serving executable')
    if "finalPeerFloor" in record:
        phase.verify_floor(record["finalPeerFloor"], files["node-cert.pem"], manifest, fresh=False)
        phase.match_floor(record["finalPeerFloor"], manifest, "final")
        if record['finalPeerFloor']['servingExecutableSHA256'] != record['prePeerFloor']['servingExecutableSHA256']:
            raise ValueError('Stored final acknowledgement changed serving executable')


def install(bundle, worker_root, *, restart, now=None, kill=lambda point: None, superseded_bundle=None):
    legacy = _legacy()
    now = now or datetime.now(timezone.utc)
    root = Path(worker_root)
    from worker_config import no_migration
    no_migration(root)
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
            proposal_floor = phase.strict(files['peer-floor-observation.json'])
            for field in ('floorSHA256','journalIdentitySHA256','journalUID','servingProcessSHA256','servingExecutableSHA256'):
                if observed[field] != proposal_floor[field]:
                    raise ValueError('Actual current process/journal differs from the frozen proposal observation')
            if (legacy._regular(root / "node-cert.pem") != files["previous-node-cert.pem"]
                    or legacy._regular(root / "peer-policy.json") != files["previous-peer-policy.json"]):
                raise ValueError("Existing host public bytes differ from the frozen actual current tuple")
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
        _verify_record(record, manifest, files, raw)
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
        if post['servingExecutableSHA256'] != record['prePeerFloor']['servingExecutableSHA256']:
            raise ValueError('Renewal changed serving executable')
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
    from worker_config import no_migration
    no_migration(root)
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
        if not phase.signed_shape(receipt, expected, "controlSignature"):
            raise ValueError("CP commit does not bind exact final peer P+2/hash")
        from cryptography import x509
        x509.load_pem_x509_certificate(files["control-cert.pem"]).public_key().verify(bytes.fromhex(receipt["controlSignature"]), legacy._canonical(expected))
        if any(record.get(k) != v for k, v in identity(manifest, raw).items()):
            raise ValueError("Finalization proposal differs")
        _verify_record(record, manifest, files, raw)
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
        phase.match_floor(observed, manifest, "final")
        if observed['servingExecutableSHA256'] != record['prePeerFloor']['servingExecutableSHA256']:
            raise ValueError('Finalization changed serving executable')
        # Freeze the first authenticated final observation durably before archive
        # publication. A replay's fresh nonce must never change immutable bytes.
        final_floor = record.get("finalPeerFloor", observed)
        if record["phase"] != "finalized":
            frozen = {**record, "phase": "finalizing", "restartRequired": False, "finalPeerFloor": final_floor}
            legacy._atomic(root / "leaf-rotation.json", phase.canonical(frozen))
        record = {**record, "phase": "finalized", "restartRequired": False, "finalPeerFloor": final_floor}
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


def _commit(raw, manifest, manifest_raw, files):
    from cryptography import x509
    value, expected = phase.strict(raw), phase.commit_body(manifest, manifest_raw)
    if not phase.signed_shape(value, expected, "controlSignature"):
        raise ValueError("Exact signed current CP C+1/final phase commitment is required")
    x509.load_pem_x509_certificate(files["control-cert.pem"]).public_key().verify(bytes.fromhex(value["controlSignature"]), _legacy()._canonical(expected))
    return value


def verify_settled(worker_root, *, now=None):
    """Read-only SF1. The generic caller holds the mutation lock; no lock bypass."""
    legacy, root = _legacy(), Path(worker_root)
    now = now or datetime.now(timezone.utc)
    from worker_config import no_migration
    no_migration(root)
    record = _record(root)
    if (not record or record.get("peerSchemaVersion") != 3 or record.get("phase") != "finalized"
            or not isinstance(record.get("rotationId"), str) or not re.fullmatch(r"[0-9a-f]{32}", record["rotationId"])):
        raise ValueError("SF1 requires exact settled finalized :3 history")
    journal_raw = legacy._history_bytes(root / "leaf-rotation.json")
    directory = root / "leaf-rotation-finalized"
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or directory.is_symlink()
            or (os.name != 'nt' and (info.st_uid != os.geteuid() or info.st_mode & 0o022))
            or list(directory.glob('*.next')) or (root / 'leaf-rotation.json.next').exists()):
        raise ValueError("SF1 refuses unsettled or unsafe history")
    archive_raw = legacy._history_bytes(directory / (record["rotationId"] + '.json'), limit=1024*1024)
    archive = phase.strict(archive_raw)
    keys = {"schemaVersion", "journal", "journalRaw", "rotationManifest", "files", "commitReceipt"}
    if (not isinstance(archive, dict) or set(archive) != keys or archive['schemaVersion'] != 'saintvision-node-finalized-rotation:3'
            or archive['journalRaw'].encode() != journal_raw or phase.canonical(archive['journal']) != phase.canonical(record)):
        raise ValueError("SF1 original immutable history differs")
    manifest_raw = archive['rotationManifest'].encode()
    files = {name:raw.encode() for name,raw in archive['files'].items()}
    validated = legacy.validate_bundle(None, root, now=now, installed=True, finalized=True,
                                       _archived_public_material=(manifest_raw, files))
    manifest = validated['manifest']
    _verify_record(record, manifest, files, manifest_raw)
    _commit(archive['commitReceipt'].encode(), manifest, manifest_raw, files)
    if legacy._finalized_evidence(validated, manifest_raw, archive['commitReceipt'].encode(), record, journal_raw) != archive_raw:
        raise ValueError("SF1 canonical original archive binding differs")
    if (legacy._regular(root/'node-cert.pem') != files['node-cert.pem']
            or legacy._regular(root/'peer-policy.json') != files['peer-policy-final.json']
            or legacy._regular(root/'ca.pem') != files['ca.pem']):
        raise ValueError("SF1 current credentials differ from the settled final bytes")
    context = _target(root, record)
    actual = _floor(root, manifest, files)
    phase.match_floor(actual, manifest, 'final')
    if actual['servingExecutableSHA256'] != record['finalPeerFloor']['servingExecutableSHA256']:
        raise ValueError('SF1 serving executable differs from settled history')
    phase.validate_policy(files['peer-policy-final.json'],manifest,'final',now=now,before_write=True)
    from worker_config import credential_archive
    _, credentials = credential_archive(root)
    if (legacy._history_bytes(root/'leaf-rotation.json') != journal_raw
            or legacy._history_bytes(directory/(record['rotationId']+'.json'), limit=1024*1024) != archive_raw
            or _target(root, record) != context):
        raise ValueError("SF1 changed during read-only verification")
    return dict(schemaVersion='saintvision-settled-rotation-verification:1', verified=True,
                archiveSHA256=phase.digest(archive_raw), journalSHA256=phase.digest(journal_raw),
                credentialsSHA256={name:phase.digest(raw) for name,raw in credentials.items()},
                context=context, actualFinalPeerFloor=actual)


def resume_publication(bundle, worker_root, *, commit_receipt=None, now=None):
    """RS1 starts the same stopped CID only; unsigned reads never become an ack."""
    legacy, root = _legacy(), Path(worker_root)
    now = now or datetime.now(timezone.utc)
    from worker_config import no_migration
    import worker_peer_floor as transport
    no_migration(root)
    with legacy._exclusive(root/'leaf-rotation.lock'):
        record = _record(root)
        if not record or record.get('peerSchemaVersion') != 3 or record.get('publicationIntent') is not True:
            raise ValueError('RS1 requires original authenticated durable :3 publication intent')
        phase_name = {'installing':'overlap','installed':'overlap','finalizing':'final','finalized':'final'}.get(record['phase'])
        if phase_name is None:
            raise ValueError('RS1 unknown phase is blocked')
        validated = legacy.validate_bundle(bundle, root, now=now, installed=True, finalized=record['phase']=='finalized')
        manifest, files = validated['manifest'], validated['files']
        raw = legacy._regular(Path(bundle)/'rotation.json')
        _verify_record(record, manifest, files, raw)
        phase.validate_policy(files['peer-policy-'+phase_name+'.json'], manifest, phase_name, now=now, before_write=True)
        if phase_name == 'final':
            if commit_receipt is None:
                raise ValueError('RS1 final start requires the exact signed CP commitment')
            _commit(legacy._regular(Path(commit_receipt)), manifest, raw, files)
        expected = _target(root, record)
        _, _, container, _, _, _ = transport.target(root)
        start_attempted = False
        if not container['State'].get('Running'):
            entries = transport.stopped_entries(root, expected)
            actual_identity = phase.strict(entries['journal/identity.json'])
            if actual_identity != dict(Tenant=manifest['tenantId'],Node=manifest['nodeId'],Epoch=manifest['recoveryEpoch']):
                raise ValueError('RS1 actual durable identity differs')
            actual_floor = phase.strict(entries['journal/.peer-policy'])
            if not isinstance(actual_floor, dict) or set(actual_floor) != {'Version','Hash'}:
                raise ValueError('RS1 actual durable floor shape differs')
            phase.version(actual_floor['Version'])
            predecessors = ('current','overlap') if phase_name == 'overlap' else (('final',) if record['phase']=='finalized' else ('overlap','final'))
            if (actual_floor['Version'],actual_floor['Hash']) not in {(manifest[n+'PeerPolicyVersion'],manifest[n+'PeerPolicySHA256']) for n in predecessors}:
                raise ValueError('RS1 actual durable floor is outside the frozen tuples')
            wanted = {'node-cert.pem':files['node-cert.pem'], 'peer-policy.json':files['peer-policy-'+phase_name+'.json'],
                      'ca.pem':files['ca.pem'], 'node-key.pem':legacy._regular(root/'node-key.pem'), 'signer.pub':legacy._regular(root/'signer.pub')}
            if len(wanted['signer.pub']) != 32 or any(entries[name] != body or legacy._regular(root/name) != body for name,body in wanted.items()):
                raise ValueError('RS1 actual/host credentials do not equal the frozen active tuple')
            # Repeat actual reads and ownership immediately before the only action.
            if transport.stopped_entries(root, expected) != entries or _target(root, record) != expected:
                raise ValueError('RS1 stopped state changed before start')
            before_start = datetime.now(timezone.utc)
            legacy.validate_bundle(bundle,root,now=before_start,installed=True,finalized=record['phase']=='finalized')
            phase.validate_policy(files['peer-policy-'+phase_name+'.json'],manifest,phase_name,now=before_start,before_write=True)
            try:
                start_attempted = True
                transport.docker('start', expected['containerId'])
            except Exception:
                # A lost response is not evidence of failure or rollback authority.
                _target(root, record)
                _, _, value, _, _, _ = transport.target(root)
                if not value['State'].get('Running') or value['State'].get('Restarting'):
                    raise ValueError('RS1 uncertain start remains forward-only') from None
        _target(root, record)
        actual = _floor(root, manifest, files)
        phase.match_floor(actual, manifest, phase_name)
        if actual['servingExecutableSHA256'] != record['prePeerFloor']['servingExecutableSHA256']:
            raise ValueError('RS1 serving executable changed')
        return dict(schemaVersion='saintvision-peer-publication-reentry:1', rotationId=manifest['rotationId'],
                    phase=phase_name, startAttempted=start_attempted, containerId=expected['containerId'], actualPeerFloor=actual, acceptanceAssessed=False)
