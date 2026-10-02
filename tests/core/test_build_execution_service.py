"""Fail-closed behaviour of the S08-BE product caller (card 214).

Every test here is about a refusal, because the only thing this caller may do when any
input disagrees is refuse without releasing the lease.  The positive case exists once,
as the control: without it a refusal test proves nothing about the refusal.

The two node-agent receipts are supplied as plain dictionaries with the field names the
card 211 contract decision fixed.  Their strict schemas belong to that contract PR, so
these tests assert the authority comparison -- node identity, epoch agreement, daemon
identity, required cleanup observations -- and the atomicity of the commit.
"""

from contextlib import contextmanager
from copy import deepcopy

import pytest

from inv.build_execution import (
    BuildExecutionResult,
    BuildExecutionService,
    PRODUCT_ENABLE_SETTING,
)
from inv.errors import DomainError

TENANT = "123e4567-e89b-12d3-a456-426614174000"
PROJECT = "prj_c214"
EPOCH = "223e4567-e89b-12d3-a456-426614174000"
RUN = "run_c214"
NODE = "nod_c214"
RESOURCE = "res_c214"
LEASE = "lse_c214"
SESSION = "7f4a1c62-9d1e-4a3b-8c55-0f21aa9b4e10"
EVIDENCE_ID = "evd_c214"
ENABLED = {PRODUCT_ENABLE_SETTING: "1"}

DAEMON = {"pid": 42, "processUid": 1000, "processStartTicks": 28815, "comm": "buildkitd"}


def health(**overrides):
    document = {
        "schemaVersion": "build-provider-health-receipt:1",
        "writerKind": "node-agent",
        "nodeId": NODE,
        "builderInstanceId": "builder-c214",
        "builderProfileId": "rootless-product-v1",
        "recoveryEpoch": EPOCH,
        "observedAt": "2026-10-02T08:00:00Z",
        "runtimeIdentity": "sha256:" + "a" * 64,
        "daemonIdentity": dict(DAEMON),
        "isolation": {
            "userNamespace": True,
            "seccompMode": "filter",
            "lsm": "apparmor",
            "noNewPrivileges": True,
            "cgroupMode": "v2",
        },
    }
    document.update(overrides)
    return document


def cleanup(**overrides):
    document = {
        "schemaVersion": "build-physical-cleanup-receipt:1",
        "writerKind": "node-agent",
        "buildSessionId": SESSION,
        "nodeId": NODE,
        "resourceId": RESOURCE,
        "leaseId": LEASE,
        "recoveryEpoch": EPOCH,
        "daemonIdentity": dict(DAEMON),
        "stopResult": "stopped",
        "partialExportDisposition": "purged",
        "cacheDisposition": "retained",
        "builderClaimReleased": True,
        "cgroupRemoved": True,
        "verifiedAt": "2026-10-02T08:00:05Z",
    }
    document.update(overrides)
    return document


class _Connection:
    """Answers only the statements this service issues, and records the writes."""

    def __init__(self, database):
        self.db = database
        self._result = None

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        if "FROM inv.resources" in text:
            self._result = {"node_id": self.db.resource_node_id}
        elif "FROM inv.resource_leases" in text and "FOR UPDATE" in text:
            self._result = deepcopy(self.db.lease_row)
        elif text.startswith("INSERT INTO inv.evidence"):
            self.db.writes.append(("evidence", params))
            self._result = None
        elif text.startswith("UPDATE inv.resource_leases"):
            self.db.writes.append(("release", params))
            self._result = {"lease_id": LEASE} if self.db.release_succeeds else None
        elif text.startswith("INSERT INTO inv.outbox"):
            self.db.writes.append(("outbox", params))
            self._result = None
        else:  # pragma: no cover - a statement this service must not issue
            raise AssertionError(f"unexpected statement: {text}")
        return self

    def fetchone(self):
        return self._result


class _Database:
    def __init__(self, *, lease_epoch=EPOCH, resource_node_id=NODE, release_succeeds=True):
        self.recovery_epoch = EPOCH
        self.resource_node_id = resource_node_id
        self.release_succeeds = release_succeeds
        self.writes = []
        self.committed = []
        self.rolled_back = []
        self.lease_row = {
            "tenant_id": TENANT,
            "project_id": PROJECT,
            "resource_id": RESOURCE,
            "recovery_epoch": lease_epoch,
            "released_at": None,
        }

    @contextmanager
    def transaction(self, tenant_id):
        assert tenant_id == TENANT
        start = len(self.writes)
        try:
            yield _Connection(self)
        except BaseException:
            # A real transaction discards the statements; the fake records that it would.
            self.rolled_back.append(self.writes[start:])
            del self.writes[start:]
            raise
        else:
            self.committed.append(self.writes[start:])


class _Adapter:
    def __init__(self, *, receipt=None, error=None):
        self.receipt = receipt if receipt is not None else {"buildSessionId": SESSION}
        self.error = error
        self.calls = 0

    def execute(self, principal, request, plan, decision, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        from inv.build_adapter import BuildAdapterResult

        return BuildAdapterResult(
            receipt=dict(self.receipt),
            evidence={"evidenceId": EVIDENCE_ID, "kind": "BuildReceipt"},
        )


class _Boundary:
    def __init__(self, *, health_receipt=None, cleanup_receipt=None, daemon_after=None):
        self.health_receipt = health_receipt if health_receipt is not None else health()
        self.cleanup_receipt = cleanup_receipt if cleanup_receipt is not None else cleanup()
        self.daemon_after = daemon_after if daemon_after is not None else dict(DAEMON)
        self.quarantined_nodes = []
        self.cancelled_sessions = []

    def collect_product_health(self):
        return deepcopy(self.health_receipt)

    def daemon_identity(self):
        return dict(self.daemon_after)

    def collect_cleanup_receipt(self, build_session_id):
        assert build_session_id == SESSION
        return deepcopy(self.cleanup_receipt)

    def cancel_and_quarantine_session(self, build_session_id, reason_code):
        self.cancelled_sessions.append((build_session_id, reason_code))

    def quarantine_node(self, node_id, reason_code):
        self.quarantined_nodes.append((node_id, reason_code))


def request_plan_decision(lease_epoch=EPOCH):
    request = {"tenantId": TENANT, "projectId": PROJECT, "workspaceId": "wsp_c214"}
    plan = {
        "buildSessionId": SESSION,
        "lease": {
            "leaseId": LEASE,
            "resourceId": RESOURCE,
            "fencingToken": "7:1",
            "recoveryEpoch": lease_epoch,
        }
    }
    decision = {"decisionId": "dec_c214"}
    return request, plan, decision


def build(**kwargs):
    database = kwargs.pop("database", None) or _Database()
    adapter = kwargs.pop("adapter", None) or _Adapter()
    boundary = kwargs.pop("boundary", None) or _Boundary()
    environment = kwargs.pop("environment", ENABLED)
    service = BuildExecutionService(database, adapter, boundary, environment=environment)
    return service, database, adapter, boundary


def run(service, *, lease_epoch=EPOCH):
    request, plan, decision = request_plan_decision(lease_epoch)
    return service.execute(
        object(),
        request,
        plan,
        decision,
        policy_version="v1",
        run_id=RUN,
        evidence_id=EVIDENCE_ID,
        actor_id="act_c214",
    )


# --- the control -------------------------------------------------------------------------


def test_an_agreeing_dispatch_persists_releases_and_records_in_one_transaction():
    service, database, adapter, boundary = build()
    result = run(service)
    assert isinstance(result, BuildExecutionResult)
    assert result.lease_released is True and result.cleanup_verified is True
    assert adapter.calls == 1
    # One transaction carries all three writes, in this order, and nothing rolled back.
    committed = [batch for batch in database.committed if batch]
    assert [kind for kind, _ in committed[-1]] == ["evidence", "release", "outbox"]
    assert database.rolled_back == []
    assert boundary.quarantined_nodes == []


# --- the product enable ------------------------------------------------------------------


@pytest.mark.parametrize("environment", [{}, {PRODUCT_ENABLE_SETTING: "0"},
                                         {PRODUCT_ENABLE_SETTING: "true"},
                                         {PRODUCT_ENABLE_SETTING: " 1"}])
def test_product_dispatch_is_off_unless_the_value_is_exactly_one(environment):
    service, _database, adapter, _boundary = build(environment=environment)
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "RES-0006" and refused.value.status == 503
    assert adapter.calls == 0


# --- health authority --------------------------------------------------------------------


def test_a_health_receipt_about_another_node_is_refused():
    service, _database, adapter, _boundary = build(
        boundary=_Boundary(health_receipt=health(nodeId="nod_somewhere_else"))
    )
    with pytest.raises(DomainError) as refused:
        run(service)
    assert "did not lease" in str(refused.value)
    assert adapter.calls == 0


@pytest.mark.parametrize(
    "receipt_epoch,lease_epoch",
    [
        ("333e4567-e89b-12d3-a456-426614174000", EPOCH),   # builder disagrees
        (EPOCH, "333e4567-e89b-12d3-a456-426614174000"),   # lease disagrees
        ("333e4567-e89b-12d3-a456-426614174000",
         "333e4567-e89b-12d3-a456-426614174000"),          # both, database alone differs
    ],
    ids=["builder-epoch", "lease-epoch", "database-epoch"],
)
def test_the_three_way_epoch_agreement_is_required(receipt_epoch, lease_epoch):
    service, _database, adapter, _boundary = build(
        boundary=_Boundary(health_receipt=health(recoveryEpoch=receipt_epoch))
    )
    with pytest.raises(DomainError) as refused:
        run(service, lease_epoch=lease_epoch)
    assert "recovery epoch" in str(refused.value)
    assert adapter.calls == 0


@pytest.mark.parametrize("key", ["seccompMode", "lsm", "cgroupMode"])
@pytest.mark.parametrize("value", ["unavailable-ci-reference", "unconfined-ci-reference"])
def test_ci_reference_isolation_values_are_refused_for_product(key, value):
    isolation = dict(health()["isolation"])
    isolation[key] = value
    service, _database, adapter, _boundary = build(
        boundary=_Boundary(health_receipt=health(isolation=isolation))
    )
    with pytest.raises(DomainError) as refused:
        run(service)
    assert "CI reference value" in str(refused.value)
    assert adapter.calls == 0


@pytest.mark.parametrize("writer", ["control-plane", "caller", None])
def test_only_the_node_agent_may_write_the_health_receipt(writer):
    service, _database, adapter, _boundary = build(
        boundary=_Boundary(health_receipt=health(writerKind=writer))
    )
    with pytest.raises(DomainError) as refused:
        run(service)
    assert "node agent" in str(refused.value)
    assert adapter.calls == 0


# --- daemon liveness ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "after,code",
    [
        ({**DAEMON, "pid": 99}, "VERIFY-0002"),
        ({**DAEMON, "processStartTicks": 99999}, "VERIFY-0002"),
        ({**DAEMON, "processUid": 0}, "VERIFY-0002"),
        # A rootlesskit process answering in buildkitd's place is refused one step
        # earlier, by name, rather than compared field by field.
        ({**DAEMON, "comm": "rootlesskit"}, "RES-0006"),
    ],
    ids=["pid", "start-ticks", "uid", "comm"],
)
def test_a_daemon_that_changed_across_the_dispatch_goes_to_cleanup(after, code):
    boundary = _Boundary(daemon_after=after)
    service, database, _adapter, _boundary = build(boundary=boundary)
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == code
    assert all(batch == [] for batch in database.committed)
    if code == "VERIFY-0002":
        assert boundary.cancelled_sessions == [(SESSION, "VERIFY-0002")]


# --- cleanup authority -------------------------------------------------------------------


@pytest.mark.parametrize(
    "override,fragment",
    [
        ({"nodeId": "nod_other"}, "nodeId does not bind"),
        ({"resourceId": "res_other"}, "resourceId does not bind"),
        ({"leaseId": "lse_other"}, "leaseId does not bind"),
        ({"buildSessionId": "11111111-2222-4333-8444-555555555555"},
         "buildSessionId does not bind"),
        ({"recoveryEpoch": "333e4567-e89b-12d3-a456-426614174000"}, "recovery epoch"),
        ({"writerKind": "control-plane"}, "node agent"),
        ({"schemaVersion": "build-physical-cleanup-receipt:0"}, "schema is not authoritative"),
        ({"stopResult": ""}, "no stop result"),
        ({"partialExportDisposition": "kept"}, "partial export"),
        ({"cacheDisposition": "whatever"}, "cache"),
        ({"builderClaimReleased": False}, "builder claim"),
        ({"cgroupRemoved": False}, "cgroup"),
        ({"verifiedAt": ""}, "no verification time"),
        ({"daemonIdentity": {**DAEMON, "pid": 77}}, "different daemon"),
    ],
)
def test_every_required_cleanup_observation_must_agree_or_nothing_is_released(override, fragment):
    boundary = _Boundary(cleanup_receipt=cleanup(**override))
    service, database, _adapter, _boundary = build(boundary=boundary)
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "VERIFY-0022" and refused.value.status == 409
    assert fragment in str(refused.value)
    # Nothing committed, nothing released, and the node is quarantined instead.
    assert all(batch == [] for batch in database.committed)
    assert boundary.quarantined_nodes == [(NODE, "VERIFY-0022")]


def test_a_missing_cleanup_receipt_is_refused_rather_than_treated_as_clean():
    boundary = _Boundary(cleanup_receipt=None)
    boundary.cleanup_receipt = None
    service, database, _adapter, _boundary = build(boundary=boundary)
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "VERIFY-0022"
    assert all(batch == [] for batch in database.committed)


# --- atomicity ---------------------------------------------------------------------------


def test_a_lease_released_concurrently_rolls_the_whole_commit_back():
    database = _Database(release_succeeds=False)
    service, database, _adapter, _boundary = build(database=database)
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "LEASE-0002"
    # The Evidence INSERT that preceded the failed release is discarded with it.
    assert database.rolled_back and [kind for kind, _ in database.rolled_back[-1]] == [
        "evidence",
        "release",
    ]
    assert all(batch == [] for batch in database.committed)


def test_a_lease_that_drifts_between_dispatch_and_commit_is_refused_at_commit():
    """The authority that mattered at dispatch must still hold when the release lands."""

    database = _Database()

    class _DriftingAdapter(_Adapter):
        def execute(self, *args, **kwargs):
            result = super().execute(*args, **kwargs)
            # The epoch moved while the external call was in flight.
            database.lease_row["recovery_epoch"] = "333e4567-e89b-12d3-a456-426614174000"
            return result

    service, database, _adapter, boundary = build(database=database, adapter=_DriftingAdapter())
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "LEASE-0002" and refused.value.status == 409
    assert all(batch == [] for batch in database.committed)
    assert boundary.quarantined_nodes == []


def test_the_outbox_event_type_is_the_contracted_string():
    service, database, _adapter, _boundary = build()
    run(service)
    outbox = [params for kind, params in database.committed[-1] if kind == "outbox"]
    assert len(outbox) == 1
    assert outbox[0][3] == "inv.build.dispatch_completed"
    payload = outbox[0][4].obj
    # Redacted: decision, binding, resource, lease and the persisted Evidence only.
    assert set(payload) == {
        "decisionId", "bindingDigest", "resourceId", "leaseId",
        "leasedNodeId", "evidenceId", "evidenceDigest",
    }


def test_the_persisted_envelope_carries_the_cleanup_receipt_and_its_digest():
    service, database, _adapter, _boundary = build()
    result = run(service)
    evidence = [params for kind, params in database.committed[-1] if kind == "evidence"]
    envelope = evidence[0][3].obj
    # The contract's names, and the pair the product path requires.
    assert envelope["cleanupReceipt"]["physicalReceipt"]["buildSessionId"] == SESSION
    assert len(envelope["cleanupReceipt"]["physicalReceiptDigest"]) == 64
    assert result.evidence_digest and len(result.evidence_digest) == 64


# --- what the product path requires although the contract leaves it optional ------------


def test_a_plan_without_a_build_session_id_is_refused_before_dispatch():
    """``BuildPlan.buildSessionId`` is optional in the contract; here it is not.

    A legacy plan without one stays contract valid, but the physical cleanup receipt binds
    itself to a session, so a product dispatch with no session has nothing for that receipt
    to be about.
    """

    service, _database, adapter, _boundary = build()
    request, plan, decision = request_plan_decision()
    plan.pop("buildSessionId")
    with pytest.raises(DomainError) as refused:
        service.execute(
            object(), request, plan, decision,
            policy_version="v1", run_id=RUN, evidence_id=EVIDENCE_ID, actor_id="act_c214",
        )
    assert refused.value.code == "RES-0006"
    assert "buildSessionId" in str(refused.value)
    assert adapter.calls == 0


def test_a_receipt_session_that_differs_from_the_admitted_plan_is_refused():
    other = "22222222-3333-4444-8555-666666666666"
    service, database, _adapter, _boundary = build(
        adapter=_Adapter(receipt={"buildSessionId": other})
    )
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "VERIFY-0002"
    assert "differs from the admitted plan" in str(refused.value)
    assert all(batch == [] for batch in database.committed)


def test_case_alone_never_decides_the_session_or_epoch_comparison():
    service, database, _adapter, _boundary = build(
        adapter=_Adapter(receipt={"buildSessionId": SESSION.upper()})
    )
    result = run(service)
    assert result.lease_released is True


def test_the_persisted_cleanup_receipt_carries_the_pair_the_contract_only_pairs():
    """The contract makes the pair ``dependentRequired``, so neither present is valid.

    The product path requires both, and the digest has to be the canonical digest of the
    physical receipt beside it -- a digest of something else is a pair in name only.
    """

    service, database, _adapter, _boundary = build()
    run(service)
    evidence = [params for kind, params in database.committed[-1] if kind == "evidence"]
    cleanup = evidence[0][3].obj["cleanupReceipt"]
    assert set(cleanup) == {"physicalReceipt", "physicalReceiptDigest"}
    from inv.build_execution import canonical_digest

    assert cleanup["physicalReceiptDigest"] == canonical_digest(cleanup["physicalReceipt"])


def test_a_mismatched_physical_digest_is_refused_rather_than_committed():
    service, database, _adapter, _boundary = build()
    original = BuildExecutionService._require_physical_pair

    def tampering(self, cleanup):
        cleanup["physicalReceiptDigest"] = "0" * 64
        return original(self, cleanup)

    BuildExecutionService._require_physical_pair = tampering
    try:
        with pytest.raises(DomainError) as refused:
            run(service)
    finally:
        BuildExecutionService._require_physical_pair = original
    assert refused.value.code == "VERIFY-0022"
    assert "does not match the physical receipt" in str(refused.value)
    assert all(batch == [] for batch in database.committed)
