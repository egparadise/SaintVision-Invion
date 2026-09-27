from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from inv.node_channels import node_uri
from inv.tooling import NodePrincipal

import tools.s01_readiness_preflight as s01
from tools.s01_readiness_preflight import (
    aggregate_inputs,
    evaluate_capability_rows,
    lint_inventory,
    probe_certificate_chain,
    probe_control_plane,
    probe_dns,
    probe_pilot_capabilities,
    report_exit_code,
    write_redacted_report,
)
from tools.lan_pki import ca_pair, fingerprint, issue, pem


def inventory() -> dict:
    nodes = []
    for index in range(5):
        colocated = index == 0
        nodes.append(
            {
                "nodeId": f"nod_{index + 1:026d}",
                "hostname": f"node-{index}.internal.example",
                "dnsName": f"node-{index}.internal.example",
                "ip": f"192.168.45.{140 + index}",
                "installationId": f"machine-{index}",
                "os": {"family": "linux", "version": "24.04", "containerRuntime": "docker"},
                "role": "cp-colocated" if colocated else "worker",
                "certificateSHA256": f"{index + 1:064x}",
                "profile": "lan-workspace-v1",
                "hardware": {
                    "cpuModel": "synthetic-cpu",
                    "physicalCoreCount": 4,
                    "logicalThreadCount": 8,
                    "gpus": [],
                    "storageDevice": "synthetic-disk",
                    "networkInterface": "synthetic-nic",
                },
                "capacity": {
                    "cpuMillis": 8000,
                    "memoryBytes": 16_000_000_000,
                    "gpuDevices": 0,
                    "storageBytes": 1_000_000_000_000,
                    "networkBitsPerSecond": 1_000_000_000,
                },
                "allowedResources": {
                    "cpuMillis": 4000,
                    "memoryBytes": 8_000_000_000,
                    "gpuDevices": 0,
                    "storageBytes": 500_000_000_000,
                },
                "allowedFolders": [f"/srv/inv/data-{index}"],
                "ntp": {"configured": True, "source": "synthetic-ntp", "maxSkewSeconds": 5},
                "storageRole": "provider",
            }
        )
    return {
        "schemaVersion": "s01-readiness-inventory:1",
        "topology": "cp-colocated-plus-four-workers",
        "hostnames": {
            "controlPlane": ["cp.internal.example"],
            "portal": ["portal.internal.example"],
            "idp": ["idp.internal.example"],
        },
        "nodes": nodes,
    }


def test_inventory_lint_accepts_complete_five_node_input_without_echoing_values():
    value = inventory()
    result = lint_inventory(value)
    rendered = json.dumps(result, sort_keys=True)

    assert result == {
        "id": "inventory-lint",
        "status": "PASS",
        "code": "inventory-valid",
        "facts": {"nodeCount": 5, "missingFieldCount": 0, "invalidFieldCount": 0},
    }
    for secretish in (value["nodes"][0]["nodeId"], value["nodes"][0]["ip"], "/srv/inv"):
        assert secretish not in rendered


def test_inventory_lint_distinguishes_missing_input_from_invalid_supplied_value():
    assert lint_inventory(None)["status"] == "BLOCKED"
    missing = inventory()
    del missing["nodes"][2]["allowedFolders"]
    missing_result = lint_inventory(missing)
    assert missing_result["status"] == "BLOCKED"
    assert missing_result["facts"]["missingFieldCount"] == 1

    invalid = inventory()
    invalid["nodes"][3]["allowedResources"]["cpuMillis"] = 9000
    invalid_result = lint_inventory(invalid)
    assert invalid_result["status"] == "FAIL"
    assert invalid_result["facts"]["invalidFieldCount"] == 1


def test_inventory_lint_treats_present_null_values_as_missing_not_pass():
    value = inventory()
    value["schemaVersion"] = None
    value["nodes"][0]["profile"] = None
    value["nodes"][0]["role"] = None
    value["nodes"][0]["ntp"]["configured"] = None
    value["nodes"][0]["capacity"]["gpuDevices"] = None

    result = lint_inventory(value)

    assert result["status"] == "BLOCKED"
    assert result["facts"]["missingFieldCount"] == 5
    assert result["facts"]["invalidFieldCount"] == 0

    value["nodes"] = None
    result = lint_inventory(value)
    assert result["status"] == "BLOCKED"
    assert result["facts"]["missingFieldCount"] >= 1


def test_control_plane_requires_both_real_session_and_anonymous_boundary():
    responses = {
        ("/v1/health", False): (200, {"unresolvedSettings": []}, {}),
        ("/readyz", False): (200, {"status": "ready"}, {}),
        ("/v1/session", False): (401, {}, {"www-authenticate": "Bearer"}),
        ("/v1/session", True): (200, {"subjectId": "redacted"}, {}),
    }

    def fetch(path: str, *, authenticated: bool):
        return responses[(path, authenticated)]

    def health_fetch(_path: str, *, authenticated: bool):
        return responses[("/v1/health", authenticated)]

    checks = probe_control_plane(
        base_url="https://secret-host.example",
        health_url="https://health-secret.example/v1/health",
        token="secret-token",
        fetch=fetch,
        health_fetch=health_fetch,
    )
    assert [check["status"] for check in checks] == ["PASS", "PASS", "PASS"]
    rendered = json.dumps(checks, sort_keys=True)
    assert "secret-host" not in rendered
    assert "secret-token" not in rendered
    assert "redacted" not in rendered


def test_missing_token_blocks_session_even_when_anonymous_401_is_correct():
    def fetch(path: str, *, authenticated: bool):
        if path == "/v1/health":
            return 200, {"unresolvedSettings": []}, {}
        if path == "/readyz":
            return 200, {"status": "ready"}, {}
        return 401, {}, {"www-authenticate": "Bearer"}

    def health_fetch(_path: str, *, authenticated: bool):
        return 200, {"unresolvedSettings": ["INV_SECRET_ENDPOINT"]}, {}

    checks = probe_control_plane(
        base_url="http://127.0.0.1:8080",
        health_url="http://127.0.0.1:9000/v1/health",
        token=None,
        fetch=fetch,
        health_fetch=health_fetch,
    )
    assert checks[2]["status"] == "BLOCKED"
    assert checks[2]["code"] == "access-token-missing"
    assert checks[2]["facts"]["anonymousBoundaryValid"] is True


def test_unresolved_health_setting_is_fail_without_setting_names():
    def fetch(path: str, *, authenticated: bool):
        if path == "/v1/health":
            return 200, {"unresolvedSettings": ["INV_SECRET_ENDPOINT"]}, {}
        if path == "/readyz":
            return 200, {"status": "ready"}, {}
        return 401, {}, {"www-authenticate": "Bearer"}

    def health_fetch(_path: str, *, authenticated: bool):
        return 200, {"unresolvedSettings": ["INV_SECRET_ENDPOINT"]}, {}

    health = probe_control_plane(
        base_url="https://cp.example",
        health_url="https://health.example/v1/health",
        token=None,
        fetch=fetch,
        health_fetch=health_fetch,
    )[0]
    assert health["status"] == "FAIL"
    assert health["facts"] == {"unresolvedSettingCount": 1}
    assert "INV_SECRET_ENDPOINT" not in json.dumps(health)


def test_health_surface_is_separate_and_plaintext_token_is_never_sent():
    calls: list[tuple[str, bool]] = []

    def fetch(path: str, *, authenticated: bool):
        calls.append((path, authenticated))
        if path == "/readyz":
            return 200, {"status": "ready"}, {}
        return 401, {}, {"www-authenticate": "Bearer"}

    checks = probe_control_plane(
        base_url="http://cp.example",
        health_url=None,
        token="must-not-be-sent",
        fetch=fetch,
        health_fetch=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    assert checks[0]["status"] == "BLOCKED"
    assert checks[0]["code"] == "health-url-missing"
    assert checks[2]["status"] == "FAIL"
    assert checks[2]["code"] == "plaintext-token-transport-rejected"
    assert ("/v1/session", True) not in calls


def capability_rows(value: dict) -> list[dict]:
    return [
        {
            "node_id": node["nodeId"],
            "certificate_sha256": node["certificateSHA256"],
            "snapshot": {
                "profileVersion": node["profile"],
                "cpuCapacityMillis": node["capacity"]["cpuMillis"],
                "memoryCapacityBytes": node["capacity"]["memoryBytes"],
            },
        }
        for node in value["nodes"]
    ]


def test_capability_comparison_is_exact_and_redacted():
    value = inventory()
    result = evaluate_capability_rows(value, capability_rows(value), database_read_only=True)
    assert result["status"] == "PASS"
    assert result["facts"] == {
        "inventoryNodeCount": 5,
        "registeredNodeCount": 5,
        "matchedNodeCount": 5,
        "databaseReadOnly": True,
    }
    rows = capability_rows(value)
    rows[1]["snapshot"]["memoryCapacityBytes"] += 1
    failed = evaluate_capability_rows(value, rows, database_read_only=True)
    assert failed["status"] == "FAIL"
    assert failed["facts"]["matchedNodeCount"] == 4
    assert value["nodes"][1]["nodeId"] not in json.dumps(failed)


def _write_pilot_certificates(
    state: Path,
    value: dict,
    *,
    count: int = 5,
    wrong_identity_index: int | None = None,
) -> None:
    tenant_id = "00000000-0000-0000-0000-000000000001"
    epoch = "00000000-0000-0000-0000-000000000002"
    ca_key, ca_cert = ca_pair()
    (state / "public" / "nodes").mkdir(parents=True)
    (state / "ca.pem").write_bytes(pem(ca_cert))
    state_nodes = []
    for index, node in enumerate(value["nodes"][:count]):
        node_key = Ed25519PrivateKey.generate()
        uri = node_uri(NodePrincipal(tenant_id, node["nodeId"]), epoch)
        if index == wrong_identity_index:
            uri += "/wrong"
        leaf = issue(ca_key, ca_cert, node_key.public_key(), uri, address=node["ip"])
        node_dir = state / "public" / "nodes" / node["nodeId"]
        node_dir.mkdir()
        (node_dir / "node-cert.pem").write_bytes(pem(leaf))
        node["certificateSHA256"] = fingerprint(leaf)
        state_nodes.append(
            {"nodeId": node["nodeId"], "nodeIP": node["ip"], "provisioned": True}
        )
    (state / "private-state.json").write_text(
        json.dumps(
            {
                "tenantId": tenant_id,
                "epoch": epoch,
                "nodes": state_nodes,
            }
        ),
        encoding="utf-8",
    )


def test_pilot_certificate_chain_matches_product_identity_for_all_five_nodes(tmp_path: Path):
    value = inventory()
    state = tmp_path / "pilot"
    _write_pilot_certificates(state, value)

    passed = probe_certificate_chain(state, value, None)
    assert passed["status"] == "PASS"
    assert passed["facts"] == {"registeredLeafCount": 5, "verifiedLeafCount": 5}
    assert value["nodes"][0]["nodeId"] not in json.dumps(passed)

    value["nodes"][0]["certificateSHA256"] = "f" * 64
    assert probe_certificate_chain(state, value, None)["status"] == "FAIL"


def test_pilot_certificate_chain_blocks_partial_or_null_registration(tmp_path: Path):
    value = inventory()
    state = tmp_path / "pilot"
    _write_pilot_certificates(state, value, count=1)

    result = probe_certificate_chain(state, value, None)
    assert result["status"] == "BLOCKED"
    assert result["code"] == "registered-node-certificates-incomplete"
    assert result["facts"]["registeredLeafCount"] == 1

    private_state = state / "private-state.json"
    private_state.write_text(json.dumps({"tenantId": "tenant", "epoch": "epoch", "nodes": None}))
    assert probe_certificate_chain(state, value, None)["status"] == "BLOCKED"


def test_pilot_certificate_chain_rejects_wrong_spiffe_identity(tmp_path: Path):
    value = inventory()
    state = tmp_path / "pilot"
    _write_pilot_certificates(state, value, wrong_identity_index=2)

    result = probe_certificate_chain(state, value, None)

    assert result["status"] == "FAIL"
    assert result["facts"]["verifiedLeafCount"] == 4


def test_dns_probe_pass_fail_and_blocked_are_redacted():
    value = inventory()
    hostnames = 3 + len(value["nodes"])
    passed = probe_dns(value, resolver=lambda *_args: [(None,)])
    assert passed["status"] == "PASS"
    assert passed["facts"] == {"hostnameCount": hostnames, "resolvedCount": hostnames}

    secret = "dns-exception-secret"

    def failing_resolver(*_args):
        raise RuntimeError(secret)

    failed = probe_dns(value, resolver=failing_resolver)
    assert failed["status"] == "FAIL"
    assert secret not in json.dumps(failed)

    value["hostnames"]["portal"] = None
    blocked = probe_dns(value, resolver=lambda *_args: [(None,)])
    assert blocked["status"] == "BLOCKED"
    assert blocked["code"] == "inventory-not-ready"


def test_pilot_capability_probe_sets_read_only_scope_and_redacts_dsn(tmp_path: Path):
    value = inventory()
    secret_dsn = "postgresql://secret-user:secret-password@pilot.invalid/db"
    secret_tenant = "tenant-secret-marker"
    state = tmp_path / "pilot"
    state.mkdir()
    (state / "private-state.json").write_text(
        json.dumps({"runtimeDSN": secret_dsn, "tenantId": secret_tenant}), encoding="utf-8"
    )
    statements: list[str] = []

    class Result:
        def __init__(self, *, one=None, rows=None):
            self.one = one
            self.rows = rows or []

        def fetchone(self):
            return self.one

        def fetchall(self):
            return self.rows

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, statement, parameters=None):
            normalized = " ".join(statement.split())
            statements.append(normalized)
            if normalized == "SHOW transaction_read_only":
                return Result(one=("on",))
            if normalized.startswith("SELECT n.node_id"):
                return Result(rows=capability_rows(value))
            return Result(one=(None,))

    used_dsns: list[str] = []

    def connect(dsn: str):
        used_dsns.append(dsn)
        return Connection()

    result = probe_pilot_capabilities(state, value, connect=connect)
    assert result["status"] == "PASS"
    assert used_dsns == [secret_dsn]
    assert statements[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    assert "SET LOCAL statement_timeout = '2s'" in statements
    assert any("set_config('inv.tenant_id'" in statement for statement in statements)
    rendered = json.dumps(result)
    assert secret_dsn not in rendered
    assert secret_tenant not in rendered


def test_input_aggregation_uses_fail_then_blocked_then_pass_priority():
    checks = [
        {"id": "health-unresolved-settings", "status": "PASS"},
        {"id": "readyz", "status": "PASS"},
        {"id": "session-boundary", "status": "BLOCKED"},
        {"id": "node-certificate-chain", "status": "PASS"},
        {"id": "dns-resolution", "status": "FAIL"},
        {"id": "inventory-lint", "status": "PASS"},
        {"id": "pilot-capability-match", "status": "PASS"},
    ]
    inputs = aggregate_inputs(checks)
    assert inputs["U2"]["status"] == "BLOCKED"
    assert inputs["U4"]["status"] == "FAIL"
    assert inputs["U5"]["status"] == "PASS"


def test_report_writer_removes_stale_report_and_never_serializes_forbidden_fields(tmp_path: Path):
    target = tmp_path / "report.json"
    target.write_text('{"overallStatus":"PASS","stale":true}', encoding="utf-8")
    report = {
        "schemaVersion": "s01-readiness-preflight:1",
        "readOnly": True,
        "redacted": True,
        "checks": [{"id": "readyz", "status": "BLOCKED", "code": "input-missing", "facts": {}}],
        "inputs": {"U1": {"status": "BLOCKED", "code": "input-missing"}},
    }
    write_redacted_report(target, report)
    saved = json.loads(target.read_text("utf-8"))
    assert saved == report
    assert "stale" not in saved

    bad = dict(report, token="secret")
    with pytest.raises(ValueError, match="forbidden"):
        write_redacted_report(target, bad)
    assert not target.exists()

    with pytest.raises(ValueError, match="forbidden"):
        write_redacted_report(
            target,
            dict(report, checks=[{"facts": {"message": "-----BEGIN CERTIFICATE-----"}}]),
        )
    assert not target.exists()


@pytest.mark.parametrize("protected", ["inventory", "ca", "state-child"])
def test_main_validates_protected_output_before_unlink(
    tmp_path: Path, protected: str
):
    state = tmp_path / "state"
    state.mkdir()
    inventory_path = tmp_path / "inventory.json"
    ca_path = tmp_path / "node-ca.pem"
    inventory_path.write_text("inventory sentinel", encoding="utf-8")
    ca_path.write_text("ca sentinel", encoding="utf-8")
    state_child = state / "private-state.json"
    state_child.write_text("state sentinel", encoding="utf-8")
    output = {
        "inventory": inventory_path,
        "ca": ca_path,
        "state-child": state_child,
    }[protected]
    before = output.read_bytes()

    with pytest.raises(SystemExit) as error:
        s01.main(
            [
                "--inventory",
                str(inventory_path),
                "--state",
                str(state),
                "--ca-bundle",
                str(ca_path),
                "--output",
                str(output),
            ]
        )

    assert error.value.code == 2
    assert output.read_bytes() == before


def test_main_report_and_stdout_are_redacted_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    value = inventory()
    inventory_path = tmp_path / "inventory-secret-marker.json"
    inventory_path.write_text(json.dumps(value), encoding="utf-8")
    state = tmp_path / "state-secret-marker"
    state.mkdir()
    report_path = tmp_path / "report.json"
    token = "token-secret-marker"
    monkeypatch.setenv("TEST_S01_TOKEN", token)

    def fake_http_fetcher(base_url, token_value, ca_bundle, timeout_seconds, *, exact_url=False):
        assert "secret-marker" not in str(ca_bundle)

        def fetch(path: str, *, authenticated: bool):
            if exact_url:
                return 200, {"unresolvedSettings": []}, {}
            if path == "/readyz":
                return 200, {"status": "ready"}, {}
            if authenticated:
                assert token_value == token
                return 200, {"subjectId": "response-secret-marker"}, {}
            return 401, {}, {"www-authenticate": "Bearer"}

        return fetch

    monkeypatch.setattr(s01, "http_fetcher", fake_http_fetcher)
    monkeypatch.setattr(
        s01,
        "probe_certificate_chain",
        lambda *_args: s01._check(
            "node-certificate-chain", "PASS", "certificate-chain-valid", registeredLeafCount=5, verifiedLeafCount=5
        ),
    )
    monkeypatch.setattr(
        s01,
        "probe_dns",
        lambda *_args: s01._check("dns-resolution", "PASS", "dns-resolved", hostnameCount=8, resolvedCount=8),
    )
    monkeypatch.setattr(
        s01,
        "probe_pilot_capabilities",
        lambda *_args: s01._check(
            "pilot-capability-match",
            "PASS",
            "pilot-capabilities-match",
            inventoryNodeCount=5,
            registeredNodeCount=5,
            matchedNodeCount=5,
            databaseReadOnly=True,
        ),
    )

    exit_code = s01.main(
        [
            "--base-url",
            "https://cp-secret-marker.example",
            "--health-url",
            "https://health-secret-marker.example/v1/health",
            "--token-env",
            "TEST_S01_TOKEN",
            "--inventory",
            str(inventory_path),
            "--state",
            str(state),
            "--output",
            str(report_path),
        ]
    )

    assert exit_code == 0
    rendered = report_path.read_text(encoding="utf-8") + capsys.readouterr().out
    for secret in (
        token,
        "secret-marker",
        value["nodes"][0]["nodeId"],
        value["nodes"][0]["ip"],
        value["nodes"][0]["certificateSHA256"],
        "-----BEGIN CERTIFICATE-----",
        "postgresql://",
    ):
        assert secret not in rendered


def test_main_without_any_input_uses_real_probes_and_blocks_every_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    for name in (
        "INV_S01_BASE_URL",
        "INV_S01_HEALTH_URL",
        "INV_S01_ACCESS_TOKEN",
        "INV_S01_INVENTORY",
        "INV_LAN_PILOT_STATE",
        "INV_NODE_MTLS_CA_BUNDLE",
        "INV_S01_HTTP_CA_BUNDLE",
    ):
        monkeypatch.delenv(name, raising=False)
    report_path = tmp_path / "no-input-report.json"

    exit_code = s01.main(["--output", str(report_path)])

    assert exit_code == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert len(report["checks"]) == 7
    assert {check["status"] for check in report["checks"]} == {"BLOCKED"}
    assert set(report["inputs"]) == {"U1", "U2", "U3", "U4", "U5", "U6"}
    assert {value["status"] for value in report["inputs"].values()} == {"BLOCKED"}
    assert report["overallStatus"] == "BLOCKED"
    assert json.loads(capsys.readouterr().out)["counts"] == {
        "PASS": 0,
        "FAIL": 0,
        "BLOCKED": 7,
    }


def test_cli_help_bootstraps_control_plane_import_without_pythonpath():
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}

    result = subprocess.run(
        [sys.executable, str(s01.ROOT / "tools" / "s01_readiness_preflight.py"), "--help"],
        cwd=s01.ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "--health-url" in result.stdout


@pytest.mark.parametrize(
    ("checks", "expected"),
    [
        ([{"status": "PASS"}], 0),
        ([{"status": "PASS"}, {"status": "FAIL"}], 1),
        ([{"status": "PASS"}, {"status": "BLOCKED"}], 2),
        ([], 2),
    ],
)
def test_exit_code_does_not_count_blocked_as_pass(checks: list[dict], expected: int):
    assert report_exit_code(checks) == expected
