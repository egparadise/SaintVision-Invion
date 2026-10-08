from argparse import Namespace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

import pytest
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "deploy/lan"))

import lan_pilot
from lan_pki import fingerprint, issue, pem, private_pem
import worker_leaf_rotation as rotation

NODE_ID = "nod_01HZZZZZZZZZZZZZZZZZZZZZZZ"
TENANT_ID = "22222222-2222-4222-8222-222222222222"
EPOCH = "11111111-1111-4111-8111-111111111111"
NODE_IP = "192.168.45.81"


def _ca(now):
    root_key = Ed25519PrivateKey.generate()
    intermediate_key = Ed25519PrivateKey.generate()
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test root")])
    intermediate_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test issuer")])
    root = (
        x509.CertificateBuilder()
        .subject_name(root_name)
        .issuer_name(root_name)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(hours=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .add_extension(
            x509.KeyUsage(False, False, False, False, False, True, True, None, None),
            critical=True,
        )
        .sign(root_key, None)
    )
    intermediate = (
        x509.CertificateBuilder()
        .subject_name(intermediate_name)
        .issuer_name(root_name)
        .public_key(intermediate_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(hours=1))
        .not_valid_after(now + timedelta(days=20))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(False, False, False, False, False, True, True, None, None),
            critical=True,
        )
        .sign(root_key, None)
    )
    return root_key, root, intermediate_key, intermediate


def _write(path, name, raw):
    path.mkdir(parents=True, exist_ok=True)
    (path / name).write_bytes(raw)


def _fixture(tmp_path, *, now=None, second_node_key=False):
    now = now or datetime(2026, 10, 7, 1, 0, tzinfo=timezone.utc)
    root_key, root, issuer_key, issuer = _ca(now)
    chain = pem(issuer) + pem(root)
    node_key = Ed25519PrivateKey.generate()
    next_key = Ed25519PrivateKey.generate() if second_node_key else node_key
    control_key = Ed25519PrivateKey.generate()
    node_uri = f"spiffe://saintvision.ai/tenant/{TENANT_ID}/node/{NODE_ID}/epoch/{EPOCH}"
    control_uri = f"spiffe://saintvision.ai/tenant/{TENANT_ID}/control-plane/epoch/{EPOCH}"
    current_node = issue(
        issuer_key,
        issuer,
        node_key.public_key(),
        node_uri,
        address=NODE_IP,
        now=now - timedelta(minutes=1),
        valid_for=timedelta(minutes=5),
    )
    current_control = issue(
        issuer_key,
        issuer,
        control_key.public_key(),
        control_uri,
        now=now - timedelta(minutes=1),
        valid_for=timedelta(minutes=5),
    )
    next_node = issue(
        issuer_key,
        issuer,
        next_key.public_key(),
        node_uri,
        address=NODE_IP,
        now=now,
        valid_for=timedelta(minutes=4),
    )
    next_control = issue(
        issuer_key,
        issuer,
        control_key.public_key(),
        control_uri,
        now=now,
        valid_for=timedelta(minutes=4),
    )
    worker = tmp_path / "worker"
    _write(worker, "ca.pem", chain)
    _write(worker, "node-key.pem", private_pem(node_key))
    _write(worker, "node-cert.pem", pem(current_node))
    current_policy = {
        "version": 7,
        "tenantId": TENANT_ID,
        "nodeId": NODE_ID,
        "recoveryEpoch": EPOCH,
        "expiresAt": (now + timedelta(minutes=3)).isoformat().replace("+00:00", "Z"),
        "clientFingerprints": [fingerprint(current_control)],
    }
    _write(worker, "peer-policy.json", json.dumps(current_policy).encode())
    _write(worker, "manifest.json", json.dumps({"nodeId": NODE_ID}).encode())
    bundle = tmp_path / "bundle"
    overlap_expires = now + timedelta(minutes=2)
    not_after = min(next_node.not_valid_after_utc, next_control.not_valid_after_utc)
    overlap = {
        **current_policy,
        "version": 8,
        "expiresAt": overlap_expires.isoformat().replace("+00:00", "Z"),
        "clientFingerprints": [fingerprint(current_control), fingerprint(next_control)],
    }
    final = {
        **overlap,
        "expiresAt": not_after.isoformat().replace("+00:00", "Z"),
        "clientFingerprints": [fingerprint(next_control)],
    }
    material = {
        "ca.pem": chain,
        "node-cert.pem": pem(next_node),
        "control-cert.pem": pem(next_control),
        "peer-policy-overlap.json": json.dumps(overlap, indent=2).encode(),
        "peer-policy-final.json": json.dumps(final, indent=2).encode(),
    }
    manifest = {
        "schemaVersion": rotation.SCHEMA,
        "rotationId": "a" * 32,
        "tenantId": TENANT_ID,
        "nodeId": NODE_ID,
        "recoveryEpoch": EPOCH,
        "nodeIP": NODE_IP,
        "currentChannelVersion": 7,
        "targetChannelVersion": 8,
        "currentNodeCertificateSHA256": fingerprint(current_node),
        "nextNodeCertificateSHA256": fingerprint(next_node),
        "currentControlCertificateSHA256": fingerprint(current_control),
        "nextControlCertificateSHA256": fingerprint(next_control),
        "caBundleSHA256": hashlib.sha256(chain).hexdigest(),
        "createdAt": now.isoformat().replace("+00:00", "Z"),
        "overlapExpiresAt": overlap_expires.isoformat().replace("+00:00", "Z"),
        "certificateNotAfter": not_after.isoformat().replace("+00:00", "Z"),
        "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in material.items()},
    }
    for name, raw in material.items():
        _write(bundle, name, raw)
    _write(bundle, "rotation.json", rotation._canonical(manifest))
    return Namespace(
        now=now,
        worker=worker,
        bundle=bundle,
        manifest=manifest,
        current_node=current_node,
        current_control=current_control,
        next_node=next_node,
        next_control=next_control,
        node_key=node_key,
        control_key=control_key,
        root_key=root_key,
        root=root,
        chain=chain,
        issuer_key=issuer_key,
        issuer=issuer,
    )


def test_short_lived_leaf_rotation_preserves_node_key_and_finalizes_overlap(tmp_path):
    fixture = _fixture(tmp_path)
    before_key = (fixture.worker / "node-key.pem").read_bytes()
    restarts = []

    receipt = rotation.install(
        fixture.bundle, fixture.worker, now=fixture.now, restart=lambda root: restarts.append(root)
    )

    assert receipt["targetChannelVersion"] == 8
    assert receipt["installedNodeCertificateSHA256"] == fingerprint(fixture.next_node)
    assert restarts == [fixture.worker.resolve()]
    assert (fixture.worker / "node-key.pem").read_bytes() == before_key
    assert x509.load_pem_x509_certificate(
        (fixture.worker / "node-cert.pem").read_bytes()
    ).fingerprint(hashes.SHA256()).hex() == fingerprint(fixture.next_node)
    assert json.loads((fixture.worker / "peer-policy.json").read_text())["clientFingerprints"] == [
        fingerprint(fixture.current_control),
        fingerprint(fixture.next_control),
    ]

    commit_body = {
        "schemaVersion": rotation.SCHEMA,
        "rotationId": fixture.manifest["rotationId"],
        "proposalDigest": receipt["proposalDigest"],
        "nodeId": NODE_ID,
        "channelVersion": 8,
        "certificateSHA256": fingerprint(fixture.next_node),
        "committed": True,
    }
    commit = {
        **commit_body,
        "controlSignature": fixture.control_key.sign(rotation._canonical(commit_body)).hex(),
    }
    commit_path = tmp_path / "commit.json"
    commit_path.write_text(json.dumps(commit), encoding="utf-8")
    result = rotation.finalize(
        fixture.bundle,
        fixture.worker,
        commit_path,
        now=fixture.now + timedelta(seconds=30),
        restart=lambda root: restarts.append(root),
    )
    assert result == {"rotationId": "a" * 32, "finalized": True, "channelVersion": 8}
    assert json.loads((fixture.worker / "peer-policy.json").read_text())["clientFingerprints"] == [
        fingerprint(fixture.next_control)
    ]
    assert len(restarts) == 2
    assert (
        rotation.finalize(
            fixture.bundle,
            fixture.worker,
            commit_path,
            now=fixture.now + timedelta(seconds=30),
            restart=lambda root: restarts.append(root),
        )
        == result
    )
    assert len(restarts) == 2
    with pytest.raises(ValueError, match="completed leaf rotation"):
        rotation.install(
            fixture.bundle,
            fixture.worker,
            now=fixture.now + timedelta(seconds=30),
            restart=lambda _root: None,
        )

    commit_path.write_text(json.dumps({**commit, "controlSignature": "0" * 128}), encoding="utf-8")
    with pytest.raises(InvalidSignature):
        rotation.finalize(
            fixture.bundle,
            fixture.worker,
            commit_path,
            now=fixture.now + timedelta(seconds=30),
            restart=lambda _root: None,
        )


def test_uncommitted_rotation_rolls_back_only_to_fresh_exact_authority(tmp_path):
    fixture = _fixture(tmp_path)
    rotation.install(fixture.bundle, fixture.worker, now=fixture.now, restart=lambda _root: None)
    restarts = []
    result = rotation.rollback(
        fixture.bundle,
        fixture.worker,
        now=fixture.now + timedelta(seconds=30),
        restart=lambda root: restarts.append(root),
    )
    restored = x509.load_pem_x509_certificate((fixture.worker / "node-cert.pem").read_bytes())
    assert result == {"rotationId": "a" * 32, "rolledBack": True, "channelVersion": 7}
    assert fingerprint(restored) == fingerprint(fixture.current_node)
    assert (
        rotation.rollback(
            fixture.bundle,
            fixture.worker,
            now=fixture.now + timedelta(seconds=30),
            restart=lambda root: restarts.append(root),
        )
        == result
    )
    assert restarts == [fixture.worker.resolve()]
    with pytest.raises(ValueError, match="completed leaf rotation"):
        rotation.install(
            fixture.bundle,
            fixture.worker,
            now=fixture.now + timedelta(seconds=30),
            restart=lambda _root: None,
        )

    other = _fixture(tmp_path / "expired")
    rotation.install(other.bundle, other.worker, now=other.now, restart=lambda _root: None)
    with pytest.raises(ValueError, match="expired or differs"):
        rotation.rollback(
            other.bundle,
            other.worker,
            now=other.now + timedelta(minutes=5),
            restart=lambda _root: None,
        )


@pytest.mark.parametrize(
    "point",
    [
        "before-install",
        "after-intent",
        "after-public-install",
        "after-install",
        "before-restart",
    ],
)
def test_rotation_kill_points_recover_idempotently_without_replacing_key(tmp_path, point):
    fixture = _fixture(tmp_path)
    old_key = (fixture.worker / "node-key.pem").read_bytes()
    killed = False

    def kill(current):
        nonlocal killed
        if current == point and not killed:
            killed = True
            raise RuntimeError("synthetic kill")

    with pytest.raises(RuntimeError, match="synthetic kill"):
        rotation.install(
            fixture.bundle, fixture.worker, now=fixture.now, restart=lambda _root: None, kill=kill
        )
    restarts = []
    first = rotation.install(
        fixture.bundle, fixture.worker, now=fixture.now, restart=lambda root: restarts.append(root)
    )
    replay = rotation.install(
        fixture.bundle, fixture.worker, now=fixture.now, restart=lambda root: restarts.append(root)
    )
    assert first == replay
    assert restarts == [fixture.worker.resolve()]
    assert (fixture.worker / "node-key.pem").read_bytes() == old_key


@pytest.mark.parametrize("point", ["after-intent", "after-public-install"])
def test_installing_journal_makes_pre_and_post_publication_crashes_rollback_safe(tmp_path, point):
    fixture = _fixture(tmp_path)

    def kill(current):
        if current == point:
            raise RuntimeError("synthetic publication kill")

    with pytest.raises(RuntimeError, match="synthetic publication kill"):
        rotation.install(
            fixture.bundle,
            fixture.worker,
            now=fixture.now,
            restart=lambda _root: None,
            kill=kill,
        )

    journal = json.loads((fixture.worker / "leaf-rotation.json").read_text("utf-8"))
    assert journal["phase"] == "installing"
    restarts = []
    assert rotation.rollback(
        fixture.bundle,
        fixture.worker,
        now=fixture.now + timedelta(seconds=30),
        restart=lambda root: restarts.append(root),
    ) == {"rotationId": "a" * 32, "rolledBack": True, "channelVersion": 7}
    assert restarts == [fixture.worker.resolve()]
    assert fingerprint(
        x509.load_pem_x509_certificate((fixture.worker / "node-cert.pem").read_bytes())
    ) == fingerprint(fixture.current_node)


@pytest.mark.parametrize(
    "fault,error",
    [
        ("wrong-node", "identity"),
        ("wrong-chain", "pinned chain"),
        ("expired-root", "issuing chain"),
        ("wrong-key", "private key"),
        ("stale-version", "version"),
        ("expired", "validity window"),
    ],
)
def test_rotation_rejects_wrong_identity_chain_key_version_and_expiry(tmp_path, fault, error):
    fixture = _fixture(tmp_path, second_node_key=fault == "wrong-key")
    manifest = json.loads((fixture.bundle / "rotation.json").read_text())
    if fault == "wrong-node":
        manifest["nodeId"] = "nod_01J00000000000000000000000"
    elif fault == "wrong-chain":
        other = _fixture(tmp_path / "other")
        (fixture.bundle / "ca.pem").write_bytes(other.chain)
        manifest["files"]["ca.pem"] = hashlib.sha256(other.chain).hexdigest()
        manifest["caBundleSHA256"] = manifest["files"]["ca.pem"]
    elif fault == "expired-root":
        root = (
            x509.CertificateBuilder()
            .subject_name(fixture.root.subject)
            .issuer_name(fixture.root.subject)
            .public_key(fixture.root_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(fixture.now - timedelta(days=3))
            .not_valid_after(fixture.now - timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
            .add_extension(
                x509.KeyUsage(False, False, False, False, False, True, True, None, None),
                critical=True,
            )
            .sign(fixture.root_key, None)
        )
        chain = pem(fixture.issuer) + pem(root)
        (fixture.worker / "ca.pem").write_bytes(chain)
        (fixture.bundle / "ca.pem").write_bytes(chain)
        manifest["files"]["ca.pem"] = hashlib.sha256(chain).hexdigest()
        manifest["caBundleSHA256"] = manifest["files"]["ca.pem"]
    elif fault == "stale-version":
        manifest["targetChannelVersion"] = manifest["currentChannelVersion"]
    (fixture.bundle / "rotation.json").write_bytes(rotation._canonical(manifest))
    now = fixture.now + timedelta(minutes=5) if fault == "expired" else fixture.now
    with pytest.raises(ValueError, match=error):
        rotation.install(fixture.bundle, fixture.worker, now=now, restart=lambda _root: None)


def test_rotation_refuses_concurrent_second_writer_and_different_retry(tmp_path):
    fixture = _fixture(tmp_path)
    (fixture.worker / "leaf-rotation.lock").write_text("held", encoding="utf-8")
    with pytest.raises(ValueError, match="Another leaf rotation writer"):
        rotation.install(
            fixture.bundle, fixture.worker, now=fixture.now, restart=lambda _root: None
        )
    (fixture.worker / "leaf-rotation.lock").unlink()
    rotation.install(fixture.bundle, fixture.worker, now=fixture.now, restart=lambda _root: None)
    manifest = json.loads((fixture.bundle / "rotation.json").read_text())
    manifest["rotationId"] = "b" * 32
    (fixture.bundle / "rotation.json").write_bytes(rotation._canonical(manifest))
    with pytest.raises(ValueError, match="Another leaf rotation or stale channel version"):
        rotation.install(
            fixture.bundle, fixture.worker, now=fixture.now, restart=lambda _root: None
        )


def test_revocation_registry_rejects_bad_shape_and_exposes_exact_fingerprint(tmp_path):
    path = tmp_path / "revocations.json"
    path.write_text(
        json.dumps(
            [
                {
                    "serialNumber": "01",
                    "certificateSHA256": "a" * 64,
                    "reason": "superseded",
                    "revokedAt": "2026-10-07T00:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    assert lan_pilot._load_revocations(path) == {"a" * 64}
    path.write_text(json.dumps([{"certificateSHA256": "a" * 64}]), encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete"):
        lan_pilot._load_revocations(path)


def test_worker_rotation_cli_and_bundle_are_shipped_without_private_material():
    source = (ROOT / "tools/lan_pilot.py").read_text("utf-8")
    assert '"worker_leaf_rotation.py"' in source
    assert "node-key.pem" not in rotation.FILE_NAMES
    assert "private" not in rotation.MANIFEST_KEYS


class _Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, row):
        self.row = row

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _params=None):
        if "FROM inv.node_channels" in query:
            return _Result(self.row)
        return _Result()


def _prepare_inputs(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, now=datetime.now(timezone.utc))
    pilot = tmp_path / "pilot"
    (pilot / "public").mkdir(parents=True)
    state = {
        "epoch": EPOCH,
        "tenantId": TENANT_ID,
        "nodes": [
            {
                "nodeId": NODE_ID,
                "nodeIP": NODE_IP,
                "nodePort": 18443,
                "provisioned": True,
                "coLocatedWithControlPlane": False,
            }
        ],
        "nodeId": NODE_ID,
        "nodeIP": NODE_IP,
        "nodePort": 18443,
        "serverIP": "192.168.45.74",
        "downloadPort": 18081,
        "baseSHA": "a" * 40,
        "serverNodeColocationAllowed": False,
        "agentImage": "sha256:" + "b" * 64,
        "initialized": True,
        "adminDSN": "synthetic",
        "caMode": "external-intermediate",
        "caBundleSHA256": hashlib.sha256(fixture.chain).hexdigest(),
    }
    (pilot / "private-state.json").write_text(json.dumps(state), encoding="utf-8")
    (pilot / "ca.pem").write_bytes(fixture.chain)
    (pilot / "control-cert.pem").write_bytes(pem(fixture.current_control))
    (pilot / "control-key.pem").write_bytes(private_pem(fixture.control_key))
    (pilot / "public" / "node-cert.pem").write_bytes(pem(fixture.current_node))
    policy = {
        "version": 7,
        "tenantId": TENANT_ID,
        "nodeId": NODE_ID,
        "recoveryEpoch": EPOCH,
        "expiresAt": fixture.current_control.not_valid_after_utc.isoformat().replace("+00:00", "Z"),
        "clientFingerprints": [fingerprint(fixture.current_control)],
    }
    (pilot / "peer-policy.json").write_text(json.dumps(policy), encoding="utf-8")
    csr_path = tmp_path / "node.csr"
    csr_value = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, NODE_ID)]))
        .sign(fixture.node_key, None)
    )
    csr_path.write_bytes(csr_value.public_bytes(serialization.Encoding.PEM))
    password = b"test-issuing-password"
    ca_key = tmp_path / "issuer-key.pem"
    ca_password = tmp_path / "issuer-key.pass"
    ca_chain = tmp_path / "ca-chain.pem"
    revocations = tmp_path / "revocations.json"
    ca_key.write_bytes(
        fixture.issuer_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(password),
        )
    )
    ca_password.write_bytes(password)
    ca_chain.write_bytes(fixture.chain)
    revocations.write_text("[]\n", encoding="utf-8")
    row = (
        7,
        fingerprint(fixture.current_node),
        fixture.current_node.not_valid_after_utc,
        True,
        f"https://{NODE_IP}:18443",
    )
    monkeypatch.setattr(lan_pilot.psycopg, "connect", lambda _dsn: _Connection(row))
    args = Namespace(
        state=pilot,
        csr=csr_path,
        output=tmp_path / "prepared",
        ca_key=ca_key,
        ca_key_password_file=ca_password,
        ca_chain=ca_chain,
        revocations=revocations,
        safety_window_hours=1,
        overlap_seconds=120,
        leaf_valid_seconds=240,
    )
    return fixture, state, row, args


def test_cp_prepare_uses_csr_only_exact_chain_and_monotonic_channel(tmp_path, monkeypatch, capsys):
    fixture, _state, _row, args = _prepare_inputs(tmp_path, monkeypatch)

    lan_pilot.prepare_leaf_rotation(args)
    output = json.loads(capsys.readouterr().out)
    raw, manifest, files = lan_pilot._rotation_material(args.output)

    assert output["privateKeyTransferred"] is False
    assert output["proposalDigest"] == hashlib.sha256(raw).hexdigest()
    assert manifest["currentChannelVersion"] == 7
    assert manifest["targetChannelVersion"] == 8
    assert manifest["currentNodeCertificateSHA256"] == fingerprint(fixture.current_node)
    assert set(files) == set(rotation.FILE_NAMES)
    assert not any("key" in name for name in files)

    lan_pilot.prepare_leaf_rotation(args)
    replay = json.loads(capsys.readouterr().out)
    assert replay["idempotentReplay"] is True
    assert replay["proposalDigest"] == output["proposalDigest"]

    args.revocations.write_text(
        json.dumps(
            [
                {
                    "serialNumber": format(fixture.current_node.serial_number, "x"),
                    "certificateSHA256": fingerprint(fixture.current_node),
                    "reason": "superseded",
                    "revokedAt": datetime.now(timezone.utc).isoformat(),
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="revoked"):
        lan_pilot.prepare_leaf_rotation(args)


def test_cp_prepare_refuses_revoked_current_leaf_without_writing_bundle(tmp_path, monkeypatch):
    fixture, _state, _row, args = _prepare_inputs(tmp_path, monkeypatch)
    args.revocations.write_text(
        json.dumps(
            [
                {
                    "serialNumber": format(fixture.current_node.serial_number, "x"),
                    "certificateSHA256": fingerprint(fixture.current_node),
                    "reason": "superseded",
                    "revokedAt": datetime.now(timezone.utc).isoformat(),
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="revoked"):
        lan_pilot.prepare_leaf_rotation(args)
    assert not args.output.exists()


def test_cp_commit_requires_exact_node_receipt_and_channel_cas(tmp_path, monkeypatch, capsys):
    _fixture_value, _state, row, args = _prepare_inputs(tmp_path, monkeypatch)
    lan_pilot.prepare_leaf_rotation(args)
    capsys.readouterr()
    worker = tmp_path / "node-root"
    for name in ("ca.pem", "node-key.pem", "node-cert.pem", "peer-policy.json", "manifest.json"):
        (worker / name).parent.mkdir(parents=True, exist_ok=True)
    worker.joinpath("ca.pem").write_bytes((args.state / "ca.pem").read_bytes())
    worker.joinpath("node-key.pem").write_bytes(
        _fixture_value.worker.joinpath("node-key.pem").read_bytes()
    )
    worker.joinpath("node-cert.pem").write_bytes(
        args.state.joinpath("public/node-cert.pem").read_bytes()
    )
    worker.joinpath("peer-policy.json").write_bytes(
        args.state.joinpath("peer-policy.json").read_bytes()
    )
    worker.joinpath("manifest.json").write_text(json.dumps({"nodeId": NODE_ID}), encoding="utf-8")
    receipt = rotation.install(args.output, worker, restart=lambda _root: None)
    receipt_path = tmp_path / "node-receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    calls = []

    def provision(_conn, principal, *, epoch, endpoint, certificate_der, expected_version):
        calls.append((principal.node_id, epoch, endpoint, expected_version, certificate_der))
        return 8

    monkeypatch.setattr(lan_pilot, "provision_channel", provision)
    monkeypatch.setattr(lan_pilot.psycopg, "connect", lambda _dsn: _Connection(row))
    commit_args = Namespace(
        state=args.state,
        bundle=args.output,
        node_receipt=receipt_path,
        output=tmp_path / "commit-receipt.json",
    )
    lan_pilot.commit_leaf_rotation(commit_args)
    result = json.loads(capsys.readouterr().out)
    commit = json.loads(commit_args.output.read_text("utf-8"))
    assert calls[0][:4] == (NODE_ID, EPOCH, f"https://{NODE_IP}:18443", 7)
    assert result["restartObserverRequired"] is True
    assert commit["channelVersion"] == 8
    assert commit["certificateSHA256"] == receipt["installedNodeCertificateSHA256"]

    bad = dict(receipt, targetChannelVersion=9)
    receipt_path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="receipt differs"):
        lan_pilot.commit_leaf_rotation(commit_args)
    receipt_path.write_text(json.dumps({**receipt, "nodeSignature": "0" * 128}), encoding="utf-8")
    with pytest.raises(InvalidSignature):
        lan_pilot.commit_leaf_rotation(commit_args)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    control_key_path = args.state / "control-key.pem"
    saved_control_key = control_key_path.read_bytes()
    control_key_path.write_bytes(private_pem(Ed25519PrivateKey.generate()))
    with pytest.raises(ValueError, match="key differs"):
        lan_pilot.commit_leaf_rotation(commit_args)
    control_key_path.write_bytes(saved_control_key)
    monkeypatch.setattr(
        lan_pilot.psycopg,
        "connect",
        lambda _dsn: _Connection((9, "c" * 64, row[2], True, row[4])),
    )
    with pytest.raises(ValueError, match="concurrent or stale"):
        lan_pilot.commit_leaf_rotation(commit_args)


NODE_ID_2 = "nod_01HYYYYYYYYYYYYYYYYYYYYYYY"
NODE_IP_2 = "192.168.45.82"


class _BatchConnection:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        if "FROM inv.node_channels" in query:
            return _Result(self.rows[params[1]])
        return _Result()


def _batch_inputs(tmp_path, monkeypatch):
    fixture, state, row, single = _prepare_inputs(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    second_key = Ed25519PrivateKey.generate()
    second_node = issue(
        fixture.issuer_key,
        fixture.issuer,
        second_key.public_key(),
        f"spiffe://saintvision.ai/tenant/{TENANT_ID}/node/{NODE_ID_2}/epoch/{EPOCH}",
        address=NODE_IP_2,
        now=now - timedelta(minutes=1),
        valid_for=timedelta(minutes=5),
    )
    state["nodes"].append(
        {
            "nodeId": NODE_ID_2,
            "nodeIP": NODE_IP_2,
            "nodePort": 18443,
            "provisioned": True,
            "coLocatedWithControlPlane": False,
        }
    )
    (single.state / "private-state.json").write_text(json.dumps(state), encoding="utf-8")
    second_public = single.state / "public" / "nodes" / NODE_ID_2
    second_public.mkdir(parents=True)
    (second_public / "node-cert.pem").write_bytes(pem(second_node))
    second_policy_dir = single.state / "nodes" / NODE_ID_2
    second_policy_dir.mkdir(parents=True)
    second_policy = {
        "version": 11,
        "tenantId": TENANT_ID,
        "nodeId": NODE_ID_2,
        "recoveryEpoch": EPOCH,
        "expiresAt": fixture.current_control.not_valid_after_utc.isoformat().replace("+00:00", "Z"),
        "clientFingerprints": [fingerprint(fixture.current_control)],
    }
    (second_policy_dir / "peer-policy.json").write_text(json.dumps(second_policy), encoding="utf-8")
    csr2 = tmp_path / "node-2.csr"
    csr2.write_bytes(
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, NODE_ID_2)]))
        .sign(second_key, None)
        .public_bytes(serialization.Encoding.PEM)
    )
    rows = {
        NODE_ID: row,
        NODE_ID_2: (
            11,
            fingerprint(second_node),
            second_node.not_valid_after_utc,
            True,
            f"https://{NODE_IP_2}:18443",
        ),
    }
    monkeypatch.setattr(lan_pilot.psycopg, "connect", lambda _dsn: _BatchConnection(rows))

    def provision(_conn, principal, *, epoch, endpoint, certificate_der, expected_version):
        certificate = x509.load_der_x509_certificate(certificate_der)
        rows[principal.node_id] = (
            expected_version + 1,
            fingerprint(certificate),
            certificate.not_valid_after_utc,
            True,
            endpoint,
        )
        return expected_version + 1

    monkeypatch.setattr(lan_pilot, "provision_channel", provision)
    batch = Namespace(
        state=single.state,
        csr=[single.csr, csr2],
        output=tmp_path / "batch",
        ca_key=single.ca_key,
        ca_key_password_file=single.ca_key_password_file,
        ca_chain=single.ca_chain,
        revocations=single.revocations,
        safety_window_hours=1,
        overlap_seconds=120,
        leaf_valid_seconds=240,
    )
    return fixture, second_key, second_node, rows, batch


def _batch_worker(tmp_path, name, *, chain, key, certificate, policy, node_id):
    worker = tmp_path / name
    worker.mkdir()
    (worker / "ca.pem").write_bytes(chain)
    (worker / "node-key.pem").write_bytes(private_pem(key))
    (worker / "node-cert.pem").write_bytes(pem(certificate))
    (worker / "peer-policy.json").write_text(json.dumps(policy), encoding="utf-8")
    (worker / "manifest.json").write_text(json.dumps({"nodeId": node_id}), encoding="utf-8")
    return worker


def test_multi_node_batch_shares_one_cp_leaf_and_switches_only_after_all_nodes(
    tmp_path, monkeypatch
):
    fixture, second_key, second_node, _rows, args = _batch_inputs(tmp_path, monkeypatch)
    old_control_raw = (args.state / "control-cert.pem").read_bytes()
    old_control_fingerprint = fingerprint(fixture.current_control)

    with pytest.raises(ValueError, match="shared leaf rotation batch"):
        single = Namespace(
            **{**vars(args), "csr": args.csr[0], "output": tmp_path / "unsafe-single"}
        )
        lan_pilot.prepare_leaf_rotation(single)
    with pytest.raises(ValueError, match="shared leaf rotation batch"):
        lan_pilot.commit_leaf_rotation(
            Namespace(
                state=args.state,
                bundle=tmp_path / "unused-bundle",
                node_receipt=tmp_path / "unused-receipt",
                output=tmp_path / "unused-output",
            )
        )

    lan_pilot.prepare_leaf_rotation_batch(args)
    batch_raw, batch, bundles = lan_pilot._batch_material(args.output)
    assert batch["batchId"]
    assert len(bundles) == 2
    assert len({files["control-cert.pem"] for _raw, _manifest, files in bundles.values()}) == 1
    assert not any("key" in item.name for item in args.output.rglob("*"))
    assert all(
        manifest["nextControlCertificateSHA256"] == batch["nextControlCertificateSHA256"]
        for _raw, manifest, _files in bundles.values()
    )

    first_policy = json.loads((args.state / "peer-policy.json").read_text("utf-8"))
    second_policy = json.loads(
        (args.state / "nodes" / NODE_ID_2 / "peer-policy.json").read_text("utf-8")
    )
    worker1 = _batch_worker(
        tmp_path,
        "batch-worker-1",
        chain=fixture.chain,
        key=fixture.node_key,
        certificate=fixture.current_node,
        policy=first_policy,
        node_id=NODE_ID,
    )
    worker2 = _batch_worker(
        tmp_path,
        "batch-worker-2",
        chain=fixture.chain,
        key=second_key,
        certificate=second_node,
        policy=second_policy,
        node_id=NODE_ID_2,
    )
    receipt1 = rotation.install(
        args.output / f"nodes/{NODE_ID}", worker1, restart=lambda _root: None
    )
    receipt2 = rotation.install(
        args.output / f"nodes/{NODE_ID_2}", worker2, restart=lambda _root: None
    )
    receipt1_path = tmp_path / "receipt-1.json"
    receipt2_path = tmp_path / "receipt-2.json"
    receipt1_path.write_text(json.dumps(receipt1), encoding="utf-8")
    receipt2_path.write_text(json.dumps(receipt2), encoding="utf-8")

    lan_pilot.stage_leaf_rotation_batch(
        Namespace(state=args.state, bundle=args.output, node_receipt=receipt1_path)
    )
    assert (args.state / "control-cert.pem").read_bytes() == old_control_raw
    assert (
        old_control_fingerprint
        in json.loads((worker1 / "peer-policy.json").read_text("utf-8"))["clientFingerprints"]
    )
    with pytest.raises(ValueError, match="Every Node"):
        lan_pilot.commit_leaf_rotation_batch(
            Namespace(state=args.state, bundle=args.output, output=tmp_path / "commits-early")
        )
    assert (args.state / "control-cert.pem").read_bytes() == old_control_raw

    lan_pilot.stage_leaf_rotation_batch(
        Namespace(state=args.state, bundle=args.output, node_receipt=receipt2_path)
    )

    def stop_before_switch(point):
        if point == "before-control-switch":
            raise RuntimeError("simulated batch crash")

    with pytest.raises(RuntimeError, match="simulated batch crash"):
        lan_pilot.commit_leaf_rotation_batch(
            Namespace(
                state=args.state,
                bundle=args.output,
                output=tmp_path / "commits",
                _kill=stop_before_switch,
            )
        )
    assert (args.state / "control-cert.pem").read_bytes() == old_control_raw
    for worker in (worker1, worker2):
        assert (
            old_control_fingerprint
            in json.loads((worker / "peer-policy.json").read_text("utf-8"))["clientFingerprints"]
        )

    def stop_after_switch(point):
        if point == "after-control-switch":
            raise RuntimeError("simulated post-switch crash")

    with pytest.raises(RuntimeError, match="simulated post-switch crash"):
        lan_pilot.commit_leaf_rotation_batch(
            Namespace(
                state=args.state,
                bundle=args.output,
                output=tmp_path / "commits",
                _kill=stop_after_switch,
            )
        )
    assert (
        fingerprint(x509.load_pem_x509_certificate((args.state / "control-cert.pem").read_bytes()))
        == batch["nextControlCertificateSHA256"]
    )
    for worker in (worker1, worker2):
        assert (
            batch["nextControlCertificateSHA256"]
            in json.loads((worker / "peer-policy.json").read_text("utf-8"))["clientFingerprints"]
        )

    commit_args = Namespace(state=args.state, bundle=args.output, output=tmp_path / "commits")
    lan_pilot.commit_leaf_rotation_batch(commit_args)
    assert (
        fingerprint(x509.load_pem_x509_certificate((args.state / "control-cert.pem").read_bytes()))
        == batch["nextControlCertificateSHA256"]
    )
    for node_id, worker in ((NODE_ID, worker1), (NODE_ID_2, worker2)):
        rotation.finalize(
            args.output / f"nodes/{node_id}",
            worker,
            commit_args.output / f"{node_id}.json",
            restart=lambda _root: None,
        )
        assert json.loads((worker / "peer-policy.json").read_text("utf-8"))[
            "clientFingerprints"
        ] == [batch["nextControlCertificateSHA256"]]

    before = (args.output / f"nodes/{NODE_ID}/control-cert.pem").read_bytes()
    lan_pilot.prepare_leaf_rotation_batch(args)
    assert (args.output / f"nodes/{NODE_ID}/control-cert.pem").read_bytes() == before
    other = Namespace(**{**vars(args), "output": tmp_path / "different-batch"})
    with pytest.raises(ValueError, match="Another leaf rotation batch"):
        lan_pilot.prepare_leaf_rotation_batch(other)


def test_batch_manifest_rejects_per_node_cp_leaf_mutation(tmp_path, monkeypatch):
    _fixture_value, _key, _node, _rows, args = _batch_inputs(tmp_path, monkeypatch)
    lan_pilot.prepare_leaf_rotation_batch(args)
    second_control = args.output / f"nodes/{NODE_ID_2}/control-cert.pem"
    second_control.write_bytes((args.state / "control-cert.pem").read_bytes())
    with pytest.raises(ValueError, match="digest differs"):
        lan_pilot._batch_material(args.output)


def test_runtime_preflight_rejects_the_observed_old_cryptography_before_state_write(
    monkeypatch,
):
    result = rotation.runtime_preflight()
    assert result["compatible"] is True
    assert result["minimumCryptography"] == "50.0.1"
    monkeypatch.setattr(rotation.cryptography, "__version__", "41.0.7")
    with pytest.raises(RuntimeError, match="cryptography 50.0.1"):
        rotation.runtime_preflight()


def test_isolated_rotation_runtime_is_exactly_pinned_and_preflighted():
    source = (ROOT / "deploy/lan/prepare-leaf-rotation-runtime.sh").read_text("utf-8")
    assert "python3 -m venv" in source
    assert "cryptography==50.0.1" in source
    assert '"$runtime_dir/bin/python" "$worker_script" runtime-preflight' in source
    assert "sudo" not in source
    assert "pip install" in source


def test_expired_partial_batch_is_superseded_by_fresh_all_node_batch(tmp_path, monkeypatch, capsys):
    fixture, second_key, second_node, rows, args = _batch_inputs(tmp_path, monkeypatch)
    lan_pilot.prepare_leaf_rotation_batch(args)
    capsys.readouterr()
    _batch_raw, old_batch, old_bundles = lan_pilot._batch_material(args.output)
    first_policy = json.loads((args.state / "peer-policy.json").read_text("utf-8"))
    second_policy = json.loads(
        (args.state / "nodes" / NODE_ID_2 / "peer-policy.json").read_text("utf-8")
    )
    worker1 = _batch_worker(
        tmp_path,
        "recovery-worker-1",
        chain=fixture.chain,
        key=fixture.node_key,
        certificate=fixture.current_node,
        policy=first_policy,
        node_id=NODE_ID,
    )
    worker2 = _batch_worker(
        tmp_path,
        "recovery-worker-2",
        chain=fixture.chain,
        key=second_key,
        certificate=second_node,
        policy=second_policy,
        node_id=NODE_ID_2,
    )
    receipt = rotation.install(
        args.output / f"nodes/{NODE_ID}", worker1, restart=lambda _root: None
    )
    receipt_path = tmp_path / "partial-receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    lan_pilot.stage_leaf_rotation_batch(
        Namespace(state=args.state, bundle=args.output, node_receipt=receipt_path)
    )
    capsys.readouterr()
    expired_journal = (args.state / "leaf-rotation-batch.json").read_bytes()
    overlap = datetime.fromisoformat(old_batch["overlapExpiresAt"].replace("Z", "+00:00"))
    recovery_now = overlap + timedelta(seconds=1)
    recovery = Namespace(
        **{
            **vars(args),
            "expired_batch": args.output,
            "output": tmp_path / "recovery-batch",
            "overlap_seconds": 900,
            "leaf_valid_seconds": 1200,
            "_now": recovery_now,
        }
    )
    lan_pilot.prepare_leaf_rotation_recovery_batch(recovery)
    output = json.loads(capsys.readouterr().out)
    assert output["recovery"] is True
    assert output["expiredBatchSuperseded"] is True
    _new_raw, new_batch, new_bundles = lan_pilot._batch_material(recovery.output)
    assert new_batch["batchId"] != old_batch["batchId"]
    assert new_bundles[NODE_ID][1]["currentChannelVersion"] == rows[NODE_ID][0]
    assert (
        new_bundles[NODE_ID][1]["currentNodeCertificateSHA256"]
        == old_bundles[NODE_ID][1]["nextNodeCertificateSHA256"]
    )
    assert new_bundles[NODE_ID_2][1]["currentChannelVersion"] == 11
    journal = lan_pilot._load_batch_journal(args.state)
    assert journal["batchId"] == new_batch["batchId"]
    assert journal["phase"] == "prepared"
    recovery_record = args.state / f'leaf-rotation-recovery-{old_batch["batchId"]}.json'
    assert (
        json.loads(recovery_record.read_text("utf-8"))["replacementBatchId"] == new_batch["batchId"]
    )
    # Publishing the replacement directory before the CP journal is crash-replayable.
    (args.state / "leaf-rotation-batch.json").write_bytes(expired_journal)
    lan_pilot.prepare_leaf_rotation_recovery_batch(recovery)
    replay = json.loads(capsys.readouterr().out)
    assert replay["idempotentReplay"] is True
    assert lan_pilot._load_batch_journal(args.state)["batchId"] == new_batch["batchId"]
    original_csr = args.csr[0].read_bytes()
    wrong_key = Ed25519PrivateKey.generate()
    args.csr[0].write_bytes(
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, NODE_ID)]))
        .sign(wrong_key, None)
        .public_bytes(serialization.Encoding.PEM)
    )
    with pytest.raises(ValueError, match="CSR binding differs"):
        lan_pilot.prepare_leaf_rotation_recovery_batch(recovery)
    args.csr[0].write_bytes(original_csr)

    # A crash after archiving the old journal but before writing the new intent is replayable:
    # the current public files still match the fresh bundle's declared recovery base.
    old_journal = json.loads((worker1 / "leaf-rotation.json").read_text("utf-8"))
    rotation._supersede_expired_journal(
        args.output / f"nodes/{NODE_ID}",
        recovery.output / f"nodes/{NODE_ID}",
        worker1,
        old_journal,
        now=recovery_now + timedelta(seconds=1),
    )
    assert not (worker1 / "leaf-rotation.json").exists()
    recovered1 = rotation.install(
        recovery.output / f"nodes/{NODE_ID}",
        worker1,
        restart=lambda _root: None,
        now=recovery_now + timedelta(seconds=1),
        superseded_bundle=args.output / f"nodes/{NODE_ID}",
    )
    recovered2 = rotation.install(
        recovery.output / f"nodes/{NODE_ID_2}",
        worker2,
        restart=lambda _root: None,
        now=recovery_now + timedelta(seconds=1),
    )
    assert recovered1["targetChannelVersion"] == rows[NODE_ID][0] + 1
    assert recovered2["targetChannelVersion"] == 12
    assert (worker1 / "leaf-rotation-superseded" / f'{old_batch["batchId"]}.json').is_file()

    bad_worker = _batch_worker(
        tmp_path,
        "bad-policy-worker",
        chain=fixture.chain,
        key=fixture.node_key,
        certificate=x509.load_pem_x509_certificate(old_bundles[NODE_ID][2]["node-cert.pem"]),
        policy={**first_policy, "version": first_policy["version"] + 99},
        node_id=NODE_ID,
    )
    (bad_worker / "leaf-rotation.json").write_text(json.dumps(old_journal), encoding="utf-8")
    with pytest.raises(ValueError, match="safe supersession base"):
        rotation.install(
            recovery.output / f"nodes/{NODE_ID}",
            bad_worker,
            restart=lambda _root: None,
            now=recovery_now + timedelta(seconds=1),
            superseded_bundle=args.output / f"nodes/{NODE_ID}",
        )


def test_expired_supersession_rejects_policy_or_channel_drift(tmp_path, monkeypatch, capsys):
    fixture, second_key, second_node, rows, args = _batch_inputs(tmp_path, monkeypatch)
    lan_pilot.prepare_leaf_rotation_batch(args)
    capsys.readouterr()
    _raw, old_batch, _bundles = lan_pilot._batch_material(args.output)
    worker = _batch_worker(
        tmp_path,
        "drift-worker",
        chain=fixture.chain,
        key=fixture.node_key,
        certificate=fixture.current_node,
        policy=json.loads((args.state / "peer-policy.json").read_text("utf-8")),
        node_id=NODE_ID,
    )
    receipt = rotation.install(args.output / f"nodes/{NODE_ID}", worker, restart=lambda _root: None)
    receipt_path = tmp_path / "drift-receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    lan_pilot.stage_leaf_rotation_batch(
        Namespace(state=args.state, bundle=args.output, node_receipt=receipt_path)
    )
    capsys.readouterr()
    overlap = datetime.fromisoformat(old_batch["overlapExpiresAt"].replace("Z", "+00:00"))
    recovery = Namespace(
        **{
            **vars(args),
            "expired_batch": args.output,
            "output": tmp_path / "drift-recovery",
            "overlap_seconds": 900,
            "leaf_valid_seconds": 1200,
            "_now": overlap + timedelta(seconds=1),
        }
    )
    rows[NODE_ID] = (99, rows[NODE_ID][1], rows[NODE_ID][2], True, rows[NODE_ID][4])
    with pytest.raises(ValueError, match="channel state differs"):
        lan_pilot.prepare_leaf_rotation_recovery_batch(recovery)
    assert not recovery.output.exists()


def test_overlap_default_allows_operator_delay_but_remains_bounded():
    assert lan_pilot.DEFAULT_ROTATION_OVERLAP_SECONDS == 14400
    assert rotation.MAXIMUM_OVERLAP_SECONDS == 21600
    source = (ROOT / "tools/lan_pilot.py").read_text("utf-8")
    assert "default=DEFAULT_ROTATION_OVERLAP_SECONDS" in source
    assert "MAXIMUM_OVERLAP_SECONDS + 1" in source
