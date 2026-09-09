from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
import psycopg
from psycopg.types.json import Jsonb
import pytest
from inv.approvals import Principal
from inv.errors import DomainError
from inv.ids import new_id
from inv.leases import Allocation
from inv.node_channels import revoke_channel
from inv.observation import NodeObservation
from inv.placement import PlacementStore
from inv.scheduler import Request
from test_approvals import approval
from test_node_runtime import node_runtime
from test_node_delivery import remote
from test_postgres import planned

pytestmark = pytest.mark.postgres


@pytest.fixture
def placement(remote):
    a = remote
    NodeObservation(a.e.db, a.client).poll_resources(a.node)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)",
            (a.e.tenant, a.e.project, a.e.node),
        )
        conn.execute(
            "INSERT INTO inv.project_resource_limits(tenant_id,project_id,cpu_millis,memory_bytes) VALUES(%s,%s,1000,268435456)",
            (a.e.tenant, a.e.project),
        )
        # Fixed synthetic counter values isolate reservation arithmetic from host
        # load. The observation transport/certificate was actually exercised above.
        row = conn.execute(
            "SELECT snapshot FROM inv.node_resource_snapshots WHERE tenant_id=%s AND node_id=%s",
            (a.e.tenant, a.e.node),
        ).fetchone()
        snapshot = {
            **row[0],
            "cpuCapacityMillis": 1000,
            "cpuBusyMillis": 0,
            "memoryCapacityBytes": 268435456,
            "memoryAvailableBytes": 268435456,
        }
        conn.execute(
            "UPDATE inv.node_resource_snapshots SET snapshot=%s WHERE tenant_id=%s AND node_id=%s",
            (Jsonb(snapshot), a.e.tenant, a.e.node),
        )
    a.placement = PlacementStore(a.e.db)
    a.request = Request(500, 67108864, max_host_load=Decimal(1))
    return a


def reserve(a, run=None, *, key="place", request=None, node_ids=None):
    return a.placement.reserve(
        a.people["requester"],
        a.e.project,
        (run or a.run)["runId"],
        request or a.request,
        key=key,
        policy_version="roof:test:1",
        node_ids=node_ids,
    )


def test_observation_to_explain_and_fenced_reservation_is_idempotent(placement):
    a = placement
    first = reserve(a)
    assert first == reserve(a)
    assert (
        first["placement"]["nodeId"] == a.e.node
        and first["placement"]["weightsVersion"] == "1.0.0"
    )
    assert sorted(l["amount"] for l in first["leases"]) == [500, 67108864]
    assert all(l["fencingToken"].startswith(a.e.epoch + ":") for l in first["leases"])
    with pytest.raises(DomainError, match="IDEM-0001"):
        reserve(a, request=replace(a.request, cpu_millis=501))


@pytest.mark.parametrize(
    "invalid", ["future", "stale", "missing", "revoked", "membership"]
)
def test_invalid_current_observation_never_reserves(placement, invalid):
    a = placement
    with psycopg.connect(a.e.owner) as conn:
        if invalid == "future":
            conn.execute(
                "UPDATE inv.node_resource_snapshots SET received_at=clock_timestamp()+interval '1 minute' WHERE tenant_id=%s",
                (a.e.tenant,),
            )
        elif invalid == "stale":
            conn.execute(
                "UPDATE inv.node_resource_snapshots SET received_at=clock_timestamp()-interval '1 minute' WHERE tenant_id=%s",
                (a.e.tenant,),
            )
        elif invalid == "missing":
            conn.execute(
                "DELETE FROM inv.node_resource_snapshots WHERE tenant_id=%s",
                (a.e.tenant,),
            )
        elif invalid == "revoked":
            revoke_channel(conn, a.node, expected_version=1)
        else:
            conn.execute(
                "UPDATE inv.project_nodes SET enabled=false WHERE tenant_id=%s",
                (a.e.tenant,),
            )
    with pytest.raises(DomainError):
        reserve(a)
    with a.e.db.transaction(a.e.tenant) as conn:
        assert not conn.execute("SELECT 1 FROM inv.resource_leases").fetchall()


def test_pool_filter_cannot_expand_scope_and_unmeasured_workloads_fail_closed(
    placement,
):
    a = placement
    with pytest.raises(DomainError, match="AUTH-0030"):
        reserve(a, node_ids=[new_id("nod")])
    for request in [
        replace(a.request, gpu_count=1),
        replace(a.request, required_bytes=1),
    ]:
        with pytest.raises(DomainError, match="RES-0008"):
            reserve(a, request=request)
    with pytest.raises(DomainError, match="AUTH-0030"):
        a.placement.reserve(
            Principal(a.e.tenant, "outsider"),
            a.e.project,
            a.run["runId"],
            a.request,
            key="unauthorized",
            policy_version="roof:test:1",
        )


def test_concurrent_placement_and_direct_lease_share_project_ceiling(placement):
    a = placement
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.project_resource_limits SET cpu_millis=500,version=2 WHERE tenant_id=%s",
            (a.e.tenant,),
        )
    runs = [planned(a.e) for _ in range(8)]

    def take(index):
        try:
            if index % 2:
                a.e.leases.reserve(
                    a.e.tenant,
                    a.e.project,
                    runs[index]["runId"],
                    [Allocation(a.e.resource, 500)],
                    key="direct:" + str(index),
                )
            else:
                reserve(a, runs[index], key="placement:" + str(index))
            return True
        except DomainError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(take, range(8))) == 1
    with a.e.db.transaction(a.e.tenant) as conn:
        assert (
            conn.execute(
                "SELECT sum(amount) AS used FROM inv.resource_leases WHERE resource_id=%s AND released_at IS NULL",
                (a.e.resource,),
            ).fetchone()["used"]
            == 500
        )


def test_explain_event_failure_rolls_back_all_resources(placement, monkeypatch):
    import inv.placement as module

    a = placement

    def crash(*args):
        raise RuntimeError("synthetic explain publication failure")

    monkeypatch.setattr(module, "event", crash)
    with pytest.raises(RuntimeError):
        reserve(a)
    with a.e.db.transaction(a.e.tenant) as conn:
        assert not conn.execute("SELECT 1 FROM inv.resource_leases").fetchall()
        assert not conn.execute(
            "SELECT 1 FROM inv.idempotency WHERE operation='placement.reserve'"
        ).fetchall()


def test_ceiling_must_be_provisioned_before_placement(remote):
    a = remote
    a.placement = PlacementStore(a.e.db)
    a.request = Request(500, 67108864)
    with pytest.raises(DomainError, match="RES-0008"):
        reserve(a)


def test_ceiling_cannot_be_deleted_or_lowered_below_existing_reservations(placement):
    a = placement
    reserve(a)
    for statement in [
        "DELETE FROM inv.project_resource_limits WHERE tenant_id=%s",
        "UPDATE inv.project_resource_limits SET cpu_millis=499,version=version+1 WHERE tenant_id=%s",
        "UPDATE inv.project_resource_limits SET cpu_millis=1001 WHERE tenant_id=%s",
    ]:
        with pytest.raises(psycopg.errors.CheckViolation):
            with psycopg.connect(a.e.owner) as conn:
                conn.execute(statement, (a.e.tenant,))


def test_membership_lock_permission_cannot_edit_authorized_nodes(placement):
    a = placement
    reserve(a)
    for statement in [
        "UPDATE inv.project_nodes SET enabled=false",
        "DELETE FROM inv.project_nodes",
    ]:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with a.e.db.transaction(a.e.tenant) as conn:
                conn.execute(statement)
    with pytest.raises(psycopg.errors.CheckViolation):
        with a.e.db.transaction(a.e.tenant) as conn:
            conn.execute("UPDATE inv.project_nodes SET lock_sentinel=false")
