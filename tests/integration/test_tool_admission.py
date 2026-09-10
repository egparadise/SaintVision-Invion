from dataclasses import replace
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import json
import psycopg
import pytest
from inv.approvals import digest
from inv.contracts import validate_contract
from inv.db import Database
from inv.errors import DomainError
from inv.ids import new_id
from inv.leases import Allocation
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
        rows = conn.execute(
            "SELECT to_jsonb(c) AS row FROM inv.tool_claims c"
        ).fetchall()
    assert persisted == result.claim
    assert "synthetic-private-value" not in json.dumps(rows, default=str)
    assert "synthetic-private-value" not in json.dumps(persisted)


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
    assert (
        not replay.may_start and replay.launch is None and replay.claim == first.claim
    )
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
def test_execution_requires_exact_owned_live_and_sufficient_allocations(
    gateway, change
):
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
        conn.execute(
            "UPDATE inv.nodes SET " + updates[fault] + " WHERE node_id=%s", (a.e.node,)
        )
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


@pytest.mark.parametrize(
    "fault", ["missing", "features", "node", "epoch", "version", "expired"]
)
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


def test_audit_publish_failure_rolls_back_claim_so_retry_can_be_first(
    gateway, monkeypatch
):
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


@pytest.mark.parametrize(
    "fault", ["cancel", "restore", "changed-content", "profile-revoked"]
)
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
