"""Fail-closed sequencing for the admitted S08-BE build transport boundary."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

import inv.build_adapter as adapter_module
from inv.build_adapter import (
    BuildExecutionAdapter,
    _AdmittedBuild,
    _lock_live_build_authority,
)
from inv.build_governance import BuildProviderObservation
from inv.errors import DomainError
from inv.policy import action_digest


TENANT = "123e4567-e89b-12d3-a456-426614174000"
EPOCH = "223e4567-e89b-12d3-a456-426614174000"
NOW = datetime(2026, 10, 1, 7, 0, tzinfo=timezone.utc)


class _ClockConnection:
    def execute(self, sql, _params=None):
        assert sql == "SELECT clock_timestamp() AS now"
        return self

    def fetchone(self):
        return {"now": NOW}


class _Database:
    recovery_epoch = EPOCH

    def __init__(self):
        self.active_transactions = 0
        self.transaction_count = 0

    @contextmanager
    def transaction(self, tenant_id):
        assert tenant_id == TENANT
        assert self.active_transactions == 0
        self.active_transactions += 1
        self.transaction_count += 1
        try:
            yield _ClockConnection()
        finally:
            self.active_transactions -= 1


class _Transport:
    def __init__(self, database, *, dispatch_error=None, cleanup_error=None):
        self.database = database
        self.dispatch_error = dispatch_error
        self.cleanup_error = cleanup_error
        self.calls = []
        self.admitted = None

    def observe(self, plan):
        assert self.database.active_transactions == 0
        self.calls.append("observe")
        return BuildProviderObservation(
            builder_instance_id="builder-1",
            builder_profile_id="rootless-v1",
            observation_digest="a" * 64,
            recovery_epoch=7,
            observed_at=NOW,
        )

    def dispatch(self, admitted):
        assert self.database.active_transactions == 0
        assert isinstance(admitted, _AdmittedBuild)
        assert len(admitted.binding_digest) == 64
        assert admitted.binding_digest != admitted.roof_binding_digest
        assert admitted.roof_binding_digest == "b" * 64
        assert admitted.builder_node_id == "node-1"
        assert admitted.binding_digest == action_digest(
            {
                "roofBindingDigest": admitted.roof_binding_digest,
                "runId": admitted.run_id,
                "builderNodeId": admitted.builder_node_id,
                "leaseId": admitted.plan["lease"]["leaseId"],
                "resourceId": admitted.plan["lease"]["resourceId"],
                "fencingToken": admitted.plan["lease"]["fencingToken"],
            }
        )
        self.calls.append("dispatch")
        self.admitted = admitted
        admitted.plan["transportMutation"] = True
        if self.dispatch_error:
            raise self.dispatch_error
        return {"receipt": "strict"}

    def cancel_and_quarantine(self, admitted, reason_code):
        assert self.database.active_transactions == 0
        assert admitted is self.admitted
        self.calls.append(("cancel", reason_code))
        if self.cleanup_error:
            raise self.cleanup_error


def _inputs():
    return (
        object(),
        {"tenantId": TENANT, "projectId": "project-1"},
        {
            "lease": {
                "leaseId": "lease-1",
                "resourceId": "resource-1",
                "fencingToken": f"{EPOCH}:7",
            }
        },
        {"decisionId": "decision-1"},
    )


def _patch_boundary(monkeypatch, *, authorize_error=None, finalize_error=None):
    calls = []
    monkeypatch.setattr(adapter_module, "validate_contract", lambda *_args: None)

    def authorize(_conn, _principal, request, plan, _decision, **_kwargs):
        calls.append(("authorize", deepcopy(request), deepcopy(plan)))
        if authorize_error:
            raise authorize_error
        return {"bindingDigest": "b" * 64}

    def live(_conn, request, plan, run_id, **_kwargs):
        calls.append(("live", deepcopy(request), deepcopy(plan), run_id))
        return "node-1"

    def finalize(_conn, _principal, request, plan, _decision, receipt, **_kwargs):
        calls.append(("finalize", deepcopy(request), deepcopy(plan), deepcopy(receipt)))
        if finalize_error:
            raise finalize_error
        return {"result": "succeeded"}

    monkeypatch.setattr(adapter_module, "authorize_build", authorize)
    monkeypatch.setattr(adapter_module, "_lock_live_build_authority", live)
    monkeypatch.setattr(adapter_module, "finalize_build", finalize)
    return calls


def _execute(adapter):
    principal, request, plan, decision = _inputs()
    return adapter.execute(
        principal,
        request,
        plan,
        decision,
        policy_version="s08-build-v1",
        run_id="run-1",
        evidence_id="evidence-1",
        actor_id="operator-1",
    )


def test_transport_receives_only_admitted_binding_between_two_short_transactions(monkeypatch):
    calls = _patch_boundary(monkeypatch)
    database = _Database()
    transport = _Transport(database)

    result = _execute(BuildExecutionAdapter(database, transport))

    assert database.transaction_count == 2
    assert transport.calls == ["observe", "dispatch", "observe"]
    assert [call[0] for call in calls] == ["authorize", "live", "live", "finalize"]
    assert "transportMutation" not in calls[-1][2]
    assert result.evidence == {"result": "succeeded"}


def test_failed_admission_has_zero_dispatch_side_effect(monkeypatch):
    _patch_boundary(
        monkeypatch,
        authorize_error=DomainError("AUTH-0061", "Tenant is contained", 423),
    )
    database = _Database()
    transport = _Transport(database)

    with pytest.raises(DomainError, match="AUTH-0061"):
        _execute(BuildExecutionAdapter(database, transport))

    assert database.transaction_count == 1
    assert transport.calls == ["observe"]


def test_failed_live_lease_admission_has_zero_dispatch_side_effect(monkeypatch):
    _patch_boundary(monkeypatch)

    def reject_live_lease(*_args, **_kwargs):
        raise DomainError("LEASE-0002", "Stale live lease", 409)

    monkeypatch.setattr(adapter_module, "_lock_live_build_authority", reject_live_lease)
    database = _Database()
    transport = _Transport(database)

    with pytest.raises(DomainError, match="LEASE-0002"):
        _execute(BuildExecutionAdapter(database, transport))

    assert database.transaction_count == 1
    assert transport.calls == ["observe"]


def test_final_authority_drift_cancels_and_quarantines(monkeypatch):
    _patch_boundary(
        monkeypatch,
        finalize_error=DomainError("LEASE-0002", "Fence changed", 409),
    )
    database = _Database()
    transport = _Transport(database)

    with pytest.raises(DomainError, match="LEASE-0002"):
        _execute(BuildExecutionAdapter(database, transport))

    assert transport.calls == [
        "observe",
        "dispatch",
        "observe",
        ("cancel", "LEASE-0002"),
    ]


def test_final_builder_node_drift_cancels_and_quarantines(monkeypatch):
    _patch_boundary(monkeypatch)
    nodes = iter(("node-1", "node-2"))
    monkeypatch.setattr(
        adapter_module,
        "_lock_live_build_authority",
        lambda *_args, **_kwargs: next(nodes),
    )
    database = _Database()
    transport = _Transport(database)

    with pytest.raises(DomainError, match="NODE-0033"):
        _execute(BuildExecutionAdapter(database, transport))

    assert transport.calls == [
        "observe",
        "dispatch",
        "observe",
        ("cancel", "NODE-0033"),
    ]


def test_ambiguous_dispatch_failure_also_cancels_and_quarantines(monkeypatch):
    _patch_boundary(monkeypatch)
    database = _Database()
    transport = _Transport(database, dispatch_error=RuntimeError("unknown side effect"))

    with pytest.raises(RuntimeError, match="unknown side effect"):
        _execute(BuildExecutionAdapter(database, transport))

    assert transport.calls == ["observe", "dispatch", ("cancel", "SYS-0001")]


def test_unverified_cancel_is_a_cleanup_failure(monkeypatch):
    _patch_boundary(monkeypatch)
    database = _Database()
    transport = _Transport(
        database,
        dispatch_error=RuntimeError("unknown side effect"),
        cleanup_error=RuntimeError("cancel unobserved"),
    )

    with pytest.raises(DomainError, match="VERIFY-0022"):
        _execute(BuildExecutionAdapter(database, transport))


class _LeaseConnection:
    def __init__(self, lease, node):
        self.lease = lease
        self.node = node

    def execute(self, sql, _params=None):
        if "FROM inv.resource_leases" in sql:
            return _One(self.lease)
        if "FROM inv.nodes" in sql:
            return _One(self.node)
        raise AssertionError(sql)


class _One:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.row


def _live_rows():
    lease = {
        "lease_id": "lease-1",
        "tenant_id": UUID(TENANT),
        "project_id": "project-1",
        "run_id": "run-1",
        "resource_id": "resource-1",
        "released_at": None,
        "expires_at": NOW + timedelta(seconds=10),
        "recovery_epoch": UUID(EPOCH),
        "fencing_token": 7,
    }
    node = {
        "status": "online",
        "recovery_epoch": UUID(EPOCH),
        "heartbeat_at": NOW - timedelta(seconds=1),
        "clock_skew_seconds": 0,
    }
    request = {"tenantId": TENANT, "projectId": "project-1"}
    plan = {
        "lease": {
            "leaseId": "lease-1",
            "resourceId": "resource-1",
            "fencingToken": f"{EPOCH}:7",
            "expiresAt": (NOW + timedelta(seconds=10)).isoformat(),
        }
    }
    return lease, node, request, plan


def _patch_locks(monkeypatch):
    monkeypatch.setattr(
        adapter_module,
        "lock_run",
        lambda _conn, run, project: {"run_id": run, "project_id": project},
    )
    monkeypatch.setattr(
        adapter_module,
        "lock_resources",
        lambda _conn, ids: {ids[0]: {"resource_id": ids[0], "node_id": "node-1"}},
    )


def test_live_build_authority_accepts_exact_fresh_online_lease(monkeypatch):
    _patch_locks(monkeypatch)
    lease, node, request, plan = _live_rows()
    assert (
        _lock_live_build_authority(
            _LeaseConnection(lease, node),
            request,
            plan,
            "run-1",
            database_recovery_epoch=EPOCH,
            now=NOW,
        )
        == "node-1"
    )


class _LockOrderConnection:
    def __init__(self, lease, node):
        self.lease = lease
        self.node = node
        self.statements = []

    def execute(self, sql, _params=None):
        normalized = " ".join(sql.split())
        self.statements.append(normalized)
        if "FROM inv.runs" in normalized:
            return _One({"run_id": "run-1", "project_id": "project-1"})
        if "FROM inv.resources WHERE resource_id=ANY" in normalized:
            return _One([{"resource_id": "resource-1", "node_id": "node-1"}])
        if "FROM inv.nodes WHERE node_id=%s FOR UPDATE" in normalized:
            return _One({"node_id": "node-1"})
        if "FROM inv.resources WHERE resource_id=%s FOR UPDATE" in normalized:
            return _One({"resource_id": "resource-1", "node_id": "node-1"})
        if "FROM inv.resource_leases" in normalized:
            return _One(self.lease)
        if "SELECT status,recovery_epoch,heartbeat_at,clock_skew_seconds" in normalized:
            return _One(self.node)
        raise AssertionError(normalized)


def test_live_build_authority_uses_run_node_resource_lease_lock_order():
    lease, node, request, plan = _live_rows()
    conn = _LockOrderConnection(lease, node)

    assert (
        _lock_live_build_authority(
            conn,
            request,
            plan,
            "run-1",
            database_recovery_epoch=EPOCH,
            now=NOW,
        )
        == "node-1"
    )
    assert "FROM inv.runs" in conn.statements[0]
    assert "resource_id=ANY" in conn.statements[1]
    assert "FROM inv.nodes" in conn.statements[2] and "FOR UPDATE" in conn.statements[2]
    assert "FROM inv.resources" in conn.statements[3] and "FOR UPDATE" in conn.statements[3]
    assert "FROM inv.resource_leases" in conn.statements[4] and "FOR UPDATE" in conn.statements[4]
    assert "SELECT status,recovery_epoch,heartbeat_at,clock_skew_seconds" in conn.statements[5]


@pytest.mark.parametrize(
    "mutate,code",
    [
        (
            lambda lease, _node, _plan: lease.__setitem__(
                "tenant_id", UUID("323e4567-e89b-12d3-a456-426614174000")
            ),
            "LEASE-0002",
        ),
        (
            lambda lease, _node, _plan: lease.__setitem__("project_id", "project-2"),
            "LEASE-0002",
        ),
        (lambda lease, _node, _plan: lease.__setitem__("released_at", NOW), "LEASE-0002"),
        (lambda lease, _node, _plan: lease.__setitem__("expires_at", NOW), "LEASE-0002"),
        (
            lambda lease, _node, _plan: lease.__setitem__(
                "recovery_epoch", UUID("423e4567-e89b-12d3-a456-426614174000")
            ),
            "LEASE-0002",
        ),
        (
            lambda _lease, _node, plan: plan["lease"].__setitem__("fencingToken", f"{EPOCH}:8"),
            "LEASE-0002",
        ),
        (
            lambda _lease, _node, plan: plan["lease"].__setitem__(
                "expiresAt", (NOW + timedelta(seconds=11)).isoformat()
            ),
            "LEASE-0002",
        ),
        (lambda _lease, node, _plan: node.__setitem__("status", "draining"), "NODE-0033"),
        (
            lambda _lease, node, _plan: node.__setitem__(
                "recovery_epoch", UUID("523e4567-e89b-12d3-a456-426614174000")
            ),
            "NODE-0033",
        ),
        (
            lambda _lease, node, _plan: node.__setitem__(
                "heartbeat_at", NOW - timedelta(seconds=16)
            ),
            "RES-0003",
        ),
        (
            lambda _lease, node, _plan: node.__setitem__(
                "heartbeat_at", NOW + timedelta(microseconds=1)
            ),
            "RES-0003",
        ),
        (lambda _lease, node, _plan: node.__setitem__("clock_skew_seconds", 6), "RES-0003"),
    ],
)
def test_live_build_authority_rejects_lease_fence_drain_and_observation_drift(
    monkeypatch, mutate, code
):
    _patch_locks(monkeypatch)
    lease, node, request, plan = _live_rows()
    mutate(lease, node, plan)

    with pytest.raises(DomainError, match=code):
        _lock_live_build_authority(
            _LeaseConnection(lease, node),
            request,
            plan,
            "run-1",
            database_recovery_epoch=EPOCH,
            now=NOW,
        )
