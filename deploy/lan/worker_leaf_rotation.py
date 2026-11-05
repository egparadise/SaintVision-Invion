"""Crash-safe installation of a CP-issued LAN Node leaf rotation.

The Node private key never leaves ``worker_root``.  A rotation directory contains
only public certificates, policies, and a strict manifest.  Installation is
serialized, journaled, and finishes copying all public material into the Node
state before the container is restarted.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Callable
import peer_policy_phase as peer_phase
import worker_peer_floor

import cryptography
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.x509.oid import ExtendedKeyUsageOID

SCHEMA = "saintvision-lan-leaf-rotation:1"
OFFLINE_SCHEMA = "saintvision-lan-leaf-rotation:2"
OFFLINE_RECOVERY_MODE = "fully-expired-offline"
MANIFEST_KEYS = {
    "schemaVersion",
    "rotationId",
    "tenantId",
    "nodeId",
    "recoveryEpoch",
    "nodeIP",
    "currentChannelVersion",
    "targetChannelVersion",
    "currentNodeCertificateSHA256",
    "nextNodeCertificateSHA256",
    "currentControlCertificateSHA256",
    "nextControlCertificateSHA256",
    "caBundleSHA256",
    "createdAt",
    "overlapExpiresAt",
    "certificateNotAfter",
    "files",
}
OFFLINE_MANIFEST_KEYS = MANIFEST_KEYS | {
    "recoveryMode",
    "offlineAuthorizationSHA256",
    "currentPeerPolicySHA256",
    "supersededRotationId",
    "supersededProposalDigest",
}
FILE_NAMES = (
    "ca.pem",
    "node-cert.pem",
    "control-cert.pem",
    "peer-policy-overlap.json",
    "peer-policy-final.json",
)
HEX = re.compile(r"[a-f0-9]{64}\Z")
NODE_ID = re.compile(r"nod_[0-9A-HJKMNP-TV-Z]{26}\Z")
MINIMUM_PYTHON = (3, 11)
REQUIRED_CRYPTOGRAPHY = (50, 0, 1)
MAXIMUM_OVERLAP_SECONDS = 21600


def manifest_keys(schema):
    if schema == peer_phase.SCHEMA:
        return MANIFEST_KEYS | peer_phase.PEER_FIELDS
    return OFFLINE_MANIFEST_KEYS if schema == OFFLINE_SCHEMA else MANIFEST_KEYS


def file_names(manifest):
    return (*FILE_NAMES, *peer_phase.EXTRA_FILES) if manifest.get("schemaVersion") == peer_phase.SCHEMA else FILE_NAMES


def _peer_binding(manifest):
    return peer_phase.binding(manifest)


def observe_actual_floor(worker_root, manifest, files):
    return worker_peer_floor.observe(worker_root, manifest, files)


def floor_target_context(worker_root):
    return worker_peer_floor.context(worker_root)


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:[.+-].*)?", value)
    if not match:
        raise RuntimeError("cryptography version is not a supported semantic version")
    return tuple(int(part) for part in match.groups())


def runtime_preflight() -> dict:
    """Fail before any state write when the isolated worker runtime is incompatible."""
    crypto_version = _version_tuple(cryptography.__version__)
    api_available = all(
        hasattr(x509.Certificate, attribute)
        for attribute in ("not_valid_before_utc", "not_valid_after_utc")
    )
    if sys.version_info[:2] < MINIMUM_PYTHON:
        raise RuntimeError("Node leaf rotation requires Python 3.11 or newer")
    if crypto_version < REQUIRED_CRYPTOGRAPHY or not api_available:
        raise RuntimeError("Node leaf rotation requires cryptography 50.0.1 or newer with UTC APIs")
    return {
        "compatible": True,
        "pythonVersion": ".".join(str(value) for value in sys.version_info[:3]),
        "cryptographyVersion": cryptography.__version__,
        "minimumPython": ".".join(str(value) for value in MINIMUM_PYTHON),
        "minimumCryptography": ".".join(str(value) for value in REQUIRED_CRYPTOGRAPHY),
        "utcCertificateAPI": True,
    }


def _utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("Rotation timestamps must be UTC RFC3339 values")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo != timezone.utc or parsed.isoformat().replace("+00:00", "Z") != value:
        raise ValueError("Rotation timestamps must be canonical UTC RFC3339 values")
    return parsed


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _regular(path: Path, *, limit: int = 65536) -> bytes:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
        raise ValueError("Rotation input is missing, empty, oversized, or not a regular file")
    return path.read_bytes()


def _certificates(raw: bytes) -> list[x509.Certificate]:
    blocks = re.findall(
        b"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", raw, flags=re.DOTALL
    )
    return [x509.load_pem_x509_certificate(block) for block in blocks]


def _verify_signature(issuer: x509.Certificate, certificate: x509.Certificate) -> None:
    key = issuer.public_key()
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("Node issuing chain must use Ed25519")
    key.verify(certificate.signature, certificate.tbs_certificate_bytes)


def _leaf(
    raw: bytes,
    *,
    intermediate: x509.Certificate,
    uri: str,
    usage: x509.ObjectIdentifier,
    now: datetime,
    address: str | None = None,
) -> x509.Certificate:
    certificate = x509.load_pem_x509_certificate(raw)
    _verify_signature(intermediate, certificate)
    constraints = certificate.extensions.get_extension_for_class(x509.BasicConstraints).value
    usages = certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    names = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    uris = names.get_values_for_type(x509.UniformResourceIdentifier)
    addresses = names.get_values_for_type(x509.IPAddress)
    expected_addresses = [] if address is None else [ipaddress.ip_address(address)]
    if (
        certificate.issuer != intermediate.subject
        or constraints.ca
        or list(usages) != [usage]
        or uris != [uri]
        or addresses != expected_addresses
        or not certificate.not_valid_before_utc <= now < certificate.not_valid_after_utc
    ):
        raise ValueError("Rotated leaf identity, usage, address, or validity differs")
    return certificate


def _historical_expired_leaf(
    raw: bytes,
    *,
    intermediate: x509.Certificate,
    uri: str,
    usage: x509.ObjectIdentifier,
    now: datetime,
    address: str | None = None,
) -> x509.Certificate:
    """Validate an expired leaf as signed history, never as live authority."""
    certificate = x509.load_pem_x509_certificate(raw)
    _verify_signature(intermediate, certificate)
    constraints = certificate.extensions.get_extension_for_class(x509.BasicConstraints).value
    usages = certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    names = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    expected_addresses = [] if address is None else [ipaddress.ip_address(address)]
    if (
        certificate.issuer != intermediate.subject
        or constraints.ca
        or list(usages) != [usage]
        or names.get_values_for_type(x509.UniformResourceIdentifier) != [uri]
        or names.get_values_for_type(x509.IPAddress) != expected_addresses
        or certificate.not_valid_before_utc >= certificate.not_valid_after_utc
        or certificate.not_valid_after_utc > now
    ):
        raise ValueError("Expired historical leaf identity, chain, or expiry differs")
    return certificate


def _policy(raw: bytes, *, manifest: dict, fingerprints: list[str], expires: str) -> dict:
    if manifest.get("schemaVersion") == peer_phase.SCHEMA:
        phase = "final" if expires == manifest["certificateNotAfter"] else "overlap"
        value = peer_phase.validate_policy(raw, manifest, phase)
        if value["clientFingerprints"] != fingerprints or value["expiresAt"] != expires:
            raise ValueError("Peer phase authority differs")
        return value
    value = json.loads(raw)
    expected = {
        "version": manifest["targetChannelVersion"],
        "tenantId": manifest["tenantId"],
        "nodeId": manifest["nodeId"],
        "recoveryEpoch": manifest["recoveryEpoch"],
        "expiresAt": expires,
        "clientFingerprints": fingerprints,
    }
    if value != expected:
        raise ValueError("Peer policy differs from the exact rotation authority")
    return value


def validate_bundle(
    bundle: Path,
    worker_root: Path,
    *,
    now: datetime | None = None,
    installed: bool | None = False,
    finalized: bool = False,
) -> dict:
    """Validate exact chain, Node/key binding, time window, and monotonic version."""
    now = now or datetime.now(timezone.utc)
    manifest_raw = _regular(bundle / "rotation.json")
    manifest = peer_phase.strict(manifest_raw)
    if not isinstance(manifest, dict):
        raise ValueError("Rotation manifest shape differs")
    schema = manifest.get("schemaVersion")
    expected_keys = manifest_keys(schema)
    if set(manifest) != expected_keys:
        raise ValueError("Rotation manifest shape differs")
    offline = schema == OFFLINE_SCHEMA
    if (
        schema not in {SCHEMA, OFFLINE_SCHEMA, peer_phase.SCHEMA}
        or not isinstance(manifest["rotationId"], str)
        or not re.fullmatch(r"[0-9a-f]{32}", manifest["rotationId"])
        or not isinstance(manifest["tenantId"], str)
        or not NODE_ID.fullmatch(manifest["nodeId"])
        or not isinstance(manifest["recoveryEpoch"], str)
        or type(manifest["currentChannelVersion"]) is not int
        or type(manifest["targetChannelVersion"]) is not int
        or manifest["targetChannelVersion"] != manifest["currentChannelVersion"] + 1
        or any(
            not isinstance(manifest[key], str) or not HEX.fullmatch(manifest[key])
            for key in (
                "currentNodeCertificateSHA256",
                "nextNodeCertificateSHA256",
                "currentControlCertificateSHA256",
                "nextControlCertificateSHA256",
                "caBundleSHA256",
            )
        )
        or not isinstance(manifest["files"], dict)
        or set(manifest["files"]) != set(file_names(manifest))
        or any(
            not isinstance(value, str) or not HEX.fullmatch(value)
            for value in manifest["files"].values()
        )
    ):
        raise ValueError("Rotation manifest identity, version, or digest is invalid")
    if offline and (
        manifest["recoveryMode"] != OFFLINE_RECOVERY_MODE
        or not isinstance(manifest["offlineAuthorizationSHA256"], str)
        or not HEX.fullmatch(manifest["offlineAuthorizationSHA256"])
        or not isinstance(manifest["currentPeerPolicySHA256"], str)
        or not HEX.fullmatch(manifest["currentPeerPolicySHA256"])
        or not (
            (
                manifest["supersededRotationId"] is None
                and manifest["supersededProposalDigest"] is None
            )
            or (
                isinstance(manifest["supersededRotationId"], str)
                and re.fullmatch(r"[0-9a-f]{32}", manifest["supersededRotationId"])
                and isinstance(manifest["supersededProposalDigest"], str)
                and HEX.fullmatch(manifest["supersededProposalDigest"])
            )
        )
    ):
        raise ValueError("Offline recovery authority binding is invalid")
    created = _utc(manifest["createdAt"])
    overlap = _utc(manifest["overlapExpiresAt"])
    not_after = _utc(manifest["certificateNotAfter"])
    if (
        not created <= now < (not_after if finalized else overlap)
        or not overlap < not_after
        or (finalized and installed is not True)
        or (overlap - now).total_seconds() > MAXIMUM_OVERLAP_SECONDS
    ):
        raise ValueError("Rotation overlap or certificate validity window is invalid")

    files = {name: _regular(bundle / name) for name in file_names(manifest)}
    if any(_digest(files[name]) != manifest["files"][name] for name in file_names(manifest)):
        raise ValueError("Rotation public material digest differs")
    if _digest(files["ca.pem"]) != manifest["caBundleSHA256"]:
        raise ValueError("Rotation issuing chain differs")
    pinned_ca = _regular(worker_root / "ca.pem")
    if not hashlib.sha256(pinned_ca).digest() == hashlib.sha256(files["ca.pem"]).digest():
        raise ValueError("Rotation issuing chain is not the pinned chain")
    chain = _certificates(files["ca.pem"])
    if len(chain) != 2:
        raise ValueError("Pinned chain must contain one intermediate and one root")
    intermediate, root = chain
    intermediate_constraints = intermediate.extensions.get_extension_for_class(
        x509.BasicConstraints
    ).value
    root_constraints = root.extensions.get_extension_for_class(x509.BasicConstraints).value
    _verify_signature(root, intermediate)
    _verify_signature(root, root)
    if (
        intermediate.issuer != root.subject
        or root.issuer != root.subject
        or not intermediate_constraints.ca
        or intermediate_constraints.path_length != 0
        or not root_constraints.ca
        or root_constraints.path_length != 1
        or not intermediate.not_valid_before_utc <= now < intermediate.not_valid_after_utc
        or not root.not_valid_before_utc <= now < root.not_valid_after_utc
    ):
        raise ValueError("Pinned issuing chain constraints or validity differ")

    old_node_raw = _regular(worker_root / "node-cert.pem")
    old_node = x509.load_pem_x509_certificate(old_node_raw)
    expected_current = {
        (
            manifest["nextNodeCertificateSHA256"]
            if installed
            else manifest["currentNodeCertificateSHA256"]
        )
    }
    if installed is None:
        expected_current.add(manifest["nextNodeCertificateSHA256"])
    if old_node.fingerprint(hashes.SHA256()).hex() not in expected_current:
        raise ValueError("Current Node leaf does not match the rotation base")
    using_historical_base = (
        offline
        and old_node.fingerprint(hashes.SHA256()).hex() == manifest["currentNodeCertificateSHA256"]
    )
    if using_historical_base:
        _historical_expired_leaf(
            old_node_raw,
            intermediate=intermediate,
            uri=f'spiffe://saintvision.ai/tenant/{manifest["tenantId"]}/node/{manifest["nodeId"]}/epoch/{manifest["recoveryEpoch"]}',
            usage=ExtendedKeyUsageOID.SERVER_AUTH,
            now=now,
            address=manifest["nodeIP"],
        )
        if (
            _digest(_regular(worker_root / "peer-policy.json"))
            != manifest["currentPeerPolicySHA256"]
        ):
            raise ValueError("Expired historical peer policy differs")
    next_node = _leaf(
        files["node-cert.pem"],
        intermediate=intermediate,
        uri=f'spiffe://saintvision.ai/tenant/{manifest["tenantId"]}/node/{manifest["nodeId"]}/epoch/{manifest["recoveryEpoch"]}',
        usage=ExtendedKeyUsageOID.SERVER_AUTH,
        now=now,
        address=manifest["nodeIP"],
    )
    if next_node.fingerprint(hashes.SHA256()).hex() != manifest["nextNodeCertificateSHA256"]:
        raise ValueError("Next Node leaf fingerprint differs")
    private = serialization.load_pem_private_key(
        _regular(worker_root / "node-key.pem"), password=None
    )
    if not isinstance(private, Ed25519PrivateKey) or private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ) != next_node.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ):
        raise ValueError("Rotated Node leaf does not preserve the Node private key")
    if using_historical_base and private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ) != old_node.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ):
        raise ValueError("Expired historical Node leaf does not match the Node private key")
    next_control = _leaf(
        files["control-cert.pem"],
        intermediate=intermediate,
        uri=f'spiffe://saintvision.ai/tenant/{manifest["tenantId"]}/control-plane/epoch/{manifest["recoveryEpoch"]}',
        usage=ExtendedKeyUsageOID.CLIENT_AUTH,
        now=now,
    )
    if next_control.fingerprint(hashes.SHA256()).hex() != manifest["nextControlCertificateSHA256"]:
        raise ValueError("Next Control Plane leaf fingerprint differs")
    if schema == peer_phase.SCHEMA:
        peer_phase.versions(manifest)
        observation = peer_phase.strict(files["peer-floor-observation.json"])
        if _digest(files["peer-floor-observation.json"]) != manifest["floorObservationSHA256"]:
            raise ValueError("Frozen actual floor observation differs")
        peer_phase.verify_floor(observation, files["previous-node-cert.pem"], manifest, fresh=False)
        peer_phase.match_floor(observation, manifest, "current")
        previous = x509.load_pem_x509_certificate(files["previous-node-cert.pem"])
        old_policy = peer_phase.strict(files["previous-peer-policy.json"])
        if (previous.fingerprint(hashes.SHA256()).hex() != manifest["currentNodeCertificateSHA256"]
                or previous.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
                != next_node.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
                or _digest(files["previous-peer-policy.json"]) != manifest["currentPeerPolicySHA256"]
                or type(old_policy.get("version")) is not int
                or old_policy["version"] != manifest["currentPeerPolicyVersion"]
                or (old_policy.get("tenantId"), old_policy.get("nodeId"), old_policy.get("recoveryEpoch")) != (manifest["tenantId"], manifest["nodeId"], manifest["recoveryEpoch"])
                or old_policy.get("clientFingerprints") != [manifest["currentControlCertificateSHA256"]]):
            raise ValueError("Previous actual peer policy/certificate tuple differs")
        _leaf(files["previous-node-cert.pem"], intermediate=intermediate,
              uri=f'spiffe://saintvision.ai/tenant/{manifest["tenantId"]}/node/{manifest["nodeId"]}/epoch/{manifest["recoveryEpoch"]}',
              usage=ExtendedKeyUsageOID.SERVER_AUTH, now=_utc(manifest["createdAt"]), address=manifest["nodeIP"])
    overlap_fingerprints = (
        [manifest["nextControlCertificateSHA256"]]
        if offline
        else [
            manifest["currentControlCertificateSHA256"],
            manifest["nextControlCertificateSHA256"],
        ]
    )
    _policy(
        files["peer-policy-overlap.json"],
        manifest=manifest,
        fingerprints=overlap_fingerprints,
        expires=manifest["overlapExpiresAt"],
    )
    _policy(
        files["peer-policy-final.json"],
        manifest=manifest,
        fingerprints=[manifest["nextControlCertificateSHA256"]],
        expires=manifest["certificateNotAfter"],
    )
    return {"manifest": manifest, "files": files, "proposalDigest": _digest(manifest_raw)}


def _atomic(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".next")
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def _exclusive(path: Path):
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValueError("Another leaf rotation writer owns the Node lock") from None
    try:
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


def _owned_directory(path: Path) -> None:
    """Reject redirected or foreign/writable history paths before publication."""
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or path.is_symlink()
        or getattr(path, "is_junction", lambda: False)()
        or (os.name != "nt" and (info.st_uid != os.geteuid() or info.st_mode & 0o022))
    ):
        raise ValueError("Rotation history directory is unsafe")


def _history_bytes(path: Path, *, limit: int = 65536) -> bytes:
    info = path.lstat()
    if os.name != "nt" and (info.st_uid != os.geteuid() or info.st_mode & 0o022):
        raise ValueError("Rotation history file ownership or mode is unsafe")
    return _regular(path, limit=limit)


def _immutable(path: Path, raw: bytes, *, publish: bool) -> None:
    """Publish complete evidence without replacing an existing archive or staging file."""
    temporary = path.with_name(path.name + ".next")
    if path.exists() or path.is_symlink():
        if _history_bytes(path, limit=max(65536, len(raw))) != raw:
            raise ValueError("Finalized rotation archive collision")
        if temporary.exists() or temporary.is_symlink():
            if _history_bytes(temporary, limit=max(65536, len(raw))) != raw:
                raise ValueError("Finalized rotation archive staging collision")
            if publish:
                # A completed immutable publication already preserves these exact bytes.
                # Only the owned, regular, verified duplicate may be retired on replay.
                temporary.unlink()
                if os.name != "nt":
                    descriptor = os.open(path.parent, os.O_RDONLY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
        return
    if temporary.exists() or temporary.is_symlink():
        if _history_bytes(temporary, limit=max(65536, len(raw))) != raw:
            raise ValueError("Finalized rotation archive staging collision")
    if not publish:
        return
    if not temporary.exists():
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
    # link is atomic and fails if the destination exists; rename/replace can overwrite.
    os.link(temporary, path)
    temporary.unlink()
    if os.name != "nt":
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _finalized_evidence(
    validated: dict,
    manifest_raw: bytes,
    commit_raw: bytes,
    journal: dict,
    journal_raw: bytes,
) -> bytes:
    manifest, files = validated["manifest"], validated["files"]
    identity = {
        "rotationId": manifest["rotationId"],
        "proposalDigest": _digest(manifest_raw),
        "targetChannelVersion": manifest["targetChannelVersion"],
    }
    receipt = journal.get("receipt", {})
    receipt_body = {
        "schemaVersion": manifest["schemaVersion"],
        **identity,
        "nodeId": manifest["nodeId"],
        "installedNodeCertificateSHA256": manifest["nextNodeCertificateSHA256"],
        "installedAt": receipt.get("installedAt"),
        "restartObserved": True,
    }
    commit = json.loads(commit_raw)
    commit_body = {
        "schemaVersion": manifest["schemaVersion"],
        "rotationId": manifest["rotationId"],
        "proposalDigest": identity["proposalDigest"],
        "nodeId": manifest["nodeId"],
        "channelVersion": manifest["targetChannelVersion"],
        "certificateSHA256": manifest["nextNodeCertificateSHA256"],
        "committed": True,
    }
    expected_journal = {**identity, "phase": "finalized", "restartRequired": False, "receipt": receipt}
    archive_schema = "saintvision-node-finalized-rotation:1"
    if manifest["schemaVersion"] == peer_phase.SCHEMA:
        receipt_body.update(**_peer_binding(manifest), prePeerFloor=receipt.get("prePeerFloor"), postPeerFloor=receipt.get("postPeerFloor"))
        commit_body.update(_peer_binding(manifest))
        for value, phase_name, cert_name in ((receipt_body["prePeerFloor"], "current", "previous-node-cert.pem"),
                                             (receipt_body["postPeerFloor"], "overlap", "node-cert.pem"),
                                             (journal.get("finalPeerFloor"), "final", "node-cert.pem")):
            peer_phase.verify_floor(value, files[cert_name], manifest, fresh=False)
            peer_phase.match_floor(value, manifest, phase_name)
        expected_journal.update(peerSchemaVersion=3, publicationIntent=True,
                                peerPhaseBinding=_peer_binding(manifest),
                                prePeerFloor=receipt_body["prePeerFloor"],
                                targetContext=journal.get("targetContext"), finalPeerFloor=journal.get("finalPeerFloor"))
        context = journal.get("targetContext")
        if (not isinstance(context, dict) or set(context) != {"nodeId", "containerId", "image", "configSHA256", "mountsSHA256", "volumeSHA256", "consumers"}
                or context["nodeId"] != manifest["nodeId"] or not HEX.fullmatch(context["containerId"])):
            raise ValueError("Finalized actual target binding differs")
        archive_schema = "saintvision-node-finalized-rotation:3"
    if (
        json.loads(journal_raw) != journal
        or journal != expected_journal
        or set(receipt) != {*receipt_body, "nodeSignature"}
        or any(receipt.get(key) != value for key, value in receipt_body.items())
        or not _utc(manifest["createdAt"])
        <= _utc(receipt["installedAt"])
        < _utc(manifest["overlapExpiresAt"])
        or set(commit) != {*commit_body, "controlSignature"}
        or any(commit.get(key) != value for key, value in commit_body.items())
    ):
        raise ValueError("Finalized rotation evidence binding differs")
    for value, key, body, certificate in (
        (receipt, "nodeSignature", receipt_body, "node-cert.pem"),
        (commit, "controlSignature", commit_body, "control-cert.pem"),
    ):
        signature = value.get(key)
        if not isinstance(signature, str) or not re.fullmatch(r"[a-f0-9]{128}", signature):
            raise ValueError("Finalized rotation evidence signature differs")
        x509.load_pem_x509_certificate(files[certificate]).public_key().verify(
            bytes.fromhex(signature), _canonical(body)
        )
    return _canonical(
        {
            "schemaVersion": archive_schema,
            "journal": journal,
            "journalRaw": journal_raw.decode("utf-8"),
            "rotationManifest": manifest_raw.decode("utf-8"),
            "files": {name: raw.decode("utf-8") for name, raw in files.items()},
            "commitReceipt": commit_raw.decode("utf-8"),
        }
    )


def _require_settled_archive(path: Path) -> None:
    temporary = path.with_name(path.name + ".next")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError(
            "Predecessor staging residue requires exact predecessor finalize/retire replay"
        )


def _finalized_successor(
    worker_root: Path, journal: dict, validated: dict, *, now: datetime
) -> None:
    """Allow only a normal successor bound to the exact archived finalized authority."""
    archive_dir = worker_root / "leaf-rotation-finalized"
    _owned_directory(archive_dir)
    rotation_id = journal.get("rotationId")
    if not isinstance(rotation_id, str) or not re.fullmatch(r"[a-f0-9]{32}", rotation_id):
        raise ValueError("Finalized rotation identity differs")
    archive_path = archive_dir / f"{rotation_id}.json"
    _require_settled_archive(archive_path)
    archive_raw = _history_bytes(archive_path)
    archive = json.loads(archive_raw)
    if (
        set(archive)
        != {"schemaVersion", "journal", "journalRaw", "rotationManifest", "files", "commitReceipt"}
        or archive["schemaVersion"] not in {"saintvision-node-finalized-rotation:1", "saintvision-node-finalized-rotation:3"}
    ):
        raise ValueError("Finalized rotation archive shape differs")
    manifest_raw = archive["rotationManifest"].encode("utf-8")
    old = json.loads(manifest_raw)
    expected_keys = manifest_keys(old.get("schemaVersion"))
    if set(old) != expected_keys or set(archive["files"]) != set(file_names(old)):
        raise ValueError("Finalized rotation archive manifest differs")
    files = {name: raw.encode("utf-8") for name, raw in archive["files"].items()}
    if any(_digest(files[name]) != old["files"][name] for name in file_names(old)):
        raise ValueError("Finalized rotation archive public material differs")
    verified_raw = _finalized_evidence(
        {"manifest": old, "files": files},
        manifest_raw,
        archive["commitReceipt"].encode("utf-8"),
        journal,
        archive["journalRaw"].encode("utf-8"),
    )
    new = validated["manifest"]
    if (
        verified_raw != archive_raw
        or archive["journal"] != journal
        or journal.get("phase") != "finalized"
        or archive["journalRaw"].encode("utf-8") != _regular(worker_root / "leaf-rotation.json")
        or new["schemaVersion"] not in {SCHEMA, peer_phase.SCHEMA}
        or old["rotationId"] == new["rotationId"]
        or any(
            old[key] != new[key]
            for key in ("tenantId", "nodeId", "recoveryEpoch", "nodeIP", "caBundleSHA256")
        )
        or old["targetChannelVersion"] != new["currentChannelVersion"]
        or old["nextNodeCertificateSHA256"] != new["currentNodeCertificateSHA256"]
        or old["nextControlCertificateSHA256"] != new["currentControlCertificateSHA256"]
        or files["ca.pem"] != validated["files"]["ca.pem"]
        or files["node-cert.pem"] != _regular(worker_root / "node-cert.pem")
        or files["peer-policy-final.json"] != _regular(worker_root / "peer-policy.json")
        or _utc(old["createdAt"]) >= _utc(new["createdAt"])
        or (archive_dir / f'{new["rotationId"]}.json').exists()
        or (archive_dir / f'{new["rotationId"]}.json').is_symlink()
    ):
        raise ValueError("Normal successor differs from the finalized generation")
    if new["schemaVersion"] == peer_phase.SCHEMA:
        prior_policy = peer_phase.strict(files["peer-policy-final.json"])
        if (new["currentPeerPolicyVersion"] != prior_policy["version"]
                or new["currentPeerPolicySHA256"] != _digest(files["peer-policy-final.json"])
                or validated["files"]["previous-peer-policy.json"] != files["peer-policy-final.json"]
                or validated["files"]["previous-node-cert.pem"] != files["node-cert.pem"]):
            raise ValueError("Normal :1/:3 successor differs from actual finalized peer P/hash")
    intermediate = _certificates(files["ca.pem"])[0]
    for filename, uri, usage, address in (
        (
            "node-cert.pem",
            f'spiffe://saintvision.ai/tenant/{new["tenantId"]}/node/{new["nodeId"]}/epoch/{new["recoveryEpoch"]}',
            ExtendedKeyUsageOID.SERVER_AUTH,
            new["nodeIP"],
        ),
        (
            "control-cert.pem",
            f'spiffe://saintvision.ai/tenant/{new["tenantId"]}/control-plane/epoch/{new["recoveryEpoch"]}',
            ExtendedKeyUsageOID.CLIENT_AUTH,
            None,
        ),
    ):
        certificate = _leaf(
            files[filename],
            intermediate=intermediate,
            uri=uri,
            usage=usage,
            now=now,
            address=address,
        )
        fingerprint_key = (
            "currentNodeCertificateSHA256" if address else "currentControlCertificateSHA256"
        )
        if certificate.fingerprint(hashes.SHA256()).hex() != new[fingerprint_key]:
            raise ValueError("Finalized authority certificate differs")
        if address and certificate.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ) != x509.load_pem_x509_certificate(
            validated["files"]["node-cert.pem"]
        ).public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ):
            raise ValueError("Finalized Node key differs from the normal successor")
    _policy(
        files["peer-policy-final.json"],
        manifest=old,
        fingerprints=[new["currentControlCertificateSHA256"]],
        expires=old["certificateNotAfter"],
    )


def _finalization_body(
    manifest: dict, manifest_raw: bytes, files: dict, evidence_raw: bytes, actual_final_floor=None
) -> dict:
    return {
        "schemaVersion": ("saintvision-node-finalized-attestation:3" if manifest["schemaVersion"] == peer_phase.SCHEMA else "saintvision-node-finalized-attestation:1"),
        "rotationId": manifest["rotationId"],
        "proposalDigest": _digest(manifest_raw),
        "tenantId": manifest["tenantId"],
        "nodeId": manifest["nodeId"],
        "recoveryEpoch": manifest["recoveryEpoch"],
        "channelVersion": manifest["targetChannelVersion"],
        "caBundleSHA256": manifest["caBundleSHA256"],
        "nodeCertificateSHA256": manifest["nextNodeCertificateSHA256"],
        "controlCertificateSHA256": manifest["nextControlCertificateSHA256"],
        "finalPeerPolicySHA256": _digest(files["peer-policy-final.json"]),
        "evidenceSHA256": _digest(evidence_raw),
        **_peer_binding(manifest),
        **({"actualFinalPeerFloor": actual_final_floor} if manifest["schemaVersion"] == peer_phase.SCHEMA else {}),
    }


def verify_finalized_attestation(value: dict, manifest_raw: bytes, files: dict) -> dict:
    """Verify transferred public evidence and the Node's distinct finalization signature."""
    manifest = json.loads(manifest_raw)
    evidence_raw = value["evidence"].encode("utf-8")
    proof = json.loads(evidence_raw)
    journal = proof["journal"]
    expected = _finalization_body(manifest, manifest_raw, files, evidence_raw, value.get("actualFinalPeerFloor"))
    if manifest["schemaVersion"] == peer_phase.SCHEMA:
        peer_phase.verify_floor(value.get("actualFinalPeerFloor"), files["node-cert.pem"], manifest, fresh=False)
        peer_phase.match_floor(value["actualFinalPeerFloor"], manifest, "final")
    if (
        set(value) != {*expected, "evidence", "nodeSignature"}
        or any(value.get(key) != item for key, item in expected.items())
        or proof.get("schemaVersion") != ("saintvision-node-finalized-rotation:3" if manifest["schemaVersion"] == peer_phase.SCHEMA else "saintvision-node-finalized-rotation:1")
        or proof.get("rotationManifest") != manifest_raw.decode("utf-8")
        or proof.get("files") != {name: raw.decode("utf-8") for name, raw in files.items()}
        or _finalized_evidence(
            {"manifest": manifest, "files": files},
            manifest_raw,
            proof["commitReceipt"].encode("utf-8"),
            journal,
            proof["journalRaw"].encode("utf-8"),
        )
        != evidence_raw
    ):
        raise ValueError("Node finalized attestation differs from the exact batch")
    signature = value.get("nodeSignature")
    if not isinstance(signature, str) or not re.fullmatch(r"[a-f0-9]{128}", signature):
        raise ValueError("Node finalized attestation signature differs")
    x509.load_pem_x509_certificate(files["node-cert.pem"]).public_key().verify(
        bytes.fromhex(signature), _canonical(expected)
    )
    return proof


def attest_finalized(bundle: Path, worker_root: Path, *, now: datetime | None = None) -> dict:
    """Sign only the exact active finalized public generation; no success flag is trusted."""
    runtime_preflight()
    with _exclusive(worker_root / "leaf-rotation.lock"):
        validated = validate_bundle(bundle, worker_root, now=now, installed=True, finalized=True)
        manifest, files = validated["manifest"], validated["files"]
        archive_dir = worker_root / "leaf-rotation-finalized"
        _owned_directory(archive_dir)
        evidence_raw = _history_bytes(archive_dir / f'{manifest["rotationId"]}.json')
        actual_final = None
        if manifest["schemaVersion"] == peer_phase.SCHEMA:
            actual_final = observe_actual_floor(worker_root, manifest, files)
            peer_phase.match_floor(actual_final, manifest, "final")
        body = _finalization_body(manifest, _regular(bundle / "rotation.json"), files, evidence_raw, actual_final)
        private = serialization.load_pem_private_key(
            _regular(worker_root / "node-key.pem"), password=None
        )
        value = {
            **body,
            "evidence": evidence_raw.decode("utf-8"),
            "nodeSignature": private.sign(_canonical(body)).hex(),
        }
        proof = verify_finalized_attestation(value, _regular(bundle / "rotation.json"), files)
        if proof["journalRaw"].encode("utf-8") != _regular(
            worker_root / "leaf-rotation.json"
        ) or files["peer-policy-final.json"] != _regular(worker_root / "peer-policy.json"):
            raise ValueError("Only the exact active finalized Node can attest")
        return value


def _supersede_expired_journal(
    old_bundle: Path,
    new_bundle: Path,
    worker_root: Path,
    journal: dict,
    *,
    now: datetime,
) -> None:
    """Archive exactly one expired partial-batch journal before a fresh recovery install."""
    old_raw = _regular(old_bundle / "rotation.json")
    old_manifest = json.loads(old_raw)
    if not isinstance(old_manifest, dict) or set(old_manifest) != MANIFEST_KEYS:
        raise ValueError("Superseded rotation manifest shape differs")
    old_files = {name: _regular(old_bundle / name) for name in FILE_NAMES}
    if any(_digest(old_files[name]) != old_manifest["files"].get(name) for name in FILE_NAMES):
        raise ValueError("Superseded rotation public material digest differs")
    new_manifest = json.loads(_regular(new_bundle / "rotation.json"))
    old_overlap = _utc(old_manifest["overlapExpiresAt"])
    old_not_after = _utc(old_manifest["certificateNotAfter"])
    current_leaf = x509.load_pem_x509_certificate(_regular(worker_root / "node-cert.pem"))
    current_policy = _regular(worker_root / "peer-policy.json")
    expected_journal = {
        "rotationId": old_manifest["rotationId"],
        "proposalDigest": _digest(old_raw),
        "targetChannelVersion": old_manifest["targetChannelVersion"],
    }
    fully_expired = new_manifest.get("recoveryMode") == OFFLINE_RECOVERY_MODE
    time_is_safe = old_not_after <= now if fully_expired else old_overlap <= now < old_not_after
    if (
        journal.get("phase") != "restarted"
        or any(journal.get(key) != value for key, value in expected_journal.items())
        or not time_is_safe
        or current_leaf.fingerprint(hashes.SHA256()).hex()
        != old_manifest["nextNodeCertificateSHA256"]
        or current_policy != old_files["peer-policy-overlap.json"]
        or new_manifest.get("tenantId") != old_manifest["tenantId"]
        or new_manifest.get("nodeId") != old_manifest["nodeId"]
        or new_manifest.get("recoveryEpoch") != old_manifest["recoveryEpoch"]
        or new_manifest.get("currentChannelVersion") != old_manifest["targetChannelVersion"]
        or new_manifest.get("currentNodeCertificateSHA256")
        != old_manifest["nextNodeCertificateSHA256"]
        or new_manifest.get("currentControlCertificateSHA256")
        != old_manifest["currentControlCertificateSHA256"]
        or new_manifest.get("caBundleSHA256") != old_manifest["caBundleSHA256"]
        or (
            fully_expired
            and (
                new_manifest.get("supersededRotationId") != old_manifest["rotationId"]
                or new_manifest.get("supersededProposalDigest") != _digest(old_raw)
                or new_manifest.get("currentPeerPolicySHA256") != _digest(current_policy)
            )
        )
    ):
        raise ValueError("Expired rotation is not an exact safe supersession base")
    archive_dir = worker_root / "leaf-rotation-superseded"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive = archive_dir / f'{old_manifest["rotationId"]}.json'
    journal_raw = _canonical(journal)
    if archive.exists():
        if _regular(archive) != journal_raw:
            raise ValueError("Superseded rotation journal archive differs")
    else:
        _atomic(archive, journal_raw)
    (worker_root / "leaf-rotation.json").unlink()


def install(
    bundle: Path,
    worker_root: Path,
    *,
    restart: Callable[[Path], None],
    now: datetime | None = None,
    kill: Callable[[str], None] = lambda _point: None,
    superseded_bundle: Path | None = None,
) -> dict:
    """Install public material atomically, then restart; exact retries are idempotent."""
    runtime_preflight()
    if peer_phase.strict(_regular(Path(bundle) / "rotation.json")).get("schemaVersion") == peer_phase.SCHEMA:
        from worker_plain_rotation import install as plain_install
        return plain_install(bundle, worker_root, restart=restart, now=now, kill=kill, superseded_bundle=superseded_bundle)
    raise ValueError("Legacy :1/:2 installation is blocked; normal renewal requires authenticated :3 actual floors; partial/expired state requires separate offline recovery")

def finalize(
    bundle: Path,
    worker_root: Path,
    commit_receipt: Path,
    *,
    restart: Callable[[Path], None],
    now: datetime | None = None,
) -> dict:
    """End bounded overlap only after the CP proves the same channel CAS committed."""
    runtime_preflight()
    if peer_phase.strict(_regular(Path(bundle) / "rotation.json")).get("schemaVersion") == peer_phase.SCHEMA:
        from worker_plain_rotation import finalize as plain_finalize
        return plain_finalize(bundle, worker_root, commit_receipt, restart=restart, now=now)
    with _exclusive(worker_root / "leaf-rotation.lock"):
        journal_path = worker_root / "leaf-rotation.json"
        journal = json.loads(_regular(journal_path))
        if journal.get("phase") != "finalized":
            raise ValueError("Legacy in-flight finalization is blocked; only exact historical finalized archive replay is supported")
        validated = validate_bundle(
            bundle,
            worker_root,
            now=now,
            installed=True,
            finalized=journal.get("phase") == "finalized",
        )
        manifest = validated["manifest"]
        receipt = json.loads(_regular(commit_receipt))
        expected_body = {
            "schemaVersion": manifest["schemaVersion"],
            "rotationId": manifest["rotationId"],
            "proposalDigest": validated["proposalDigest"],
            "nodeId": manifest["nodeId"],
            "channelVersion": manifest["targetChannelVersion"],
            "certificateSHA256": manifest["nextNodeCertificateSHA256"],
            "committed": True,
        }
        if set(receipt) != {*expected_body, "controlSignature"} or any(
            receipt.get(key) != value for key, value in expected_body.items()
        ):
            raise ValueError("Control Plane commit receipt differs from the installed rotation")
        signature = receipt.get("controlSignature")
        if not isinstance(signature, str) or not re.fullmatch(r"[a-f0-9]{128}", signature):
            raise ValueError("Control Plane commit receipt signature is invalid")
        control = x509.load_pem_x509_certificate(validated["files"]["control-cert.pem"])
        control.public_key().verify(bytes.fromhex(signature), _canonical(expected_body))
        if (
            any(journal.get(key) != value for key, value in expected_body.items() if key in journal)
            or journal.get("rotationId") != manifest["rotationId"]
            or journal.get("proposalDigest") != validated["proposalDigest"]
            or journal.get("targetChannelVersion") != manifest["targetChannelVersion"]
            or journal.get("phase") not in {"restarted", "finalized"}
        ):
            raise ValueError("Only the exact restarted rotation can be finalized")
        result = {
            "rotationId": manifest["rotationId"],
            "finalized": True,
            "channelVersion": manifest["targetChannelVersion"],
        }
        already_finalized = journal.get("phase") == "finalized"
        prior_journal_raw = _regular(journal_path)
        journal = {**journal, "phase": "finalized", "restartRequired": False}
        finalized_journal_raw = prior_journal_raw if already_finalized else _canonical(journal)
        archive_dir = worker_root / "leaf-rotation-finalized"
        _owned_directory(archive_dir)
        archive_path = archive_dir / f'{manifest["rotationId"]}.json'
        evidence_raw = _finalized_evidence(
            validated,
            _regular(bundle / "rotation.json"),
            _regular(commit_receipt),
            journal,
            finalized_journal_raw,
        )
        _immutable(archive_path, evidence_raw, publish=False)
        if not already_finalized:
            _atomic(worker_root / "peer-policy.json", validated["files"]["peer-policy-final.json"])
            restart(worker_root)
        elif (
            _regular(worker_root / "peer-policy.json")
            != validated["files"]["peer-policy-final.json"]
        ):
            raise ValueError("Finalized current peer policy differs")
        _immutable(archive_path, evidence_raw, publish=True)
        if not already_finalized:
            _atomic(journal_path, finalized_journal_raw)
        return result


def rollback(
    bundle: Path,
    worker_root: Path,
    *,
    restart: Callable[[Path], None],
    now: datetime | None = None,
) -> dict:
    """Restore the prior public material only while both prior authorities are fresh."""
    runtime_preflight()
    if peer_phase.strict(_regular(Path(bundle) / "rotation.json")).get("schemaVersion") == peer_phase.SCHEMA:
        from worker_plain_rotation import rollback as plain_rollback
        return plain_rollback(bundle, worker_root, restart=restart, now=now)
    raise ValueError("Legacy rollback is blocked: publication and actual floor/CP state are unknown; preserve current bytes and journal for separate offline recovery")

def docker_restart(worker_root: Path) -> None:
    manifest = json.loads((worker_root / "manifest.json").read_text("utf-8"))
    node_id = manifest["nodeId"]
    if not NODE_ID.fullmatch(node_id):
        raise ValueError("Worker manifest Node identity is invalid")
    container = "saintvision-" + node_id.lower()
    from worker_config import check_running, install_files

    # A running Authority rereads peer bytes on every handshake. Stop the exact
    # owned plain container BEFORE any volume copy; publication intent is already
    # durable in :3 and every error thereafter remains forward-only/blocked.
    _, _, before, _, _, _ = worker_peer_floor.target(worker_root)
    subprocess.run(["docker", "stop", before["Id"]], check=True, timeout=60, capture_output=True)
    _, _, stopped, _, _, _ = worker_peer_floor.target(worker_root)
    if stopped["Id"] != before["Id"] or stopped["State"].get("Running"):
        raise ValueError("Owned Node changed or did not quiesce before public-file copy")
    install_files(container, worker_root, rotation_publication=True)
    subprocess.run(["docker", "start", before["Id"]], check=True, timeout=60, capture_output=True)
    check_running(container)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("runtime-preflight")
    floor_parser = commands.add_parser("observe-floor")
    floor_parser.add_argument("--worker-root", type=Path, required=True)
    floor_parser.add_argument("--nonce", required=True)
    install_parser = commands.add_parser("install")
    install_parser.add_argument("--bundle", type=Path, required=True)
    install_parser.add_argument("--worker-root", type=Path, required=True)
    install_parser.add_argument(
        "--supersede-expired-bundle",
        type=Path,
        help="Exact expired partial-batch bundle whose restarted journal may be superseded",
    )
    finalize_parser = commands.add_parser("finalize")
    finalize_parser.add_argument("--bundle", type=Path, required=True)
    finalize_parser.add_argument("--worker-root", type=Path, required=True)
    finalize_parser.add_argument("--commit-receipt", type=Path, required=True)
    attest_parser = commands.add_parser("attest-finalized")
    attest_parser.add_argument("--bundle", type=Path, required=True)
    attest_parser.add_argument("--worker-root", type=Path, required=True)
    rollback_parser = commands.add_parser("rollback")
    rollback_parser.add_argument("--bundle", type=Path, required=True)
    rollback_parser.add_argument("--worker-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "runtime-preflight":
            result = runtime_preflight()
        elif args.command == "observe-floor":
            runtime_preflight()
            metadata = peer_phase.strict(_regular(args.worker_root / "manifest.json"))
            scope = {"nodeId": metadata["nodeId"], "tenantId": metadata["tenantId"], "recoveryEpoch": metadata["epoch"]}
            result = worker_peer_floor.observe(args.worker_root, scope,
                                               {"node-cert.pem": _regular(args.worker_root / "node-cert.pem")}, nonce=args.nonce)
        elif args.command == "install":
            result = install(
                args.bundle,
                args.worker_root,
                restart=docker_restart,
                superseded_bundle=args.supersede_expired_bundle,
            )
        elif args.command == "finalize":
            result = finalize(
                args.bundle, args.worker_root, args.commit_receipt, restart=docker_restart
            )
        elif args.command == "attest-finalized":
            result = attest_finalized(args.bundle, args.worker_root)
        else:
            result = rollback(args.bundle, args.worker_root, restart=docker_restart)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        print(
            f"Node leaf rotation rejected ({type(error).__name__}); no credentials printed.",
            file=os.sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
