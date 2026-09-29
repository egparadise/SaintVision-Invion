"""PG-free LAN pilot multi-Node state and artifact boundary tests."""

import io
import json
import os
import re
import subprocess
import sys
import tarfile
import zipfile
from argparse import Namespace
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import intranet_pki
import lan_pilot


def node(node_id, node_ip, *, provisioned=True, colocated=False):
    return dict(
        nodeId=node_id,
        nodeIP=node_ip,
        nodePort=18443,
        provisioned=provisioned,
        coLocatedWithControlPlane=colocated,
    )


def state(nodes):
    primary = nodes[0]
    return dict(
        epoch="epoch-test",
        tenantId="tenant-test",
        nodes=nodes,
        nodeId=primary["nodeId"],
        nodeIP=primary["nodeIP"],
        nodePort=18443,
        serverIP="192.168.45.74",
        downloadPort=18081,
        baseSHA="a" * 40,
        serverNodeColocationAllowed=any(current["nodeIP"] == "192.168.45.74" for current in nodes),
        agentImage="sha256:" + "b" * 64,
        initialized=True,
    )


def csr(node_id):
    key = Ed25519PrivateKey.generate()
    request = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, node_id)]))
        .sign(key, None)
    )
    return request.public_bytes(serialization.Encoding.PEM)


def test_legacy_single_node_state_normalizes_and_addition_preserves_identity():
    legacy = dict(
        epoch="epoch-test",
        tenantId="tenant-test",
        nodeId="nod_primary",
        serverIP="192.168.45.74",
        nodeIP="192.168.45.81",
        nodePort=18443,
        initialized=True,
    )

    normalized = lan_pilot.normalized_state(legacy)
    expanded, added = lan_pilot.add_requested_nodes(normalized, ["192.168.45.81", "192.168.45.82"])

    assert expanded["nodeId"] == "nod_primary"
    assert expanded["nodeIP"] == "192.168.45.81"
    assert expanded["nodes"][0] == node("nod_primary", "192.168.45.81")
    assert len(added) == 1
    assert added[0]["nodeIP"] == "192.168.45.82"
    assert added[0]["nodeId"].startswith("nod_")
    assert added[0]["provisioned"] is False


def test_node_addresses_are_private_unique_and_distinct_from_server():
    lan_pilot.validate_node_ips("192.168.45.74", ["192.168.45.81", "192.168.45.82"])
    with pytest.raises(ValueError, match="specified once"):
        lan_pilot.validate_node_ips("192.168.45.74", ["192.168.45.81", "192.168.45.81"])
    with pytest.raises(ValueError, match="allow-server-node-colocation"):
        lan_pilot.validate_node_ips("192.168.45.74", ["192.168.45.74"])
    lan_pilot.validate_node_ips(
        "192.168.45.74", ["192.168.45.74"], allow_server_node_colocation=True
    )
    with pytest.raises(ValueError, match="private LAN"):
        lan_pilot.validate_node_ips("192.168.45.74", ["8.8.8.8"])


def test_colocated_node_metadata_is_derived_and_cannot_be_forged():
    configured = state(
        [
            node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81"),
            node("nod_01J00000000000000000000000", "192.168.45.74", colocated=True),
        ]
    )

    assert lan_pilot.configured_nodes(configured)[1]["coLocatedWithControlPlane"] is True
    configured["nodes"][1]["coLocatedWithControlPlane"] = False
    with pytest.raises(ValueError, match="co-location metadata differs"):
        lan_pilot.configured_nodes(configured)

    configured["nodes"][1]["coLocatedWithControlPlane"] = True
    configured["serverNodeColocationAllowed"] = False
    with pytest.raises(ValueError, match="not authorized"):
        lan_pilot.configured_nodes(configured)


def test_colocated_node_addition_requires_persisted_opt_in():
    configured = state(
        [
            node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81"),
        ]
    )
    with pytest.raises(ValueError, match="not authorized"):
        lan_pilot.add_requested_nodes(configured, ["192.168.45.74"])

    configured["serverNodeColocationAllowed"] = True
    expanded, added = lan_pilot.add_requested_nodes(configured, ["192.168.45.74"])
    assert added[0]["nodeIP"] == "192.168.45.74"
    assert expanded["nodes"][1]["coLocatedWithControlPlane"] is True


def test_colocation_revoke_preserves_identity_but_removes_operational_access(tmp_path):
    configured = state(
        [
            node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81"),
            node("nod_01J00000000000000000000000", "192.168.45.74", colocated=True),
        ]
    )
    original = json.loads(json.dumps(configured["nodes"][1]))

    revoked_state, revoked = lan_pilot.revoked_colocation_state(configured)

    assert revoked_state["serverNodeColocationAllowed"] is False
    assert revoked[0]["nodeId"] == original["nodeId"]
    assert revoked[0]["nodeIP"] == original["nodeIP"]
    assert revoked[0]["disabled"] is True
    assert revoked[0]["disabledReason"] == "server-node-colocation-revoked"
    assert [item["nodeId"] for item in lan_pilot.configured_nodes(revoked_state)] == [
        configured["nodes"][0]["nodeId"],
        original["nodeId"],
    ]
    assert [item["nodeId"] for item in lan_pilot.active_configured_nodes(revoked_state)] == [
        configured["nodes"][0]["nodeId"]
    ]

    public = tmp_path / "public"
    public.mkdir()
    with pytest.raises(PermissionError, match="not an allowed Node"):
        lan_pilot.artifact_for_client(revoked_state, public, original["nodeIP"], "/worker.zip")


def test_revoked_node_certificate_is_not_active_and_requires_known_reason():
    configured = state(
        [
            node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81"),
        ]
    )
    configured["nodes"][0]["credentialRevoked"] = True
    configured["nodes"][0]["credentialRevocationReason"] = "key-compromise"
    configured["nodes"][0]["credentialRevokedAt"] = "2026-09-30T00:00:00+09:00"

    assert lan_pilot.active_configured_nodes(configured) == []

    configured["nodes"][0]["credentialRevocationReason"] = "operator-note-only"
    with pytest.raises(ValueError, match="reason is invalid"):
        lan_pilot.configured_nodes(configured)


def test_revoke_cli_persists_fail_closed_state_before_channel_revoke(monkeypatch, capsys):
    configured = state(
        [
            node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81"),
            node("nod_01J00000000000000000000000", "192.168.45.74", colocated=True),
        ]
    )
    configured["tenantId"] = "00000000-0000-4000-8000-000000000001"
    configured["adminDSN"] = "not-printed"
    events = []

    class Result:
        def fetchone(self):
            return (7, True)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, _params):
            if query.startswith("SELECT version"):
                return Result()
            return None

    monkeypatch.setattr(lan_pilot, "load", lambda _path: configured)
    monkeypatch.setattr(
        lan_pilot,
        "save",
        lambda _path, value: events.append(("saved", value["nodes"][1]["disabled"])),
    )
    monkeypatch.setattr(lan_pilot.psycopg, "connect", lambda _dsn: Connection())
    monkeypatch.setattr(
        lan_pilot,
        "revoke_channel",
        lambda _conn, node, expected_version: events.append(
            ("revoked", node.node_id, expected_version)
        )
        or 8,
    )

    lan_pilot.revoke_server_node_colocation(Namespace(state=Path("unused")))
    output = json.loads(capsys.readouterr().out)

    assert events == [
        ("saved", True),
        ("revoked", configured["nodes"][1]["nodeId"], 7),
    ]
    assert output["statePreserved"] is True
    assert output["disabledNodes"][0]["disabledReason"] == "server-node-colocation-revoked"
    assert output["channels"][0] == {
        "nodeId": configured["nodes"][1]["nodeId"],
        "channel": "revoked",
        "channelVersion": 8,
    }


def test_certificate_revoke_cli_marks_state_before_channel_version(monkeypatch, capsys):
    current = state(
        [
            node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81"),
        ]
    )
    current["tenantId"] = "00000000-0000-4000-8000-000000000001"
    current["adminDSN"] = "not-printed"
    events = []

    class Result:
        def fetchone(self):
            return (5, True)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, _params):
            if query.startswith("SELECT version"):
                return Result()
            return None

    monkeypatch.setattr(lan_pilot, "load", lambda _path: current)
    monkeypatch.setattr(
        lan_pilot,
        "save",
        lambda _path, value: events.append(("saved", value["nodes"][0]["credentialRevoked"])),
    )
    monkeypatch.setattr(lan_pilot.psycopg, "connect", lambda _dsn: Connection())
    monkeypatch.setattr(
        lan_pilot,
        "revoke_channel",
        lambda _conn, principal, expected_version: events.append(
            ("revoked", principal.node_id, expected_version)
        )
        or 6,
    )

    lan_pilot.revoke_node_certificate(
        Namespace(state=Path("unused"), node_id=current["nodeId"], reason="superseded")
    )
    output = json.loads(capsys.readouterr().out)

    assert events == [
        ("saved", True),
        ("revoked", current["nodeId"], 5),
    ]
    assert output["channel"] == "revoked"
    assert output["channelVersion"] == 6
    assert output["restartBootstrapRequired"] is True


def test_colocated_manifest_is_excluded_from_adr100_measurements():
    configured = state(
        [
            node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81"),
            node("nod_01J00000000000000000000000", "192.168.45.74", colocated=True),
        ]
    )
    manifest = lan_pilot.manifest_for_node(
        configured, configured["nodes"][1], {"RootFS": {"Layers": []}, "Config": {}}, "test:tag"
    )

    assert manifest["schemaVersion"] == 3
    assert manifest["coLocatedWithControlPlane"] is True
    assert manifest["measurementEligible"] == {"s05": False, "s07": False}
    assert manifest["exclusionReason"] == "cp-host-colocation"


def test_csr_common_name_selects_exact_configured_node():
    configured = state(
        [
            node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81"),
            node("nod_01J00000000000000000000000", "192.168.45.82"),
        ]
    )

    selected = lan_pilot.node_from_csr(configured, csr("nod_01J00000000000000000000000"))

    assert selected["nodeIP"] == "192.168.45.82"
    with pytest.raises(ValueError, match="not configured"):
        lan_pilot.node_from_csr(configured, csr("nod_01J11111111111111111111111"))


def test_legacy_single_node_public_paths_remain_downloadable(tmp_path):
    legacy = dict(
        epoch="epoch-test",
        tenantId="tenant-test",
        nodeId="nod_primary",
        serverIP="192.168.45.74",
        nodeIP="192.168.45.81",
        nodePort=18443,
        initialized=True,
    )
    public = tmp_path / "public"
    public.mkdir()
    (public / "worker.zip").write_bytes(b"legacy-worker")
    (public / "node-cert.pem").write_bytes(b"legacy-certificate")

    assert (
        lan_pilot.artifact_for_client(legacy, public, "192.168.45.81", "/worker.zip")
        == public / "worker.zip"
    )
    assert (
        lan_pilot.artifact_for_client(legacy, public, "192.168.45.81", "/node-cert.pem")
        == public / "node-cert.pem"
    )


def test_secondary_node_never_falls_back_to_primary_legacy_artifacts(tmp_path):
    configured = state(
        [
            node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81"),
            node("nod_01J00000000000000000000000", "192.168.45.82"),
        ]
    )
    public = tmp_path / "public"
    public.mkdir()
    (public / "worker.zip").write_bytes(b"primary-worker-only")
    (public / "node-cert.pem").write_bytes(b"primary-certificate-only")

    assert lan_pilot.artifact_for_client(configured, public, "192.168.45.82", "/worker.zip") is None
    assert (
        lan_pilot.artifact_for_client(configured, public, "192.168.45.82", "/node-cert.pem") is None
    )


@pytest.mark.parametrize("field", ["nodeId", "recoveryEpoch", "clientFingerprints"])
def test_existing_peer_policy_mismatch_is_rejected_without_replacement(tmp_path, field):
    configured = state(
        [
            node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81"),
        ]
    )
    ca_key, ca_cert = lan_pilot.ca_pair()
    control_key = Ed25519PrivateKey.generate()
    control = lan_pilot.issue(
        ca_key,
        ca_cert,
        control_key.public_key(),
        "spiffe://saintvision.ai/tenant/tenant-test/control-plane/epoch/epoch-test",
    )
    (tmp_path / "control-cert.pem").write_bytes(lan_pilot.pem(control))
    policy = dict(
        version=1,
        tenantId=configured["tenantId"],
        nodeId=configured["nodeId"],
        recoveryEpoch=configured["epoch"],
        expiresAt="2099-01-01T00:00:00+00:00",
        clientFingerprints=[lan_pilot.fingerprint(control)],
    )
    if field == "nodeId":
        policy[field] = "nod_DIFFERENT"
    elif field == "recoveryEpoch":
        policy[field] = "different-epoch"
    else:
        policy[field] = ["0" * 64]
    target = tmp_path / "peer-policy.json"
    target.write_text(json.dumps(policy, indent=2), encoding="utf-8")
    before = target.read_bytes()

    with pytest.raises(ValueError, match="Existing peer policy identity differs"):
        lan_pilot.ensure_node_policy(tmp_path, configured, configured["nodes"][0])

    assert target.read_bytes() == before


def test_bundle_emits_distinct_node_archives_and_ip_scoped_downloads(tmp_path, monkeypatch, capsys):
    nodes = [
        node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81"),
        node("nod_01J00000000000000000000000", "192.168.45.82"),
    ]
    configured = state(nodes)
    lan_pilot.save(tmp_path, configured)
    (tmp_path / "ca.pem").write_bytes(b"public-ca")
    (tmp_path / "signer.pub").write_bytes(b"public-signer")
    for current in nodes:
        policy_path = lan_pilot.node_policy_path(tmp_path, configured, current)
        policy_path.write_text(
            json.dumps(
                dict(
                    version=1,
                    tenantId=configured["tenantId"],
                    nodeId=current["nodeId"],
                    recoveryEpoch=configured["epoch"],
                    expiresAt="2099-01-01T00:00:00Z",
                    clientFingerprints=["f" * 64],
                )
            ),
            encoding="utf-8",
        )

    def fake_run(command, **_kwargs):
        command = [str(value) for value in command]
        if command[:3] == ["docker", "image", "inspect"] and "--format" in command:
            return configured["agentImage"]
        if command[:2] == ["docker", "save"]:
            Path(command[3]).write_bytes(b"node-image")
            return ""
        if command[:3] == ["docker", "image", "inspect"]:
            return json.dumps(
                [
                    {
                        "RootFS": {"Layers": ["sha256:" + "c" * 64]},
                        "Config": {"Entrypoint": ["/inv-node"]},
                    }
                ]
            )
        raise AssertionError(command)

    monkeypatch.setattr(lan_pilot, "run", fake_run)
    lan_pilot.bundle(Namespace(state=tmp_path, go=None, reuse_image=True))
    output = json.loads(capsys.readouterr().out)

    assert len(output["nodes"]) == 2
    assert output["nodes"][0]["sha256"] != output["nodes"][1]["sha256"]
    for current, artifact in zip(nodes, output["nodes"], strict=True):
        archive_path = Path(artifact["archive"])
        with zipfile.ZipFile(archive_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            policy = json.loads(archive.read("peer-policy.json"))
        assert (manifest["nodeId"], manifest["nodeIP"]) == (current["nodeId"], current["nodeIP"])
        assert policy["nodeId"] == current["nodeId"]

    public = tmp_path / "public"
    first = lan_pilot.artifact_for_client(configured, public, "192.168.45.81", "/worker.zip")
    second = lan_pilot.artifact_for_client(configured, public, "192.168.45.82", "/worker.zip")
    assert first == Path(output["nodes"][0]["archive"])
    assert second == Path(output["nodes"][1]["archive"])
    assert first != second
    assert (
        lan_pilot.artifact_for_client(configured, public, "192.168.45.81", "/worker.sha256") is None
    )
    with pytest.raises(PermissionError, match="not an allowed Node"):
        lan_pilot.artifact_for_client(configured, public, "192.168.45.99", "/worker.zip")


def test_external_intermediate_stays_central_and_signs_control_identity(tmp_path):
    ca_dir = tmp_path / "ca"
    state_dir = tmp_path / "pilot"
    state_dir.mkdir()
    intranet_pki.initialize(
        ca_dir,
        root_password_file=tmp_path / "offline-secret" / "node-root.pass",
        profile="node-mtls",
    )
    paths = intranet_pki._paths(ca_dir)
    configured = state(
        [
            node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81"),
        ]
    )
    args = Namespace(
        ca_key=paths["intermediate_key"],
        ca_key_password_file=paths["intermediate_password"],
        ca_chain=paths["chain"],
    )

    result = lan_pilot.ensure_pilot_pki(state_dir, configured, args)

    assert result["caMode"] == "external-intermediate"
    assert (state_dir / "ca.pem").read_bytes() == paths["chain"].read_bytes()
    assert not (state_dir / "ca-key.pem").exists()
    assert not (state_dir / "ca-key.pass").exists()
    (state_dir / "private-state.json").write_text(
        json.dumps({**configured, "caMode": "external-intermediate"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="all required"):
        lan_pilot.load_pilot_ca_key(state_dir)
    key = lan_pilot.load_pilot_ca_key(
        state_dir,
        key_path=paths["intermediate_key"],
        password_path=paths["intermediate_password"],
        chain_path=paths["chain"],
    )
    intermediate = x509.load_pem_x509_certificate(paths["intermediate_certificate"].read_bytes())
    assert key.public_key().public_bytes_raw() == intermediate.public_key().public_bytes_raw()
    control = x509.load_pem_x509_certificate((state_dir / "control-cert.pem").read_bytes())
    intermediate.public_key().verify(control.signature, control.tbs_certificate_bytes)

    changed_chain = tmp_path / "changed-chain.pem"
    changed_chain.write_bytes(paths["root_certificate"].read_bytes())
    args.ca_chain = changed_chain
    with pytest.raises(ValueError):
        lan_pilot.ensure_pilot_pki(state_dir, configured, args)


def test_external_database_dsn_requires_exact_private_passfile_and_loopback(tmp_path):
    dsn = tmp_path / "admin.dsn"
    passfile = tmp_path / "admin.pgpass"
    passfile.write_text(
        "127.0.0.1:55440:saintvision_lan:postgres:" + ("a" * 64) + "\n",
        encoding="utf-8",
    )
    passfile.chmod(0o600)
    dsn.write_text(
        "host=127.0.0.1 port=55440 dbname=saintvision_lan user=postgres "
        f"passfile='{passfile.as_posix()}'",
        encoding="utf-8",
    )

    value = lan_pilot.read_external_dsn(dsn, "postgres")
    parsed = lan_pilot.psycopg.conninfo.conninfo_to_dict(value)
    assert parsed["host"] == "127.0.0.1"
    assert parsed["connect_timeout"] == "5"
    assert "password" not in parsed
    assert lan_pilot.external_dsn_password(value, "postgres") == "a" * 64

    dsn.write_text(
        "host=127.0.0.1 port=55440 dbname=saintvision_lan user=postgres "
        f"passfile='{passfile.as_posix()}' password=secret",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="passfile-backed loopback"):
        lan_pilot.read_external_dsn(dsn, "postgres")

    dsn.write_text(
        "host=127.0.0.1 port=55440 dbname=saintvision_lan user=postgres",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="passfile-backed loopback"):
        lan_pilot.read_external_dsn(dsn, "postgres")

    passfile.write_text(
        "198.51.100.20:55440:saintvision_lan:postgres:" + ("a" * 64) + "\n",
        encoding="utf-8",
    )
    dsn.write_text(
        "host=198.51.100.20 port=55440 dbname=saintvision_lan user=postgres "
        f"passfile='{passfile.as_posix()}'",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="passfile-backed loopback"):
        lan_pilot.read_external_dsn(dsn, "postgres")

    passfile.write_text(
        "127.0.0.1:55440:saintvision_lan:inv_lan_runtime:" + ("a" * 64) + "\n",
        encoding="utf-8",
    )
    dsn.write_text(
        "host=127.0.0.1 port=55440 dbname=saintvision_lan user=postgres "
        f"passfile='{passfile.as_posix()}'",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="identity differs"):
        lan_pilot.read_external_dsn(dsn, "postgres")


def test_remote_database_script_uses_scram_dedicated_network_and_private_files():
    root = Path(__file__).resolve().parents[1]
    script = (root / "deploy/lan/prepare-pilot-database.sh").read_text(encoding="utf-8")
    verifier = (root / "deploy/lan/verify-pilot-database.sh").read_text(encoding="utf-8")

    assert "POSTGRES_HOST_AUTH_METHOD=trust" not in script
    assert "--auth-host=scram-sha-256 --auth-local=scram-sha-256" in script
    assert "docker network create --label ai.saintvision.lan-pilot=card150" in script
    assert "docker network create --internal" not in script
    assert '--network "$network"' in script
    assert '--publish "127.0.0.1:${host_port}:5432"' in script
    assert "POSTGRES_PASSWORD_FILE=/run/secrets/postgres-password" in script
    assert 'credentialStorage":"operator-private-files' in script
    assert not re.search(
        r"(?m)^psql\b[^\n]*(?:runtime_password|\$\([^\n]*runtime-password)", script
    )
    assert "\\set runtime_password `cat /run/secrets/runtime-password`" in script
    assert "SET log_statement = 'none'" in script
    assert "SET log_min_error_statement = 'panic'" in script
    assert "ALTER ROLE inv_lan_runtime LOGIN NOSUPERUSER NOBYPASSRLS" in script
    assert "NOCREATEDB NOCREATEROLE NOREPLICATION" in script
    assert "rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication" in verifier
    assert "'f|f|f|f|f'" in verifier


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell verifier runs in hosted Linux")
def test_remote_database_verifier_fails_closed_for_role_and_hba_drift(tmp_path):
    root = Path(__file__).resolve().parents[1]
    fake_docker = tmp_path / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env bash
set -eu
command_line="$*"
case "$command_line" in
  *'{{.Internal}}'*) echo false ;;
  *'ai.saintvision.lan-pilot'*) echo card150 ;;
  *'len .NetworkSettings.Networks'*) echo 1 ;;
  *'if index .NetworkSettings.Networks'*) echo yes ;;
  *'HostConfig.PortBindings'*) echo 127.0.0.1 ;;
  *'PGPASSFILE=/dev/null'*) exit 1 ;;
  *'PGPASSWORD=wrong'*) exit 1 ;;
  *'rolsuper, rolbypassrls'*) echo "${FAKE_RUNTIME_PRIVILEGES:-f|f|f|f|f}" ;;
  *'pg_auth_members'*) echo "${FAKE_UNEXPECTED_MEMBERSHIPS:-0}" ;;
  *'pg_hba_file_rules'*) echo "${FAKE_AUTH_METHODS:-scram-sha-256}" ;;
  *'SHOW password_encryption'*) echo scram-sha-256 ;;
  *'SELECT current_user'*'inv_lan_runtime'*) echo inv_lan_runtime ;;
  *'SELECT current_user'*) echo postgres ;;
  *) echo "unexpected docker invocation" >&2; exit 3 ;;
esac
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o700)
    command = [
        "bash",
        str(root / "deploy/lan/verify-pilot-database.sh"),
        "saintvision-test-db",
        "saintvision-test-network",
    ]
    environment = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}

    assert subprocess.run(command, env=environment, check=False).returncode == 0
    for variable, value in (
        ("FAKE_RUNTIME_PRIVILEGES", "f|f|f|f|t"),
        ("FAKE_UNEXPECTED_MEMBERSHIPS", "1"),
        ("FAKE_AUTH_METHODS", "md5"),
    ):
        drifted = {**environment, variable: value}
        assert subprocess.run(command, env=drifted, check=False).returncode == 1


def test_bind_db_auth_requires_negative_rejection_and_role_bound_credentials(
    tmp_path, monkeypatch, capsys
):
    configured = state([node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81")])
    configured.update(
        databaseMode=lan_pilot.EXTERNAL_DATABASE_MODE,
        adminDSN="host=127.0.0.1 port=55442 dbname=saintvision_lan user=postgres",
        runtimeDSN=("host=127.0.0.1 port=55442 dbname=saintvision_lan user=inv_lan_runtime"),
    )
    (tmp_path / "private-state.json").write_text(json.dumps(configured), encoding="utf-8")
    admin_passfile = tmp_path / "admin.pgpass"
    runtime_passfile = tmp_path / "runtime.pgpass"
    admin_passfile.write_text(
        "127.0.0.1:55442:saintvision_lan:postgres:" + ("a" * 64) + "\n",
        encoding="utf-8",
    )
    runtime_passfile.write_text(
        "127.0.0.1:55442:saintvision_lan:inv_lan_runtime:" + ("b" * 64) + "\n",
        encoding="utf-8",
    )
    admin_passfile.chmod(0o600)
    runtime_passfile.chmod(0o600)
    rejected = []
    runtime_privileges = [False, False, False, False, False]
    runtime_memberships = ["inv_kernel"]
    auth_methods = ["scram-sha-256", "scram-sha-256"]

    class Result:
        def __init__(self, *, one=None, rows=None):
            self.one = one
            self.rows = rows or []

        def fetchone(self):
            return self.one

        def fetchall(self):
            return self.rows

    class Connection:
        def __init__(self, dsn):
            self.info = lan_pilot.psycopg.conninfo.conninfo_to_dict(dsn)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, query):
            if query == "SHOW password_encryption":
                return Result(one=("scram-sha-256",))
            if "pg_hba_file_rules" in query:
                return Result(rows=[(method,) for method in auth_methods])
            if "FROM pg_auth_members" in query:
                return Result(rows=[(role,) for role in runtime_memberships])
            if "FROM pg_roles" in query:
                return Result(one=tuple(runtime_privileges))
            if query == "SELECT current_user":
                return Result(one=(self.info["user"],))
            raise AssertionError(query)

    def connect(dsn):
        info = lan_pilot.psycopg.conninfo.conninfo_to_dict(dsn)
        if info.get("password") == "0" * 64 or str(info.get("passfile", "")).endswith(
            ".missing-pgpass"
        ):
            rejected.append(info["user"])
            raise lan_pilot.psycopg.OperationalError("expected rejection")
        return Connection(dsn)

    monkeypatch.setattr(lan_pilot.psycopg, "connect", connect)
    lan_pilot.bind_db_auth(
        Namespace(
            state=tmp_path,
            admin_passfile=admin_passfile,
            runtime_passfile=runtime_passfile,
        )
    )

    saved = json.loads((tmp_path / "private-state.json").read_text(encoding="utf-8"))
    assert rejected == ["postgres", "postgres"]
    assert "password=" not in saved["adminDSN"]
    assert "password=" not in saved["runtimeDSN"]
    assert saved["databaseAuthentication"] == "scram-sha-256"
    output = capsys.readouterr().out
    assert json.loads(output)["wrongCredentialRejected"] is True
    assert "a" * 64 not in output
    assert "b" * 64 not in output

    for privilege_index in range(len(runtime_privileges)):
        runtime_privileges[privilege_index] = True
        with pytest.raises(ValueError, match="elevated privileges"):
            lan_pilot.bind_db_auth(
                Namespace(
                    state=tmp_path,
                    admin_passfile=admin_passfile,
                    runtime_passfile=runtime_passfile,
                )
            )
        runtime_privileges[privilege_index] = False

    auth_methods[1] = "md5"
    with pytest.raises(ValueError, match="not exclusively SCRAM"):
        lan_pilot.bind_db_auth(
            Namespace(
                state=tmp_path,
                admin_passfile=admin_passfile,
                runtime_passfile=runtime_passfile,
            )
        )

    auth_methods[1] = "scram-sha-256"
    runtime_memberships.append("pg_write_server_files")
    with pytest.raises(ValueError, match="membership differs"):
        lan_pilot.bind_db_auth(
            Namespace(
                state=tmp_path,
                admin_passfile=admin_passfile,
                runtime_passfile=runtime_passfile,
            )
        )


def test_prebuilt_image_archive_is_bound_to_inspection_and_tag(tmp_path):
    tag = "saintvision-lan-node:epoch-te"
    archive_path = tmp_path / "node-agent.tar"
    inspect_path = tmp_path / "image-inspect.json"
    config_value = {
        "config": {
            "Entrypoint": ["/inv-node"],
            "Cmd": None,
            "WorkingDir": "",
            "Env": None,
            "User": "",
        },
        "rootfs": {"diff_ids": []},
    }
    config = json.dumps(config_value, separators=(",", ":")).encode()
    image_hex = __import__("hashlib").sha256(config).hexdigest()
    config_name = image_hex + ".json"
    manifest = json.dumps([{"Config": config_name, "RepoTags": [tag], "Layers": []}]).encode()
    with tarfile.open(archive_path, "w") as archive:
        for name, data in [("manifest.json", manifest), (config_name, config)]:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    inspect_path.write_text(
        json.dumps(
            [
                {
                    "Id": "sha256:" + image_hex,
                    "RepoTags": [tag],
                    "RootFS": {"Layers": []},
                    "Config": config_value["config"],
                }
            ]
        ),
        encoding="utf-8",
    )

    image_id, inspected = lan_pilot.load_prebuilt_image(
        archive_path, inspect_path, tag, tmp_path / "copied.tar"
    )

    assert image_id == "sha256:" + image_hex
    assert inspected["Config"]["Entrypoint"] == ["/inv-node"]
    assert (tmp_path / "copied.tar").read_bytes() == archive_path.read_bytes()

    inspect_path.write_text(
        json.dumps(
            [
                {
                    "Id": "sha256:" + ("c" * 64),
                    "RepoTags": [tag],
                    "RootFS": {"Layers": ["sha256:" + ("d" * 64)]},
                    "Config": config_value["config"],
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="image ID differs"):
        lan_pilot.load_prebuilt_image(archive_path, inspect_path, tag, tmp_path / "rejected.tar")

    inspected = json.loads(inspect_path.read_text(encoding="utf-8"))
    inspected[0]["Id"] = "sha256:" + image_hex
    inspect_path.write_text(json.dumps(inspected), encoding="utf-8")
    with pytest.raises(ValueError, match="layers differ"):
        lan_pilot.load_prebuilt_image(archive_path, inspect_path, tag, tmp_path / "rejected.tar")


def test_status_rows_keep_partial_nodes_visible(monkeypatch):
    nodes = [
        node("nod_01HZZZZZZZZZZZZZZZZZZZZZZZ", "192.168.45.81"),
        node("nod_01J00000000000000000000000", "192.168.45.82"),
    ]
    configured = state(nodes)

    class Result:
        def __init__(self, value):
            self.value = value

        def fetchone(self):
            return self.value

    class Connection:
        def execute(self, query, params):
            node_id = params[0]
            if "FROM inv.nodes" in query:
                if node_id == nodes[0]["nodeId"]:
                    return Result(dict(node_id=node_id, status="online", heartbeat_at="now"))
                return Result(None)
            if node_id == nodes[0]["nodeId"]:
                return Result(
                    dict(
                        received_at="now",
                        snapshot={
                            "tenantId": configured["tenantId"],
                            "recoveryEpoch": configured["epoch"],
                            "nonce": "secret-challenge",
                            "observedAt": "then",
                            "profileVersion": "lan-observe-v1",
                            "osType": "linux",
                            "agentVersion": "0.1.0",
                            "cpuCapacityMillis": 4000,
                            "memoryCapacityBytes": 8000,
                            "memoryAvailableBytes": 6000,
                        },
                    )
                )
            return Result(None)

    class Transaction:
        def __enter__(self):
            return Connection()

        def __exit__(self, *_args):
            return False

    class Runtime:
        def transaction(self, tenant_id):
            assert tenant_id == configured["tenantId"]
            return Transaction()

    monkeypatch.setattr(lan_pilot, "runtime", lambda _state: Runtime())
    rows = lan_pilot.node_status_rows(configured)

    assert [(row["nodeId"], row["nodeIP"]) for row in rows] == [
        (nodes[0]["nodeId"], "192.168.45.81"),
        (nodes[1]["nodeId"], "192.168.45.82"),
    ]
    assert rows[0]["observed"] is True
    assert rows[0]["snapshot"] == {
        "receivedAt": "now",
        "observedAt": "then",
        "profileVersion": "lan-observe-v1",
        "osType": "linux",
        "agentVersion": "0.1.0",
        "cpuCapacityMillis": 4000,
        "memoryCapacityBytes": 8000,
        "memoryAvailableBytes": 6000,
    }
    assert not {"tenantId", "recoveryEpoch", "nonce"} & set(rows[0]["snapshot"])
    assert rows[1]["node"] is None
    assert rows[1]["observed"] is False
