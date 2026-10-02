"""Real PostgreSQL boundary for migration 0059 and the internal build worker."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from psycopg.types.json import Jsonb

from inv.approvals import Principal
from inv.build_execution import BuildExecutionResult, PRODUCT_ENABLE_SETTING
from inv.build_execution_worker import BuildExecutionIntentQueue, BuildExecutionWorker
from inv.build_governance import canonical_build_action
from inv.errors import DomainError
from inv.ids import new_id
from inv.policy import action_digest

pytestmark = pytest.mark.postgres
ULID = "01M3PTP800EEMWMDYKEZZ3CWNP"


def build_documents(env, subject):
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
        "decisionId": "policy-s08-product-real-pg",
        "tenantId": env.tenant,
        "projectId": env.project,
        "subjectId": subject,
        "effect": "allow",
        "riskLevel": "L1",
        "actionDigest": action_digest(canonical_build_action(request)),
        "expiresAt": "2030-10-02T06:05:00Z",
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
            "leaseId": f"lse_{ULID}",
            "resourceId": env.resource,
            "fencingToken": f"{env.epoch}:7",
            "expiresAt": "2030-10-02T06:05:00Z",
        },
        "cacheNamespaceDigest": "d" * 64,
        "secretRefsDigest": "e" * 64,
        "resolvedBaseImageDigests": ["sha256:" + "f" * 64],
    }
    return request, plan, decision


def scheduled_run(env):
    run = env.runs.create(env.tenant, env.project)
    run = env.runs.transition(env.tenant, run["runId"], "validated", expected_version=1)
    run = env.runs.transition(env.tenant, run["runId"], "planned", expected_version=2)
    return env.runs.transition(env.tenant, run["runId"], "scheduled", expected_version=3)


def enqueue(env):
    run = scheduled_run(env)
    subject = "oidc:build-operator"
    principal = Principal(env.tenant, subject)
    request, plan, decision = build_documents(env, subject)
    queue = BuildExecutionIntentQueue(env.db)
    intent = queue.enqueue(
        principal,
        request,
        plan,
        decision,
        policy_version="s08-build-v1",
        run_id=run["runId"],
        evidence_id=new_id("evd"),
    )
    return queue, intent


def test_enqueue_is_exact_replay_and_database_owns_canonical_digests(env):
    queue, intent = enqueue(env)
    replay = queue.enqueue(
        Principal(env.tenant, intent.actor_id),
        intent.request,
        intent.plan,
        intent.decision,
        policy_version=intent.policy_version,
        run_id=intent.run_id,
        evidence_id=intent.evidence_id,
    )
    assert replay == intent
    with psycopg.connect(env.owner) as conn:
        row = conn.execute(
            """SELECT request_sha256,
              encode(sha256(convert_to(request::text,'UTF8')),'hex') AS observed_request,
              plan_sha256,encode(sha256(convert_to(plan::text,'UTF8')),'hex') AS observed_plan,
              decision_sha256,
              encode(sha256(convert_to(decision::text,'UTF8')),'hex') AS observed_decision
              FROM inv.build_execution_intents WHERE run_id=%s""",
            (intent.run_id,),
        ).fetchone()
    assert row[0] == row[1]
    assert row[2] == row[3]
    assert row[4] == row[5]

    changed = dict(intent.request, targetStage="different")
    changed_action_digest = action_digest(canonical_build_action(changed))
    changed_plan = dict(
        intent.plan,
        requestDigest=action_digest(changed),
        actionDigest=changed_action_digest,
    )
    changed_decision = dict(intent.decision, actionDigest=changed_action_digest)
    with pytest.raises(DomainError) as caught:
        queue.enqueue(
            Principal(env.tenant, intent.actor_id),
            changed,
            changed_plan,
            changed_decision,
            policy_version=intent.policy_version,
            run_id=intent.run_id,
            evidence_id=intent.evidence_id,
        )
    assert caught.value.code == "IDEM-0001"


def test_two_connections_cannot_claim_the_same_intent_and_other_tenant_cannot_see_it(env):
    queue, intent = enqueue(env)

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = list(executor.map(lambda _: queue.claim_next(env.tenant), range(2)))
    winners = [row for row in claimed if row is not None]
    assert len(winners) == 1
    assert winners[0].run_id == intent.run_id
    assert queue.claim_next(env.other) is None

    with psycopg.connect(env.owner) as conn:
        state = conn.execute(
            "SELECT status,claimed_at,completed_at FROM inv.build_execution_intents WHERE run_id=%s",
            (intent.run_id,),
        ).fetchone()
    assert state[0] == "claimed" and state[1] is not None and state[2] is None


def test_skip_locked_claims_the_second_intent_while_the_first_row_is_locked(env):
    queue, first = enqueue(env)
    _other_queue, second = enqueue(env)
    with psycopg.connect(env.owner) as blocker:
        blocker.execute(
            "SELECT 1 FROM inv.build_execution_intents WHERE run_id=%s FOR UPDATE",
            (first.run_id,),
        )
        claimed = queue.claim_next(env.tenant)
        assert claimed is not None
        assert claimed.run_id == second.run_id


def test_payload_update_delete_and_invalid_transition_are_rejected_by_database(env):
    queue, intent = enqueue(env)
    with psycopg.connect(env.owner) as conn:
        conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (env.tenant,))
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """UPDATE inv.build_execution_intents
                SET status='claimed',request=request || '{\"targetStage\":\"drift\"}'::jsonb
                WHERE run_id=%s""",
                (intent.run_id,),
            )
        conn.rollback()
    claimed = queue.claim_next(env.tenant)
    assert claimed is not None
    queue.complete(claimed)
    with psycopg.connect(env.owner) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "UPDATE inv.build_execution_intents SET status='pending' WHERE run_id=%s",
                (intent.run_id,),
            )
        conn.rollback()
    with psycopg.connect(env.owner) as conn:
        conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (env.tenant,))
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "DELETE FROM inv.build_execution_intents WHERE run_id=%s", (intent.run_id,)
            )


def test_claim_skips_owner_tampered_digest_and_insert_rejects_poison_binding(env):
    queue, intent = enqueue(env)
    _other_queue, healthy = enqueue(env)
    with psycopg.connect(env.owner) as conn:
        conn.execute("SET LOCAL session_replication_role=replica")
        conn.execute(
            """UPDATE inv.build_execution_intents
            SET request=request || '{\"targetStage\":\"tampered\"}'::jsonb
            WHERE run_id=%s""",
            (intent.run_id,),
        )
    claimed = queue.claim_next(env.tenant)
    assert claimed is not None and claimed.run_id == healthy.run_id
    with psycopg.connect(env.owner) as conn:
        corrupt = conn.execute(
            """SELECT status,last_error_code FROM inv.build_execution_intents
            WHERE run_id=%s""",
            (intent.run_id,),
        ).fetchone()
    assert corrupt == ("quarantined", "VERIFY-0002")

    _bad_queue, bad_contract = enqueue(env)
    _next_queue, next_healthy = enqueue(env)
    with psycopg.connect(env.owner) as conn:
        conn.execute("SET LOCAL session_replication_role=replica")
        conn.execute(
            """UPDATE inv.build_execution_intents
            SET request=request - 'kind',
                request_sha256=encode(
                  sha256(convert_to((request - 'kind')::text,'UTF8')),'hex')
            WHERE run_id=%s""",
            (bad_contract.run_id,),
        )
    claimed = queue.claim_next(env.tenant)
    assert claimed is not None and claimed.run_id == next_healthy.run_id
    with psycopg.connect(env.owner) as conn:
        invalid = conn.execute(
            """SELECT status,last_error_code FROM inv.build_execution_intents
            WHERE run_id=%s""",
            (bad_contract.run_id,),
        ).fetchone()
    assert invalid == ("quarantined", "VERIFY-0002")

    run = scheduled_run(env)
    request, plan, decision = build_documents(env, "oidc:other-actor")
    with psycopg.connect(env.owner) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """INSERT INTO inv.build_execution_intents(
                tenant_id,project_id,run_id,request,plan,decision,
                policy_version,evidence_id,actor_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    env.tenant,
                    env.project,
                    run["runId"],
                    Jsonb(request),
                    Jsonb(plan),
                    Jsonb(decision),
                    "s08-build-v1",
                    new_id("evd"),
                    "oidc:different-actor",
                ),
            )


def test_claimed_intent_requeues_only_before_the_dispatch_decision_is_consumed(env):
    queue, _intent = enqueue(env)
    claimed = queue.claim_next(env.tenant)
    assert claimed is not None
    assert queue.requeue_if_unconsumed(claimed, "RES-0006") is True
    assert queue.claim_next(env.tenant) is None
    with psycopg.connect(env.owner) as conn:
        retry = conn.execute(
            """SELECT status,attempt_count,last_error_code,
            next_attempt_at IS NOT NULL FROM inv.build_execution_intents
            WHERE run_id=%s""",
            (claimed.run_id,),
        ).fetchone()
        conn.execute("SELECT pg_sleep(1.1)")
    assert retry == ("pending", 1, "RES-0006", True)
    claimed = queue.claim_next(env.tenant)
    assert claimed is not None
    assert claimed.attempt_count == 2

    claim_key = action_digest({"decisionId": claimed.decision["decisionId"]})
    with psycopg.connect(env.owner) as conn:
        conn.execute(
            """INSERT INTO inv.idempotency(
            tenant_id,project_id,operation,key,request_hash,response
            ) VALUES (%s,%s,'build.dispatch',%s,%s,%s)""",
            (
                env.tenant,
                env.project,
                claim_key,
                "a" * 64,
                Jsonb(
                    {
                        "state": "claimed",
                        "bindingDigest": "a" * 64,
                        "decisionId": claimed.decision["decisionId"],
                    }
                ),
            ),
        )
    assert queue.requeue_if_unconsumed(claimed, "RES-0006") is False
    with psycopg.connect(env.owner) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "UPDATE inv.build_execution_intents SET status='pending' WHERE run_id=%s",
                (claimed.run_id,),
            )
        conn.rollback()
    with psycopg.connect(env.owner) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """UPDATE inv.build_execution_intents
                SET status='quarantined',last_error_code='SYS-0001' WHERE run_id=%s""",
                (claimed.run_id,),
            )


class SuccessfulService:
    def __init__(self):
        self.calls = []

    def execute(self, principal, request, plan, decision, **kwargs):
        self.calls.append((principal, request, plan, decision, kwargs))
        return BuildExecutionResult(kwargs["evidence_id"], "a" * 64, True, True)


class FailingService:
    def execute(self, *_args, **_kwargs):
        raise DomainError("RES-0006", "pre-dispatch fence unavailable", 503, retryable=True)


def test_internal_product_worker_calls_service_once_and_completes(env):
    queue, intent = enqueue(env)
    service = SuccessfulService()
    worker = BuildExecutionWorker(
        queue,
        service,
        environment={PRODUCT_ENABLE_SETTING: "1"},
    )
    result = worker.once(env.tenant)
    assert result and result.evidence_id == intent.evidence_id
    assert len(service.calls) == 1
    assert worker.once(env.tenant) is None
    with psycopg.connect(env.owner) as conn:
        state = conn.execute(
            "SELECT status,claimed_at,completed_at FROM inv.build_execution_intents WHERE run_id=%s",
            (intent.run_id,),
        ).fetchone()
    assert state[0] == "completed" and state[1] is not None and state[2] is not None


def test_disabled_product_worker_does_not_consume_pending_intent(env):
    queue, intent = enqueue(env)
    with pytest.raises(DomainError) as caught:
        BuildExecutionWorker(queue, SuccessfulService(), environment={}).once(env.tenant)
    assert caught.value.code == "RES-0006"
    with psycopg.connect(env.owner) as conn:
        status = conn.execute(
            "SELECT status FROM inv.build_execution_intents WHERE run_id=%s", (intent.run_id,)
        ).fetchone()[0]
    assert status == "pending"


def test_pre_dispatch_product_failure_returns_unconsumed_intent_to_pending(env):
    queue, intent = enqueue(env)
    worker = BuildExecutionWorker(
        queue,
        FailingService(),
        environment={PRODUCT_ENABLE_SETTING: "1"},
    )
    with pytest.raises(DomainError) as caught:
        worker.once(env.tenant)
    assert caught.value.code == "RES-0006"
    with psycopg.connect(env.owner) as conn:
        state = conn.execute(
            """SELECT status,claimed_at,attempt_count,last_error_code,
            next_attempt_at IS NOT NULL
            FROM inv.build_execution_intents WHERE run_id=%s""",
            (intent.run_id,),
        ).fetchone()
        conn.execute("SELECT pg_sleep(1.1)")
    assert state == ("pending", None, 1, "RES-0006", True)

    success = SuccessfulService()
    result = BuildExecutionWorker(
        queue,
        success,
        environment={PRODUCT_ENABLE_SETTING: "1"},
    ).once(env.tenant)
    assert result is not None and len(success.calls) == 1
    with psycopg.connect(env.owner) as conn:
        retried = conn.execute(
            """SELECT status,attempt_count,last_error_code
            FROM inv.build_execution_intents WHERE run_id=%s""",
            (intent.run_id,),
        ).fetchone()
    assert retried == ("completed", 2, None)
