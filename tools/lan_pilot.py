"""Operator-only LAN observation bootstrap. No web login, grants or workload dispatch.

All generated material belongs in an ignored private state directory. Each
Node-bound worker archive contains public material only; its private TLS key is
created on that worker. Existing databases, containers, Node identities,
certificates and journals are never reset.
"""

import argparse
import getpass
import hashlib
import ipaddress
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import zipfile
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import BoundedSemaphore
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/control-plane/src"))
sys.path.insert(0, str(ROOT / "deploy/lan"))
import psycopg
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from inv.db import Database
from inv.ids import new_id
from inv.node_channels import certificate_identity, node_uri, provision_channel, revoke_channel
from inv.node_transport import NodeTLSClient
from inv.observer_worker import ObservationWorker
from inv.tooling import NodePrincipal
from lan_pki import ca_pair, csr_public_key, fingerprint, issue, pem, private_pem
from worker_leaf_rotation import FILE_NAMES as ROTATION_FILE_NAMES
from worker_leaf_rotation import MANIFEST_KEYS as ROTATION_MANIFEST_KEYS
from worker_leaf_rotation import MAXIMUM_OVERLAP_SECONDS
from worker_leaf_rotation import SCHEMA as ROTATION_SCHEMA
from psycopg import sql
from psycopg.conninfo import make_conninfo

COLOCATION_REVOKED_REASON = "server-node-colocation-revoked"
CERTIFICATE_REVOCATION_REASONS = {
    "key-compromise",
    "affiliation-changed",
    "superseded",
    "cessation-of-operation",
    "privilege-withdrawn",
}
EXTERNAL_DATABASE_MODE = "ssh-tunnel-external"
LOCAL_DATABASE_MODE = "managed-local-docker"
BATCH_ROTATION_SCHEMA = "saintvision-lan-leaf-rotation-batch:1"
BATCH_MANIFEST_KEYS = {
    "schemaVersion",
    "batchId",
    "tenantId",
    "recoveryEpoch",
    "createdAt",
    "overlapExpiresAt",
    "certificateNotAfter",
    "currentControlCertificateSHA256",
    "nextControlCertificateSHA256",
    "caBundleSHA256",
    "nodes",
}
BATCH_JOURNAL_KEYS = {
    "schemaVersion",
    "batchId",
    "batchDigest",
    "bundlePath",
    "phase",
    "stagedNodeIds",
}
DEFAULT_ROTATION_OVERLAP_SECONDS = 14400
RECOVERY_RECORD_SCHEMA = "saintvision-lan-leaf-rotation-recovery:1"


def run(args, **kwargs):
    result = subprocess.run(
        [str(x) for x in args], capture_output=True, timeout=kwargs.pop("timeout", 30), **kwargs
    )
    if result.returncode:
        raise RuntimeError(
            f"{Path(str(args[0])).name} failed; exit={result.returncode}; diagnostics suppressed"
        )
    return result.stdout.decode("utf-8", errors="replace").strip()


def write(path, data):
    if path.exists():
        raise ValueError(f"Refusing to replace {path.name}")
    with path.open("xb") as stream:
        stream.write(data.encode() if isinstance(data, str) else data)
    path.chmod(0o600)


def atomic_write(path, data):
    """Durably replace one public/operator record without following a symlink."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"Refusing unsafe destination {path.name}")
    raw = data.encode() if isinstance(data, str) else data
    temporary = path.with_name(path.name + ".next")
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
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
def exclusive_file(path):
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValueError("Another leaf rotation writer owns the state lock") from None
    try:
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


def private_directory(path):
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Private state must not be a symlink")
    if os.name == "nt":
        run(
            [
                "icacls.exe",
                path,
                "/inheritance:r",
                "/grant:r",
                f"{getpass.getuser()}:(OI)(CI)F",
                "*S-1-5-18:(OI)(CI)F",
                "*S-1-5-32-544:(OI)(CI)F",
            ]
        )
    else:
        path.chmod(0o700)


def _read_pgpass(path, *, host, port, dbname, user):
    passfile = Path(path)
    if not passfile.is_absolute() or passfile.is_symlink() or not passfile.is_file():
        raise ValueError("External database passfile is missing or unsafe")
    if os.name != "nt" and stat.S_IMODE(passfile.stat().st_mode) & 0o077:
        raise ValueError("External database passfile must be owner-only")
    raw = passfile.read_bytes()
    if len(raw) > 1024 or b"\x00" in raw:
        raise ValueError("External database passfile is invalid")
    rows = raw.decode("utf-8").splitlines()
    if len(rows) != 1:
        raise ValueError("External database passfile must contain one exact entry")
    fields = rows[0].split(":")
    if (
        len(fields) != 5
        or fields[:4] != [host, str(port), dbname, user]
        or not re.fullmatch(r"[a-f0-9]{64}", fields[4])
    ):
        raise ValueError("External database passfile identity differs")
    return fields[4]


def read_external_dsn(path, expected_user):
    """Accept a loopback SSH-tunnel DSN backed by one owner-private pgpass entry."""
    if path is None or path.is_symlink() or not path.is_file():
        raise ValueError("External database DSN file is missing or unsafe")
    raw = path.read_bytes()
    if len(raw) > 4096 or b"\x00" in raw:
        raise ValueError("External database DSN file is invalid")
    value = raw.decode("utf-8").strip()
    info = psycopg.conninfo.conninfo_to_dict(value)
    if (
        info.get("host") not in ("127.0.0.1", "localhost")
        or info.get("user") != expected_user
        or info.get("password")
        or not info.get("passfile")
        or info.get("dbname") != "saintvision_lan"
    ):
        raise ValueError("External database DSN must use a passfile-backed loopback tunnel")
    port = int(info.get("port", 5432))
    if not 1024 <= port <= 65535:
        raise ValueError("External database tunnel port is invalid")
    _read_pgpass(
        info["passfile"],
        host=info["host"],
        port=port,
        dbname=info["dbname"],
        user=expected_user,
    )
    return make_conninfo(value, connect_timeout=5)


def external_dsn_password(value, expected_user):
    info = psycopg.conninfo.conninfo_to_dict(value)
    return _read_pgpass(
        info["passfile"],
        host=info["host"],
        port=int(info.get("port", 5432)),
        dbname=info["dbname"],
        user=expected_user,
    )


def _dsn_with_passfile(value, expected_user, passfile):
    info = psycopg.conninfo.conninfo_to_dict(value)
    host = info.get("host")
    port = int(info.get("port", 5432))
    if (
        host not in ("127.0.0.1", "localhost")
        or info.get("user") != expected_user
        or info.get("dbname") != "saintvision_lan"
        or info.get("password")
    ):
        raise ValueError("Existing external database identity differs")
    passfile = Path(passfile).resolve()
    _read_pgpass(
        passfile,
        host=host,
        port=port,
        dbname=info["dbname"],
        user=expected_user,
    )
    return make_conninfo(
        host=host,
        port=port,
        dbname=info["dbname"],
        user=expected_user,
        passfile=str(passfile),
        connect_timeout=5,
    )


def bind_db_auth(args):
    """Move an existing external pilot state from trust to private pgpass credentials."""
    path, state = args.state, load(args.state)
    if state.get("databaseMode") != EXTERNAL_DATABASE_MODE:
        raise ValueError("Only an external pilot database can bind external credentials")
    admin_dsn = _dsn_with_passfile(state["adminDSN"], "postgres", args.admin_passfile)
    runtime_dsn = _dsn_with_passfile(state["runtimeDSN"], "inv_lan_runtime", args.runtime_passfile)
    admin_info = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    no_credential = make_conninfo(
        host=admin_info["host"],
        port=int(admin_info["port"]),
        dbname=admin_info["dbname"],
        user="postgres",
        passfile=str(path / ".missing-pgpass"),
        connect_timeout=2,
    )
    wrong_credential = make_conninfo(
        host=admin_info["host"],
        port=int(admin_info["port"]),
        dbname=admin_info["dbname"],
        user="postgres",
        password="0" * 64,
        connect_timeout=2,
    )
    for rejected in (no_credential, wrong_credential):
        try:
            with psycopg.connect(rejected):
                pass
        except psycopg.OperationalError:
            continue
        raise ValueError("Pilot database accepted a missing or incorrect credential")
    with psycopg.connect(admin_dsn) as conn:
        encryption = conn.execute("SHOW password_encryption").fetchone()[0]
        methods = [
            row[0]
            for row in conn.execute(
                "SELECT auth_method FROM pg_hba_file_rules " "WHERE type='host' AND error IS NULL"
            ).fetchall()
        ]
        if encryption != "scram-sha-256" or not methods or set(methods) != {"scram-sha-256"}:
            raise ValueError("Pilot database host authentication is not exclusively SCRAM")
        role_privileges = conn.execute(
            "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication "
            "FROM pg_roles WHERE rolname = 'inv_lan_runtime'"
        ).fetchone()
        if role_privileges != (False, False, False, False, False):
            raise ValueError("Pilot runtime role has elevated privileges")
        memberships = [
            row[0]
            for row in conn.execute(
                "SELECT parent.rolname FROM pg_auth_members m "
                "JOIN pg_roles child ON child.oid=m.member "
                "JOIN pg_roles parent ON parent.oid=m.roleid "
                "WHERE child.rolname='inv_lan_runtime' ORDER BY parent.rolname"
            ).fetchall()
        ]
        if memberships != ["inv_kernel"]:
            raise ValueError("Pilot runtime role membership differs from inv_kernel only")
    with psycopg.connect(runtime_dsn) as conn:
        if conn.execute("SELECT current_user").fetchone()[0] != "inv_lan_runtime":
            raise ValueError("Pilot runtime credential is not role-bound")
    state["adminDSN"] = admin_dsn
    state["runtimeDSN"] = runtime_dsn
    state["databaseAuthentication"] = "scram-sha-256"
    save(path, state)
    print(
        json.dumps(
            {
                "databaseAuthentication": "scram-sha-256",
                "missingCredentialRejected": True,
                "wrongCredentialRejected": True,
                "adminCredentialAccepted": True,
                "runtimeCredentialAccepted": True,
                "credentialsPrinted": False,
            }
        )
    )


def _pem_certificates(raw):
    blocks = re.findall(
        b"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", raw, flags=re.DOTALL
    )
    return [x509.load_pem_x509_certificate(block) for block in blocks]


def _load_external_ca(key_path, password_path, chain_path):
    values = (key_path, password_path, chain_path)
    if not all(values):
        raise ValueError("External CA key, password file, and chain are all required")
    for value in values:
        if value.is_symlink() or not value.is_file():
            raise ValueError("External CA inputs must be regular files")
    key_raw = key_path.read_bytes()
    password = password_path.read_bytes().strip()
    chain_raw = chain_path.read_bytes()
    if not password or len(password) > 1024 or len(chain_raw) > 65536:
        raise ValueError("External CA input is invalid")
    key = serialization.load_pem_private_key(key_raw, password=password)
    certificates = _pem_certificates(chain_raw)
    if not isinstance(key, Ed25519PrivateKey) or len(certificates) != 2:
        raise ValueError("External CA must be one Ed25519 intermediate and one root")
    intermediate, root = certificates
    now = datetime.now(timezone.utc)
    basic = intermediate.extensions.get_extension_for_class(x509.BasicConstraints).value
    root_basic = root.extensions.get_extension_for_class(x509.BasicConstraints).value
    if (
        not basic.ca
        or basic.path_length != 0
        or not root_basic.ca
        or root_basic.path_length != 1
        or not intermediate.not_valid_before_utc <= now < intermediate.not_valid_after_utc
        or not root.not_valid_before_utc <= now < root.not_valid_after_utc
        or key.public_key().public_bytes_raw() != intermediate.public_key().public_bytes_raw()
    ):
        raise ValueError("External CA constraints or key binding differ")
    root.public_key().verify(intermediate.signature, intermediate.tbs_certificate_bytes)
    return key_raw, password, chain_raw, key, intermediate


def ensure_pilot_pki(path, state, args):
    external = any(
        getattr(args, name, None) is not None
        for name in ("ca_key", "ca_key_password_file", "ca_chain")
    )
    if (path / "ca.pem").exists():
        if external:
            _, _, chain_raw, _, _ = _load_external_ca(
                args.ca_key, args.ca_key_password_file, args.ca_chain
            )
            if (
                hashlib.sha256((path / "ca.pem").read_bytes()).digest()
                != hashlib.sha256(chain_raw).digest()
            ):
                raise ValueError("Existing pilot CA differs from requested external CA")
        if state.get("caMode") == "external-intermediate" and any(
            (path / name).exists() for name in ("ca-key.pem", "ca-key.pass")
        ):
            raise ValueError("External issuing key must not be copied into pilot state")
        return state
    if external:
        key_raw, password, chain_raw, ca_key, ca_cert = _load_external_ca(
            args.ca_key, args.ca_key_password_file, args.ca_chain
        )
        state["caMode"] = "external-intermediate"
        state["caBundleSHA256"] = hashlib.sha256(chain_raw).hexdigest()
    else:
        ca_key, ca_cert = ca_pair()
        key_raw, password, chain_raw = private_pem(ca_key), None, pem(ca_cert)
        state["caMode"] = "pilot-self-signed"
        state["caBundleSHA256"] = hashlib.sha256(chain_raw).hexdigest()
    control_key, signing_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    control = issue(
        ca_key,
        ca_cert,
        control_key.public_key(),
        f'spiffe://saintvision.ai/tenant/{state["tenantId"]}/control-plane/epoch/{state["epoch"]}',
    )
    material = [
        ("control-key.pem", private_pem(control_key)),
        ("control-cert.pem", pem(control)),
        ("signer-key.pem", private_pem(signing_key)),
        (
            "signer.pub",
            signing_key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            ),
        ),
        ("ca.pem", chain_raw),
    ]
    if state["caMode"] == "pilot-self-signed":
        material.append(("ca-key.pem", key_raw))
    for name, data in material:
        write(path / name, data)
    return state


def load_pilot_ca_key(path, *, key_path=None, password_path=None, chain_path=None):
    state = load(path) if (path / "private-state.json").is_file() else {}
    if state.get("caMode") == "external-intermediate" or any(
        value is not None for value in (key_path, password_path, chain_path)
    ):
        _, _, chain_raw, key, _ = _load_external_ca(key_path, password_path, chain_path)
        if (
            hashlib.sha256((path / "ca.pem").read_bytes()).digest()
            != hashlib.sha256(chain_raw).digest()
        ):
            raise ValueError("External issuing chain differs from pilot trust bundle")
        return key
    password_path = path / "ca-key.pass"
    password = password_path.read_bytes().strip() if password_path.is_file() else None
    key = serialization.load_pem_private_key((path / "ca-key.pem").read_bytes(), password=password)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Pilot issuing key type differs")
    return key


def load_prebuilt_image(archive_path, inspect_path, tag, target):
    """Validate a remotely built docker-save archive without using local Docker."""
    for value in (archive_path, inspect_path):
        if value is None or value.is_symlink() or not value.is_file():
            raise ValueError("Prebuilt image inputs must be regular files")
    if inspect_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Prebuilt image inspection exceeds limit")
    inspected_values = json.loads(inspect_path.read_text("utf-8"))
    if not isinstance(inspected_values, list) or len(inspected_values) != 1:
        raise ValueError("Prebuilt image inspection must contain exactly one image")
    inspected = inspected_values[0]
    image_id = inspected.get("Id")
    tags = inspected.get("RepoTags")
    rootfs = inspected.get("RootFS")
    if (
        not isinstance(image_id, str)
        or not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id)
        or not isinstance(tags, list)
        or tag not in tags
        or not isinstance(rootfs, dict)
        or not isinstance(rootfs.get("Layers"), list)
        or not isinstance(inspected.get("Config"), dict)
    ):
        raise ValueError("Prebuilt image inspection is incomplete")
    with tarfile.open(archive_path, mode="r:*") as archive:
        manifest_member = archive.getmember("manifest.json")
        if not manifest_member.isfile() or manifest_member.size > 1024 * 1024:
            raise ValueError("Prebuilt image manifest is invalid")
        stream = archive.extractfile(manifest_member)
        manifest = json.load(stream)
        if not isinstance(manifest, list) or len(manifest) != 1:
            raise ValueError("Prebuilt image archive must contain exactly one image")
        entry = manifest[0]
        config_name = entry.get("Config")
        config_match = re.fullmatch(
            r"(?:blobs/sha256/)?([a-f0-9]{64})(?:\.json)?",
            config_name if isinstance(config_name, str) else "",
        )
        if not config_match or tag not in entry.get("RepoTags", []):
            raise ValueError("Prebuilt archive and inspection identity differ")
        config_digest = "sha256:" + config_match.group(1)
        config_member = archive.getmember(config_name)
        if not config_member.isfile() or config_member.size > 2 * 1024 * 1024:
            raise ValueError("Prebuilt image config is missing")
        config_stream = archive.extractfile(config_member)
        config_raw = config_stream.read()
        if hashlib.sha256(config_raw).hexdigest() != config_match.group(1):
            raise ValueError("Prebuilt image config digest differs")
        if image_id != config_digest and "index.json" not in archive.getnames():
            raise ValueError("Prebuilt image ID differs from archive config digest")
        archive_config = json.loads(config_raw)
        archive_runtime = archive_config.get("config")
        archive_layers = archive_config.get("rootfs", {}).get("diff_ids")
        if not isinstance(archive_runtime, dict) or archive_layers != rootfs.get("Layers"):
            raise ValueError("Prebuilt archive and inspection layers differ")
        inspect_runtime = inspected["Config"]
        for key in ("Entrypoint", "Cmd", "WorkingDir", "Env", "User"):
            if archive_runtime.get(key) != inspect_runtime.get(key):
                raise ValueError("Prebuilt archive and inspection runtime differ")
        if image_id != config_digest:
            # Docker's containerd image store exposes the OCI manifest digest as
            # inspect.Id. Classic stores expose the config digest instead. Bind
            # either representation to the same docker-save archive rather than
            # accepting an arbitrary inspect ID from the build host.
            try:
                index_member = archive.getmember("index.json")
                layout_member = archive.getmember("oci-layout")
            except KeyError:
                raise ValueError("Prebuilt image ID differs from archive config digest") from None
            if (
                not index_member.isfile()
                or index_member.size > 1024 * 1024
                or not layout_member.isfile()
                or layout_member.size > 1024
            ):
                raise ValueError("Prebuilt OCI image index is invalid")
            index = json.load(archive.extractfile(index_member))
            layout = json.load(archive.extractfile(layout_member))
            descriptors = index.get("manifests") if isinstance(index, dict) else None
            if (
                layout != {"imageLayoutVersion": "1.0.0"}
                or index.get("schemaVersion") != 2
                or not isinstance(descriptors, list)
                or len(descriptors) != 1
            ):
                raise ValueError("Prebuilt OCI image index is invalid")
            descriptor = descriptors[0]
            digest = descriptor.get("digest") if isinstance(descriptor, dict) else None
            digest_match = re.fullmatch(r"sha256:([a-f0-9]{64})", digest or "")
            annotations = descriptor.get("annotations") if isinstance(descriptor, dict) else None
            if (
                not digest_match
                or image_id != digest
                or not isinstance(annotations, dict)
                or annotations.get("org.opencontainers.image.ref.name") != tag.rsplit(":", 1)[-1]
                or not annotations.get("io.containerd.image.name", "").endswith("/" + tag)
            ):
                raise ValueError("Prebuilt OCI manifest identity differs from inspection")
            manifest_member = archive.getmember("blobs/sha256/" + digest_match.group(1))
            if (
                not manifest_member.isfile()
                or manifest_member.size != descriptor.get("size")
                or manifest_member.size > 2 * 1024 * 1024
            ):
                raise ValueError("Prebuilt OCI manifest is invalid")
            manifest_raw = archive.extractfile(manifest_member).read()
            if hashlib.sha256(manifest_raw).hexdigest() != digest_match.group(1):
                raise ValueError("Prebuilt OCI manifest digest differs")
            oci_manifest = json.loads(manifest_raw)
            legacy_layers = []
            for layer_name in entry.get("Layers", []):
                layer_match = re.fullmatch(
                    r"(?:blobs/sha256/)?([a-f0-9]{64})(?:/layer\.tar)?", layer_name
                )
                if not layer_match:
                    raise ValueError("Prebuilt archive layer identity is invalid")
                legacy_layers.append("sha256:" + layer_match.group(1))
            oci_layers = oci_manifest.get("layers")
            if (
                oci_manifest.get("schemaVersion") != 2
                or oci_manifest.get("config", {}).get("digest") != config_digest
                or not isinstance(oci_layers, list)
                or [layer.get("digest") for layer in oci_layers] != legacy_layers
            ):
                raise ValueError("Prebuilt OCI manifest and archive content differ")
    shutil.copyfile(archive_path, target)
    return image_id, inspected


def configured_nodes(state):
    """Return the configured Nodes while retaining the version-1 state shape."""
    raw = state.get("nodes")
    if raw is None:
        raw = [
            dict(
                nodeId=state["nodeId"],
                nodeIP=state["nodeIP"],
                nodePort=state.get("nodePort", 18443),
                provisioned=bool(state.get("initialized")),
            )
        ]
    nodes = []
    seen_ids, seen_ips = set(), set()
    colocation_allowed = state.get("serverNodeColocationAllowed", False)
    if type(colocation_allowed) is not bool:
        raise ValueError("Server Node co-location authorization must be boolean")
    for item in raw:
        node = dict(item)
        node.setdefault("nodePort", 18443)
        node.setdefault("provisioned", bool(state.get("initialized")))
        colocated = node["nodeIP"] == state.get("serverIP")
        declared_colocation = node.get("coLocatedWithControlPlane", colocated)
        if type(declared_colocation) is not bool or declared_colocation != colocated:
            raise ValueError("Node Control Plane co-location metadata differs from its address")
        disabled = node.get("disabled", False)
        disabled_reason = node.get("disabledReason")
        if type(disabled) is not bool:
            raise ValueError("Node disabled marker must be boolean")
        if disabled:
            if not colocated or disabled_reason != COLOCATION_REVOKED_REASON:
                raise ValueError("Only a revoked co-located Node may be disabled in pilot state")
        elif disabled_reason is not None:
            raise ValueError("Active Node cannot carry a disabled reason")
        credential_revoked = node.get("credentialRevoked", False)
        revocation_reason = node.get("credentialRevocationReason")
        if type(credential_revoked) is not bool:
            raise ValueError("Node credential revocation marker must be boolean")
        if credential_revoked:
            if revocation_reason not in CERTIFICATE_REVOCATION_REASONS:
                raise ValueError("Node credential revocation reason is invalid")
        elif revocation_reason is not None:
            raise ValueError("Active credential cannot carry a revocation reason")
        if colocated and not colocation_allowed and not disabled:
            raise ValueError("Server Node co-location is not authorized in private state")
        node["coLocatedWithControlPlane"] = colocated
        if node["nodeId"] in seen_ids or node["nodeIP"] in seen_ips:
            raise ValueError("Duplicate Node identity or address in private state")
        seen_ids.add(node["nodeId"])
        seen_ips.add(node["nodeIP"])
        nodes.append(node)
    if not nodes:
        raise ValueError("At least one Node is required")
    return nodes


def active_configured_nodes(state):
    """Return Nodes authorized for bundles, enrollment, and observation."""
    return [
        node
        for node in configured_nodes(state)
        if not node.get("disabled", False) and not node.get("credentialRevoked", False)
    ]


def normalized_state(state):
    result = dict(state)
    nodes = configured_nodes(result)
    result["nodes"] = nodes
    primary = nodes[0]
    for key in ("nodeId", "nodeIP", "nodePort"):
        if key in result and result[key] != primary[key]:
            raise ValueError("Legacy primary Node fields differ from nodes[0]")
        result[key] = primary[key]
    return result


def load(path):
    return normalized_state(json.loads((path / "private-state.json").read_text("utf-8")))


def save(path, data):
    data = normalized_state(data)
    temp = path / "private-state.tmp"
    with temp.open("w", encoding="utf-8") as out:
        json.dump(data, out, indent=2)
    temp.chmod(0o600)
    os.replace(temp, path / "private-state.json")


def validate_node_ips(server_ip, node_ips, *, allow_server_node_colocation=False):
    server = ipaddress.ip_address(server_ip)
    if server.version != 4 or not server.is_private or server.is_loopback:
        raise ValueError("Explicit private LAN IPv4 addresses are required")
    if len(node_ips) != len(set(node_ips)):
        raise ValueError("Each Node address must be specified once")
    for value in node_ips:
        addr = ipaddress.ip_address(value)
        if addr.version != 4 or not addr.is_private or addr.is_loopback:
            raise ValueError("Explicit private LAN IPv4 addresses are required")
        if addr == server and not allow_server_node_colocation:
            raise ValueError(
                "Server and Node addresses must differ unless "
                "--allow-server-node-colocation is set"
            )


def add_requested_nodes(state, node_ips, *, node_port=None):
    """Add addresses without replacing any previously assigned identity."""
    result = normalized_state(state)
    nodes = [dict(node) for node in result["nodes"]]
    node_port = node_port or nodes[0]["nodePort"]
    if any(node["nodePort"] != node_port for node in nodes):
        raise ValueError("Requested Node port differs from existing pilot identity")
    existing = {node["nodeIP"]: node for node in nodes}
    added = []
    for node_ip in node_ips:
        if node_ip in existing:
            continue
        node = dict(nodeId=new_id("nod"), nodeIP=node_ip, nodePort=node_port, provisioned=False)
        nodes.append(node)
        existing[node_ip] = node
        added.append(node)
    result["nodes"] = nodes
    return normalized_state(result), added


def revoked_colocation_state(state):
    """Preserve a co-located identity while revoking its operational opt-in."""
    result = normalized_state(state)
    nodes = [dict(node) for node in result["nodes"]]
    revoked = []
    for node in nodes:
        if node["nodeIP"] == result["serverIP"]:
            node["disabled"] = True
            node["disabledReason"] = COLOCATION_REVOKED_REASON
            revoked.append(node)
    result["nodes"] = nodes
    result["serverNodeColocationAllowed"] = False
    return normalized_state(result), revoked


def node_by_id(state, node_id):
    matches = [node for node in active_configured_nodes(state) if node["nodeId"] == node_id]
    if len(matches) != 1:
        raise ValueError("CSR Node identity is not configured")
    return matches[0]


def node_from_csr(state, raw):
    if len(raw) > 16384:
        raise ValueError("CSR exceeds limit")
    csr = x509.load_pem_x509_csr(raw)
    names = csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if len(names) != 1:
        raise ValueError("CSR must contain one Node common name")
    return node_by_id(state, names[0].value)


def node_state_directory(path, node):
    target = path / "nodes" / node["nodeId"]
    target.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise ValueError("Node state must not be a symlink")
    if os.name != "nt":
        target.chmod(0o700)
    return target


def node_policy_path(path, state, node):
    if node["nodeId"] == configured_nodes(state)[0]["nodeId"]:
        return path / "peer-policy.json"
    return node_state_directory(path, node) / "peer-policy.json"


def node_public_directory(path, node):
    target = path / "public" / "nodes" / node["nodeId"]
    target.mkdir(parents=True, exist_ok=True)
    return target


def node_certificate_path(path, state, node):
    legacy = path / "public" / "node-cert.pem"
    specific = path / "public" / "nodes" / node["nodeId"] / "node-cert.pem"
    if specific.exists():
        return specific
    if node["nodeId"] == configured_nodes(state)[0]["nodeId"] and legacy.exists():
        return legacy
    return node_public_directory(path, node) / "node-cert.pem"


def ensure_node_policy(path, state, node):
    target = node_policy_path(path, state, node)
    expected = dict(
        version=1, tenantId=state["tenantId"], nodeId=node["nodeId"], recoveryEpoch=state["epoch"]
    )
    control = x509.load_pem_x509_certificate((path / "control-cert.pem").read_bytes())
    expected_fingerprints = [fingerprint(control)]
    if target.exists():
        policy = json.loads(target.read_text("utf-8"))
        if (
            any(policy.get(key) != value for key, value in expected.items())
            or policy.get("clientFingerprints") != expected_fingerprints
        ):
            raise ValueError("Existing peer policy identity differs")
        return target
    policy = dict(
        **expected,
        expiresAt=min(
            datetime.now(timezone.utc) + timedelta(days=6), control.not_valid_after_utc
        ).isoformat(),
        clientFingerprints=expected_fingerprints,
    )
    write(target, json.dumps(policy, indent=2))
    return target


def manifest_for_node(state, node, inspected, tag):
    manifest = {
        key: state[key] for key in ("tenantId", "epoch", "serverIP", "baseSHA", "agentImage")
    }
    colocated = node["nodeIP"] == state["serverIP"]
    manifest.update(
        nodeId=node["nodeId"],
        nodeIP=node["nodeIP"],
        nodePort=node["nodePort"],
        scope="observation-only",
        schemaVersion=3,
        agentTag=tag,
        coLocatedWithControlPlane=colocated,
        measurementEligible=dict(
            s05=False if colocated else None, s07=False if colocated else None
        ),
        exclusionReason="cp-host-colocation" if colocated else None,
        imageLayers=inspected["RootFS"]["Layers"],
        imageConfig=inspected["Config"],
    )
    return manifest


def artifact_for_client(state, public, client_ip, request_path):
    """Map a worker source address to only that worker's public artifact."""
    active = active_configured_nodes(state)
    matches = [node for node in active if node["nodeIP"] == client_ip]
    if len(matches) != 1:
        raise PermissionError("Client address is not an allowed Node")
    names = {
        "/worker.zip": "worker.zip",
        "/node-cert.pem": "node-cert.pem",
        "/workspace-worker.zip": "workspace-worker.zip",
    }
    name = names.get(request_path)
    if name is None:
        return None
    node = matches[0]
    target = public / "nodes" / node["nodeId"] / name
    if target.is_file():
        return target
    if node["nodeId"] == active[0]["nodeId"]:
        legacy = public / name
        if legacy.is_file():
            return legacy
    return None


def runtime(state):
    return Database(state["runtimeDSN"], recovery_epoch=state["epoch"])


def tls(path):
    return dict(
        ca_file=str(path / "ca.pem"),
        certificate_file=str(path / "control-cert.pem"),
        key_file=str(path / "control-key.pem"),
        timeout=5,
    )


def provision_observation_node(conn, state):
    conn.execute(
        "INSERT INTO inv.tenants VALUES(%s,%s) ON CONFLICT DO NOTHING",
        (state["tenantId"], "two-PC connection pilot"),
    )
    conn.execute(
        "INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch) VALUES(%s,%s,'offline',%s) ON CONFLICT DO NOTHING",
        (state["tenantId"], state["nodeId"], state["epoch"]),
    )
    # The tenant insert trigger creates a row with false. Pin the gate before
    # committing the new pilot; never leave its execution authority implicit.
    conn.execute(
        "INSERT INTO inv.tenant_controls(tenant_id,kill_switch) VALUES(%s,true) ON CONFLICT(tenant_id) DO UPDATE SET kill_switch=true,version=inv.tenant_controls.version+1,updated_at=clock_timestamp()",
        (state["tenantId"],),
    )


def init(args):
    path = args.state
    requested_node_port = getattr(args, "node_port", None)
    if requested_node_port is not None and not 1024 <= requested_node_port <= 65535:
        raise ValueError("Node publish port is invalid")
    requested_download_port = getattr(args, "download_port", None)
    if requested_download_port is not None and not 1024 <= requested_download_port <= 65535:
        raise ValueError("Bootstrap download port is invalid")
    validate_node_ips(
        args.server_ip, args.node_ip, allow_server_node_colocation=args.allow_server_node_colocation
    )
    private_directory(path)
    if (path / "private-state.json").exists():
        state = load(path)
        if state["serverIP"] != args.server_ip:
            raise ValueError("Existing server address differs")
        if args.allow_server_node_colocation and args.server_ip in args.node_ip:
            state["serverNodeColocationAllowed"] = True
        state, added = add_requested_nodes(state, args.node_ip, node_port=requested_node_port)
        if added:
            # Persist assigned identities before side effects. A retry resumes the
            # same Nodes and never rotates an existing identity or channel.
            save(path, state)
        if requested_download_port is not None and requested_download_port != state.get(
            "downloadPort"
        ):
            issued = list((path / "public" / "nodes").glob("*/node-cert.pem"))
            if issued or (path / "public" / "node-cert.pem").is_file():
                raise ValueError("Bootstrap port cannot change after enrollment")
            state["downloadPort"] = requested_download_port
            save(path, state)
        if state.get("initialized") and all(
            node["provisioned"] for node in configured_nodes(state)
        ):
            if state.get("databaseMode") == EXTERNAL_DATABASE_MODE:
                if getattr(args, "admin_dsn_file", None) is not None:
                    if state["adminDSN"] != read_external_dsn(args.admin_dsn_file, "postgres"):
                        raise ValueError("Existing external admin DSN differs")
                    if state["runtimeDSN"] != read_external_dsn(
                        args.runtime_dsn_file, "inv_lan_runtime"
                    ):
                        raise ValueError("Existing external runtime DSN differs")
            state = ensure_pilot_pki(path, state, args)
            save(path, state)
            print("Existing pilot preserved; use status.")
            return
    else:
        epoch, tenant = str(uuid4()), str(uuid4())
        db_password, app_password = uuid4().hex + uuid4().hex, uuid4().hex + uuid4().hex
        node_port = requested_node_port or 18443
        nodes = [
            dict(nodeId=new_id("nod"), nodeIP=node_ip, nodePort=node_port, provisioned=False)
            for node_ip in args.node_ip
        ]
        state = dict(
            epoch=epoch,
            tenantId=tenant,
            nodes=nodes,
            serverIP=args.server_ip,
            nodeId=nodes[0]["nodeId"],
            nodeIP=nodes[0]["nodeIP"],
            nodePort=nodes[0]["nodePort"],
            downloadPort=requested_download_port or 18081,
            serverNodeColocationAllowed=(
                args.allow_server_node_colocation and args.server_ip in args.node_ip
            ),
            baseSHA=run(["git", "rev-parse", "HEAD"], cwd=ROOT),
            initialized=False,
        )
        external_dsn = getattr(args, "admin_dsn_file", None) is not None
        if external_dsn != (getattr(args, "runtime_dsn_file", None) is not None):
            raise ValueError("Both external database DSN files are required")
        if external_dsn:
            state["databaseMode"] = EXTERNAL_DATABASE_MODE
            state["container"] = None
            state["dbPort"] = int(
                psycopg.conninfo.conninfo_to_dict(
                    read_external_dsn(args.admin_dsn_file, "postgres")
                )["port"]
            )
            state["adminDSN"] = read_external_dsn(args.admin_dsn_file, "postgres")
            state["runtimeDSN"] = read_external_dsn(args.runtime_dsn_file, "inv_lan_runtime")
        else:
            state["databaseMode"] = LOCAL_DATABASE_MODE
            state["container"] = "saintvision-lan-db-" + epoch[:8]
            state["dbPort"] = 55440
            state["adminDSN"] = make_conninfo(
                host="127.0.0.1",
                port=55440,
                dbname="saintvision_lan",
                user="postgres",
                password=db_password,
                connect_timeout=5,
            )
            state["runtimeDSN"] = make_conninfo(
                state["adminDSN"], user="inv_lan_runtime", password=app_password
            )
        save(path, state)
        if state["databaseMode"] == LOCAL_DATABASE_MODE:
            write(
                path / "postgres.env",
                f"POSTGRES_DB=saintvision_lan\nPOSTGRES_USER=postgres\nPOSTGRES_PASSWORD={db_password}\n",
            )
    state.setdefault("databaseMode", LOCAL_DATABASE_MODE)
    if state["databaseMode"] == EXTERNAL_DATABASE_MODE:
        if getattr(args, "admin_dsn_file", None) is not None:
            if state["adminDSN"] != read_external_dsn(args.admin_dsn_file, "postgres"):
                raise ValueError("Existing external admin DSN differs")
            if state["runtimeDSN"] != read_external_dsn(args.runtime_dsn_file, "inv_lan_runtime"):
                raise ValueError("Existing external runtime DSN differs")
    elif state["databaseMode"] == LOCAL_DATABASE_MODE:
        exists = subprocess.run(
            ["docker", "container", "inspect", state["container"]], capture_output=True, timeout=15
        )
        if exists.returncode:
            image = run(
                ["docker", "image", "inspect", "pgvector/pgvector:pg16", "--format", "{{.Id}}"]
            )
            run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    state["container"],
                    "--label",
                    "ai.saintvision.pilot=" + state["epoch"],
                    "--restart",
                    "unless-stopped",
                    "--pids-limit",
                    "256",
                    "--memory",
                    "512m",
                    "--cpus",
                    "1",
                    "--publish",
                    "127.0.0.1:55440:5432",
                    "--env-file",
                    path / "postgres.env",
                    "--mount",
                    f'type=volume,source={state["container"]}-data,target=/var/lib/postgresql/data',
                    image,
                ],
                timeout=60,
            )
        else:
            info = json.loads(exists.stdout)[0]
            if info["Config"]["Labels"].get("ai.saintvision.pilot") != state["epoch"]:
                raise ValueError("Container ownership differs")
            if not info["State"]["Running"]:
                run(["docker", "start", state["container"]])
    else:
        raise ValueError("Database mode differs")
    for attempt in range(30):
        try:
            with psycopg.connect(state["adminDSN"]):
                break
        except psycopg.OperationalError:
            if attempt == 29:
                raise RuntimeError("Pilot database readiness timed out") from None
            time.sleep(1)
    from sqlalchemy.engine import URL

    info = psycopg.conninfo.conninfo_to_dict(state["adminDSN"])
    url = URL.create(
        "postgresql+psycopg",
        username=info["user"],
        password=info.get("password"),
        host=info["host"],
        port=int(info["port"]),
        database=info["dbname"],
        query={"passfile": info["passfile"]} if info.get("passfile") else None,
    )
    env = dict(os.environ, INV_MIGRATION_DSN=url.render_as_string(hide_password=False))
    print("Applying published migrations to the isolated pilot database.", flush=True)
    run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, cwd=ROOT, timeout=120)
    with psycopg.connect(state["adminDSN"]) as conn:
        runtime_info = psycopg.conninfo.conninfo_to_dict(state["runtimeDSN"])
        runtime_password = runtime_info.get("password")
        if state["databaseMode"] == EXTERNAL_DATABASE_MODE:
            runtime_password = external_dsn_password(state["runtimeDSN"], "inv_lan_runtime")
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='inv_lan_runtime'").fetchone():
            conn.execute(
                "CREATE ROLE inv_lan_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
            )
        if runtime_password:
            conn.execute(
                sql.SQL("ALTER ROLE inv_lan_runtime PASSWORD {}").format(
                    sql.Literal(runtime_password)
                )
            )
        conn.execute("GRANT inv_kernel TO inv_lan_runtime")
        prior = conn.execute("SELECT epoch FROM inv.control_epoch").fetchone()
        if prior and str(prior[0]) != state["epoch"]:
            raise ValueError("Recovery epoch differs; refusing reset")
        conn.execute(
            "INSERT INTO inv.control_epoch VALUES(true,%s) ON CONFLICT DO NOTHING",
            (state["epoch"],),
        )
        for node in configured_nodes(state):
            provision_observation_node(conn, dict(state, **node))
    state = ensure_pilot_pki(path, state, args)
    for node in configured_nodes(state):
        ensure_node_policy(path, state, node)
    with runtime(state).transaction(state["tenantId"]) as conn:
        conn.execute("SELECT node_id FROM inv.node_resource_snapshots LIMIT 0")
        if not conn.execute("SELECT kill_switch FROM inv.tenant_controls").fetchone()[
            "kill_switch"
        ]:
            raise ValueError("Observation-only execution gate was not persisted")
    provisioned_nodes = configured_nodes(state)
    for node in provisioned_nodes:
        node["provisioned"] = True
    state["nodes"] = provisioned_nodes
    state["initialized"] = True
    save(path, state)
    print(
        json.dumps(
            dict(
                database="ready",
                scope="observation-only",
                nodeId=state["nodeId"],
                node="offline-awaiting-CSR",
                nodes=[
                    dict(
                        nodeId=node["nodeId"],
                        nodeIP=node["nodeIP"],
                        coLocatedWithControlPlane=node["coLocatedWithControlPlane"],
                        state="offline-awaiting-CSR",
                    )
                    for node in configured_nodes(state)
                ],
                workloadExecution="disabled",
            )
        )
    )


def bundle(args):
    path, state = args.state, load(args.state)
    nodes = active_configured_nodes(state)
    if not nodes:
        raise ValueError("No active Node remains after co-location revocation")
    if not state["initialized"] or not all(node["provisioned"] for node in nodes):
        raise ValueError("Initialize the pilot first")
    output = path / "public"
    output.mkdir(exist_ok=True)
    build = path / "node-build"
    build.mkdir(exist_ok=True)
    env = dict(os.environ, GOOS="linux", GOARCH="amd64", CGO_ENABLED="0")
    tag = "saintvision-lan-node:" + state["epoch"][:8]
    prebuilt_image = getattr(args, "prebuilt_image", None)
    prebuilt_inspect = getattr(args, "prebuilt_inspect", None)
    if (prebuilt_image is None) != (prebuilt_inspect is None):
        raise ValueError("Prebuilt image archive and inspection are both required")
    if prebuilt_image is not None and (args.reuse_image or args.go):
        raise ValueError("Prebuilt image cannot be combined with local build options")
    if prebuilt_image is not None:
        image, inspected = load_prebuilt_image(
            prebuilt_image, prebuilt_inspect, tag, path / "node-agent.tar"
        )
    elif not args.reuse_image:
        if not args.go:
            raise ValueError("An explicit Go executable is required for a new image build")
        print("Building Linux Node binary.", flush=True)
        run(
            [args.go, "build", "-trimpath", "-o", build / "inv-node", "./cmd/inv-node"],
            cwd=ROOT / "services/node-agent",
            env=env,
            timeout=180,
        )
        shutil.copyfile(ROOT / "deploy/lan/Dockerfile.node", build / "Dockerfile")
        run(["docker", "build", "--network=none", "--pull=false", "-t", tag, build], timeout=120)
    if prebuilt_image is None:
        image = run(["docker", "image", "inspect", tag, "--format", "{{.Id}}"])
        if args.reuse_image and image != state.get("agentImage"):
            raise ValueError("Existing image tag differs from the recorded content ID")
        # Preserve a named reference when importing into another Docker image store.
        run(["docker", "save", "-o", path / "node-agent.tar", tag], timeout=60)
        inspected = json.loads(run(["docker", "image", "inspect", image]))[0]
    state["agentImage"] = image
    save(path, state)
    artifacts = []
    for node in nodes:
        manifest = manifest_for_node(state, node, inspected, tag)
        node_output = node_public_directory(path, node)
        temporary = node_output / "worker.zip.tmp"
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            archive.write(path / "ca.pem", "ca.pem")
            archive.write(path / "signer.pub", "signer.pub")
            archive.write(node_policy_path(path, state, node), "peer-policy.json")
            archive.write(path / "node-agent.tar", "node-agent.tar")
            for name in (
                "prepare-worker.sh",
                "start-node.sh",
                "finish-worker.sh",
                "Prepare-Worker.ps1",
                "Start-Worker.ps1",
                "worker_config.py",
                "worker_leaf_rotation.py",
                "worker_storage.py",
                "worker_replacement.py",
                "worker_replace.py",
                "worker_storage_bridge.py",
                "Replace-Storage.ps1",
                "repair-node.sh",
                "Repair-Worker.ps1",
            ):
                archive.write(ROOT / "deploy/lan" / name, name)
        target = node_output / "worker.zip"
        os.replace(temporary, target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        (node_output / "worker.sha256").write_text(digest + "\n", "ascii")
        artifacts.append(
            dict(
                nodeId=node["nodeId"],
                nodeIP=node["nodeIP"],
                archive=str(target),
                sha256=digest,
                bytes=target.stat().st_size,
            )
        )
    # Preserve the original single-Node filesystem paths as aliases for the
    # primary Node. The HTTP server still resolves by source IP.
    primary = artifacts[0]
    alias = output / "worker.zip.tmp"
    shutil.copyfile(primary["archive"], alias)
    os.replace(alias, output / "worker.zip")
    (output / "worker.sha256").write_text(primary["sha256"] + "\n", "ascii")
    print(
        json.dumps(
            dict(
                nodes=artifacts,
                archive=str(output / "worker.zip"),
                sha256=primary["sha256"],
                bytes=primary["bytes"],
            )
        )
    )


def enroll(args):
    path, state = args.state, load(args.state)
    raw = args.csr.read_bytes()
    node = node_from_csr(state, raw)
    public = csr_public_key(raw, node["nodeId"])
    target = node_certificate_path(path, state, node)
    if target.exists():
        cert = x509.load_pem_x509_certificate(target.read_bytes())
        if cert.public_key().public_bytes_raw() != public.public_bytes_raw():
            raise ValueError(
                "Node already enrolled with a different key; explicit rotation required"
            )
    else:
        ca = x509.load_pem_x509_certificate((path / "ca.pem").read_bytes())
        key = load_pilot_ca_key(
            path,
            key_path=getattr(args, "ca_key", None),
            password_path=getattr(args, "ca_key_password_file", None),
            chain_path=getattr(args, "ca_chain", None),
        )
        cert = issue(
            key,
            ca,
            public,
            node_uri(NodePrincipal(state["tenantId"], node["nodeId"]), state["epoch"]),
            address=node["nodeIP"],
        )
        write(target, pem(cert))
    primary = configured_nodes(state)[0]
    legacy = path / "public" / "node-cert.pem"
    if node["nodeId"] == primary["nodeId"] and target != legacy:
        if legacy.exists() and legacy.read_bytes() != target.read_bytes():
            raise ValueError("Primary certificate alias differs; explicit rotation required")
        if not legacy.exists():
            write(legacy, target.read_bytes())
    with psycopg.connect(state["adminDSN"]) as conn:
        conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (state["tenantId"],))
        previous = conn.execute(
            "SELECT certificate_sha256 FROM inv.node_channels WHERE tenant_id=%s AND node_id=%s",
            (state["tenantId"], node["nodeId"]),
        ).fetchone()
        if previous and previous[0] != fingerprint(cert):
            raise ValueError("Pinned channel differs; explicit rotation required")
        if not previous:
            provision_channel(
                conn,
                NodePrincipal(state["tenantId"], node["nodeId"]),
                epoch=state["epoch"],
                endpoint=f'https://{node["nodeIP"]}:{node["nodePort"]}',
                certificate_der=cert.public_bytes(serialization.Encoding.DER),
                expected_version=0,
            )
    print(
        json.dumps(
            dict(
                enrolled=True,
                nodeId=node["nodeId"],
                certificateSHA256=fingerprint(cert),
                fileSHA256=hashlib.sha256(target.read_bytes()).hexdigest(),
                node="awaiting-mTLS-observation",
            )
        )
    )


def _canonical_json(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _rotation_digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _utc_z(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_revocations(path):
    if path is None or path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("An exact regular revocation registry is required")
    rows = json.loads(path.read_text("utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Revocation registry must be a list")
    fingerprints = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or not re.fullmatch(r"[a-f0-9]{64}", str(row.get("certificateSHA256", "")))
            or not isinstance(row.get("serialNumber"), str)
            or not isinstance(row.get("reason"), str)
            or not isinstance(row.get("revokedAt"), str)
        ):
            raise ValueError("Revocation registry entry is incomplete")
        fingerprints.add(row["certificateSHA256"])
    return fingerprints


def _validate_current_control_leaf(certificate, intermediate, *, state, now):
    intermediate.public_key().verify(certificate.signature, certificate.tbs_certificate_bytes)
    constraints = certificate.extensions.get_extension_for_class(x509.BasicConstraints).value
    usages = certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    names = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    expected_uri = (
        f'spiffe://saintvision.ai/tenant/{state["tenantId"]}/control-plane/epoch/{state["epoch"]}'
    )
    if (
        certificate.issuer != intermediate.subject
        or constraints.ca
        or list(usages) != [ExtendedKeyUsageOID.CLIENT_AUTH]
        or names.get_values_for_type(x509.UniformResourceIdentifier) != [expected_uri]
        or names.get_values_for_type(x509.IPAddress)
        or not certificate.not_valid_before_utc <= now < certificate.not_valid_after_utc
    ):
        raise ValueError("Current Control Plane leaf is not bound to the exact issuing chain")


def _rotation_material(path):
    manifest_raw = (path / "rotation.json").read_bytes()
    manifest = json.loads(manifest_raw)
    if not isinstance(manifest, dict) or set(manifest) != ROTATION_MANIFEST_KEYS:
        raise ValueError("Rotation manifest shape differs")
    files = {}
    for name in ROTATION_FILE_NAMES:
        target = path / name
        if target.is_symlink() or not target.is_file() or not 0 < target.stat().st_size <= 65536:
            raise ValueError("Rotation public material is missing or unsafe")
        files[name] = target.read_bytes()
    if manifest.get("schemaVersion") != ROTATION_SCHEMA or set(manifest.get("files", {})) != set(
        ROTATION_FILE_NAMES
    ):
        raise ValueError("Rotation schema or file set differs")
    if any(
        _rotation_digest(files[name]) != manifest["files"].get(name) for name in ROTATION_FILE_NAMES
    ):
        raise ValueError("Rotation public material digest differs")
    return manifest_raw, manifest, files


def _channel_row(conn, state, node, *, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    row = conn.execute(
        "SELECT version,certificate_sha256,certificate_not_after,enabled,endpoint "
        "FROM inv.node_channels WHERE tenant_id=%s AND node_id=%s" + suffix,
        (state["tenantId"], node["nodeId"]),
    ).fetchone()
    if not row:
        raise ValueError("Node channel is not enrolled")
    return row


def _batch_journal_path(path):
    return path / "leaf-rotation-batch.json"


def _load_batch_journal(path):
    target = _batch_journal_path(path)
    if not target.exists():
        return None
    value = json.loads(target.read_text("utf-8"))
    if (
        not isinstance(value, dict)
        or set(value) != BATCH_JOURNAL_KEYS
        or value.get("schemaVersion") != BATCH_ROTATION_SCHEMA
        or value.get("phase") not in {"prepared", "staging", "staged", "switched"}
        or not isinstance(value.get("stagedNodeIds"), list)
        or len(value["stagedNodeIds"]) != len(set(value["stagedNodeIds"]))
    ):
        raise ValueError("Leaf rotation batch journal differs")
    return value


def _batch_material(path):
    manifest_raw = (path / "batch.json").read_bytes()
    manifest = json.loads(manifest_raw)
    if (
        not isinstance(manifest, dict)
        or set(manifest) != BATCH_MANIFEST_KEYS
        or manifest.get("schemaVersion") != BATCH_ROTATION_SCHEMA
        or not re.fullmatch(r"[a-f0-9]{32}", str(manifest.get("batchId", "")))
        or not isinstance(manifest.get("nodes"), list)
        or len(manifest["nodes"]) < 2
    ):
        raise ValueError("Leaf rotation batch manifest differs")
    expected_node_keys = {
        "nodeId",
        "bundlePath",
        "proposalDigest",
        "currentChannelVersion",
        "targetChannelVersion",
        "nextNodeCertificateSHA256",
    }
    bundles = {}
    node_ids = []
    for row in manifest["nodes"]:
        if not isinstance(row, dict) or set(row) != expected_node_keys:
            raise ValueError("Leaf rotation batch node entry differs")
        node_id = row["nodeId"]
        if (
            not re.fullmatch(r"nod_[0-9A-HJKMNP-TV-Z]{26}", str(node_id))
            or row["bundlePath"] != f"nodes/{node_id}"
            or row["targetChannelVersion"] != row["currentChannelVersion"] + 1
        ):
            raise ValueError("Leaf rotation batch Node identity or version differs")
        node_ids.append(node_id)
        raw, proposal, files = _rotation_material(path / row["bundlePath"])
        next_node = x509.load_pem_x509_certificate(files["node-cert.pem"])
        next_control = x509.load_pem_x509_certificate(files["control-cert.pem"])
        if (
            _rotation_digest(raw) != row["proposalDigest"]
            or proposal["rotationId"] != manifest["batchId"]
            or proposal["nodeId"] != node_id
            or proposal["tenantId"] != manifest["tenantId"]
            or proposal["recoveryEpoch"] != manifest["recoveryEpoch"]
            or proposal["currentChannelVersion"] != row["currentChannelVersion"]
            or proposal["targetChannelVersion"] != row["targetChannelVersion"]
            or proposal["nextNodeCertificateSHA256"] != row["nextNodeCertificateSHA256"]
            or proposal["currentControlCertificateSHA256"]
            != manifest["currentControlCertificateSHA256"]
            or proposal["nextControlCertificateSHA256"] != manifest["nextControlCertificateSHA256"]
            or proposal["caBundleSHA256"] != manifest["caBundleSHA256"]
            or proposal["overlapExpiresAt"] != manifest["overlapExpiresAt"]
            or proposal["certificateNotAfter"] != manifest["certificateNotAfter"]
            or fingerprint(next_node) != proposal["nextNodeCertificateSHA256"]
            or fingerprint(next_control) != proposal["nextControlCertificateSHA256"]
            or _rotation_digest(files["ca.pem"]) != proposal["caBundleSHA256"]
        ):
            raise ValueError("Leaf rotation batch and Node proposal differ")
        bundles[node_id] = (raw, proposal, files)
    if node_ids != sorted(node_ids) or len(node_ids) != len(set(node_ids)):
        raise ValueError("Leaf rotation batch Nodes must be unique and sorted")
    control_values = {files["control-cert.pem"] for _raw, _proposal, files in bundles.values()}
    if len(control_values) != 1:
        raise ValueError("Leaf rotation batch must bind one shared Control Plane leaf")
    return manifest_raw, manifest, bundles


def _write_batch_journal(path, *, manifest_raw, manifest, bundle, phase, staged):
    value = {
        "schemaVersion": BATCH_ROTATION_SCHEMA,
        "batchId": manifest["batchId"],
        "batchDigest": _rotation_digest(manifest_raw),
        "bundlePath": str(bundle.resolve()),
        "phase": phase,
        "stagedNodeIds": sorted(staged),
    }
    atomic_write(_batch_journal_path(path), _canonical_json(value))
    return value


def _assert_batch_journal(journal, *, manifest_raw, manifest, bundle):
    if not journal or any(
        (
            journal["batchId"] != manifest["batchId"],
            journal["batchDigest"] != _rotation_digest(manifest_raw),
            journal["bundlePath"] != str(bundle.resolve()),
        )
    ):
        raise ValueError("Another leaf rotation batch owns the pilot state")


def _write_rotation_public_material(
    output,
    *,
    state,
    node,
    current_node,
    current_control,
    control_key,
    public_key,
    ca_key,
    intermediate,
    chain_raw,
    revocations,
    now,
    current_version,
    overlap_seconds,
    leaf_valid_seconds,
    rotation_id,
    shared_control_raw=None,
):
    principal = NodePrincipal(state["tenantId"], node["nodeId"])
    if current_node.public_key().public_bytes_raw() != public_key.public_bytes_raw():
        raise ValueError("Recovery CSR does not preserve the pinned Node key")
    current_identity = certificate_identity(
        current_node.public_bytes(serialization.Encoding.DER), principal, state["epoch"], now=now
    )
    current_names = current_node.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value
    if (
        current_identity != (fingerprint(current_node), current_node.not_valid_after_utc)
        or current_names.get_values_for_type(x509.IPAddress)
        != [ipaddress.ip_address(node["nodeIP"])]
        or current_node.issuer != intermediate.subject
        or fingerprint(current_node) in revocations
        or fingerprint(current_control) in revocations
    ):
        raise ValueError("Recovery Node or Control Plane identity is invalid or revoked")
    intermediate.public_key().verify(current_node.signature, current_node.tbs_certificate_bytes)
    lifetime = timedelta(seconds=leaf_valid_seconds)
    next_node = issue(
        ca_key,
        intermediate,
        public_key,
        node_uri(principal, state["epoch"]),
        address=node["nodeIP"],
        now=now,
        valid_for=lifetime,
    )
    if shared_control_raw is None:
        next_control = issue(
            ca_key,
            intermediate,
            control_key.public_key(),
            f'spiffe://saintvision.ai/tenant/{state["tenantId"]}/control-plane/epoch/{state["epoch"]}',
            now=now,
            valid_for=lifetime,
        )
    else:
        next_control = x509.load_pem_x509_certificate(shared_control_raw)
        _validate_current_control_leaf(next_control, intermediate, state=state, now=now)
    not_after = min(next_node.not_valid_after_utc, next_control.not_valid_after_utc)
    overlap_expires = min(now + timedelta(seconds=overlap_seconds), not_after)
    if overlap_expires <= now + timedelta(minutes=10):
        raise ValueError("Recovery overlap is too short to complete safely")
    target_version = current_version + 1
    overlap_policy = {
        "version": target_version,
        "tenantId": state["tenantId"],
        "nodeId": node["nodeId"],
        "recoveryEpoch": state["epoch"],
        "expiresAt": _utc_z(overlap_expires),
        "clientFingerprints": [fingerprint(current_control), fingerprint(next_control)],
    }
    final_policy = {
        **overlap_policy,
        "expiresAt": _utc_z(not_after),
        "clientFingerprints": [fingerprint(next_control)],
    }
    material = {
        "ca.pem": chain_raw,
        "node-cert.pem": pem(next_node),
        "control-cert.pem": pem(next_control),
        "peer-policy-overlap.json": json.dumps(overlap_policy, indent=2).encode(),
        "peer-policy-final.json": json.dumps(final_policy, indent=2).encode(),
    }
    manifest = {
        "schemaVersion": ROTATION_SCHEMA,
        "rotationId": rotation_id,
        "tenantId": state["tenantId"],
        "nodeId": node["nodeId"],
        "recoveryEpoch": state["epoch"],
        "nodeIP": node["nodeIP"],
        "currentChannelVersion": current_version,
        "targetChannelVersion": target_version,
        "currentNodeCertificateSHA256": fingerprint(current_node),
        "nextNodeCertificateSHA256": fingerprint(next_node),
        "currentControlCertificateSHA256": fingerprint(current_control),
        "nextControlCertificateSHA256": fingerprint(next_control),
        "caBundleSHA256": _rotation_digest(chain_raw),
        "createdAt": _utc_z(now),
        "overlapExpiresAt": _utc_z(overlap_expires),
        "certificateNotAfter": _utc_z(not_after),
        "files": {name: _rotation_digest(raw) for name, raw in material.items()},
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in material.items():
        atomic_write(output / name, raw)
    raw = _canonical_json(manifest)
    atomic_write(output / "rotation.json", raw)
    return raw, manifest, material


def prepare_leaf_rotation_recovery_batch(args):
    """Supersede one expired, partially staged batch with a fresh all-Node batch."""
    path, state = args.state, load(args.state)
    output = args.output.resolve()
    active = sorted(active_configured_nodes(state), key=lambda item: item["nodeId"])
    csrs = {}
    for csr_path in args.csr:
        node = node_from_csr(state, csr_path.read_bytes())
        if node["nodeId"] in csrs:
            raise ValueError("Each active Node CSR must be supplied exactly once")
        csrs[node["nodeId"]] = csr_path
    if set(csrs) != {node["nodeId"] for node in active}:
        raise ValueError("Recovery must include every active Node")
    expired_path = args.expired_batch.resolve()
    expired_raw, expired, expired_bundles = _batch_material(expired_path)
    now = getattr(args, "_now", None) or datetime.now(timezone.utc)
    overlap_expires = datetime.fromisoformat(expired["overlapExpiresAt"].replace("Z", "+00:00"))
    certificate_not_after = datetime.fromisoformat(
        expired["certificateNotAfter"].replace("Z", "+00:00")
    )
    if not overlap_expires <= now < certificate_not_after:
        raise ValueError("Recovery requires an expired overlap and still-valid batch leaves")
    if set(expired_bundles) != set(csrs):
        raise ValueError("Expired batch no longer matches the active Node set")
    current_control_raw = (path / "control-cert.pem").read_bytes()
    current_control = x509.load_pem_x509_certificate(current_control_raw)
    if fingerprint(current_control) != expired["currentControlCertificateSHA256"]:
        raise ValueError("Expired partial batch is no longer on the old global Control Plane leaf")
    control_key = serialization.load_pem_private_key(
        (path / "control-key.pem").read_bytes(), password=None
    )
    if (
        not isinstance(control_key, Ed25519PrivateKey)
        or control_key.public_key().public_bytes_raw()
        != current_control.public_key().public_bytes_raw()
    ):
        raise ValueError("Pinned Control Plane key and recovery leaf differ")
    _root, _root_key, chain_raw, ca_key, intermediate = _load_external_ca(
        args.ca_key, args.ca_key_password_file, args.ca_chain
    )
    if _rotation_digest(chain_raw) != state.get("caBundleSHA256"):
        raise ValueError("Recovery issuing chain differs from the pilot pin")
    _validate_current_control_leaf(current_control, intermediate, state=state, now=now)
    revocations = _load_revocations(args.revocations)
    if output.exists():
        replacement_raw, replacement, replacement_bundles = _batch_material(output)
        replacement_overlap = datetime.fromisoformat(
            replacement["overlapExpiresAt"].replace("Z", "+00:00")
        )
        replacement_not_after = datetime.fromisoformat(
            replacement["certificateNotAfter"].replace("Z", "+00:00")
        )
        if (
            replacement["tenantId"] != expired["tenantId"]
            or replacement["recoveryEpoch"] != expired["recoveryEpoch"]
            or replacement["currentControlCertificateSHA256"]
            != expired["currentControlCertificateSHA256"]
            or replacement["caBundleSHA256"] != expired["caBundleSHA256"]
            or set(replacement_bundles) != set(expired_bundles)
            or not now < replacement_overlap < replacement_not_after
        ):
            raise ValueError("Existing recovery batch differs from the expired batch authority")
        for node_id, (_raw, _manifest, files) in replacement_bundles.items():
            next_node = x509.load_pem_x509_certificate(files["node-cert.pem"])
            public = csr_public_key(csrs[node_id].read_bytes(), node_id)
            if next_node.public_key().public_bytes_raw() != public.public_bytes_raw():
                raise ValueError("Existing recovery batch CSR binding differs")
        with exclusive_file(path / "leaf-rotation.lock"):
            journal = _load_batch_journal(path)
            try:
                _assert_batch_journal(
                    journal,
                    manifest_raw=replacement_raw,
                    manifest=replacement,
                    bundle=output,
                )
            except ValueError:
                _assert_batch_journal(
                    journal,
                    manifest_raw=expired_raw,
                    manifest=expired,
                    bundle=expired_path,
                )
                staged = set(journal["stagedNodeIds"])
                if (
                    journal["phase"] not in {"staging", "staged"}
                    or not staged
                    or staged == set(csrs)
                ):
                    raise ValueError("Recovery requires a non-empty, incomplete staged batch")
                with psycopg.connect(state["adminDSN"]) as conn:
                    conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (state["tenantId"],))
                    for node in active:
                        node_id = node["nodeId"]
                        old_manifest = expired_bundles[node_id][1]
                        new_manifest = replacement_bundles[node_id][1]
                        row = _channel_row(conn, state, node, lock=True)
                        expected_version = (
                            old_manifest["targetChannelVersion"]
                            if node_id in staged
                            else old_manifest["currentChannelVersion"]
                        )
                        expected_certificate = (
                            old_manifest["nextNodeCertificateSHA256"]
                            if node_id in staged
                            else old_manifest["currentNodeCertificateSHA256"]
                        )
                        next_node = x509.load_pem_x509_certificate(
                            replacement_bundles[node_id][2]["node-cert.pem"]
                        )
                        public = csr_public_key(csrs[node_id].read_bytes(), node_id)
                        if (
                            (row[0], row[1], row[3])
                            != (expected_version, expected_certificate, True)
                            or new_manifest["currentChannelVersion"] != expected_version
                            or new_manifest["currentNodeCertificateSHA256"] != expected_certificate
                            or next_node.public_key().public_bytes_raw()
                            != public.public_bytes_raw()
                        ):
                            raise ValueError("Existing recovery batch or channel baseline differs")
                recovery_record = {
                    "schemaVersion": RECOVERY_RECORD_SCHEMA,
                    "expiredBatchId": expired["batchId"],
                    "expiredBatchDigest": _rotation_digest(expired_raw),
                    "replacementBatchId": replacement["batchId"],
                    "replacementBatchDigest": _rotation_digest(replacement_raw),
                    "supersededAt": replacement["createdAt"],
                    "stagedNodeIds": sorted(staged),
                }
                recovery_path = path / f'leaf-rotation-recovery-{expired["batchId"]}.json'
                if recovery_path.exists() and recovery_path.read_bytes() != _canonical_json(
                    recovery_record
                ):
                    raise ValueError("Expired batch recovery record differs")
                if not recovery_path.exists():
                    atomic_write(recovery_path, _canonical_json(recovery_record))
                _write_batch_journal(
                    path,
                    manifest_raw=replacement_raw,
                    manifest=replacement,
                    bundle=output,
                    phase="prepared",
                    staged=[],
                )
        print(
            json.dumps(
                {
                    "prepared": True,
                    "recovery": True,
                    "idempotentReplay": True,
                    "expiredBatchSuperseded": True,
                    "batchId": replacement["batchId"],
                    "nodeCount": len(replacement_bundles),
                    "batchDigest": _rotation_digest(replacement_raw),
                    "privateKeyTransferred": False,
                }
            )
        )
        return
    batch_id = uuid4().hex
    temporary = output.with_name(output.name + ".next")
    rows = []
    shared_control_raw = None
    with exclusive_file(path / "leaf-rotation.lock"):
        journal = _load_batch_journal(path)
        _assert_batch_journal(
            journal, manifest_raw=expired_raw, manifest=expired, bundle=expired_path
        )
        staged = set(journal["stagedNodeIds"])
        if journal["phase"] not in {"staging", "staged"} or not staged or staged == set(csrs):
            raise ValueError("Recovery requires a non-empty, incomplete staged batch")
        temporary.mkdir(parents=True, exist_ok=False)
        try:
            with psycopg.connect(state["adminDSN"]) as conn:
                conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (state["tenantId"],))
                for node in active:
                    node_id = node["nodeId"]
                    old_manifest = expired_bundles[node_id][1]
                    row = _channel_row(conn, state, node, lock=True)
                    if node_id in staged:
                        expected = (
                            old_manifest["targetChannelVersion"],
                            old_manifest["nextNodeCertificateSHA256"],
                            True,
                        )
                        current_node_raw = expired_bundles[node_id][2]["node-cert.pem"]
                    else:
                        expected = (
                            old_manifest["currentChannelVersion"],
                            old_manifest["currentNodeCertificateSHA256"],
                            True,
                        )
                        current_node_raw = node_certificate_path(path, state, node).read_bytes()
                    if (row[0], row[1], row[3]) != expected:
                        raise ValueError(
                            "Expired batch channel state differs from its durable journal"
                        )
                    current_node = x509.load_pem_x509_certificate(current_node_raw)
                    public_key = csr_public_key(csrs[node_id].read_bytes(), node_id)
                    node_output = temporary / "nodes" / node_id
                    proposal_raw, proposal, files = _write_rotation_public_material(
                        node_output,
                        state=state,
                        node=node,
                        current_node=current_node,
                        current_control=current_control,
                        control_key=control_key,
                        public_key=public_key,
                        ca_key=ca_key,
                        intermediate=intermediate,
                        chain_raw=chain_raw,
                        revocations=revocations,
                        now=now,
                        current_version=row[0],
                        overlap_seconds=args.overlap_seconds,
                        leaf_valid_seconds=args.leaf_valid_seconds,
                        rotation_id=batch_id,
                        shared_control_raw=shared_control_raw,
                    )
                    if shared_control_raw is None:
                        shared_control_raw = files["control-cert.pem"]
                    rows.append(
                        {
                            "nodeId": node_id,
                            "bundlePath": f"nodes/{node_id}",
                            "proposalDigest": _rotation_digest(proposal_raw),
                            "currentChannelVersion": proposal["currentChannelVersion"],
                            "targetChannelVersion": proposal["targetChannelVersion"],
                            "nextNodeCertificateSHA256": proposal["nextNodeCertificateSHA256"],
                        }
                    )
            proposals = [_rotation_material(temporary / row["bundlePath"])[1] for row in rows]
            common = {
                key: {proposal[key] for proposal in proposals}
                for key in (
                    "overlapExpiresAt",
                    "certificateNotAfter",
                    "currentControlCertificateSHA256",
                    "nextControlCertificateSHA256",
                    "caBundleSHA256",
                )
            }
            if any(len(values) != 1 for values in common.values()):
                raise ValueError("Recovery batch shared authority differs across Nodes")
            manifest = {
                "schemaVersion": BATCH_ROTATION_SCHEMA,
                "batchId": batch_id,
                "tenantId": state["tenantId"],
                "recoveryEpoch": state["epoch"],
                "createdAt": min(item["createdAt"] for item in proposals),
                **{key: next(iter(values)) for key, values in common.items()},
                "nodes": rows,
            }
            manifest_raw = _canonical_json(manifest)
            atomic_write(temporary / "batch.json", manifest_raw)
            output.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary, output)
            recovery_record = {
                "schemaVersion": RECOVERY_RECORD_SCHEMA,
                "expiredBatchId": expired["batchId"],
                "expiredBatchDigest": _rotation_digest(expired_raw),
                "replacementBatchId": batch_id,
                "replacementBatchDigest": _rotation_digest(manifest_raw),
                "supersededAt": _utc_z(now),
                "stagedNodeIds": sorted(staged),
            }
            recovery_path = path / f'leaf-rotation-recovery-{expired["batchId"]}.json'
            if recovery_path.exists() and recovery_path.read_bytes() != _canonical_json(
                recovery_record
            ):
                raise ValueError("Expired batch recovery record differs")
            if not recovery_path.exists():
                atomic_write(recovery_path, _canonical_json(recovery_record))
            replacement = _write_batch_journal(
                path,
                manifest_raw=manifest_raw,
                manifest=manifest,
                bundle=output,
                phase="prepared",
                staged=[],
            )
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    print(
        json.dumps(
            {
                "prepared": True,
                "recovery": True,
                "expiredBatchSuperseded": True,
                "batchId": batch_id,
                "nodeCount": len(rows),
                "batchDigest": replacement["batchDigest"],
                "privateKeyTransferred": False,
            }
        )
    )


def prepare_leaf_rotation_batch(args):
    """Issue one shared next CP leaf and exact per-Node public bundles."""
    path, state = args.state, load(args.state)
    active = sorted(active_configured_nodes(state), key=lambda item: item["nodeId"])
    if len(active) < 2:
        raise ValueError("A leaf rotation batch requires at least two active Nodes")
    csrs = {}
    for csr_path in args.csr:
        raw = csr_path.read_bytes()
        node = node_from_csr(state, raw)
        if node["nodeId"] in csrs:
            raise ValueError("Each active Node CSR must be supplied exactly once")
        csrs[node["nodeId"]] = csr_path
    if set(csrs) != {node["nodeId"] for node in active}:
        raise ValueError("The rotation batch must include every active Node")
    output = args.output.resolve()
    with exclusive_file(path / "leaf-rotation.lock"):
        journal = _load_batch_journal(path)
        if output.exists():
            raw, manifest, bundles = _batch_material(output)
            if set(bundles) != set(csrs):
                raise ValueError("Existing rotation batch is not an exact active-Node retry")
            for node_id, csr_path in csrs.items():
                public = csr_public_key(csr_path.read_bytes(), node_id)
                next_node = x509.load_pem_x509_certificate(bundles[node_id][2]["node-cert.pem"])
                if public.public_bytes_raw() != next_node.public_key().public_bytes_raw():
                    raise ValueError("Existing rotation batch CSR binding differs")
            if journal:
                _assert_batch_journal(journal, manifest_raw=raw, manifest=manifest, bundle=output)
            else:
                journal = _write_batch_journal(
                    path,
                    manifest_raw=raw,
                    manifest=manifest,
                    bundle=output,
                    phase="prepared",
                    staged=[],
                )
            print(
                json.dumps(
                    {
                        "prepared": True,
                        "idempotentReplay": True,
                        "batchId": manifest["batchId"],
                        "nodeCount": len(bundles),
                        "batchDigest": journal["batchDigest"],
                        "privateKeyTransferred": False,
                    }
                )
            )
            return
        if journal:
            raise ValueError("Another leaf rotation batch owns the pilot state")
        batch_id = uuid4().hex
        batch_now = datetime.now(timezone.utc)
        temporary = output.with_name(output.name + ".next")
        temporary.mkdir(parents=True, exist_ok=False)
        shared_control_raw = None
        rows = []
        try:
            for node in active:
                node_output = temporary / "nodes" / node["nodeId"]
                child = argparse.Namespace(
                    state=path,
                    csr=csrs[node["nodeId"]],
                    output=node_output,
                    ca_key=args.ca_key,
                    ca_key_password_file=args.ca_key_password_file,
                    ca_chain=args.ca_chain,
                    revocations=args.revocations,
                    safety_window_hours=args.safety_window_hours,
                    overlap_seconds=args.overlap_seconds,
                    leaf_valid_seconds=args.leaf_valid_seconds,
                    _batch_mode=True,
                    _batch_lock_held=True,
                    _batch_rotation_id=batch_id,
                    _batch_next_control_raw=shared_control_raw,
                    _batch_now=batch_now,
                    _quiet=True,
                )
                prepare_leaf_rotation(child)
                proposal_raw, proposal, files = _rotation_material(node_output)
                if shared_control_raw is None:
                    shared_control_raw = files["control-cert.pem"]
                rows.append(
                    {
                        "nodeId": node["nodeId"],
                        "bundlePath": f"nodes/{node['nodeId']}",
                        "proposalDigest": _rotation_digest(proposal_raw),
                        "currentChannelVersion": proposal["currentChannelVersion"],
                        "targetChannelVersion": proposal["targetChannelVersion"],
                        "nextNodeCertificateSHA256": proposal["nextNodeCertificateSHA256"],
                    }
                )
            proposals = [_rotation_material(temporary / row["bundlePath"])[1] for row in rows]
            common = {
                "overlapExpiresAt": {item["overlapExpiresAt"] for item in proposals},
                "certificateNotAfter": {item["certificateNotAfter"] for item in proposals},
                "currentControlCertificateSHA256": {
                    item["currentControlCertificateSHA256"] for item in proposals
                },
                "nextControlCertificateSHA256": {
                    item["nextControlCertificateSHA256"] for item in proposals
                },
                "caBundleSHA256": {item["caBundleSHA256"] for item in proposals},
            }
            if any(len(values) != 1 for values in common.values()):
                raise ValueError("Leaf rotation batch shared authority differs across Nodes")
            manifest = {
                "schemaVersion": BATCH_ROTATION_SCHEMA,
                "batchId": batch_id,
                "tenantId": state["tenantId"],
                "recoveryEpoch": state["epoch"],
                "createdAt": min(item["createdAt"] for item in proposals),
                **{key: next(iter(values)) for key, values in common.items()},
                "nodes": rows,
            }
            manifest_raw = _canonical_json(manifest)
            atomic_write(temporary / "batch.json", manifest_raw)
            output.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary, output)
            journal = _write_batch_journal(
                path,
                manifest_raw=manifest_raw,
                manifest=manifest,
                bundle=output,
                phase="prepared",
                staged=[],
            )
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    print(
        json.dumps(
            {
                "prepared": True,
                "idempotentReplay": False,
                "batchId": batch_id,
                "nodeCount": len(rows),
                "batchDigest": journal["batchDigest"],
                "privateKeyTransferred": False,
            }
        )
    )


def prepare_leaf_rotation(args):
    """Issue public rotation material from a Node-owned CSR without installing it."""
    path, state = args.state, load(args.state)
    if len(active_configured_nodes(state)) != 1 and not getattr(args, "_batch_mode", False):
        raise ValueError("Multiple active Nodes require one shared leaf rotation batch")
    node = node_from_csr(state, args.csr.read_bytes())
    if node.get("credentialRevoked"):
        raise ValueError("Revoked Node credentials cannot be rotated")
    output = args.output.resolve()
    lock = (
        nullcontext()
        if getattr(args, "_batch_lock_held", False)
        else exclusive_file(path / "leaf-rotation.lock")
    )
    with lock:
        public = csr_public_key(args.csr.read_bytes(), node["nodeId"])
        current_node_path = node_certificate_path(path, state, node)
        current_node_raw = current_node_path.read_bytes()
        current_node = x509.load_pem_x509_certificate(current_node_raw)
        if current_node.public_key().public_bytes_raw() != public.public_bytes_raw():
            raise ValueError("Rotation CSR does not preserve the pinned Node key")
        current_control_raw = (path / "control-cert.pem").read_bytes()
        current_control = x509.load_pem_x509_certificate(current_control_raw)
        control_key = serialization.load_pem_private_key(
            (path / "control-key.pem").read_bytes(), password=None
        )
        if (
            control_key.public_key().public_bytes_raw()
            != current_control.public_key().public_bytes_raw()
        ):
            raise ValueError("Pinned Control Plane key and leaf differ")
        now = getattr(args, "_batch_now", None) or datetime.now(timezone.utc)
        safety = timedelta(hours=args.safety_window_hours)
        if (
            min(current_node.not_valid_after_utc, current_control.not_valid_after_utc)
            > now + safety
        ):
            raise ValueError("Leaf rotation requested before the configured safety window")
        revocations = _load_revocations(args.revocations)
        if fingerprint(current_node) in revocations or fingerprint(current_control) in revocations:
            raise ValueError("A current rotation identity is revoked")
        _, _, chain_raw, ca_key, intermediate = _load_external_ca(
            args.ca_key, args.ca_key_password_file, args.ca_chain
        )
        if _rotation_digest(chain_raw) != state.get("caBundleSHA256"):
            raise ValueError("External issuing chain differs from the pilot pin")
        principal = NodePrincipal(state["tenantId"], node["nodeId"])
        current_identity = certificate_identity(
            current_node.public_bytes(serialization.Encoding.DER),
            principal,
            state["epoch"],
            now=now,
        )
        current_names = current_node.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
        if current_identity != (
            fingerprint(current_node),
            current_node.not_valid_after_utc,
        ) or current_names.get_values_for_type(x509.IPAddress) != [
            ipaddress.ip_address(node["nodeIP"])
        ]:
            raise ValueError("Current Node leaf is not bound to the exact issuing chain")
        intermediate.public_key().verify(current_node.signature, current_node.tbs_certificate_bytes)
        if current_node.issuer != intermediate.subject:
            raise ValueError("Current Node leaf is not bound to the exact issuing chain")
        _validate_current_control_leaf(current_control, intermediate, state=state, now=now)
        policy = json.loads(node_policy_path(path, state, node).read_text("utf-8"))
        with psycopg.connect(state["adminDSN"]) as conn:
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (state["tenantId"],))
            channel = _channel_row(conn, state, node)
        version, channel_fingerprint, channel_not_after, enabled, endpoint = channel
        if (
            not enabled
            or channel_fingerprint != fingerprint(current_node)
            or channel_not_after <= now
            or endpoint != f'https://{node["nodeIP"]}:{node["nodePort"]}'
            or policy
            != {
                "version": version,
                "tenantId": state["tenantId"],
                "nodeId": node["nodeId"],
                "recoveryEpoch": state["epoch"],
                "expiresAt": policy.get("expiresAt"),
                "clientFingerprints": [fingerprint(current_control)],
            }
        ):
            raise ValueError(
                "Pinned Node channel or peer policy differs from current public material"
            )
        if output.exists():
            raw, manifest, files = _rotation_material(output)
            next_node = x509.load_pem_x509_certificate(files["node-cert.pem"])
            if (
                manifest.get("nodeId") != node["nodeId"]
                or manifest.get("currentChannelVersion") != version
                or manifest.get("targetChannelVersion") != version + 1
                or manifest.get("currentNodeCertificateSHA256") != fingerprint(current_node)
                or manifest.get("caBundleSHA256") != _rotation_digest(chain_raw)
                or next_node.public_key().public_bytes_raw() != public.public_bytes_raw()
                or fingerprint(current_node) in revocations
                or fingerprint(next_node) in revocations
            ):
                raise ValueError("Existing rotation output is not an exact safe retry")
            if not getattr(args, "_quiet", False):
                print(
                    json.dumps(
                        dict(
                            prepared=True,
                            idempotentReplay=True,
                            nodeId=node["nodeId"],
                            rotationId=manifest["rotationId"],
                            targetChannelVersion=manifest["targetChannelVersion"],
                            proposalDigest=_rotation_digest(raw),
                        )
                    )
                )
            return
        lifetime = timedelta(seconds=args.leaf_valid_seconds)
        next_node = issue(
            ca_key,
            intermediate,
            public,
            node_uri(principal, state["epoch"]),
            address=node["nodeIP"],
            now=now,
            valid_for=lifetime,
        )
        shared_control_raw = getattr(args, "_batch_next_control_raw", None)
        if shared_control_raw is None:
            next_control = issue(
                ca_key,
                intermediate,
                control_key.public_key(),
                f'spiffe://saintvision.ai/tenant/{state["tenantId"]}/control-plane/epoch/{state["epoch"]}',
                now=now,
                valid_for=lifetime,
            )
        else:
            next_control = x509.load_pem_x509_certificate(shared_control_raw)
            _validate_current_control_leaf(next_control, intermediate, state=state, now=now)
            if (
                control_key.public_key().public_bytes_raw()
                != next_control.public_key().public_bytes_raw()
                or fingerprint(next_control) in revocations
            ):
                raise ValueError("Shared batch Control Plane leaf differs from pinned authority")
        not_after = min(next_node.not_valid_after_utc, next_control.not_valid_after_utc)
        overlap_expires = min(now + timedelta(seconds=args.overlap_seconds), not_after)
        if overlap_expires <= now + timedelta(seconds=30):
            raise ValueError("Rotation overlap is too short to complete safely")
        target_version = version + 1
        next_node_raw, next_control_raw = pem(next_node), pem(next_control)
        overlap_policy = {
            "version": target_version,
            "tenantId": state["tenantId"],
            "nodeId": node["nodeId"],
            "recoveryEpoch": state["epoch"],
            "expiresAt": _utc_z(overlap_expires),
            "clientFingerprints": [fingerprint(current_control), fingerprint(next_control)],
        }
        final_policy = {
            **overlap_policy,
            "expiresAt": _utc_z(not_after),
            "clientFingerprints": [fingerprint(next_control)],
        }
        material = {
            "ca.pem": chain_raw,
            "node-cert.pem": next_node_raw,
            "control-cert.pem": next_control_raw,
            "peer-policy-overlap.json": json.dumps(overlap_policy, indent=2).encode(),
            "peer-policy-final.json": json.dumps(final_policy, indent=2).encode(),
        }
        manifest = {
            "schemaVersion": ROTATION_SCHEMA,
            "rotationId": getattr(args, "_batch_rotation_id", None) or uuid4().hex,
            "tenantId": state["tenantId"],
            "nodeId": node["nodeId"],
            "recoveryEpoch": state["epoch"],
            "nodeIP": node["nodeIP"],
            "currentChannelVersion": version,
            "targetChannelVersion": target_version,
            "currentNodeCertificateSHA256": fingerprint(current_node),
            "nextNodeCertificateSHA256": fingerprint(next_node),
            "currentControlCertificateSHA256": fingerprint(current_control),
            "nextControlCertificateSHA256": fingerprint(next_control),
            "caBundleSHA256": _rotation_digest(chain_raw),
            "createdAt": _utc_z(now),
            "overlapExpiresAt": _utc_z(overlap_expires),
            "certificateNotAfter": _utc_z(not_after),
            "files": {name: _rotation_digest(raw) for name, raw in material.items()},
        }
        temporary = output.with_name(output.name + ".next")
        temporary.mkdir(parents=True, exist_ok=False)
        try:
            for name, raw in material.items():
                atomic_write(temporary / name, raw)
            manifest_raw = _canonical_json(manifest)
            atomic_write(temporary / "rotation.json", manifest_raw)
            os.replace(temporary, output)
            if os.name != "nt":
                directory = os.open(output.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        if not getattr(args, "_quiet", False):
            print(
                json.dumps(
                    dict(
                        prepared=True,
                        idempotentReplay=False,
                        nodeId=node["nodeId"],
                        rotationId=manifest["rotationId"],
                        targetChannelVersion=target_version,
                        proposalDigest=_rotation_digest(manifest_raw),
                        privateKeyTransferred=False,
                    )
                )
            )


def _validate_rotation_receipt(path, state, bundle, receipt_path):
    manifest_raw, manifest, files = _rotation_material(bundle.resolve())
    node = node_by_id(state, manifest["nodeId"])
    if node.get("credentialRevoked"):
        raise ValueError("Revoked Node credentials cannot be committed")
    proposal_digest = _rotation_digest(manifest_raw)
    receipt = json.loads(receipt_path.read_text("utf-8"))
    expected_receipt_body = {
        "schemaVersion": ROTATION_SCHEMA,
        "rotationId": manifest["rotationId"],
        "proposalDigest": proposal_digest,
        "targetChannelVersion": manifest["targetChannelVersion"],
        "nodeId": manifest["nodeId"],
        "installedNodeCertificateSHA256": manifest["nextNodeCertificateSHA256"],
        "installedAt": receipt.get("installedAt"),
        "restartObserved": True,
    }
    if set(receipt) != {*expected_receipt_body, "nodeSignature"} or any(
        receipt.get(key) != value for key, value in expected_receipt_body.items()
    ):
        raise ValueError("Node installation receipt differs from the rotation proposal")
    signature = receipt.get("nodeSignature")
    if not isinstance(signature, str) or not re.fullmatch(r"[a-f0-9]{128}", signature):
        raise ValueError("Node installation receipt signature is invalid")
    next_node = x509.load_pem_x509_certificate(files["node-cert.pem"])
    next_node.public_key().verify(bytes.fromhex(signature), _canonical_json(expected_receipt_body))
    installed_at = datetime.fromisoformat(receipt["installedAt"].replace("Z", "+00:00"))
    current_time = datetime.now(timezone.utc)
    overlap_expires = datetime.fromisoformat(manifest["overlapExpiresAt"].replace("Z", "+00:00"))
    certificate_not_after = datetime.fromisoformat(
        manifest["certificateNotAfter"].replace("Z", "+00:00")
    )
    if (
        installed_at.tzinfo != timezone.utc
        or installed_at > current_time + timedelta(seconds=30)
        or not current_time < overlap_expires < certificate_not_after
        or installed_at >= overlap_expires
    ):
        raise ValueError("Node installation receipt is outside the overlap window")
    control_key = serialization.load_pem_private_key(
        (path / "control-key.pem").read_bytes(), password=None
    )
    if not isinstance(control_key, Ed25519PrivateKey):
        raise ValueError("Control Plane receipt signing key type differs")
    next_control = x509.load_pem_x509_certificate(files["control-cert.pem"])
    if control_key.public_key().public_bytes_raw() != next_control.public_key().public_bytes_raw():
        raise ValueError("Control Plane key differs from the proposed control certificate")
    return manifest_raw, manifest, files, node, control_key


def stage_leaf_rotation_batch(args):
    """CAS one restarted Node while keeping the global CP leaf unchanged."""
    path, state = args.state, load(args.state)
    batch_raw, batch, bundles = _batch_material(args.bundle.resolve())
    if set(bundles) != {node["nodeId"] for node in active_configured_nodes(state)}:
        raise ValueError("Leaf rotation batch no longer matches the complete active Node set")
    receipt_value = json.loads(args.node_receipt.read_text("utf-8"))
    node_id = receipt_value.get("nodeId")
    if node_id not in bundles:
        raise ValueError("Node receipt is not part of this leaf rotation batch")
    bundle = args.bundle.resolve() / f"nodes/{node_id}"
    _raw, manifest, files, node, _control_key = _validate_rotation_receipt(
        path, state, bundle, args.node_receipt
    )
    if manifest["rotationId"] != batch["batchId"]:
        raise ValueError("Node proposal differs from the leaf rotation batch")
    with exclusive_file(path / "leaf-rotation.lock"):
        journal = _load_batch_journal(path)
        _assert_batch_journal(
            journal, manifest_raw=batch_raw, manifest=batch, bundle=args.bundle.resolve()
        )
        if journal["phase"] == "switched":
            raise ValueError("A switched leaf rotation batch cannot stage another Node")
        with psycopg.connect(state["adminDSN"]) as conn:
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (state["tenantId"],))
            row = _channel_row(conn, state, node, lock=True)
            version, certificate_sha256, _not_after, enabled, endpoint = row
            if (version, certificate_sha256, enabled) == (
                manifest["currentChannelVersion"],
                manifest["currentNodeCertificateSHA256"],
                True,
            ):
                committed_version = provision_channel(
                    conn,
                    NodePrincipal(state["tenantId"], node_id),
                    epoch=state["epoch"],
                    endpoint=endpoint,
                    certificate_der=x509.load_pem_x509_certificate(
                        files["node-cert.pem"]
                    ).public_bytes(serialization.Encoding.DER),
                    expected_version=manifest["currentChannelVersion"],
                )
                replay = False
            elif (version, certificate_sha256, enabled) == (
                manifest["targetChannelVersion"],
                manifest["nextNodeCertificateSHA256"],
                True,
            ):
                committed_version = version
                replay = True
            else:
                raise ValueError("Channel changed; concurrent or stale rotation refused")
        staged = set(journal["stagedNodeIds"])
        staged.add(node_id)
        phase = "staged" if staged == set(bundles) else "staging"
        _write_batch_journal(
            path,
            manifest_raw=batch_raw,
            manifest=batch,
            bundle=args.bundle.resolve(),
            phase=phase,
            staged=staged,
        )
    print(
        json.dumps(
            {
                "staged": True,
                "idempotentReplay": replay,
                "batchId": batch["batchId"],
                "nodeId": node_id,
                "channelVersion": committed_version,
                "globalControlLeafSwitched": False,
            }
        )
    )


def commit_leaf_rotation_batch(args):
    """Switch the shared CP leaf only after every restarted Node channel is staged."""
    path, state = args.state, load(args.state)
    batch_path = args.bundle.resolve()
    batch_raw, batch, bundles = _batch_material(batch_path)
    if set(bundles) != {node["nodeId"] for node in active_configured_nodes(state)}:
        raise ValueError("Leaf rotation batch no longer matches the complete active Node set")
    output = args.output.resolve()
    kill = getattr(args, "_kill", lambda _point: None)
    with exclusive_file(path / "leaf-rotation.lock"):
        journal = _load_batch_journal(path)
        _assert_batch_journal(journal, manifest_raw=batch_raw, manifest=batch, bundle=batch_path)
        if set(journal["stagedNodeIds"]) != set(bundles):
            raise ValueError("Every Node must restart and stage before the shared CP leaf switches")
        with psycopg.connect(state["adminDSN"]) as conn:
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (state["tenantId"],))
            for node_id, (_raw, manifest, _files) in bundles.items():
                node = node_by_id(state, node_id)
                row = _channel_row(conn, state, node, lock=True)
                if (row[0], row[1], row[3]) != (
                    manifest["targetChannelVersion"],
                    manifest["nextNodeCertificateSHA256"],
                    True,
                ):
                    raise ValueError("A staged Node channel changed before batch commit")
        shared_control = next(iter(bundles.values()))[2]["control-cert.pem"]
        current_control = (path / "control-cert.pem").read_bytes()
        current_fingerprint = fingerprint(x509.load_pem_x509_certificate(current_control))
        if current_fingerprint == batch["currentControlCertificateSHA256"]:
            kill("before-control-switch")
            atomic_write(path / "control-cert.pem", shared_control)
            switched_replay = False
            kill("after-control-switch")
        elif current_fingerprint == batch["nextControlCertificateSHA256"]:
            switched_replay = True
        else:
            raise ValueError("Global Control Plane leaf changed outside this rotation batch")
        for node_id, (_raw, manifest, files) in bundles.items():
            node = node_by_id(state, node_id)
            atomic_write(node_certificate_path(path, state, node), files["node-cert.pem"])
            atomic_write(node_policy_path(path, state, node), files["peer-policy-final.json"])
        _write_batch_journal(
            path,
            manifest_raw=batch_raw,
            manifest=batch,
            bundle=batch_path,
            phase="switched",
            staged=bundles,
        )
        output.mkdir(parents=True, exist_ok=True)
        if output.is_symlink():
            raise ValueError("Batch commit receipt directory must not be a symlink")
        control_key = serialization.load_pem_private_key(
            (path / "control-key.pem").read_bytes(), password=None
        )
        if not isinstance(control_key, Ed25519PrivateKey):
            raise ValueError("Control Plane receipt signing key type differs")
        for node_id, (proposal_raw, manifest, _files) in bundles.items():
            body = {
                "schemaVersion": ROTATION_SCHEMA,
                "rotationId": manifest["rotationId"],
                "proposalDigest": _rotation_digest(proposal_raw),
                "nodeId": node_id,
                "channelVersion": manifest["targetChannelVersion"],
                "certificateSHA256": manifest["nextNodeCertificateSHA256"],
                "committed": True,
            }
            receipt_raw = _canonical_json(
                {**body, "controlSignature": control_key.sign(_canonical_json(body)).hex()}
            )
            target = output / f"{node_id}.json"
            if target.exists() and target.read_bytes() != receipt_raw:
                raise ValueError("Existing batch commit receipt differs")
            atomic_write(target, receipt_raw)
    print(
        json.dumps(
            {
                "committed": True,
                "idempotentReplay": switched_replay,
                "batchId": batch["batchId"],
                "nodeCount": len(bundles),
                "globalControlLeafSwitched": True,
                "nodeOverlapFinalizationRequired": True,
            }
        )
    )


def commit_leaf_rotation(args):
    """CAS the DB channel, then durably publish matching CP/Node public material."""
    path, state = args.state, load(args.state)
    if len(active_configured_nodes(state)) != 1:
        raise ValueError("Multiple active Nodes require one shared leaf rotation batch")
    manifest_raw, manifest, files = _rotation_material(args.bundle.resolve())
    node = node_by_id(state, manifest["nodeId"])
    if node.get("credentialRevoked"):
        raise ValueError("Revoked Node credentials cannot be committed")
    proposal_digest = _rotation_digest(manifest_raw)
    receipt = json.loads(args.node_receipt.read_text("utf-8"))
    expected_receipt_body = {
        "schemaVersion": ROTATION_SCHEMA,
        "rotationId": manifest["rotationId"],
        "proposalDigest": proposal_digest,
        "targetChannelVersion": manifest["targetChannelVersion"],
        "nodeId": manifest["nodeId"],
        "installedNodeCertificateSHA256": manifest["nextNodeCertificateSHA256"],
        "installedAt": receipt.get("installedAt"),
        "restartObserved": True,
    }
    if set(receipt) != {*expected_receipt_body, "nodeSignature"} or any(
        receipt.get(key) != value for key, value in expected_receipt_body.items()
    ):
        raise ValueError("Node installation receipt differs from the rotation proposal")
    signature = receipt.get("nodeSignature")
    if not isinstance(signature, str) or not re.fullmatch(r"[a-f0-9]{128}", signature):
        raise ValueError("Node installation receipt signature is invalid")
    next_node = x509.load_pem_x509_certificate(files["node-cert.pem"])
    next_node.public_key().verify(bytes.fromhex(signature), _canonical_json(expected_receipt_body))
    installed_at = datetime.fromisoformat(receipt["installedAt"].replace("Z", "+00:00"))
    current_time = datetime.now(timezone.utc)
    overlap_expires = datetime.fromisoformat(manifest["overlapExpiresAt"].replace("Z", "+00:00"))
    certificate_not_after = datetime.fromisoformat(
        manifest["certificateNotAfter"].replace("Z", "+00:00")
    )
    if (
        installed_at.tzinfo != timezone.utc
        or installed_at > current_time + timedelta(seconds=30)
        or not current_time < overlap_expires < certificate_not_after
        or installed_at >= overlap_expires
    ):
        raise ValueError("Node installation receipt is outside the overlap window")
    control_key = serialization.load_pem_private_key(
        (path / "control-key.pem").read_bytes(), password=None
    )
    if not isinstance(control_key, Ed25519PrivateKey):
        raise ValueError("Control Plane receipt signing key type differs")
    next_control = x509.load_pem_x509_certificate(files["control-cert.pem"])
    if control_key.public_key().public_bytes_raw() != next_control.public_key().public_bytes_raw():
        raise ValueError("Control Plane key differs from the proposed control certificate")
    with exclusive_file(path / "leaf-rotation.lock"):
        with psycopg.connect(state["adminDSN"]) as conn:
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (state["tenantId"],))
            row = _channel_row(conn, state, node, lock=True)
            version, certificate_sha256, _not_after, enabled, endpoint = row
            if (version, certificate_sha256, enabled) == (
                manifest["currentChannelVersion"],
                manifest["currentNodeCertificateSHA256"],
                True,
            ):
                committed_version = provision_channel(
                    conn,
                    NodePrincipal(state["tenantId"], node["nodeId"]),
                    epoch=state["epoch"],
                    endpoint=endpoint,
                    certificate_der=x509.load_pem_x509_certificate(
                        files["node-cert.pem"]
                    ).public_bytes(serialization.Encoding.DER),
                    expected_version=manifest["currentChannelVersion"],
                )
            elif (version, certificate_sha256, enabled) == (
                manifest["targetChannelVersion"],
                manifest["nextNodeCertificateSHA256"],
                True,
            ):
                committed_version = version
            else:
                raise ValueError("Channel changed; concurrent or stale rotation refused")
        atomic_write(path / "control-cert.pem", files["control-cert.pem"])
        atomic_write(node_certificate_path(path, state, node), files["node-cert.pem"])
        atomic_write(node_policy_path(path, state, node), files["peer-policy-final.json"])
        commit_receipt_body = {
            "schemaVersion": ROTATION_SCHEMA,
            "rotationId": manifest["rotationId"],
            "proposalDigest": proposal_digest,
            "nodeId": manifest["nodeId"],
            "channelVersion": committed_version,
            "certificateSHA256": manifest["nextNodeCertificateSHA256"],
            "committed": True,
        }
        commit_receipt = {
            **commit_receipt_body,
            "controlSignature": control_key.sign(_canonical_json(commit_receipt_body)).hex(),
        }
        atomic_write(args.output.resolve(), _canonical_json(commit_receipt))
    print(
        json.dumps(
            {
                **commit_receipt,
                "idempotentReplay": committed_version == version,
                "restartObserverRequired": True,
                "nodeOverlapFinalizationRequired": True,
            }
        )
    )


def revoke_server_node_colocation(args):
    """Fail closed without deleting the co-located Node identity or its files."""
    state = load(args.state)
    state, revoked = revoked_colocation_state(state)
    # Persist the fail-closed marker before touching PostgreSQL. If that step
    # fails, a retry still cannot serve or enroll the co-located Node.
    save(args.state, state)
    channel_states = []
    if revoked:
        with psycopg.connect(state["adminDSN"]) as conn:
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (state["tenantId"],))
            for node in revoked:
                row = conn.execute(
                    "SELECT version,enabled FROM inv.node_channels "
                    "WHERE tenant_id=%s AND node_id=%s",
                    (state["tenantId"], node["nodeId"]),
                ).fetchone()
                if not row:
                    channel_states.append(dict(nodeId=node["nodeId"], channel="not-enrolled"))
                elif row[1]:
                    version = revoke_channel(
                        conn,
                        NodePrincipal(state["tenantId"], node["nodeId"]),
                        expected_version=row[0],
                    )
                    channel_states.append(
                        dict(nodeId=node["nodeId"], channel="revoked", channelVersion=version)
                    )
                else:
                    channel_states.append(
                        dict(
                            nodeId=node["nodeId"], channel="already-disabled", channelVersion=row[0]
                        )
                    )
    print(
        json.dumps(
            dict(
                serverNodeColocationAllowed=False,
                statePreserved=True,
                disabledNodes=[
                    dict(
                        nodeId=node["nodeId"],
                        nodeIP=node["nodeIP"],
                        disabled=True,
                        disabledReason=COLOCATION_REVOKED_REASON,
                    )
                    for node in revoked
                ],
                channels=channel_states,
            )
        )
    )


def revoke_node_certificate(args):
    """Persist a fail-closed marker before disabling the pinned DB channel."""
    state = load(args.state)
    matches = [node for node in configured_nodes(state) if node["nodeId"] == args.node_id]
    if len(matches) != 1:
        raise ValueError("Node identity is not configured")
    nodes = [dict(node) for node in configured_nodes(state)]
    target = next(node for node in nodes if node["nodeId"] == args.node_id)
    if target.get("credentialRevoked"):
        if target.get("credentialRevocationReason") != args.reason:
            raise ValueError("Node credential was revoked for another reason")
    else:
        target["credentialRevoked"] = True
        target["credentialRevocationReason"] = args.reason
        target["credentialRevokedAt"] = datetime.now(timezone.utc).isoformat()
        state["nodes"] = nodes
        save(args.state, state)
    with psycopg.connect(state["adminDSN"]) as conn:
        conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (state["tenantId"],))
        row = conn.execute(
            "SELECT version,enabled FROM inv.node_channels " "WHERE tenant_id=%s AND node_id=%s",
            (state["tenantId"], args.node_id),
        ).fetchone()
        if not row:
            channel = "not-enrolled"
            version = None
        elif row[1]:
            version = revoke_channel(
                conn, NodePrincipal(state["tenantId"], args.node_id), expected_version=row[0]
            )
            channel = "revoked"
        else:
            version = row[0]
            channel = "already-revoked"
    print(
        json.dumps(
            dict(
                nodeId=args.node_id,
                credentialRevoked=True,
                reason=args.reason,
                channel=channel,
                channelVersion=version,
                restartBootstrapRequired=True,
            )
        )
    )


def node_status_rows(state):
    result = []
    with runtime(state).transaction(state["tenantId"]) as conn:
        for node in configured_nodes(state):
            row = conn.execute(
                "SELECT node_id,status,heartbeat_at FROM inv.nodes WHERE node_id=%s",
                (node["nodeId"],),
            ).fetchone()
            snap = conn.execute(
                "SELECT received_at,snapshot FROM inv.node_resource_snapshots WHERE node_id=%s",
                (node["nodeId"],),
            ).fetchone()
            public_snapshot = None
            if snap:
                snapshot = snap["snapshot"] if isinstance(snap, dict) else snap[1]
                received_at = snap["received_at"] if isinstance(snap, dict) else snap[0]
                if isinstance(snapshot, dict):
                    public_snapshot = dict(
                        receivedAt=received_at,
                        observedAt=snapshot.get("observedAt"),
                        profileVersion=snapshot.get("profileVersion"),
                        osType=snapshot.get("osType"),
                        agentVersion=snapshot.get("agentVersion"),
                        cpuCapacityMillis=snapshot.get("cpuCapacityMillis"),
                        memoryCapacityBytes=snapshot.get("memoryCapacityBytes"),
                        memoryAvailableBytes=snapshot.get("memoryAvailableBytes"),
                    )
            result.append(
                dict(
                    nodeId=node["nodeId"],
                    nodeIP=node["nodeIP"],
                    coLocatedWithControlPlane=node["coLocatedWithControlPlane"],
                    disabled=node.get("disabled", False),
                    disabledReason=node.get("disabledReason"),
                    node=dict(row) if row else None,
                    observed=bool(snap),
                    snapshot=public_snapshot,
                )
            )
    return result


def status(args):
    state = load(args.state)
    nodes = node_status_rows(state)
    primary = nodes[0]
    result = dict(
        database="ready",
        nodes=nodes,
        node=primary["node"],
        observed=primary["observed"],
        snapshot=primary["snapshot"],
        scope="observation-only",
        webLogin="not-configured",
        workloadExecution="disabled",
    )
    print(json.dumps(result, default=str, ensure_ascii=False))


def observe(args):
    state = load(args.state)
    observer = ObservationWorker(runtime(state), NodeTLSClient(**tls(args.state)))
    while True:
        try:
            result = observer.once(state["tenantId"])
            print(
                json.dumps(
                    dict(
                        time=datetime.now(timezone.utc).isoformat(),
                        nodes=node_status_rows(state),
                        **result,
                    ),
                    default=str,
                    ensure_ascii=False,
                ),
                flush=True,
            )
        except Exception:
            nodes = [
                dict(
                    nodeId=node["nodeId"],
                    nodeIP=node["nodeIP"],
                    status=(
                        COLOCATION_REVOKED_REASON
                        if node.get("disabled")
                        else "observation-unavailable"
                    ),
                )
                for node in configured_nodes(state)
            ]
            print(json.dumps(dict(status="observation-unavailable", nodes=nodes)), flush=True)
        if args.once:
            return
        time.sleep(5)


def serve(args):
    state = load(args.state)
    public = args.state / "public"
    node_ips = [node["nodeIP"] for node in active_configured_nodes(state)]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            target = None
            if self.path == "/healthz":
                if self.client_address[0] not in {*node_ips, state["serverIP"], "127.0.0.1"}:
                    self.send_error(403)
                    return
                data = b'{"service":"SaintVision LAN bootstrap","status":"ready","scope":"public-file-transfer-only"}'
                length = len(data)
            else:
                try:
                    target = artifact_for_client(state, public, self.client_address[0], self.path)
                except PermissionError:
                    self.send_error(403)
                    return
                if target is None:
                    self.send_error(404)
                    return
                length = target.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if target is None:
                self.wfile.write(data)
            else:
                # Bound memory and apply the socket deadline to individual chunks.
                # A slow Windows download must not time out as one giant sendall.
                with target.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(256 * 1024), b""):
                        self.wfile.write(chunk)

        def log_message(self, *_):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

    class Server(ThreadingHTTPServer):
        slots = BoundedSemaphore(8)
        request_queue_size = 8

        def process_request(self, request, address):
            if not self.slots.acquire(blocking=False):
                request.close()
                return
            try:
                super().process_request(request, address)
            except Exception:
                self.slots.release()
                raise

        def process_request_thread(self, request, address):
            try:
                super().process_request_thread(request, address)
            finally:
                self.slots.release()

        def handle_error(self, request, address):
            pass

    server = Server((state["serverIP"], state["downloadPort"]), Handler)
    server.daemon_threads = True
    print(
        json.dumps(
            dict(
                service="public-bootstrap",
                listening=f'{state["serverIP"]}:{state["downloadPort"]}',
                allowedNodeIPs=node_ips,
                firewallGuidance=dict(
                    protocol="TCP", localPort=state["downloadPort"], remoteAddresses=node_ips
                ),
            )
        ),
        flush=True,
    )
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("init")
    p.add_argument("--server-ip", required=True)
    p.add_argument(
        "--node-ip",
        action="append",
        required=True,
        help="Private worker IPv4 address; repeat once per Node",
    )
    p.add_argument(
        "--allow-server-node-colocation",
        action="store_true",
        help="Explicitly allow one Node on the Control Plane host address",
    )
    p.add_argument(
        "--download-port",
        type=int,
        help="Private bootstrap TCP port (default 18081 for a new state)",
    )
    p.add_argument(
        "--node-port", type=int, help="Worker publish port fixed into every new Node identity"
    )
    p.add_argument(
        "--admin-dsn-file",
        type=Path,
        help="Passfile-backed loopback admin DSN behind an operator SSH tunnel",
    )
    p.add_argument(
        "--runtime-dsn-file",
        type=Path,
        help="Passfile-backed loopback runtime DSN behind the same SSH tunnel",
    )
    p.add_argument("--ca-key", type=Path, help="Encrypted Ed25519 issuing-intermediate private key")
    p.add_argument("--ca-key-password-file", type=Path, help="Private password file for --ca-key")
    p.add_argument("--ca-chain", type=Path, help="Issuing intermediate followed by offline root")
    p = commands.add_parser(
        "bind-db-auth",
        help="Verify SCRAM rejection/acceptance and bind private pgpass files to existing state",
    )
    p.add_argument("--admin-passfile", type=Path, required=True)
    p.add_argument("--runtime-passfile", type=Path, required=True)
    commands.add_parser(
        "revoke-server-node-colocation",
        help="Preserve but disable the Control Plane co-located Node and channel",
    )
    p = commands.add_parser(
        "revoke-node-certificate", help="Fail closed in state and disable one pinned Node channel"
    )
    p.add_argument("--node-id", required=True)
    p.add_argument("--reason", choices=sorted(CERTIFICATE_REVOCATION_REASONS), required=True)
    p = commands.add_parser("bundle")
    p.add_argument("--go")
    p.add_argument("--reuse-image", action="store_true")
    p.add_argument(
        "--prebuilt-image",
        type=Path,
        help="docker-save archive built and inspected on a Linux worker",
    )
    p.add_argument(
        "--prebuilt-inspect", type=Path, help="docker image inspect JSON for --prebuilt-image"
    )
    p = commands.add_parser("enroll")
    p.add_argument("--csr", type=Path, required=True)
    p.add_argument("--ca-key", type=Path, help="Encrypted external issuing key")
    p.add_argument("--ca-key-password-file", type=Path, help="Password file for --ca-key")
    p.add_argument("--ca-chain", type=Path, help="External issuing chain already pinned by init")
    p = commands.add_parser(
        "prepare-leaf-rotation",
        help="Issue a public Node/control rotation from a Node-owned CSR without installing it",
    )
    p.add_argument("--csr", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--ca-key", type=Path, required=True)
    p.add_argument("--ca-key-password-file", type=Path, required=True)
    p.add_argument("--ca-chain", type=Path, required=True)
    p.add_argument("--revocations", type=Path, required=True)
    p.add_argument("--safety-window-hours", type=int, choices=range(1, 169), default=48)
    p.add_argument(
        "--overlap-seconds",
        type=int,
        choices=range(600, MAXIMUM_OVERLAP_SECONDS + 1),
        default=DEFAULT_ROTATION_OVERLAP_SECONDS,
    )
    p.add_argument("--leaf-valid-seconds", type=int, choices=range(60, 518401), default=518400)
    p = commands.add_parser(
        "prepare-leaf-rotation-batch",
        help="Issue one shared Control Plane leaf and exact bundles for every active Node",
    )
    p.add_argument("--csr", type=Path, action="append", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--ca-key", type=Path, required=True)
    p.add_argument("--ca-key-password-file", type=Path, required=True)
    p.add_argument("--ca-chain", type=Path, required=True)
    p.add_argument("--revocations", type=Path, required=True)
    p.add_argument("--safety-window-hours", type=int, choices=range(1, 169), default=48)
    p.add_argument(
        "--overlap-seconds",
        type=int,
        choices=range(600, MAXIMUM_OVERLAP_SECONDS + 1),
        default=DEFAULT_ROTATION_OVERLAP_SECONDS,
    )
    p.add_argument("--leaf-valid-seconds", type=int, choices=range(60, 518401), default=518400)
    p = commands.add_parser(
        "prepare-leaf-rotation-recovery-batch",
        help="Supersede one expired partial batch with a fresh exact all-Node batch",
    )
    p.add_argument("--expired-batch", type=Path, required=True)
    p.add_argument("--csr", type=Path, action="append", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--ca-key", type=Path, required=True)
    p.add_argument("--ca-key-password-file", type=Path, required=True)
    p.add_argument("--ca-chain", type=Path, required=True)
    p.add_argument("--revocations", type=Path, required=True)
    p.add_argument("--safety-window-hours", type=int, choices=range(1, 169), default=48)
    p.add_argument(
        "--overlap-seconds",
        type=int,
        choices=range(600, MAXIMUM_OVERLAP_SECONDS + 1),
        default=DEFAULT_ROTATION_OVERLAP_SECONDS,
    )
    p.add_argument("--leaf-valid-seconds", type=int, choices=range(60, 518401), default=518400)
    p = commands.add_parser(
        "stage-leaf-rotation-batch",
        help="CAS one restarted Node channel without switching the shared Control Plane leaf",
    )
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--node-receipt", type=Path, required=True)
    p = commands.add_parser(
        "commit-leaf-rotation-batch",
        help="Switch one shared Control Plane leaf after every Node is restarted and staged",
    )
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser(
        "commit-leaf-rotation",
        help="Commit an installed Node rotation with channel CAS and durable public material",
    )
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--node-receipt", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    commands.add_parser("status")
    p = commands.add_parser("observe")
    p.add_argument("--once", action="store_true")
    commands.add_parser("serve")
    args = parser.parse_args()
    args.state = args.state.resolve()
    try:
        globals()[args.command.replace("-", "_")](args)
    except KeyboardInterrupt:
        pass
    except Exception as error:
        # Neither DSNs nor private credentials belong in console/error reporting.
        print(
            f"LAN {args.command} failed ({type(error).__name__}); no credentials printed.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
