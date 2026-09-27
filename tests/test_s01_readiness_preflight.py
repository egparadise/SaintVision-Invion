from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.s01_readiness_preflight import (
    aggregate_inputs,
    evaluate_capability_rows,
    lint_inventory,
    probe_certificate_chain,
    probe_control_plane,
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
                "nodeId": f"nod_test_{index}",
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


def test_control_plane_requires_both_real_session_and_anonymous_boundary():
    responses = {
        ("/v1/health", False): (200, {"unresolvedSettings": []}, {}),
        ("/readyz", False): (200, {"status": "ready"}, {}),
        ("/v1/session", False): (401, {}, {"www-authenticate": "Bearer"}),
        ("/v1/session", True): (200, {"subjectId": "redacted"}, {}),
    }

    def fetch(path: str, *, authenticated: bool):
        return responses[(path, authenticated)]

    checks = probe_control_plane(base_url="https://secret-host.example", token="secret-token", fetch=fetch)
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

    checks = probe_control_plane(base_url="http://127.0.0.1:8080", token=None, fetch=fetch)
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

    health = probe_control_plane(base_url="https://cp.example", token=None, fetch=fetch)[0]
    assert health["status"] == "FAIL"
    assert health["facts"] == {"unresolvedSettingCount": 1}
    assert "INV_SECRET_ENDPOINT" not in json.dumps(health)


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


def test_pilot_certificate_chain_uses_registered_leaf_and_inventory_fingerprint(tmp_path: Path):
    value = inventory()
    ca_key, ca_cert = ca_pair()
    node_key = Ed25519PrivateKey.generate()
    leaf = issue(
        ca_key,
        ca_cert,
        node_key.public_key(),
        "inv://tenant/nodes/" + value["nodes"][0]["nodeId"],
    )
    value["nodes"][0]["certificateSHA256"] = fingerprint(leaf)
    state = tmp_path / "pilot"
    (state / "public").mkdir(parents=True)
    (state / "ca.pem").write_bytes(pem(ca_cert))
    (state / "public" / "node-cert.pem").write_bytes(pem(leaf))
    (state / "private-state.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "nodeId": value["nodes"][0]["nodeId"],
                        "nodeIP": value["nodes"][0]["ip"],
                        "provisioned": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    passed = probe_certificate_chain(state, value, None)
    assert passed["status"] == "PASS"
    assert passed["facts"] == {"registeredLeafCount": 1, "verifiedLeafCount": 1}
    assert value["nodes"][0]["nodeId"] not in json.dumps(passed)

    value["nodes"][0]["certificateSHA256"] = "f" * 64
    assert probe_certificate_chain(state, value, None)["status"] == "FAIL"


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


@pytest.mark.parametrize(
    ("checks", "expected"),
    [
        ([{"status": "PASS"}], 0),
        ([{"status": "PASS"}, {"status": "FAIL"}], 1),
        ([{"status": "PASS"}, {"status": "BLOCKED"}], 2),
    ],
)
def test_exit_code_does_not_count_blocked_as_pass(checks: list[dict], expected: int):
    assert report_exit_code(checks) == expected
