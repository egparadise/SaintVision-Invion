from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from tools import five_node_lab_preflight as preflight
from tools import placement_benchmark as benchmark


def _inventory(*, profile: str = "lan-workspace-v1", count: int = 5) -> dict:
    nodes = []
    for index in range(count):
        colocated = index == 0
        nodes.append(
            {
                "nodeId": f"nod_{index:026d}",
                "ip": f"192.168.45.{140 + index}",
                "certificateSHA256": f"{index + 1:064x}",
                "profile": profile,
                "hostId": "host-cp" if colocated else f"host-ubuntu-{index}",
                "failureDomainId": f"physical-host-{index}",
                "coLocatedWithControlPlane": colocated,
                "measurementEligible": {
                    "s05": not colocated,
                    "s07": not colocated,
                },
                "exclusionReason": "cp-host-colocation" if colocated else None,
            }
        )
    value = {
        "schemaVersion": "1.0.0",
        "revision": "pending",
        "controlPlaneHostId": "host-cp",
        "nodes": nodes,
    }
    value["revision"] = benchmark.five_node_inventory_revision(value)
    return value


def _row(node: dict, *, now: datetime, heartbeat_age: float = 1.0) -> dict:
    epoch = "rec_00000000000000000000000000"
    tenant = "ten_00000000000000000000000000"
    return {
        "tenant_id": tenant,
        "node_id": node["nodeId"],
        "status": "online",
        "heartbeat_at": now - timedelta(seconds=heartbeat_age),
        "node_recovery_epoch": epoch,
        "clock_skew_seconds": 0.1,
        "channel_recovery_epoch": epoch,
        "channel_version": 1,
        "endpoint": f"https://{node['ip']}:18443",
        "certificate_sha256": node["certificateSHA256"],
        "certificate_not_after": now + timedelta(days=1),
        "channel_enabled": True,
        "snapshot_recovery_epoch": epoch,
        "snapshot_channel_version": 1,
        "snapshot_received_at": now - timedelta(seconds=1),
        "snapshot": {
            "tenantId": tenant,
            "nodeId": node["nodeId"],
            "recoveryEpoch": epoch,
            "profileVersion": node["profile"],
            "cpuCapacityMillis": 4000,
            "memoryCapacityBytes": 8_000_000_000,
            "memoryAvailableBytes": 6_000_000_000,
        },
        "database_now": now,
    }


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, rows, *, transaction_read_only="on"):
        self.rows = rows
        self.transaction_read_only = transaction_read_only
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters=None):
        self.statements.append((statement, parameters))
        if statement == "SHOW transaction_read_only":
            return _Result([{"transaction_read_only": self.transaction_read_only}])
        if statement == benchmark._FIVE_NODE_PREFLIGHT_SQL:
            return _Result(self.rows)
        return _Result([])


def _write_inventory(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_inventory_revision_and_topology_are_strict(tmp_path: Path):
    value = _inventory()
    assert benchmark.load_five_node_inventory(_write_inventory(tmp_path, value)) == value

    stale = deepcopy(value)
    stale["nodes"][1]["ip"] = "192.168.45.250"
    with pytest.raises(ValueError, match="revision mismatch"):
        benchmark.load_five_node_inventory(_write_inventory(tmp_path, stale))

    invalid = deepcopy(value)
    invalid["nodes"][0]["measurementEligible"]["s05"] = True
    invalid["revision"] = benchmark.five_node_inventory_revision(invalid)
    with pytest.raises(ValueError, match="cannot join timed waves"):
        benchmark.load_five_node_inventory(_write_inventory(tmp_path, invalid))


def test_placement_adapter_reexports_the_shared_preflight_implementation():
    assert benchmark.load_five_node_inventory is preflight.load_five_node_inventory
    assert benchmark.five_node_lab_dry_run is preflight.five_node_lab_dry_run
    assert benchmark._FIVE_NODE_PREFLIGHT_SQL == preflight._FIVE_NODE_PREFLIGHT_SQL


def test_inventory_rejects_two_cp_colocated_nodes(tmp_path: Path):
    value = _inventory(count=2)
    second = value["nodes"][1]
    second["hostId"] = value["controlPlaneHostId"]
    second["coLocatedWithControlPlane"] = True
    second["measurementEligible"] = {"s05": False, "s07": False}
    second["exclusionReason"] = "cp-host-colocation"
    value["revision"] = benchmark.five_node_inventory_revision(value)

    with pytest.raises(ValueError, match="at most one CP-colocated"):
        benchmark.load_five_node_inventory(_write_inventory(tmp_path, value))


@pytest.mark.parametrize(
    ("host_id", "declared"),
    [
        ("host-ubuntu-independent", True),
        ("host-cp", False),
    ],
)
def test_inventory_rejects_declared_colocation_that_disagrees_with_host_identity(
    tmp_path: Path,
    host_id: str,
    declared: bool,
):
    value = _inventory(count=1)
    node = value["nodes"][0]
    node["hostId"] = host_id
    node["coLocatedWithControlPlane"] = declared
    value["revision"] = benchmark.five_node_inventory_revision(value)

    with pytest.raises(ValueError, match="disagrees with host identity"):
        benchmark.load_five_node_inventory(_write_inventory(tmp_path, value))


def test_dry_run_reads_only_and_excludes_cp_colocated_node_from_timed_wave():
    value = _inventory()
    now = datetime.now(timezone.utc)
    connection = _Connection([_row(node, now=now) for node in value["nodes"]])

    report = benchmark.five_node_lab_dry_run(
        value,
        "postgresql://secret",
        connect=lambda _dsn: connection,
    )

    statements = [statement.strip().upper() for statement, _ in connection.statements]
    assert statements[0] == "SET TRANSACTION READ ONLY"
    assert statements[1] == "SHOW TRANSACTION_READ_ONLY"
    assert all(not statement.startswith(("INSERT", "UPDATE", "DELETE")) for statement in statements)
    assert report["databaseReadOnly"] is True
    assert report["syntheticRowsCreated"] is False
    assert report["heartbeatUpdated"] is False
    assert "tenantId" not in report
    assert report["allFiveSmokeReady"] is True
    assert report["timedWaveReady"] is True
    assert report["allFiveSmokeNodeIds"] == [node["nodeId"] for node in value["nodes"]]
    assert report["timedWaveNodeIds"] == [node["nodeId"] for node in value["nodes"][1:]]
    assert report["nodes"][0]["selectedForAllFiveSmoke"] is True
    assert report["nodes"][0]["selectedForTimedWave"] is False
    assert report["nodes"][0]["coLocationValidation"] == "matched"


def test_dry_run_rejects_database_that_does_not_confirm_read_only_transaction():
    value = _inventory(count=1)
    connection = _Connection([], transaction_read_only="off")

    with pytest.raises(RuntimeError, match="database preflight failed"):
        benchmark.five_node_lab_dry_run(
            value,
            "postgresql://secret",
            connect=lambda _dsn: connection,
        )


def test_dry_run_reports_stale_nodes_without_promoting_them():
    value = _inventory(profile="lan-observe-v1", count=3)
    now = datetime.now(timezone.utc)
    rows = [_row(node, now=now, heartbeat_age=20) for node in value["nodes"]]
    connection = _Connection(rows)

    report = benchmark.five_node_lab_dry_run(
        value,
        "postgresql://secret",
        connect=lambda _dsn: connection,
    )

    assert report["counts"] == {
        "inventory": 3,
        "physicalExecutionHosts": 3,
        "registered": 3,
        "ready": 0,
        "cpColocated": 1,
        "cpIndependent": 2,
        "timedWaveEligible": 2,
        "timedWaveSelected": 0,
    }
    assert report["allFiveSmokeReady"] is False
    assert "heartbeat-stale-or-missing" in report["nodes"][0]["readiness"]["reasons"]
    assert "profile-not-lan-workspace-v1" in report["nodes"][0]["readiness"]["reasons"]


def test_dry_run_rejects_inventory_node_missing_from_postgresql():
    value = _inventory(count=2)
    now = datetime.now(timezone.utc)
    connection = _Connection([_row(value["nodes"][0], now=now)])

    with pytest.raises(ValueError, match="not registered in PostgreSQL"):
        benchmark.five_node_lab_dry_run(
            value,
            "postgresql://secret",
            connect=lambda _dsn: connection,
        )


def test_report_writer_removes_stale_output_before_validation(tmp_path: Path):
    stale_report = tmp_path / "preflight.json"
    stale_report.write_text('{"timedWaveReady":true}\n', encoding="utf-8")
    invalid_inventory = _inventory(count=1)
    invalid_inventory["revision"] = "sha256:" + "0" * 64
    inventory_path = _write_inventory(tmp_path, invalid_inventory)

    with pytest.raises(ValueError, match="revision mismatch"):
        preflight.write_registration_mtls_preflight(
            inventory_path,
            "postgresql://secret",
            stale_report,
            connect=lambda _dsn: pytest.fail("validation must precede database access"),
        )

    assert not stale_report.exists()


def test_report_writer_never_deletes_inventory_when_paths_match(tmp_path: Path):
    inventory_path = _write_inventory(tmp_path, _inventory(count=1))
    original = inventory_path.read_bytes()

    with pytest.raises(ValueError, match="inventory and preflight report paths must differ"):
        preflight.write_registration_mtls_preflight(
            inventory_path,
            "postgresql://secret",
            inventory_path,
            connect=lambda _dsn: pytest.fail("same-path rejection must precede database access"),
        )

    assert inventory_path.read_bytes() == original


def test_report_writer_removes_stale_output_when_dsn_is_missing(tmp_path: Path):
    stale_report = tmp_path / "preflight.json"
    stale_report.write_text('{"timedWaveReady":true}\n', encoding="utf-8")
    inventory_path = _write_inventory(tmp_path, _inventory(count=1))

    with pytest.raises(ValueError, match="INV_TEST_ADMIN_DSN is required"):
        preflight.write_registration_mtls_preflight(inventory_path, None, stale_report)

    assert not stale_report.exists()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda row: row.update(certificate_sha256="f" * 64), "certificate fingerprint"),
        (
            lambda row: row["snapshot"].update(profileVersion="different-profile"),
            "profileVersion",
        ),
        (
            lambda row: row.update(snapshot_recovery_epoch="rec_different"),
            "recovery epochs differ",
        ),
    ],
)
def test_dry_run_rejects_registered_identity_drift(mutate, message):
    value = _inventory(count=1)
    now = datetime.now(timezone.utc)
    row = _row(value["nodes"][0], now=now)
    mutate(row)
    connection = _Connection([row])

    with pytest.raises(ValueError, match=message):
        benchmark.five_node_lab_dry_run(
            value,
            "postgresql://secret",
            connect=lambda _dsn: connection,
        )


def test_cli_keeps_synthetic_as_default_and_requires_explicit_lab_dry_run(
    monkeypatch,
    tmp_path: Path,
):
    called = []
    monkeypatch.setattr(benchmark, "_run_pytest_adapter", lambda args: called.append(args) or 17)
    assert (
        benchmark.main(
            [
                "--requests",
                "1",
                "--concurrency",
                "1",
                "--junit",
                str(tmp_path / "result.xml"),
                "--report",
                str(tmp_path / "result.json"),
            ]
        )
        == 17
    )
    assert called[0].adapter == "synthetic"

    with pytest.raises(SystemExit, match="requires --dry-run"):
        benchmark.main(
            [
                "--adapter",
                "five-node-lab",
                "--inventory",
                str(tmp_path / "inventory.json"),
            ]
        )
