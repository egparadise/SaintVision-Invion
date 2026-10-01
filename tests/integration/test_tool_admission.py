from dataclasses import replace
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import json
import psycopg
from psycopg.types.json import Jsonb
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from inv.approvals import digest
from inv.contracts import validate_contract
from inv.db import Database
from inv.errors import DomainError
from inv.gpu import current_single_gpu_allocation
from inv.ids import new_id
from inv.leases import Allocation, lock_resources
from inv.node_execution import seal_permit
from inv.node_transport import NodeDelivery
from inv.policy import action_digest
from inv.sandbox import SandboxProfile, RuntimeCapabilities, REQUIRED_CAPABILITIES
from inv.tooling import ToolGateway, NodePrincipal, CurrentPolicy

# Reuse the approval transaction setup so this suite exercises both boundaries.
from test_approvals import approval, approved, dispatch, count

pytestmark = pytest.mark.postgres


@pytest.fixture
def gateway(approval):
    a = approval
    a.workload["command"] = ["/usr/bin/printf", "synthetic-private-value"]
    a.policy["actionDigest"] = action_digest(a.workload)
    a.row = approved(a)
    a.command = dispatch(a, a.row)
    a.memory = new_id("res")
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO inv.resources VALUES(%s,%s,%s,'memory',10,10)",
            (a.e.tenant, a.memory, a.e.node),
        )
    leases = a.e.leases.reserve(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        [Allocation(a.e.resource, 1), Allocation(a.memory, 1)],
        key="gateway-resources",
        ttl_seconds=60,
    )
    a.leases = leases
    a.proofs = {r["leaseId"]: r["fencingToken"] for r in leases}
    a.profile = SandboxProfile(
        "restricted:test:1",
        frozenset({a.workload["imageDigest"]}),
        frozenset({"/usr/bin/printf"}),
    )
    a.gateway = ToolGateway(a.e.db, a.profile)
    a.node = NodePrincipal(a.e.tenant, a.e.node)
    return a


@pytest.fixture
def gpu_gateway(approval):
    a = approval
    a.workload.update(command=["/usr/bin/printf", "gpu"])
    a.workload["resources"].update(gpuCount=1, minVramBytes=1024)
    a.policy["actionDigest"] = action_digest(a.workload)
    a.row = approved(a)
    a.command = dispatch(a, a.row)
    memory = new_id("res")
    gpu = new_id("res")
    profile = SandboxProfile(
        "restricted:gpu:1",
        frozenset({a.workload["imageDigest"]}),
        frozenset({"/usr/bin/printf"}),
    )
    device = {
        "resourceId": gpu,
        "deviceId": "GPU-synthetic-0",
        "vendor": "synthetic",
        "model": "single-device",
        "totalVramBytes": 24 * 1024**3,
        "computeCapability": "8.0",
        "driverVersion": "synthetic-driver:1",
        "runtimeVersion": "synthetic-runtime:1",
        "providerVersion": "synthetic-provider:1",
        "healthy": True,
        "exclusive": True,
        "runtimeCompatible": True,
        "deviceRequestDriver": "nvidia",
    }
    device["observationDigest"] = action_digest(device)
    snapshot = {
        "nonce": "a" * 64,
        "tenantId": a.e.tenant,
        "nodeId": a.e.node,
        "recoveryEpoch": a.e.epoch,
        "profileVersion": profile.version,
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "sampleMillis": 100,
        "cpuCapacityMillis": 1000,
        "cpuBusyMillis": 0,
        "memoryCapacityBytes": 1024**3,
        "memoryAvailableBytes": 1024**3,
        "osType": "linux",
        "agentVersion": "0.1.0",
        "gpuDevices": [device],
    }
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.nodes SET heartbeat_at=clock_timestamp(),clock_skew_seconds=0 WHERE node_id=%s",
            (a.e.node,),
        )
        conn.execute(
            "INSERT INTO inv.resources VALUES(%s,%s,%s,'memory',%s,%s),(%s,%s,%s,'gpu',1,1)",
            (
                a.e.tenant,
                memory,
                a.e.node,
                1024**3,
                1024**3,
                a.e.tenant,
                gpu,
                a.e.node,
            ),
        )
        conn.execute(
            """INSERT INTO inv.node_channels(
            tenant_id,node_id,recovery_epoch,version,endpoint,certificate_sha256,
            certificate_not_after,enabled
            ) VALUES(%s,%s,%s,1,'https://127.0.0.1:9443',%s,
            clock_timestamp()+interval '1 hour',true)""",
            (a.e.tenant, a.e.node, a.e.epoch, "b" * 64),
        )
        conn.execute(
            """INSERT INTO inv.node_resource_snapshots(
            tenant_id,node_id,recovery_epoch,channel_version,received_at,snapshot
            ) VALUES(%s,%s,%s,1,clock_timestamp(),%s)""",
            (a.e.tenant, a.e.node, a.e.epoch, Jsonb(snapshot)),
        )
    leases = a.e.leases.reserve(
        a.e.tenant,
        a.e.project,
        a.run["runId"],
        [Allocation(a.e.resource, 1), Allocation(memory, 1), Allocation(gpu, 1)],
        key="gpu-gateway-resources",
        ttl_seconds=60,
    )
    a.leases = leases
    a.proofs = {row["leaseId"]: row["fencingToken"] for row in leases}
    a.profile = profile
    a.gateway = ToolGateway(a.e.db, profile)
    a.node = NodePrincipal(a.e.tenant, a.e.node)
    a.gpu_resource = gpu
    a.memory_resource = memory
    return a


def inputs(a):
    now = datetime.now(timezone.utc)
    decision = {
        **a.policy,
        "decisionId": str(uuid4()),
        "expiresAt": (now + timedelta(seconds=20)).isoformat(),
    }
    policy = CurrentPolicy("roof:test:1", now, decision)
    runtime = RuntimeCapabilities(
        a.e.node,
        a.e.epoch,
        a.profile.version,
        now + timedelta(seconds=20),
        REQUIRED_CAPABILITIES,
    )
    return {"policy": policy, "runtime": runtime}


def claim(a, **overrides):
    options = inputs(a)
    options.update(overrides)
    return a.gateway.claim(a.node, a.command, a.workload, a.proofs, **options)


def test_valid_approval_allocation_and_runtime_produce_one_bound_plan(gateway):
    a = gateway
    result = claim(a)
    assert result.may_start
    validate_contract("ExecutionClaim", result.claim)
    validate_contract("SandboxLaunchSpec", result.launch)
    assert result.claim["planDigest"] == digest(result.launch)
    assert result.launch["argv"] == a.workload["command"]
    assert result.launch["network"] == "none" and result.launch["hostAccess"] is False
    assert count(a, "tool_claims") == 1
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "scheduled"
    with a.e.db.transaction(a.e.tenant) as conn:
        persisted = conn.execute(
            "SELECT payload FROM inv.outbox WHERE event_type='inv.execution.claimed'"
        ).fetchone()["payload"]
        rows = conn.execute("SELECT to_jsonb(c) AS row FROM inv.tool_claims c").fetchall()
    assert persisted == result.claim
    assert "synthetic-private-value" not in json.dumps(rows, default=str)
    assert "synthetic-private-value" not in json.dumps(persisted)


def test_measured_single_gpu_allocation_is_bound_into_the_signed_plan(gpu_gateway):
    a = gpu_gateway
    result = claim(a)
    allocation = result.launch["gpuAllocation"]
    assert allocation["resourceId"] == a.gpu_resource
    assert allocation["deviceId"] == "GPU-synthetic-0"
    assert allocation["vramBytes"] == 24 * 1024**3
    assert allocation["exclusive"] is True
    assert result.claim["planDigest"] == digest(result.launch)


def test_gpu_allocation_never_substitutes_a_second_resources_device(gpu_gateway):
    a = gpu_gateway
    other_resource = new_id("res")
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO inv.resources VALUES(%s,%s,%s,'gpu',1,1)",
            (a.e.tenant, other_resource, a.e.node),
        )
        row = conn.execute(
            "SELECT snapshot FROM inv.node_resource_snapshots WHERE node_id=%s",
            (a.e.node,),
        ).fetchone()
        snapshot = row[0]
        leased_device = snapshot["gpuDevices"][0]
        other_device = {
            **leased_device,
            "resourceId": other_resource,
            "deviceId": "GPU-synthetic-other",
        }
        other_device["observationDigest"] = action_digest(
            {key: value for key, value in other_device.items() if key != "observationDigest"}
        )
        snapshot["gpuDevices"] = [other_device, leased_device]
        conn.execute(
            "UPDATE inv.node_resource_snapshots SET snapshot=%s WHERE node_id=%s",
            (Jsonb(snapshot), a.e.node),
        )

    with a.e.db.transaction(a.e.tenant) as conn:
        allocations = conn.execute(
            "SELECT * FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL ORDER BY lease_id",
            (a.run["runId"],),
        ).fetchall()
        resources = lock_resources(
            conn,
            [row["resource_id"] for row in allocations] + [other_resource],
        )
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        allocation = current_single_gpu_allocation(
            conn,
            a.e.db,
            node_id=a.e.node,
            workload=a.workload,
            allocations=allocations,
            resources=resources,
            profile_version=a.profile.version,
            now=now,
        )

    assert allocation["resourceId"] == a.gpu_resource
    assert allocation["deviceId"] == "GPU-synthetic-0"


def test_gpu_allocation_rejects_two_devices_for_one_leased_resource(gpu_gateway, monkeypatch):
    import inv.gpu as gpu_module

    a = gpu_gateway
    with a.e.db.transaction(a.e.tenant) as conn:
        allocations = conn.execute(
            "SELECT * FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL ORDER BY lease_id",
            (a.run["runId"],),
        ).fetchall()
        resources = lock_resources(
            conn,
            [row["resource_id"] for row in allocations],
        )
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        snapshot = conn.execute(
            "SELECT snapshot FROM inv.node_resource_snapshots WHERE node_id=%s",
            (a.e.node,),
        ).fetchone()["snapshot"]
        first = snapshot["gpuDevices"][0]
        second = {**first, "deviceId": "GPU-synthetic-ambiguous"}
        second["observationDigest"] = action_digest(
            {key: value for key, value in second.items() if key != "observationDigest"}
        )
        monkeypatch.setattr(
            gpu_module,
            "verified_gpu_devices",
            lambda *_args: {first["deviceId"]: first, second["deviceId"]: second},
        )

        with pytest.raises(DomainError, match="RES-0008"):
            current_single_gpu_allocation(
                conn,
                a.e.db,
                node_id=a.e.node,
                workload=a.workload,
                allocations=allocations,
                resources=resources,
                profile_version=a.profile.version,
                now=now,
            )


def test_uncertain_gpu_cleanup_quarantines_node_and_retains_all_leases(gpu_gateway):
    a = gpu_gateway
    result = claim(a)
    kind_by_resource = {
        a.e.resource: "cpu",
        a.memory_resource: "memory",
        a.gpu_resource: "gpu",
    }
    allocations = [
        {
            "nodeId": a.e.node,
            "kind": kind_by_resource[row["resourceId"]],
            "lease": row,
        }
        for row in a.leases
    ]
    permit = seal_permit(result, allocations, Ed25519PrivateKey.generate())

    class UncertainClient:
        @staticmethod
        def exchange(*_args, **_kwargs):
            raise DomainError("NODE-0030", "Synthetic lost cleanup receipt", 503)

    with pytest.raises(DomainError, match="NODE-0030"):
        NodeDelivery(a.e.db, UncertainClient()).deliver(a.node, permit)

    with a.e.db.transaction(a.e.tenant) as conn:
        assert (
            conn.execute("SELECT status FROM inv.nodes WHERE node_id=%s", (a.e.node,)).fetchone()[
                "status"
            ]
            == "quarantined"
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                (a.run["runId"],),
            ).fetchone()["n"]
            == 3
        )
        payload = conn.execute(
            "SELECT payload FROM inv.outbox WHERE event_type='inv.gpu.cleanup_quarantined'"
        ).fetchone()["payload"]
    assert payload == {
        "resourceId": a.gpu_resource,
        "leaseId": result.launch["gpuAllocation"]["leaseId"],
        "observationDigest": result.launch["gpuAllocation"]["observationDigest"],
        "reasonCode": "NODE-0030",
    }


@pytest.mark.parametrize("damage", ["stale", "digest", "missing"])
def test_stale_unbound_or_missing_gpu_provider_never_creates_a_claim(gpu_gateway, damage):
    a = gpu_gateway
    with psycopg.connect(a.e.owner) as conn:
        if damage == "stale":
            conn.execute(
                "UPDATE inv.node_resource_snapshots SET received_at=clock_timestamp()-interval '1 minute' WHERE node_id=%s",
                (a.e.node,),
            )
        elif damage == "missing":
            conn.execute(
                "DELETE FROM inv.node_resource_snapshots WHERE node_id=%s",
                (a.e.node,),
            )
        else:
            row = conn.execute(
                "SELECT snapshot FROM inv.node_resource_snapshots WHERE node_id=%s",
                (a.e.node,),
            ).fetchone()
            snapshot = row[0]
            snapshot["gpuDevices"][0]["observationDigest"] = "c" * 64
            conn.execute(
                "UPDATE inv.node_resource_snapshots SET snapshot=%s WHERE node_id=%s",
                (Jsonb(snapshot), a.e.node),
            )
    with pytest.raises(DomainError, match="RES-000[38]"):
        claim(a)
    assert count(a, "tool_claims") == 0


def test_eight_concurrent_deliveries_authorize_start_only_once(gateway):
    a = gateway
    barrier = Barrier(8)

    def call(_):
        barrier.wait(timeout=10)
        return claim(a)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(call, range(8)))
    assert sum(r.may_start for r in results) == 1
    assert len({r.claim["claimId"] for r in results}) == 1
    assert all(r.launch is None for r in results if not r.may_start)
    assert count(a, "tool_claims") == 1


def test_lost_first_response_restart_cancel_and_revocation_never_regrant(gateway):
    a = gateway
    first = claim(a)  # Simulate losing this response before any OS launch.
    a.gateway = ToolGateway(Database(a.e.runtime, recovery_epoch=a.e.epoch), a.profile)
    current = a.e.runs.get(a.e.tenant, a.run["runId"])
    a.e.runs.transition(
        a.e.tenant, a.run["runId"], "cancelled", expected_version=current["version"]
    )
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s",
            (a.e.tenant,),
        )
    replay = claim(a, policy=None, runtime=None)
    assert not replay.may_start and replay.launch is None and replay.claim == first.claim
    a.workload["command"][1] = "different"
    with pytest.raises(DomainError, match="IDEM-0001"):
        claim(a)


@pytest.mark.parametrize(
    "field,value",
    [
        ("commandId", str(uuid4())),
        ("actionDigest", "b" * 64),
        ("policyVersion", "changed"),
        ("recoveryEpoch", str(uuid4())),
        ("approvalId", new_id("apr")),
    ],
)
def test_forged_outbox_content_has_no_execution_effect(gateway, field, value):
    a = gateway
    a.command[field] = value
    with pytest.raises(DomainError):
        claim(a)
    assert count(a, "tool_claims") == 0


@pytest.mark.parametrize(
    "change",
    [
        "tenant",
        "node",
        "missing-proof",
        "wrong-proof",
        "short-cpu",
        "short-memory",
        "released",
        "expired",
    ],
)
def test_execution_requires_exact_owned_live_and_sufficient_allocations(gateway, change):
    a = gateway
    if change == "tenant":
        a.node = NodePrincipal(a.e.other, a.e.node)
    elif change == "node":
        a.node = NodePrincipal(a.e.tenant, new_id("nod"))
    elif change == "missing-proof":
        a.proofs.pop(next(iter(a.proofs)))
    elif change == "wrong-proof":
        a.proofs[next(iter(a.proofs))] = a.e.epoch + ":999999"
    elif change == "released":
        lease = a.leases[0]
        a.e.leases.release(
            a.e.tenant,
            lease["leaseId"],
            lease["fencingToken"],
            authenticated_node_id=a.e.node,
            stop_receipt=str(uuid4()),
        )
    else:
        # Controlled fault injection in the uniquely named synthetic DB only.
        with psycopg.connect(a.e.owner) as conn:
            if change == "expired":
                conn.execute(
                    "UPDATE inv.resource_leases SET granted_at=clock_timestamp()-interval '2 minutes',expires_at=clock_timestamp()-interval '1 minute' WHERE tenant_id=%s",
                    (a.e.tenant,),
                )
            else:
                resource = a.e.resource if change == "short-cpu" else a.memory
                # Release one required kind in this isolated DB; the exact remaining
                # live proof set must still be rejected as insufficient for the workload.
                lease = next(r for r in a.leases if r["resourceId"] == resource)
                conn.execute(
                    "UPDATE inv.resource_leases SET released_at=clock_timestamp(),stop_receipt=%s WHERE lease_id=%s",
                    (uuid4(), lease["leaseId"]),
                )
                a.proofs.pop(lease["leaseId"])
    with pytest.raises(DomainError):
        claim(a)
    assert count(a, "tool_claims") == 0


@pytest.mark.parametrize(
    "fault", ["offline", "draining", "heartbeat", "future-heartbeat", "skew", "epoch"]
)
def test_stale_node_cannot_receive_launch_permission(gateway, fault):
    a = gateway
    updates = {
        "offline": "status='offline'",
        "draining": "status='draining'",
        "heartbeat": "heartbeat_at=clock_timestamp()-interval '1 minute'",
        "future-heartbeat": "heartbeat_at=clock_timestamp()+interval '1 minute'",
        "skew": "clock_skew_seconds=NULL",
        "epoch": "recovery_epoch=NULL",
    }
    with psycopg.connect(a.e.owner) as conn:
        conn.execute("UPDATE inv.nodes SET " + updates[fault] + " WHERE node_id=%s", (a.e.node,))
    with pytest.raises(DomainError, match="RES-0006"):
        claim(a)
    assert count(a, "tool_claims") == 0


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "deny",
        "L3",
        "one-person-L2",
        "scope",
        "version",
        "stale",
        "future",
        "long-ttl",
        "claimed-votes",
    ],
)
def test_current_policy_is_required_and_cannot_weaken_approval(gateway, fault):
    a = gateway
    current = inputs(a)["policy"]
    now = datetime.now(timezone.utc)
    if fault == "missing":
        current = None
    elif fault == "version":
        current = replace(current, version="roof:changed")
    elif fault == "stale":
        current = replace(current, evaluated_at=now - timedelta(seconds=6))
    elif fault == "future":
        current = replace(current, evaluated_at=now + timedelta(seconds=3))
    else:
        changes = {
            "deny": {"effect": "deny"},
            "L3": {"riskLevel": "L3"},
            "one-person-L2": {"requiredApprovals": 1},
            "scope": {"subjectId": "outsider"},
            "long-ttl": {"expiresAt": (now + timedelta(minutes=5)).isoformat()},
            "claimed-votes": {"approvedBy": ["alice", "bob"]},
        }
        current = replace(current, decision={**current.decision, **changes[fault]})
    with pytest.raises(DomainError):
        claim(a, policy=current)
    assert count(a, "tool_claims") == 0


@pytest.mark.parametrize("fault", ["missing", "features", "node", "epoch", "version", "expired"])
def test_unverified_or_incomplete_runtime_is_denied(gateway, fault):
    a = gateway
    runtime = inputs(a)["runtime"]
    replacements = {
        "features": {"features": REQUIRED_CAPABILITIES - {"network_deny"}},
        "node": {"node_id": new_id("nod")},
        "epoch": {"recovery_epoch": str(uuid4())},
        "version": {"profile_version": "changed"},
        "expired": {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)},
    }
    runtime = None if fault == "missing" else replace(runtime, **replacements[fault])
    with pytest.raises(DomainError, match="SANDBOX-0001"):
        claim(a, runtime=runtime)
    assert count(a, "tool_claims") == 0


@pytest.mark.parametrize("actor", ["requester", "alice"])
def test_authorization_revoked_after_dispatch_stops_first_claim(gateway, actor):
    a = gateway
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
            (a.e.tenant, actor),
        )
    with pytest.raises(DomainError, match="AUTH-0030"):
        claim(a)
    assert count(a, "tool_claims") == 0


def test_audit_publish_failure_rolls_back_claim_so_retry_can_be_first(gateway, monkeypatch):
    import inv.tooling as module

    a = gateway
    original = module.event
    before = count(a, "outbox")

    def fail(*args):
        raise RuntimeError("injected claim outbox failure")

    monkeypatch.setattr(module, "event", fail)
    with pytest.raises(RuntimeError, match="injected"):
        claim(a)
    assert count(a, "tool_claims") == 0 and count(a, "outbox") == before
    monkeypatch.setattr(module, "event", original)
    assert claim(a).may_start
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with a.e.db.transaction(a.e.tenant) as conn:
            conn.execute("DELETE FROM inv.tool_claims")
    with a.e.db.transaction(a.e.other) as conn:
        assert not conn.execute("SELECT 1 FROM inv.tool_claims").fetchone()


@pytest.mark.parametrize("fault", ["cancel", "restore", "changed-content", "profile-revoked"])
def test_changed_execution_context_is_rejected_before_first_claim(gateway, fault):
    a = gateway
    if fault == "cancel":
        current = a.e.runs.get(a.e.tenant, a.run["runId"])
        a.e.runs.transition(
            a.e.tenant, a.run["runId"], "cancelled", expected_version=current["version"]
        )
    elif fault == "restore":
        epoch = str(uuid4())
        with psycopg.connect(a.e.owner) as conn:
            conn.execute("UPDATE inv.control_epoch SET epoch=%s", (epoch,))
        a.gateway = ToolGateway(Database(a.e.runtime, recovery_epoch=epoch), a.profile)
    elif fault == "changed-content":
        a.workload["command"][1] = "different"
    else:
        a.gateway = ToolGateway(
            a.e.db, replace(a.profile, images=frozenset({"sha256:" + "b" * 64}))
        )
    with pytest.raises(DomainError):
        claim(a)
    with psycopg.connect(a.e.owner) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM inv.tool_claims WHERE tenant_id=%s", (a.e.tenant,)
            ).fetchone()[0]
            == 0
        )
