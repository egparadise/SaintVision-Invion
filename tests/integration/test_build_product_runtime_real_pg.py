"""Real PostgreSQL authority and concurrency checks for Card 232."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic

import psycopg
import pytest

from inv.approvals import Principal
from inv.build_execution import BuildExecutionResult, PRODUCT_ENABLE_SETTING
from inv.build_execution_worker import BuildExecutionIntentQueue, BuildExecutionWorker
from inv.build_governance import canonical_build_action
from inv.build_product_runtime import (
    BuildExecutionAdmissionStore,
    BuildProductRuntime,
    TrustedBuildAdmissionEntry,
)
from inv.errors import DomainError
from inv.ids import new_id
from inv.policy import action_digest

pytestmark = pytest.mark.postgres
ULID = "01M3PTP800EEMWMDYKEZZ3CWNP"


def _timestamp(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _authority(env, *, grant=True, node_id=None):
    run = env.runs.create(env.tenant, env.project)
    run = env.runs.transition(env.tenant, run["runId"], "validated", expected_version=1)
    run = env.runs.transition(env.tenant, run["runId"], "planned", expected_version=2)
    run = env.runs.transition(env.tenant, run["runId"], "scheduled", expected_version=3)
    subject = "oidc:build-product-operator"
    lease_id = new_id("lse")
    resource_id = new_id("res")
    expires = datetime.now(timezone.utc) + timedelta(minutes=4)
    policy_expires = expires + timedelta(minutes=1)
    selected_node = node_id or env.node
    with psycopg.connect(env.owner) as conn:
        # A large fairness fixture creates hundreds of independently valid
        # admissions. Keep its authority observation current while building
        # the fixture; staleness is injected only after every admission is
        # durably recorded against the original resource identity.
        conn.execute(
            """UPDATE inv.nodes SET heartbeat_at=clock_timestamp()
            WHERE tenant_id=%s AND node_id=%s""",
            (env.tenant, selected_node),
        )
        if grant:
            conn.execute(
                """INSERT INTO inv.project_grants(
                tenant_id,project_id,subject_id,can_request,can_approve,enabled
                ) VALUES (%s,%s,%s,true,false,true)""",
                (env.tenant, env.project, subject),
            )
        conn.execute(
            "INSERT INTO inv.resources VALUES (%s,%s,%s,'cpu',10,10)",
            (env.tenant, resource_id, selected_node),
        )
        conn.execute(
            """INSERT INTO inv.resource_leases(
            tenant_id,project_id,run_id,resource_id,lease_id,amount,
            fencing_token,expires_at,recovery_epoch
            ) VALUES (%s,%s,%s,%s,%s,1,7,%s,%s)""",
            (env.tenant, env.project, run["runId"], resource_id, lease_id, expires, env.epoch),
        )
    request = {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildRequest",
        "tenantId": env.tenant,
        "projectId": env.project,
        "workspaceId": f"wsp_{ULID}",
        "sourceCommitSha": "a" * 40,
        "sourceTreeSha": "b" * 40,
        "contextPath": "services/worker",
        "dockerfilePath": "services/worker/Dockerfile",
        "targetPlatform": "linux/amd64",
        "targetStage": "runtime",
        "networkPolicyId": "none",
        "cachePolicyId": "cachepol_s08-default",
        "secretRefIds": [],
        "timeoutSeconds": 300,
    }
    decision = {
        "decisionId": f"policy-s08-{new_id('run')}",
        "tenantId": env.tenant,
        "projectId": env.project,
        "subjectId": subject,
        "effect": "allow",
        "riskLevel": "L1",
        "actionDigest": action_digest(canonical_build_action(request)),
        "expiresAt": _timestamp(policy_expires),
        "requiredApprovals": 1,
        "approvedBy": [],
    }
    plan = {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildPlan",
        "tenantId": env.tenant,
        "projectId": env.project,
        "workspaceId": request["workspaceId"],
        "traceId": "1" * 32,
        "requestDigest": action_digest(request),
        "actionDigest": decision["actionDigest"],
        "policyDecisionId": decision["decisionId"],
        "policyVersion": "s08-build-v1",
        "policyExpiresAt": decision["expiresAt"],
        "buildSessionId": "7f4a1c62-9d1e-4a3b-8c55-0f21aa9b4e10",
        "builderInstanceId": "builder-rootless-01",
        "builderProfileId": "buildkit-rootless-v1",
        "builderObservationDigest": "c" * 64,
        "recoveryEpoch": 7,
        "rootless": True,
        "privileged": False,
        "hostAccess": False,
        "networkMode": "none",
        "networkPolicyId": "none",
        "egressAllowlistDigest": "0" * 64,
        "devices": [],
        "binds": [],
        "budget": {"cpuMillis": 2000, "memoryBytes": 1024**3, "storageBytes": 1024**3},
        "lease": {
            "leaseId": lease_id,
            "resourceId": resource_id,
            "fencingToken": f"{env.epoch}:7",
            "expiresAt": _timestamp(expires),
        },
        "cacheNamespaceDigest": "d" * 64,
        "secretRefsDigest": "e" * 64,
        "resolvedBaseImageDigests": ["sha256:" + "f" * 64],
    }
    return Principal(env.tenant, subject), run["runId"], request, plan, decision


def _record(env, *, grant=True, node_id=None):
    principal, run_id, request, plan, decision = _authority(env, grant=grant, node_id=node_id)
    evidence_id = new_id("evd")
    admission = TrustedBuildAdmissionEntry(env.db).record_committed(
        principal,
        request,
        plan,
        decision,
        policy_version="s08-build-v1",
        run_id=run_id,
        evidence_id=evidence_id,
    )
    return admission


def _records_on_stale_node(env, count):
    admissions = [_record(env, grant=index == 0) for index in range(count)]
    with psycopg.connect(env.owner) as conn:
        conn.execute(
            """UPDATE inv.nodes SET heartbeat_at=clock_timestamp()-interval '1 hour'
            WHERE tenant_id=%s AND node_id=%s""",
            (env.tenant, env.node),
        )
    return admissions


def _new_healthy_node(env):
    node_id = new_id("nod")
    with psycopg.connect(env.owner) as conn:
        conn.execute(
            """INSERT INTO inv.nodes(
            tenant_id,node_id,status,recovery_epoch,clock_skew_seconds
            ) VALUES (%s,%s,'online',%s,0)""",
            (env.tenant, node_id, env.epoch),
        )
    return node_id


def test_committed_admission_promotes_atomically_and_is_tenant_isolated(env):
    admission = _record(env)
    store = BuildExecutionAdmissionStore(env.db)
    replay = store.record(
        Principal(admission.tenant_id, admission.actor_id),
        admission.request,
        admission.plan,
        admission.decision,
        policy_version=admission.policy_version,
        run_id=admission.run_id,
        evidence_id=admission.evidence_id,
    )
    assert replay == admission
    with pytest.raises(DomainError) as caught:
        store.record(
            Principal(admission.tenant_id, admission.actor_id),
            admission.request,
            admission.plan,
            admission.decision,
            policy_version=admission.policy_version,
            run_id=admission.run_id,
            evidence_id=new_id("evd"),
        )
    assert caught.value.code == "IDEM-0001"
    promoted = store.promote_next(env.tenant)
    assert promoted == admission
    assert store.promote_next(env.tenant) is None
    assert store.promote_next(env.other) is None
    with psycopg.connect(env.owner) as conn:
        assert (
            conn.execute(
                """SELECT count(*) FROM inv.outbox
            WHERE run_id=%s AND event_type='inv.build.admission_recorded'""",
                (admission.run_id,),
            ).fetchone()[0]
            == 1
        )
        authority = conn.execute(
            """SELECT status,request_sha256,
            encode(sha256(convert_to(request::text,'UTF8')),'hex')
            FROM inv.build_execution_admissions WHERE run_id=%s""",
            (admission.run_id,),
        ).fetchone()
        intent = conn.execute(
            "SELECT status,request,plan,decision FROM inv.build_execution_intents WHERE run_id=%s",
            (admission.run_id,),
        ).fetchone()
        audits = conn.execute(
            """SELECT payload FROM inv.outbox
            WHERE run_id=%s AND event_type='inv.build.intent_enqueued'""",
            (admission.run_id,),
        ).fetchall()
    assert authority[0] == "promoted"
    assert authority[1] == authority[2]
    assert intent == ("pending", admission.request, admission.plan, admission.decision)
    assert len(audits) == 1
    assert set(audits[0][0]) == {"projectId", "runId", "decisionId", "evidenceId"}


def test_missing_project_permission_records_no_admission(env):
    principal, run_id, request, plan, decision = _authority(env, grant=False)
    with pytest.raises(DomainError) as caught:
        BuildExecutionAdmissionStore(env.db).record(
            principal,
            request,
            plan,
            decision,
            policy_version="s08-build-v1",
            run_id=run_id,
            evidence_id=new_id("evd"),
        )
    assert caught.value.code == "AUTH-0030"
    with psycopg.connect(env.owner) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM inv.build_execution_admissions WHERE run_id=%s", (run_id,)
            ).fetchone()[0]
            == 0
        )


def test_two_product_loops_promote_and_dispatch_exactly_once(env):
    admission = _record(env)
    calls = []
    mutex = Lock()

    class Service:
        def execute(self, *args, **kwargs):
            with mutex:
                calls.append((args, kwargs))
            return BuildExecutionResult(new_id("evd"), "a" * 64, True, True)

    def tick(_):
        queue = BuildExecutionIntentQueue(env.db)
        worker = BuildExecutionWorker(queue, Service(), environment={PRODUCT_ENABLE_SETTING: "1"})
        runtime = BuildProductRuntime(
            BuildExecutionAdmissionStore(env.db),
            worker,
            environment={PRODUCT_ENABLE_SETTING: "1"},
        )
        return runtime.once(env.tenant)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(tick, range(2)))
    assert len(calls) == 1
    assert sum(result is not None for result in results) == 1
    with psycopg.connect(env.owner) as conn:
        assert (
            conn.execute(
                "SELECT status FROM inv.build_execution_admissions WHERE run_id=%s",
                (admission.run_id,),
            ).fetchone()[0]
            == "promoted"
        )
        assert (
            conn.execute(
                "SELECT status FROM inv.build_execution_intents WHERE run_id=%s",
                (admission.run_id,),
            ).fetchone()[0]
            == "completed"
        )


def test_flag_off_preserves_admission_without_intent_or_dispatch(env):
    admission = _record(env)

    class Worker:
        def once(self, _tenant):
            raise AssertionError("flag-off product work must not dispatch")

    runtime = BuildProductRuntime(BuildExecutionAdmissionStore(env.db), Worker(), environment={})
    with pytest.raises(DomainError) as caught:
        runtime.once(env.tenant)
    assert caught.value.code == "RES-0006"
    with psycopg.connect(env.owner) as conn:
        assert (
            conn.execute(
                "SELECT status FROM inv.build_execution_admissions WHERE run_id=%s",
                (admission.run_id,),
            ).fetchone()[0]
            == "ready"
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM inv.build_execution_intents WHERE run_id=%s",
                (admission.run_id,),
            ).fetchone()[0]
            == 0
        )


def test_admission_payload_update_delete_and_terminal_revival_are_rejected(env):
    admission = _record(env)
    BuildExecutionAdmissionStore(env.db).promote_next(env.tenant)
    with psycopg.connect(env.owner) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "UPDATE inv.build_execution_admissions SET actor_id='other' WHERE run_id=%s",
                (admission.run_id,),
            )
        conn.rollback()
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "UPDATE inv.build_execution_admissions SET status='ready' WHERE run_id=%s",
                (admission.run_id,),
            )
        conn.rollback()
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "DELETE FROM inv.build_execution_admissions WHERE run_id=%s",
                (admission.run_id,),
            )


def test_conflicting_existing_intent_quarantines_only_that_admission(env):
    first = _record(env)
    BuildExecutionIntentQueue(env.db).enqueue(
        Principal(first.tenant_id, first.actor_id),
        first.request,
        first.plan,
        first.decision,
        policy_version=first.policy_version,
        run_id=first.run_id,
        evidence_id=new_id("evd"),
    )
    second = _record(env, grant=False)

    promoted = BuildExecutionAdmissionStore(env.db).promote_next(env.tenant)
    assert promoted == second
    with psycopg.connect(env.owner) as conn:
        states = dict(
            conn.execute(
                """SELECT run_id,status || ':' || COALESCE(last_error_code,'')
                FROM inv.build_execution_admissions WHERE run_id IN (%s,%s)""",
                (first.run_id, second.run_id),
            ).fetchall()
        )
    assert states == {
        first.run_id: "quarantined:IDEM-0001",
        second.run_id: "promoted:",
    }
    with pytest.raises(DomainError) as caught:
        BuildExecutionAdmissionStore(env.db).record(
            Principal(first.tenant_id, first.actor_id),
            first.request,
            first.plan,
            first.decision,
            policy_version=first.policy_version,
            run_id=first.run_id,
            evidence_id=first.evidence_id,
        )
    assert caught.value.code == "IDEM-0001"


def test_stale_node_promotion_backs_off_and_recovers_without_quarantine(env):
    admission = _record(env)
    store = BuildExecutionAdmissionStore(env.db)
    with psycopg.connect(env.owner) as conn:
        conn.execute(
            """UPDATE inv.nodes SET heartbeat_at=clock_timestamp()-interval '1 hour'
            WHERE tenant_id=%s AND node_id=%s""",
            (env.tenant, env.node),
        )
    assert store.promote_next(env.tenant) is None
    with psycopg.connect(env.owner) as conn:
        retry = conn.execute(
            """SELECT status,last_error_code,retry_count,next_attempt_at > created_at
            FROM inv.build_execution_admissions WHERE run_id=%s""",
            (admission.run_id,),
        ).fetchone()
        conn.execute(
            """UPDATE inv.nodes SET heartbeat_at=clock_timestamp()
            WHERE tenant_id=%s AND node_id=%s""",
            (env.tenant, env.node),
        )
    replay = store.record(
        Principal(admission.tenant_id, admission.actor_id),
        admission.request,
        admission.plan,
        admission.decision,
        policy_version=admission.policy_version,
        run_id=admission.run_id,
        evidence_id=admission.evidence_id,
    )
    assert replay.status == "ready"
    with psycopg.connect(env.owner) as conn:
        conn.execute("SELECT pg_sleep(1.1)")
    assert retry == ("ready", "RES-0003", 1, True)
    assert store.promote_next(env.tenant) == admission


def test_retryable_stale_admission_does_not_block_next_due_admission(env):
    stale = _record(env)
    with psycopg.connect(env.owner) as conn:
        conn.execute(
            """UPDATE inv.nodes SET heartbeat_at=clock_timestamp()-interval '1 hour'
            WHERE tenant_id=%s AND node_id=%s""",
            (env.tenant, env.node),
        )

    healthy = _record(env, grant=False, node_id=_new_healthy_node(env))
    promoted = BuildExecutionAdmissionStore(env.db).promote_next(env.tenant)

    assert promoted == healthy
    with psycopg.connect(env.owner) as conn:
        states = dict(
            conn.execute(
                """SELECT run_id,status || ':' || COALESCE(last_error_code,'')
                FROM inv.build_execution_admissions WHERE run_id IN (%s,%s)""",
                (stale.run_id, healthy.run_id),
            ).fetchall()
        )
        retries = conn.execute(
            """SELECT retry_count,next_attempt_at > clock_timestamp()
            FROM inv.build_execution_admissions WHERE run_id=%s""",
            (stale.run_id,),
        ).fetchone()
    assert states == {
        stale.run_id: "ready:RES-0003",
        healthy.run_id: "promoted:",
    }
    assert retries == (1, True)


def test_promotion_tick_bounds_sixty_stale_admissions_and_reaches_healthy_row(env):
    stale = _records_on_stale_node(env, 60)
    healthy = _record(env, grant=False, node_id=_new_healthy_node(env))
    started = monotonic()
    promoted = BuildExecutionAdmissionStore(env.db).promote_next(env.tenant)
    elapsed = monotonic() - started

    assert promoted == healthy
    assert elapsed < 15
    with psycopg.connect(env.owner) as conn:
        stale_counts = conn.execute(
            """SELECT count(*),count(*) FILTER (
                WHERE status='ready' AND last_error_code='RES-0003'
                  AND retry_count=1 AND next_attempt_at > created_at
            ) FROM inv.build_execution_admissions
            WHERE run_id = ANY(%s::text[])""",
            ([admission.run_id for admission in stale],),
        ).fetchone()
    assert stale_counts == (60, 60)


def test_promotion_order_reaches_healthy_row_beyond_one_tick_budget(env):
    stale = _records_on_stale_node(env, 200)
    healthy = _record(env, grant=False, node_id=_new_healthy_node(env))
    store = BuildExecutionAdmissionStore(env.db)

    first_started = monotonic()
    assert store.promote_next(env.tenant) is None
    first_elapsed = monotonic() - first_started
    second_started = monotonic()
    promoted = store.promote_next(env.tenant)
    second_elapsed = monotonic() - second_started

    assert promoted == healthy
    assert first_elapsed < 20
    assert second_elapsed < 20
    with psycopg.connect(env.owner) as conn:
        attempted = conn.execute(
            """SELECT count(*) FILTER (WHERE retry_count=1),
            count(*) FILTER (WHERE retry_count>1)
            FROM inv.build_execution_admissions
            WHERE run_id = ANY(%s::text[])""",
            ([admission.run_id for admission in stale],),
        ).fetchone()
    assert attempted == (200, 0)
