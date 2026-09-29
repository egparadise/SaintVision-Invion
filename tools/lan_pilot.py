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
import subprocess
import sys
import tarfile
import time
import zipfile
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import BoundedSemaphore
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/control-plane/src"))
import psycopg
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID
from inv.db import Database
from inv.ids import new_id
from inv.node_channels import node_uri, provision_channel, revoke_channel
from inv.node_transport import NodeTLSClient
from inv.observer_worker import ObservationWorker
from inv.tooling import NodePrincipal
from lan_pki import ca_pair, csr_public_key, fingerprint, issue, pem, private_pem
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


def read_external_dsn(path, expected_user):
    """Accept only passwordless loopback DSNs intended for an SSH tunnel."""
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
        or info.get("dbname") != "saintvision_lan"
    ):
        raise ValueError("External database DSN must be passwordless loopback tunnel input")
    port = int(info.get("port", 5432))
    if not 1024 <= port <= 65535:
        raise ValueError("External database tunnel port is invalid")
    return make_conninfo(value, connect_timeout=5)


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
        ("ca-key.pem", key_raw),
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
    if password is not None:
        material.append(("ca-key.pass", password))
    for name, data in material:
        write(path / name, data)
    return state


def load_pilot_ca_key(path):
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
        config_member = archive.getmember(config_name)
        if not config_member.isfile() or config_member.size > 2 * 1024 * 1024:
            raise ValueError("Prebuilt image config is missing")
        config_stream = archive.extractfile(config_member)
        config_raw = config_stream.read()
        if hashlib.sha256(config_raw).hexdigest() != config_match.group(1):
            raise ValueError("Prebuilt image config digest differs")
        archive_config = json.loads(config_raw)
        archive_runtime = archive_config.get("config")
        archive_layers = archive_config.get("rootfs", {}).get("diff_ids")
        if not isinstance(archive_runtime, dict) or archive_layers != rootfs.get("Layers"):
            raise ValueError("Prebuilt archive and inspection layers differ")
        inspect_runtime = inspected["Config"]
        for key in ("Entrypoint", "Cmd", "WorkingDir", "Env", "User"):
            if archive_runtime.get(key) != inspect_runtime.get(key):
                raise ValueError("Prebuilt archive and inspection runtime differ")
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
    )
    env = dict(os.environ, INV_MIGRATION_DSN=url.render_as_string(hide_password=False))
    print("Applying published migrations to the isolated pilot database.", flush=True)
    run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, cwd=ROOT, timeout=120)
    with psycopg.connect(state["adminDSN"]) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='inv_lan_runtime'").fetchone():
            password = psycopg.conninfo.conninfo_to_dict(state["runtimeDSN"]).get("password")
            if password:
                conn.execute(
                    sql.SQL(
                        "CREATE ROLE inv_lan_runtime LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
                    ).format(sql.Literal(password))
                )
            else:
                conn.execute(
                    "CREATE ROLE inv_lan_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
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
        key = load_pilot_ca_key(path)
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
            result.append(
                dict(
                    nodeId=node["nodeId"],
                    nodeIP=node["nodeIP"],
                    coLocatedWithControlPlane=node["coLocatedWithControlPlane"],
                    disabled=node.get("disabled", False),
                    disabledReason=node.get("disabledReason"),
                    node=dict(row) if row else None,
                    observed=bool(snap),
                    snapshot=dict(snap) if snap else None,
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
        help="Passwordless loopback admin DSN behind an operator SSH tunnel",
    )
    p.add_argument(
        "--runtime-dsn-file",
        type=Path,
        help="Passwordless loopback runtime DSN behind the same SSH tunnel",
    )
    p.add_argument("--ca-key", type=Path, help="Encrypted Ed25519 issuing-intermediate private key")
    p.add_argument("--ca-key-password-file", type=Path, help="Private password file for --ca-key")
    p.add_argument("--ca-chain", type=Path, help="Issuing intermediate followed by offline root")
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
