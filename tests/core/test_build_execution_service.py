"""Fail-closed behaviour of the S08-BE product caller (card 214).

Every test here is about a refusal, because the only thing this caller may do when any
input disagrees is refuse without releasing the lease.  The positive case exists once,
as the control: without it a refusal test proves nothing about the refusal.

The two node-agent receipts are supplied as plain dictionaries with the field names the
card 211 contract decision fixed.  Their strict schemas belong to that contract PR, so
these tests assert the authority comparison -- node identity, epoch agreement, daemon
identity, required cleanup observations -- and the atomicity of the commit.
"""

import json
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from psycopg import OperationalError
from psycopg.types.json import Jsonb

from inv.build_execution import (
    BuildExecutionResult,
    BuildExecutionService,
    PRODUCT_ENABLE_SETTING,
    QUARANTINE_CAPABILITY,
    canonical_digest,
)
from inv.buildkit_transport import NodeAgentReceipts
from inv.contracts import validate_contract
from inv.errors import DomainError

TENANT = "123e4567-e89b-12d3-a456-426614174000"
PROJECT = "prj_c214"
EPOCH = "223e4567-e89b-12d3-a456-426614174000"
RUN = "run_c214"
NODE = "nod_01M3PTP800EEMWMDYKEZZ3CWNP"
RESOURCE = "res_01M3PTP800EEMWMDYKEZZ3CWNQ"
LEASE = "lse_01M3PTP800EEMWMDYKEZZ3CWNR"
SESSION = "7f4a1c62-9d1e-4a3b-8c55-0f21aa9b4e10"
EVIDENCE_ID = "evd_01M3PTP800EEMWMDYKEZZ3CWNS"
ENABLED = {PRODUCT_ENABLE_SETTING: "1"}

DAEMON = {"pid": 42, "processUid": 1000, "processStartTicks": 28815, "comm": "buildkitd"}
NOW = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)
FRESH = "2026-10-02T08:59:52Z"          # 8s old against NOW
STALE = "2026-10-02T08:59:30Z"          # 30s old, beyond the 15s window
FUTURE = "2026-10-02T09:00:30Z"         # ahead of the database clock


def health(**overrides):
    document = {
        "schemaVersion": "build-provider-health-receipt:1",
        "writerKind": "node-agent",
        "nodeId": NODE,
        "builderInstanceId": "builder-c214",
        "builderProfileId": "rootless-product-v1",
        "recoveryEpoch": EPOCH,
        "observedAt": FRESH,
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


def _serialised(params):
    """What the driver actually sends, with JSONB frozen at execute() time."""

    if params is None:
        return None
    return tuple(
        json.loads(json.dumps(item.obj)) if isinstance(item, Jsonb) else item
        for item in params
    )


class _Connection:
    """Answers only the statements this service issues, and records the writes."""

    def __init__(self, database):
        self.db = database
        self._result = None

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        # psycopg serialises a JSONB parameter when execute() is called.  Recording the live
        # object instead let a later mutation of the same dict appear in the "persisted" row,
        # which is how an envelope could gain a field after its digest was taken (#312 N1).
        params = _serialised(params)
        if text == "SELECT clock_timestamp() AS now":   # exact: the release UPDATE also calls it
            self._result = {"now": self.db.now}
        elif "FROM inv.resources" in text:
            self._result = {"node_id": self.db.resource_node_id}
        elif "FROM inv.nodes" in text and "FOR UPDATE" in text:
            self._result = {"status": self.db.node_status, "recovery_epoch": EPOCH}
        elif "FROM inv.resource_leases" in text and "FOR UPDATE" in text:
            self._result = deepcopy(self.db.lease_row)
        elif "FROM inv.build_execution_intents" in text and "FOR UPDATE" in text:
            self._result = {"status": "claimed", "attempt_count": 1}
        elif text.startswith("INSERT INTO inv.evidence"):
            self.db.writes.append(("evidence", params))
            self._result = None
        elif text.startswith("UPDATE inv.resource_leases"):
            self.db.writes.append(("release", params))
            self._result = {"lease_id": LEASE} if self.db.release_succeeds else None
        elif text.startswith("UPDATE inv.nodes SET status='quarantined'"):
            self.db.writes.append(("node_quarantine", params))
            self.db.node_status = "quarantined"
            self._result = None
        elif text.startswith("INSERT INTO inv.outbox"):
            self.db.writes.append(("outbox", params))
            self._result = None
        else:  # pragma: no cover - a statement this service must not issue
            raise AssertionError(f"unexpected statement: {text}")
        return self

    def fetchone(self):
        return self._result


class _Database:
    def __init__(self, *, lease_epoch=EPOCH, resource_node_id=NODE, release_succeeds=True,
                 now=None):
        self.recovery_epoch = EPOCH
        self.now = now or NOW
        self.resource_node_id = resource_node_id
        self.release_succeeds = release_succeeds
        self.node_status = "online"
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


def caller_cleanup(**overrides):
    """The BuildReceipt's own cleanup receipt: it duplicates four physical observations."""

    document = {
        "cacheDisposition": "retained",
        "builderClaimReleased": True,
        "cgroupRemoved": True,
        "verifiedAt": "2026-10-02T08:00:05Z",
    }
    document.update(overrides)
    return document


class _Adapter:
    def __init__(self, *, receipt=None, error=None):
        self.receipt = receipt if receipt is not None else {
            "buildSessionId": SESSION, "cleanup": caller_cleanup()
        }
        self.error = error
        self.calls = 0
        self.call_kwargs = []

    def execute(self, principal, request, plan, decision, **kwargs):
        self.calls += 1
        self.call_kwargs.append(dict(kwargs))
        if self.error is not None:
            raise self.error
        from inv.build_adapter import BuildAdapterResult

        return BuildAdapterResult(
            receipt=dict(self.receipt),
            evidence={"evidenceId": EVIDENCE_ID, "kind": "BuildReceipt"},
        )


class _Boundary:
    #: This fake records a quarantine durably enough for the orchestration under test: it
    #: keeps the marker and the tests read it.  The production collector declares the
    #: opposite, which is the whole of N2.
    records_durable_quarantine = True

    def __init__(
        self, *, health_receipt=None, cleanup_receipt=None, daemon_after=None,
        preflight_error=None,
    ):
        self.health_receipt = health_receipt if health_receipt is not None else health()
        self.cleanup_receipt = cleanup_receipt if cleanup_receipt is not None else cleanup()
        self.daemon_after = daemon_after if daemon_after is not None else dict(DAEMON)
        self.quarantined_nodes = []
        self.cancelled_sessions = []
        self.preflight_calls = []
        self.preflight_error = preflight_error

    def preflight_quarantine(self, node_id, recovery_epoch):
        self.preflight_calls.append((node_id, recovery_epoch))
        if self.preflight_error is not None:
            raise self.preflight_error

    def collect_product_health(self):
        return deepcopy(self.health_receipt)

    def daemon_identity(self):
        return dict(self.daemon_after)

    def collect_cleanup_receipt(self, build_session_id):
        assert build_session_id == SESSION
        return deepcopy(self.cleanup_receipt)

    def cancel_and_quarantine_session(self, build_session_id, reason_code, **identity):
        self.cancelled_sessions.append((build_session_id, reason_code))

    def quarantine_node(self, node_id, build_session_id, reason_code, **identity):
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
        intent_claim_fencing_token=1,
    )


def assert_only_quarantine_was_committed(database, reason_code):
    """A failed post-dispatch commit may persist only the scheduling fence."""

    writes = [(kind, params) for batch in database.committed for kind, params in batch]
    assert [kind for kind, _ in writes] == ["node_quarantine", "outbox"]
    event = writes[1][1]
    assert event[3] == "inv.build.node_quarantined"
    assert event[4]["reasonCode"] == reason_code
    assert event[4]["buildSessionId"] == SESSION
    assert event[4]["leaseId"] == LEASE
    assert event[4]["resourceId"] == RESOURCE
    assert event[4]["decisionId"] == "dec_c214"
    assert len(event[4]["bindingDigest"]) == 64
    assert database.node_status == "quarantined"


def assert_only_preflight_observation_was_committed(database):
    """A pre-dispatch outage is observed, but never permanently fences the Node."""

    writes = [(kind, params) for batch in database.committed for kind, params in batch]
    assert [kind for kind, _ in writes] == ["outbox"]
    event = writes[0][1]
    assert event[3] == "inv.build.quarantine_preflight_unavailable"
    assert event[4]["reasonCode"] == "RES-0006"
    assert event[4]["nodeId"] == NODE
    assert database.node_status == "online"


# --- the control -------------------------------------------------------------------------


def test_an_agreeing_dispatch_persists_releases_and_records_in_one_transaction():
    service, database, adapter, boundary = build()
    result = run(service)
    assert isinstance(result, BuildExecutionResult)
    assert result.lease_released is True and result.cleanup_verified is True
    assert adapter.calls == 1
    # One transaction carries all three writes, in this order, and nothing rolled back.
    committed = [batch for batch in database.committed if batch]
    assert [kind for kind, _ in committed[-1]] == ["release", "evidence", "outbox"]
    assert database.rolled_back == []
    assert boundary.quarantined_nodes == []


def test_intent_claim_fencing_token_reaches_adapter_before_dispatch():
    adapter = _Adapter(error=DomainError("RES-0006", "stop before dispatch", 503, retryable=True))
    service, _database, _adapter, _boundary = build(adapter=adapter)
    request, plan, decision = request_plan_decision()

    with pytest.raises(DomainError, match="stop before dispatch"):
        service.execute(
            object(),
            request,
            plan,
            decision,
            policy_version="v1",
            run_id=RUN,
            evidence_id=EVIDENCE_ID,
            actor_id="act_c214",
            intent_claim_fencing_token=7,
        )

    assert adapter.calls == 1
    assert adapter.call_kwargs[0]["intent_claim_fencing_token"] == 7


def test_product_dispatch_without_an_intent_claim_generation_is_refused():
    service, _database, adapter, _boundary = build()
    request, plan, decision = request_plan_decision()

    with pytest.raises(DomainError) as refused:
        service.execute(
            object(),
            request,
            plan,
            decision,
            policy_version="v1",
            run_id=RUN,
            evidence_id=EVIDENCE_ID,
            actor_id="act_c214",
        )

    assert refused.value.code == "RES-0006"
    assert "claim generation" in str(refused.value)
    assert adapter.calls == 0


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


def test_an_unreachable_runtime_channel_is_observed_without_permanent_quarantine():
    """N-1: a transient pre-dispatch outage refuses only this dispatch."""

    boundary = _Boundary(
        preflight_error=DomainError(
            "RES-0006", "Node quarantine channel is not live", 503, retryable=True
        )
    )
    service, database, adapter, _boundary = build(boundary=boundary)
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "RES-0006" and refused.value.retryable is True
    assert adapter.calls == 0
    assert_only_preflight_observation_was_committed(database)


# --- health authority --------------------------------------------------------------------


def test_a_health_receipt_about_another_node_is_refused():
    service, _database, adapter, _boundary = build(
        boundary=_Boundary(health_receipt=health(nodeId="nod_01M3PTP800EEMWMDYKEZZ3CWZZ"))
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
    if code == "VERIFY-0002":
        assert_only_quarantine_was_committed(database, code)
        assert boundary.cancelled_sessions == [(SESSION, "VERIFY-0002")]
    else:
        assert all(batch == [] for batch in database.committed)


# --- cleanup authority -------------------------------------------------------------------


@pytest.mark.parametrize(
    "override,fragment",
    [
        ({"nodeId": "nod_01M3PTP800EEMWMDYKEZZ3CWZZ"}, "nodeId does not bind"),
        ({"resourceId": "res_01M3PTP800EEMWMDYKEZZ3CWZZ"}, "resourceId does not bind"),
        ({"leaseId": "lse_01M3PTP800EEMWMDYKEZZ3CWZZ"}, "leaseId does not bind"),
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
    # No product success is committed; the independent scheduling fence is.
    assert_only_quarantine_was_committed(database, "VERIFY-0022")
    assert boundary.quarantined_nodes == [(NODE, "VERIFY-0022")]


def test_a_missing_cleanup_receipt_is_refused_rather_than_treated_as_clean():
    boundary = _Boundary(cleanup_receipt=None)
    boundary.cleanup_receipt = None
    service, database, _adapter, _boundary = build(boundary=boundary)
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "VERIFY-0022"
    assert_only_quarantine_was_committed(database, "VERIFY-0022")


# --- atomicity ---------------------------------------------------------------------------


def test_a_lease_released_concurrently_rolls_the_whole_commit_back():
    database = _Database(release_succeeds=False)
    service, database, _adapter, _boundary = build(database=database)
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "LEASE-0002"
    # The release is attempted before anything is written down, because the receipt has to
    # state whether it succeeded (#312 N1).  So the only statement to unwind is the release,
    # and no Evidence row or outbox event ever existed to be discarded.
    assert database.rolled_back and [kind for kind, _ in database.rolled_back[-1]] == ["release"]
    assert_only_quarantine_was_committed(database, "LEASE-0002")
    assert _boundary.quarantined_nodes == [(NODE, "LEASE-0002")]


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
    assert_only_quarantine_was_committed(database, "LEASE-0002")
    # The external dispatch already happened, so the loser leaves a reconciliation marker
    # rather than raising and forgetting (#312 F-R4).
    assert boundary.quarantined_nodes == [(NODE, "LEASE-0002")]


def test_the_outbox_event_type_is_the_contracted_string():
    service, database, _adapter, _boundary = build()
    run(service)
    outbox = [params for kind, params in database.committed[-1] if kind == "outbox"]
    assert len(outbox) == 1
    assert outbox[0][3] == "inv.build.dispatch_completed"
    payload = outbox[0][4]
    # Redacted: decision, binding, resource, lease and the persisted Evidence only.
    # Six keys: the contract's additionalProperties:false allows no more (#312 F-R3).
    assert set(payload) == {
        "decisionId", "bindingDigest", "resourceId", "leaseId", "evidenceId", "evidenceDigest",
    }


def test_the_persisted_envelope_carries_the_cleanup_receipt_and_its_digest():
    service, database, _adapter, _boundary = build()
    result = run(service)
    evidence = [params for kind, params in database.committed[-1] if kind == "evidence"]
    envelope = evidence[0][3]
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
        adapter=_Adapter(receipt={"buildSessionId": other, "cleanup": caller_cleanup()})
    )
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "VERIFY-0002"
    assert "differs from the admitted plan" in str(refused.value)
    assert all(batch == [] for batch in database.committed)


def test_case_alone_never_decides_the_session_or_epoch_comparison():
    service, database, _adapter, _boundary = build(
        adapter=_Adapter(receipt={"buildSessionId": SESSION.upper(),
                                  "cleanup": caller_cleanup()})
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
    cleanup = evidence[0][3]["cleanupReceipt"]
    # The public receipt: its own four observations, the lease fact this transaction proved,
    # and the physical pair the product path requires.
    assert set(cleanup) == {
        "cacheDisposition", "builderClaimReleased", "cgroupRemoved", "verifiedAt",
        "leaseReleased", "physicalReceipt", "physicalReceiptDigest",
    }
    assert cleanup["leaseReleased"] is True
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
    assert_only_quarantine_was_committed(database, "VERIFY-0022")


# --- #312 Codex review: four boundaries the earlier tests fixed as success ---------------


@pytest.mark.parametrize("observed,label", [(STALE, "30s old"), (FUTURE, "ahead of the clock")],
                         ids=["stale", "future"])
def test_a_health_receipt_that_is_not_fresh_is_refused(observed, label):
    """F-R1: the contract's stale-observedAt boundary, measured against the database clock.

    Codex reproduced a release with ``observedAt`` in 2020.  The adapter's own provider
    freshness is about a different observation and does not stand in for this one.
    """

    service, database, adapter, _boundary = build(
        boundary=_Boundary(health_receipt=health(observedAt=observed))
    )
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "RES-0003" and refused.value.status == 409
    assert adapter.calls == 0
    assert all(batch == [] for batch in database.committed)


@pytest.mark.parametrize(
    "override",
    [
        {"cacheDisposition": "quarantined"},
        {"builderClaimReleased": False},
        {"cgroupRemoved": False},
        {"verifiedAt": "2020-01-01T00:00:00Z"},
    ],
    ids=["cacheDisposition", "builderClaimReleased", "cgroupRemoved", "verifiedAt"],
)
def test_the_two_cleanup_receipts_must_agree_on_every_duplicated_observation(override):
    """F-R2: two cleanup receipts that contradict each other must not release a lease."""

    service, database, _adapter, boundary = build(
        adapter=_Adapter(receipt={"buildSessionId": SESSION, "cleanup": caller_cleanup(**override)})
    )
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "VERIFY-0022"
    assert_only_quarantine_was_committed(database, "VERIFY-0022")
    assert boundary.quarantined_nodes == [(NODE, "VERIFY-0022")]


def test_the_completed_payload_passes_the_public_contract_validator():
    """F-R3: the six keys the contract allows, checked by the canonical validator."""

    from inv.contracts import validate_contract

    service, database, _adapter, _boundary = build()
    run(service)
    payload = [p for kind, p in database.committed[-1] if kind == "outbox"][0][4]
    assert set(payload) == {
        "decisionId", "bindingDigest", "resourceId", "leaseId", "evidenceId", "evidenceDigest",
    }
    validate_contract("BuildDispatchCompletedPayload", payload)


def test_losing_a_lease_race_after_the_external_dispatch_records_reconciliation():
    """F-R4: the loser dispatched externally, so it may not simply raise and forget."""

    database = _Database(release_succeeds=False)
    service, database, _adapter, boundary = build(database=database)
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "LEASE-0002"
    assert_only_quarantine_was_committed(database, "LEASE-0002")
    # Nothing durable landed, so the node holds unaccounted external state.
    assert boundary.quarantined_nodes == [(NODE, "LEASE-0002")]


def test_the_persisted_envelope_is_the_one_its_digest_covers():
    """#312 N1: r1 wrote the Evidence row and *then* added ``leaseReleased`` to the receipt.

    psycopg serialises a JSONB parameter at ``execute()``, so the stored envelope was missing a
    field strict ``BuildCleanupReceipt`` requires; with serialisation deferred the stored
    envelope gained the field afterwards and no longer matched the digest the outbox and the
    result carry.  Recomputing the digest from what was persisted is the only assertion that
    sees either outcome -- checking that the field is present does not.
    """

    service, database, _adapter, _boundary = build()
    result = run(service)
    stored = {kind: params for batch in database.committed for kind, params in batch}
    envelope = stored["evidence"][3]
    receipt = envelope["cleanupReceipt"]
    # The row is a strict BuildCleanupReceipt, as persisted rather than as intended.
    validate_contract("BuildCleanupReceipt", receipt)
    assert receipt["leaseReleased"] is True
    assert canonical_digest(envelope) == result.evidence_digest
    assert stored["outbox"][4]["evidenceDigest"] == result.evidence_digest


def test_a_cleanup_receipt_the_public_contract_does_not_allow_is_not_persisted():
    """#312 N1: the row is checked against the strict contract before it exists.

    ``BuildCleanupReceipt`` is ``additionalProperties: false``, so a field nobody validates
    cannot ride into the Evidence envelope on the caller's receipt.  The duplicated-observation
    comparison only looks at the four fields it compares, which is a different question.
    """

    service, database, _adapter, _boundary = build(
        adapter=_Adapter(
            receipt={
                "buildSessionId": SESSION,
                "cleanup": caller_cleanup(operatorNote="anything at all"),
            }
        )
    )
    with pytest.raises(DomainError) as refused:
        run(service)
    # The canonical validator refuses with its own redacted code; the row never exists.
    assert refused.value.code == "VAL-0002"
    assert "BuildCleanupReceipt" in str(refused.value)
    assert all(batch == [] for batch in database.committed)


def test_a_transport_that_cannot_record_a_quarantine_does_not_dispatch():
    """#312 N2: the production collector's ``quarantine_node`` only raises.

    A race loser dispatched externally and consumed its one-shot decision claim, so without a
    durable marker nobody learns that the node holds unaccounted state.  The refusal belongs
    before the dispatch: refusing afterwards leaves exactly that state behind.
    """

    boundary = _Boundary()
    boundary.records_durable_quarantine = False
    service, _database, adapter, _b = build(boundary=boundary)
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "RES-0006" and refused.value.status == 503
    assert adapter.calls == 0


def test_the_production_collector_declares_the_quarantine_capability_absent():
    """#312 N2: fail closed by default -- the declaration is the transport's, not a guess."""

    assert getattr(NodeAgentReceipts, QUARANTINE_CAPABILITY, False) is False


def test_a_failing_quarantine_does_not_replace_the_race_it_was_recording():
    """#312 N2: the transport's own refusal must not become the caller's answer."""

    def refuse(node_id, build_session_id, reason_code, **identity):
        raise DomainError("NODE-0030", "Node agent quarantine is unavailable", 503)

    boundary = _Boundary()
    boundary.quarantine_node = refuse
    database = _Database(release_succeeds=False)
    service, _database, _adapter, _b = build(database=database, boundary=boundary)
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "LEASE-0002"
    assert_only_quarantine_was_committed(database, "LEASE-0002")


def test_a_failing_control_plane_fence_does_not_replace_the_original_error(monkeypatch):
    """N-2: driver/check/FK failures are secondary to the dispatch authority failure."""

    boundary = _Boundary(daemon_after={**DAEMON, "pid": 99})
    service, _database, _adapter, _b = build(boundary=boundary)

    def unavailable(**_kwargs):
        raise OperationalError("database unavailable")

    monkeypatch.setattr(service, "_mark_node_quarantined", unavailable)
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "VERIFY-0002"


def test_two_callers_contending_on_one_lease_release_and_record_exactly_once():
    """F-R4: the same lease, two commits. One lands; the other must not add a second.

    The fake database is shared, so the winner's ``released_at`` is what the loser reads --
    the same thing the conditional UPDATE enforces in PostgreSQL.
    """

    database = _Database()
    first, _db, _adapter, boundary_a = build(database=database)
    result = run(first)
    assert result.lease_released is True

    # The winner's release is now visible to anyone who looks.
    database.lease_row["released_at"] = NOW
    second, _db, _adapter, boundary_b = build(database=database)
    with pytest.raises(DomainError) as refused:
        run(second)
    assert refused.value.code == "LEASE-0002"

    releases = [k for batch in database.committed for k, _ in batch if k == "release"]
    outbox_types = [
        params[3]
        for batch in database.committed
        for kind, params in batch
        if kind == "outbox"
    ]
    assert releases == ["release"]
    assert outbox_types == ["inv.build.dispatch_completed", "inv.build.node_quarantined"]
    assert boundary_a.quarantined_nodes == []
    assert boundary_b.quarantined_nodes == [(NODE, "LEASE-0002")]


def test_a_retry_after_a_lost_success_response_does_not_release_twice():
    """F-R4: the caller never saw the answer, so it tries again. The lease says no.

    This fake does not model the adapter's one-shot claim; the real second barrier is
    ``IDEM-0001`` there, and this test pins the barrier this module owns -- the lease was
    already released, so no second release or event can be written.
    """

    database = _Database()
    service, _db, _adapter, _boundary = build(database=database)
    run(service)
    database.lease_row["released_at"] = NOW
    with pytest.raises(DomainError) as refused:
        run(service)
    assert refused.value.code == "LEASE-0002"
    assert [k for batch in database.committed for k, _ in batch if k == "release"] == ["release"]
