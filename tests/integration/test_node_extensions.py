from copy import copy, deepcopy
import hashlib
import os
from uuid import uuid4
import psycopg
import pytest
from inv.approvals import Principal
from inv.control import Control
from inv.errors import DomainError
from inv.node_channels import NodeChannels, provision_channel, revoke_channel
from inv.node_transfer import NodeTransfer
from inv.observation import NodeObservation
from inv.observer_worker import ObservationWorker
from test_approvals import approval
from test_node_runtime import node_runtime
from test_node_delivery import remote, start
from test_snapshots import storage

pytestmark = pytest.mark.postgres


def export_node(a, data):
    a.daemon.terminate()
    a.daemon.communicate(timeout=12)
    root = a.path / "exports"
    root.mkdir(mode=0o700)
    digest = hashlib.sha256(data).hexdigest()
    file = root / digest
    file.write_bytes(data)
    file.chmod(0o400)
    a.args.extend(["--objects", str(root)])
    start(a)
    with psycopg.connect(a.e.owner) as conn:
        provision_channel(
            conn,
            a.node,
            epoch=a.e.epoch,
            endpoint=a.endpoint,
            certificate_der=a.server_cert.der,
            expected_version=1,
        )
    return digest


def test_actual_node_resource_snapshot_and_observer_loop(remote):
    a = remote
    worker = ObservationWorker(a.e.db, a.client)
    assert worker.once(a.e.tenant) == {"observed": 1, "unavailable": 0}
    with a.e.db.transaction(a.e.tenant) as conn:
        row = conn.execute(
            "SELECT * FROM inv.node_resource_snapshots WHERE node_id=%s", (a.e.node,)
        ).fetchone()
    s = row["snapshot"]
    assert (
        0 <= s["cpuBusyMillis"] <= s["cpuCapacityMillis"] and s["cpuCapacityMillis"] > 0
    )
    assert (
        0 <= s["memoryAvailableBytes"] <= s["memoryCapacityBytes"]
        and s["memoryCapacityBytes"] > 0
    )
    assert (
        s["nodeId"] == a.e.node
        and s["recoveryEpoch"] == a.e.epoch
        and s["sampleMillis"] >= 100
    )
    assert not list((a.path / "state").glob("*.intent"))


def test_snapshot_replay_and_revocation_cannot_update_observation(remote):
    a = remote
    o = NodeObservation(a.e.db, a.client)
    proof, request = o.begin(a.node)
    snapshot = a.client.resource_snapshot(proof, request)
    response = {
        k: snapshot[k]
        for k in (
            "nonce",
            "tenantId",
            "nodeId",
            "recoveryEpoch",
            "profileVersion",
            "observedAt",
        )
    }
    o.accept(a.node, proof, request, response, snapshot=snapshot)
    with pytest.raises(DomainError):
        o.accept(a.node, proof, request, response, snapshot=snapshot)
    proof, request = o.begin(a.node)
    snapshot = a.client.resource_snapshot(proof, request)
    response = {k: snapshot[k] for k in response}
    with psycopg.connect(a.e.owner) as conn:
        revoke_channel(conn, a.node, expected_version=1)
    with pytest.raises(DomainError, match="NODE-0033"):
        o.accept(a.node, proof, request, response, snapshot=snapshot)


def test_three_capacity_figures_ignore_future_and_revoked_measurements(remote):
    a = remote
    o = NodeObservation(a.e.db, a.client)
    o.poll_resources(a.node)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)",
            (a.e.tenant, a.e.project, a.e.node),
        )
    control = Control(a.e.db)
    p = Principal(a.e.tenant, "requester")
    capacity = control.capacity(p, a.e.project)
    assert (
        capacity["totalOffered"]
        == capacity["largestSingleNode"]
        == {"cpuMillis": 1000, "memoryBytes": 268435456}
    )
    assert (
        0 <= capacity["spareNow"]["cpuMillis"] <= 1000
        and not capacity["unmeasuredNodes"]
    )
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.node_resource_snapshots SET received_at=clock_timestamp()+interval '1 minute' WHERE node_id=%s",
            (a.e.node,),
        )
    assert control.capacity(p, a.e.project)["spareNow"] == {
        "cpuMillis": 0,
        "memoryBytes": 0,
    }
    o.poll_resources(a.node)
    with psycopg.connect(a.e.owner) as conn:
        revoke_channel(conn, a.node, expected_version=1)
    assert control.capacity(p, a.e.project)["unmeasuredNodes"] == [a.e.node]
    with pytest.raises(DomainError):
        control.capacity(Principal(a.e.tenant, "outsider"), a.e.project)


def test_real_mtls_transfer_restarts_after_lost_chunk_and_verifies_bytes(
    remote, storage, monkeypatch
):
    a = remote
    data = b"synthetic content" * 40000
    digest = export_node(a, data)
    transfer = NodeTransfer(a.e.db, a.client, storage)
    oid = str(uuid4())
    original = a.client.read_chunk
    calls = []

    def dropped(channel, request):
        calls.append(request["offset"])
        result = original(channel, request)
        if len(calls) == 2:
            raise OSError("synthetic response lost")
        return result

    monkeypatch.setattr(a.client, "read_chunk", dropped)
    with pytest.raises(OSError):
        transfer.fetch(a.node, a.e.project, oid, digest, len(data))
    assert storage.status(a.e.tenant, a.e.project, oid)["state"] == "uploading"
    monkeypatch.setattr(a.client, "read_chunk", original)
    result = NodeTransfer(a.e.db, a.client, storage).fetch(
        a.node, a.e.project, oid, digest, len(data)
    )
    assert (
        result["transferredBytes"] == len(data) and result["effectiveBitsPerSecond"] > 0
    )
    assert result["path"] == "node-to-control-plane"
    assert storage.status(a.e.tenant, a.e.project, oid)["state"] == "ready"
    assert (
        transfer.fetch(a.node, a.e.project, oid, digest, len(data))["transferredBytes"]
        == 0
    )


def test_transfer_revocation_before_part_commit_keeps_staging(
    remote, storage, monkeypatch
):
    a = remote
    data = b"synthetic"
    digest = export_node(a, data)
    original = a.client.read_chunk

    def revoke(channel, request):
        result = original(channel, request)
        with psycopg.connect(a.e.owner) as conn:
            revoke_channel(conn, a.node, expected_version=2)
        return result

    monkeypatch.setattr(a.client, "read_chunk", revoke)
    oid = str(uuid4())
    with pytest.raises(DomainError, match="NODE-0033"):
        NodeTransfer(a.e.db, a.client, storage).fetch(
            a.node, a.e.project, oid, digest, len(data)
        )
    assert storage.status(a.e.tenant, a.e.project, oid)["parts"] == []


def test_transfer_refuses_source_links_or_wrong_catalog_checksum(remote, storage):
    a = remote
    data = b"synthetic"
    digest = export_node(a, data)
    source = a.path / "exports" / digest
    outside = a.path / "outside"
    outside.write_bytes(data)
    outside.chmod(0o400)
    source.unlink()
    source.symlink_to(outside)
    with pytest.raises(DomainError):
        NodeTransfer(a.e.db, a.client, storage).fetch(
            a.node, a.e.project, str(uuid4()), digest, len(data)
        )
    assert outside.read_bytes() == data
