"""Real PostgreSQL evidence for preserving a revoked CP-colocated Node."""

from argparse import Namespace
import json
from pathlib import Path
import sys
from uuid import uuid4

import psycopg
import pytest

from inv.ids import new_id

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import lan_pilot  # noqa: E402

pytestmark = pytest.mark.postgres


def _node(node_id: str, node_ip: str, *, colocated: bool) -> dict:
    return {
        "nodeId": node_id,
        "nodeIP": node_ip,
        "nodePort": 18443,
        "provisioned": True,
        "coLocatedWithControlPlane": colocated,
    }


def test_real_revoke_preserves_node_and_records_channel_version_and_audit(
    postgres,
    tmp_path: Path,
    capsys,
):
    tenant = str(uuid4())
    epoch = str(uuid4())
    independent_id = new_id("nod")
    colocated_id = new_id("nod")
    server_ip = "192.168.45.74"
    nodes = [
        _node(independent_id, "192.168.45.143", colocated=False),
        _node(colocated_id, server_ip, colocated=True),
    ]
    state = {
        "epoch": epoch,
        "tenantId": tenant,
        "nodes": nodes,
        "nodeId": independent_id,
        "nodeIP": nodes[0]["nodeIP"],
        "nodePort": 18443,
        "serverIP": server_ip,
        "downloadPort": 18081,
        "serverNodeColocationAllowed": True,
        "initialized": True,
        "adminDSN": postgres.owner,
        "runtimeDSN": postgres.runtime,
    }
    lan_pilot.save(tmp_path, state)

    preserved = {
        tmp_path / "nodes" / colocated_id / "node-key.pem": b"preserved-private-key",
        tmp_path / "nodes" / colocated_id / "journal": b"preserved-journal",
        tmp_path / "public" / "nodes" / colocated_id / "node-cert.pem": b"preserved-cert",
    }
    for path, content in preserved.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    fingerprints = {
        independent_id: "a" * 64,
        colocated_id: "b" * 64,
    }
    with psycopg.connect(postgres.owner) as conn:
        conn.execute("INSERT INTO inv.tenants VALUES (%s,'revocation-test')", (tenant,))
        for node in nodes:
            conn.execute(
                "INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch) "
                "VALUES (%s,%s,'offline',%s)",
                (tenant, node["nodeId"], epoch),
            )
            conn.execute(
                "INSERT INTO inv.node_channels("
                "tenant_id,node_id,recovery_epoch,version,endpoint,certificate_sha256,"
                "certificate_not_after,enabled) "
                "VALUES (%s,%s,%s,1,%s,%s,clock_timestamp()+interval '1 day',true)",
                (
                    tenant,
                    node["nodeId"],
                    epoch,
                    f"https://{node['nodeIP']}:18443",
                    fingerprints[node["nodeId"]],
                ),
            )
            conn.execute(
                "INSERT INTO inv.node_channel_audit("
                "tenant_id,node_id,version,action,certificate_sha256) "
                "VALUES (%s,%s,1,'provision',%s)",
                (tenant, node["nodeId"], fingerprints[node["nodeId"]]),
            )

    lan_pilot.revoke_server_node_colocation(Namespace(state=tmp_path))
    output = json.loads(capsys.readouterr().out)

    assert output["statePreserved"] is True
    assert output["channels"] == [
        {
            "nodeId": colocated_id,
            "channel": "revoked",
            "channelVersion": 2,
        }
    ]
    assert postgres.owner not in json.dumps(output)

    persisted = json.loads((tmp_path / "private-state.json").read_text(encoding="utf-8"))
    assert persisted["serverNodeColocationAllowed"] is False
    assert [(node["nodeId"], node.get("disabled")) for node in persisted["nodes"]] == [
        (independent_id, None),
        (colocated_id, True),
    ]
    assert persisted["nodes"][1]["disabledReason"] == "server-node-colocation-revoked"
    assert all(path.read_bytes() == content for path, content in preserved.items())

    with psycopg.connect(postgres.owner) as conn:
        channels = conn.execute(
            "SELECT node_id,version,enabled FROM inv.node_channels "
            "WHERE tenant_id=%s ORDER BY node_id",
            (tenant,),
        ).fetchall()
        audits = conn.execute(
            "SELECT node_id,version,action,certificate_sha256 "
            "FROM inv.node_channel_audit WHERE tenant_id=%s ORDER BY node_id,version",
            (tenant,),
        ).fetchall()
        node_count = conn.execute(
            "SELECT count(*) FROM inv.nodes WHERE tenant_id=%s",
            (tenant,),
        ).fetchone()[0]

    by_node = {row[0]: row[1:] for row in channels}
    assert by_node[independent_id] == (1, True)
    assert by_node[colocated_id] == (2, False)
    assert audits == sorted(
        [
            (independent_id, 1, "provision", fingerprints[independent_id]),
            (colocated_id, 1, "provision", fingerprints[colocated_id]),
            (colocated_id, 2, "revoke", fingerprints[colocated_id]),
        ]
    )
    assert node_count == 2
