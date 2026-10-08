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

import cryptography
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.x509.oid import ExtendedKeyUsageOID

SCHEMA = "saintvision-lan-leaf-rotation:1"
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


def _policy(raw: bytes, *, manifest: dict, fingerprints: list[str], expires: str) -> dict:
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
) -> dict:
    """Validate exact chain, Node/key binding, time window, and monotonic version."""
    now = now or datetime.now(timezone.utc)
    manifest_raw = _regular(bundle / "rotation.json")
    manifest = json.loads(manifest_raw)
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
        raise ValueError("Rotation manifest shape differs")
    if (
        manifest["schemaVersion"] != SCHEMA
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
        or set(manifest["files"]) != set(FILE_NAMES)
        or any(
            not isinstance(value, str) or not HEX.fullmatch(value)
            for value in manifest["files"].values()
        )
    ):
        raise ValueError("Rotation manifest identity, version, or digest is invalid")
    created = _utc(manifest["createdAt"])
    overlap = _utc(manifest["overlapExpiresAt"])
    not_after = _utc(manifest["certificateNotAfter"])
    if (
        not created <= now < overlap < not_after
        or (overlap - now).total_seconds() > MAXIMUM_OVERLAP_SECONDS
    ):
        raise ValueError("Rotation overlap or certificate validity window is invalid")

    files = {name: _regular(bundle / name) for name in FILE_NAMES}
    if any(_digest(files[name]) != manifest["files"][name] for name in FILE_NAMES):
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
    next_control = _leaf(
        files["control-cert.pem"],
        intermediate=intermediate,
        uri=f'spiffe://saintvision.ai/tenant/{manifest["tenantId"]}/control-plane/epoch/{manifest["recoveryEpoch"]}',
        usage=ExtendedKeyUsageOID.CLIENT_AUTH,
        now=now,
    )
    if next_control.fingerprint(hashes.SHA256()).hex() != manifest["nextControlCertificateSHA256"]:
        raise ValueError("Next Control Plane leaf fingerprint differs")
    _policy(
        files["peer-policy-overlap.json"],
        manifest=manifest,
        fingerprints=[
            manifest["currentControlCertificateSHA256"],
            manifest["nextControlCertificateSHA256"],
        ],
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
    if (
        journal.get("phase") != "restarted"
        or any(journal.get(key) != value for key, value in expected_journal.items())
        or not old_overlap <= now < old_not_after
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
    worker_root = worker_root.resolve()
    worker_root.mkdir(parents=True, exist_ok=True)
    with _exclusive(worker_root / "leaf-rotation.lock"):
        journal_path = worker_root / "leaf-rotation.json"
        journal = json.loads(journal_path.read_text("utf-8")) if journal_path.exists() else None
        current_time = now or datetime.now(timezone.utc)
        if journal and superseded_bundle is not None:
            # Validate the fresh bundle before archiving the exact expired journal.
            validate_bundle(bundle, worker_root, now=current_time, installed=False)
            _supersede_expired_journal(
                superseded_bundle,
                bundle,
                worker_root,
                journal,
                now=current_time,
            )
            journal = None
        validated = validate_bundle(
            bundle,
            worker_root,
            now=current_time,
            installed=(
                None
                if journal and journal.get("phase") == "installing"
                else bool(
                    journal and journal.get("phase") in {"installed", "restarted", "finalized"}
                )
            ),
        )
        manifest, files = validated["manifest"], validated["files"]
        expected_identity = {
            "rotationId": manifest["rotationId"],
            "proposalDigest": validated["proposalDigest"],
            "targetChannelVersion": manifest["targetChannelVersion"],
        }
        if journal and any(journal.get(key) != value for key, value in expected_identity.items()):
            raise ValueError("Another leaf rotation or stale channel version is already journaled")
        if journal and journal.get("phase") in {"finalized", "rolled-back"}:
            raise ValueError("A completed leaf rotation cannot be installed again")
        if journal and journal.get("phase") == "restarted":
            return journal["receipt"]
        kill("before-install")
        backup = worker_root / "leaf-rotation-backup" / manifest["rotationId"]
        backup.mkdir(parents=True, exist_ok=True)
        for name in ("node-cert.pem", "peer-policy.json"):
            source = worker_root / name
            target = backup / name
            if not target.exists():
                _atomic(target, _regular(source))
        journal = {**expected_identity, "phase": "installing", "restartRequired": True}
        _atomic(journal_path, _canonical(journal))
        kill("after-intent")
        _atomic(worker_root / "node-cert.pem", files["node-cert.pem"])
        _atomic(worker_root / "peer-policy.json", files["peer-policy-overlap.json"])
        kill("after-public-install")
        journal = {**expected_identity, "phase": "installed", "restartRequired": True}
        _atomic(journal_path, _canonical(journal))
        kill("after-install")
        kill("before-restart")
        restart(worker_root)
        installed_at = (now or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")
        receipt_body = {
            "schemaVersion": SCHEMA,
            **expected_identity,
            "nodeId": manifest["nodeId"],
            "installedNodeCertificateSHA256": manifest["nextNodeCertificateSHA256"],
            "installedAt": installed_at,
            "restartObserved": True,
        }
        private = serialization.load_pem_private_key(
            _regular(worker_root / "node-key.pem"), password=None
        )
        if not isinstance(private, Ed25519PrivateKey):
            raise ValueError("Node receipt signing key type differs")
        receipt = {
            **receipt_body,
            "nodeSignature": private.sign(_canonical(receipt_body)).hex(),
        }
        journal = {
            **expected_identity,
            "phase": "restarted",
            "restartRequired": False,
            "receipt": receipt,
        }
        _atomic(journal_path, _canonical(journal))
        return receipt


def finalize(
    bundle: Path,
    worker_root: Path,
    commit_receipt: Path,
    *,
    restart: Callable[[Path], None],
    now: datetime | None = None,
) -> dict:
    """End bounded overlap only after the CP proves the same channel CAS committed."""
    with _exclusive(worker_root / "leaf-rotation.lock"):
        validated = validate_bundle(bundle, worker_root, now=now, installed=True)
        manifest = validated["manifest"]
        receipt = json.loads(_regular(commit_receipt))
        expected_body = {
            "schemaVersion": SCHEMA,
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
        journal_path = worker_root / "leaf-rotation.json"
        journal = json.loads(_regular(journal_path))
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
        if journal.get("phase") == "finalized":
            return result
        _atomic(worker_root / "peer-policy.json", validated["files"]["peer-policy-final.json"])
        restart(worker_root)
        journal["phase"] = "finalized"
        journal["restartRequired"] = False
        _atomic(journal_path, _canonical(journal))
        return result


def rollback(
    bundle: Path,
    worker_root: Path,
    *,
    restart: Callable[[Path], None],
    now: datetime | None = None,
) -> dict:
    """Restore the prior public material only while both prior authorities are fresh."""
    now = now or datetime.now(timezone.utc)
    with _exclusive(worker_root / "leaf-rotation.lock"):
        manifest_raw = _regular(bundle / "rotation.json")
        manifest = json.loads(manifest_raw)
        if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
            raise ValueError("Rotation manifest shape differs")
        journal_path = worker_root / "leaf-rotation.json"
        journal = json.loads(_regular(journal_path))
        if (
            journal.get("rotationId") != manifest["rotationId"]
            or journal.get("proposalDigest") != _digest(manifest_raw)
            or journal.get("phase") not in {"installing", "installed", "restarted", "rolled-back"}
        ):
            raise ValueError("Only the exact unfinalized rotation can roll back")
        backup = worker_root / "leaf-rotation-backup" / manifest["rotationId"]
        old_cert_raw = _regular(backup / "node-cert.pem")
        old_policy_raw = _regular(backup / "peer-policy.json")
        old_cert = x509.load_pem_x509_certificate(old_cert_raw)
        old_policy = json.loads(old_policy_raw)
        if (
            old_cert.fingerprint(hashes.SHA256()).hex() != manifest["currentNodeCertificateSHA256"]
            or not old_cert.not_valid_before_utc <= now < old_cert.not_valid_after_utc
            or not isinstance(old_policy, dict)
            or set(old_policy)
            != {
                "version",
                "tenantId",
                "nodeId",
                "recoveryEpoch",
                "expiresAt",
                "clientFingerprints",
            }
            or old_policy["tenantId"] != manifest["tenantId"]
            or old_policy["nodeId"] != manifest["nodeId"]
            or old_policy["recoveryEpoch"] != manifest["recoveryEpoch"]
            or old_policy["version"] != manifest["currentChannelVersion"]
            or old_policy["clientFingerprints"] != [manifest["currentControlCertificateSHA256"]]
            or _utc(old_policy["expiresAt"]) <= now
        ):
            raise ValueError("Prior public authority is expired or differs; rollback refused")
        result = {
            "rotationId": manifest["rotationId"],
            "rolledBack": True,
            "channelVersion": manifest["currentChannelVersion"],
        }
        if journal.get("phase") == "rolled-back":
            return result
        _atomic(worker_root / "node-cert.pem", old_cert_raw)
        _atomic(worker_root / "peer-policy.json", old_policy_raw)
        restart(worker_root)
        journal["phase"] = "rolled-back"
        journal["restartRequired"] = False
        _atomic(journal_path, _canonical(journal))
        return result


def docker_restart(worker_root: Path) -> None:
    manifest = json.loads((worker_root / "manifest.json").read_text("utf-8"))
    node_id = manifest["nodeId"]
    if not NODE_ID.fullmatch(node_id):
        raise ValueError("Worker manifest Node identity is invalid")
    container = "saintvision-" + node_id.lower()
    from worker_config import check_running, install_files

    install_files(container, worker_root)
    subprocess.run(["docker", "restart", container], check=True, timeout=60, capture_output=True)
    check_running(container)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("runtime-preflight")
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
    rollback_parser = commands.add_parser("rollback")
    rollback_parser.add_argument("--bundle", type=Path, required=True)
    rollback_parser.add_argument("--worker-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        runtime = runtime_preflight()
        if args.command == "runtime-preflight":
            result = runtime
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
