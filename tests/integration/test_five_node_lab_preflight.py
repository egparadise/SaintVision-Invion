"""Real-PostgreSQL boundary for the shared five-node registration/mTLS preflight."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from inv.ids import new_id
from tools.five_node_lab_preflight import (
    five_node_inventory_revision,
    write_registration_mtls_preflight,
)

pytestmark = pytest.mark.postgres


def _database_state(dsn: str, node_ids: list[str]) -> list[tuple]:
    with psycopg.connect(dsn) as connection:
        return connection.execute(
            """SELECT n.node_id,n.status,n.heartbeat_at,n.recovery_epoch,
            c.version,c.enabled,c.endpoint,c.certificate_sha256,
            s.channel_version,s.received_at,s.snapshot
            FROM inv.nodes n
            JOIN inv.node_channels c USING(tenant_id,node_id)
            JOIN inv.node_resource_snapshots s USING(tenant_id,node_id)
            WHERE n.node_id = ANY(%s)
            ORDER BY n.node_id""",
            (node_ids,),
        ).fetchall()


def test_registration_mtls_preflight_reads_five_real_rows_without_mutation(
    request: pytest.FixtureRequest,
    tmp_path: Path,
):
    # Resolve dynamically so a pytest failure never renders the credential-bearing
    # disposable-PostgreSQL fixture value in the test-call argument list.
    postgres = request.getfixturevalue("postgres")
    tenant_id = str(uuid4())
    recovery_epoch = str(uuid4())
    control_plane_host_id = "host-cp-" + uuid4().hex
    nodes = []
    for index in range(5):
        colocated = index == 0
        nodes.append(
            {
                "nodeId": new_id("nod"),
                "ip": f"192.168.45.{140 + index}",
                "certificateSHA256": f"{index + 1:064x}",
                "profile": "lan-workspace-v1",
                "hostId": control_plane_host_id if colocated else "host-" + uuid4().hex,
                "failureDomainId": "fd-" + uuid4().hex,
                "coLocatedWithControlPlane": colocated,
                "measurementEligible": {
                    "s05": not colocated,
                    "s07": not colocated,
                },
                "exclusionReason": "cp-host-colocation" if colocated else None,
            }
        )

    with psycopg.connect(postgres.owner) as connection:
        connection.execute(
            "INSERT INTO inv.tenants(tenant_id,name) VALUES(%s,'five-node-preflight')",
            (tenant_id,),
        )
        for node in nodes:
            connection.execute(
                """INSERT INTO inv.nodes(
                tenant_id,node_id,status,heartbeat_at,recovery_epoch,clock_skew_seconds)
                VALUES(%s,%s,'online',clock_timestamp(),%s,0)""",
                (tenant_id, node["nodeId"], recovery_epoch),
            )
            connection.execute(
                """INSERT INTO inv.node_channels(
                tenant_id,node_id,recovery_epoch,version,endpoint,certificate_sha256,
                certificate_not_after,enabled)
                VALUES(%s,%s,%s,1,%s,%s,clock_timestamp()+interval '1 hour',true)""",
                (
                    tenant_id,
                    node["nodeId"],
                    recovery_epoch,
                    f"https://{node['ip']}:18443",
                    node["certificateSHA256"],
                ),
            )
            snapshot = {
                "tenantId": tenant_id,
                "nodeId": node["nodeId"],
                "recoveryEpoch": recovery_epoch,
                "profileVersion": "lan-workspace-v1",
                "cpuCapacityMillis": 4000,
                "memoryCapacityBytes": 8_000_000_000,
                "memoryAvailableBytes": 6_000_000_000,
            }
            connection.execute(
                """INSERT INTO inv.node_resource_snapshots(
                tenant_id,node_id,recovery_epoch,channel_version,received_at,snapshot)
                VALUES(%s,%s,%s,1,clock_timestamp(),%s)""",
                (tenant_id, node["nodeId"], recovery_epoch, Jsonb(snapshot)),
            )

    inventory = {
        "schemaVersion": "1.0.0",
        "revision": "",
        "controlPlaneHostId": control_plane_host_id,
        "nodes": nodes,
    }
    inventory["revision"] = five_node_inventory_revision(inventory)
    inventory_path = tmp_path / "inventory.json"
    report_path = tmp_path / "preflight.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    node_ids = [node["nodeId"] for node in nodes]
    before = _database_state(postgres.owner, node_ids)

    report = write_registration_mtls_preflight(
        inventory_path,
        postgres.owner,
        report_path,
    )

    assert _database_state(postgres.owner, node_ids) == before
    assert report["databaseReadOnly"] is True
    assert report["syntheticRowsCreated"] is False
    assert report["heartbeatUpdated"] is False
    assert report["counts"]["registered"] == 5
    assert report["counts"]["ready"] == 5
    assert report["counts"]["cpColocated"] == 1
    assert report["counts"]["timedWaveSelected"] == 4
    assert report["allFiveSmokeReady"] is True
    assert report["timedWaveReady"] is True
    assert "tenantId" not in report
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert json.loads(report_text) == report
    assert '"tenantId"' not in report_text
    assert tenant_id not in report_text
    assert postgres.owner not in report_text
