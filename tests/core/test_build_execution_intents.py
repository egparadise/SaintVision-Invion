"""PG-free guards for Card 223's internal product-build caller."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from inv.approvals import Principal
from inv.build_execution import BuildExecutionResult, PRODUCT_ENABLE_SETTING
from inv.build_execution_worker import (
    BuildExecutionIntent,
    BuildExecutionWorker,
    _validated_documents,
)
from inv.build_governance import canonical_build_action
from inv.errors import DomainError
from inv.policy import action_digest

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/versions/0059_build_execution_intents.py"
WORKER = ROOT / "services/control-plane/src/inv/build_execution_worker.py"

TENANT = "123e4567-e89b-12d3-a456-426614174000"
ULID = "01M3PTP800EEMWMDYKEZZ3CWNP"
PROJECT = f"prj_{ULID}"
RUN = f"run_{ULID}"
EVIDENCE = f"evd_{ULID}"
SUBJECT = "oidc:operator"


def documents():
    request = {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildRequest",
        "tenantId": TENANT,
        "projectId": PROJECT,
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
        "decisionId": "policy-s08-product-1",
        "tenantId": TENANT,
        "projectId": PROJECT,
        "subjectId": SUBJECT,
        "effect": "allow",
        "riskLevel": "L1",
        "actionDigest": action_digest(canonical_build_action(request)),
        "expiresAt": "2026-10-02T06:05:00Z",
        "requiredApprovals": 1,
        "approvedBy": [],
    }
    plan = {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildPlan",
        "tenantId": TENANT,
        "projectId": PROJECT,
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
            "resourceId": f"res_{ULID}",
            "fencingToken": "223e4567-e89b-12d3-a456-426614174000:7",
            "expiresAt": "2026-10-02T06:05:00Z",
        },
        "cacheNamespaceDigest": "d" * 64,
        "secretRefsDigest": "e" * 64,
        "resolvedBaseImageDigests": ["sha256:" + "f" * 64],
    }
    return request, plan, decision


def intent() -> BuildExecutionIntent:
    request, plan, decision = documents()
    return BuildExecutionIntent(
        tenant_id=TENANT,
        project_id=PROJECT,
        run_id=RUN,
        request=request,
        plan=plan,
        decision=decision,
        request_sha256="1" * 64,
        plan_sha256="2" * 64,
        decision_sha256="3" * 64,
        dispatch_claim_key=action_digest({"decisionId": decision["decisionId"]}),
        policy_version="s08-build-v1",
        evidence_id=EVIDENCE,
        actor_id=SUBJECT,
        status="claimed",
        attempt_count=1,
        next_attempt_at=None,
        last_error_code=None,
    )


def test_migration_is_linear_tenant_scoped_payload_immutable_and_delete_forbidden():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision = "0058_release_acceptance_resolver"' in source
    assert 'revision = "0059_build_execution_intents"' in source
    assert 'schema="inv"' in source
    assert "ALTER TABLE inv.build_execution_intents FORCE ROW LEVEL SECURITY" in source
    assert "CREATE POLICY build_execution_intents_tenant_isolation" in source
    assert "GRANT SELECT, INSERT ON inv.build_execution_intents TO inv_kernel" in source
    assert "GRANT UPDATE(status, attempt_count, next_attempt_at, last_error_code" in source
    assert "build execution intent payload is immutable" in source
    assert "build execution intents are not deletable" in source
    assert "pending' AND NEW.status = 'claimed" in source
    assert "claimed' AND NEW.status = 'pending" in source
    assert "OLD.status IN ('pending','claimed') AND NEW.status = 'quarantined'" in source
    assert "claimed' AND NEW.status = 'completed" in source
    assert "response->>'decisionId' = OLD.decision->>'decisionId'" not in source
    assert "NEW.decision->>'subjectId' IS DISTINCT FROM NEW.actor_id" in source
    assert "NEW.plan->>'actionDigest' IS DISTINCT FROM NEW.decision->>'actionDigest'" in source
    assert "NEW.plan->>'policyExpiresAt' IS DISTINCT FROM NEW.decision->>'expiresAt'" in source
    assert "dispatch_claim_key ~ '^[0-9a-f]{64}$'" in source
    assert "AND key = OLD.dispatch_claim_key" in source
    assert "NEW.attempt_count := OLD.attempt_count + 1" in source
    assert "make_interval" in source
    assert "SELECT count(*) FROM inv.build_execution_intents" in source


def test_worker_claim_is_skip_locked_and_no_public_route_is_added():
    source = WORKER.read_text(encoding="utf-8")
    assert "FOR UPDATE SKIP LOCKED" in source
    assert "request_sha256 IS DISTINCT FROM" in source
    assert "plan_sha256 IS DISTINCT FROM" in source
    assert "decision_sha256 IS DISTINCT FROM" in source
    assert "status='quarantined',last_error_code='VERIFY-0002'" in source
    assert "next_attempt_at <= clock_timestamp()" in source
    assert "claimed_at <= clock_timestamp() - make_interval" in source
    assert "ledger.key=intent.dispatch_claim_key" in source
    assert '"Build dispatch claim identity differs"' in source
    assert "class BuildExecutionWorker" in source
    inv_root = ROOT / "services/control-plane/src/inv"
    consumers = []
    for path in inv_root.glob("*.py"):
        if path == WORKER:
            continue
        text = path.read_text(encoding="utf-8")
        if "build_execution_worker" in text or "BuildExecutionWorker" in text:
            consumers.append(path.name)
    assert consumers == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda request, plan, decision: request.update(
            tenantId="223e4567-e89b-12d3-a456-426614174000"
        ),
        lambda request, plan, decision: plan.update(projectId=f"prj_{'0' * 26}"),
        lambda request, plan, decision: decision.update(subjectId="somebody-else"),
        lambda request, plan, decision: plan.update(policyVersion="drift"),
        lambda request, plan, decision: plan.update(policyDecisionId="drift"),
        lambda request, plan, decision: plan.update(requestDigest="0" * 64),
        lambda request, plan, decision: decision.update(actionDigest="0" * 64),
        lambda request, plan, decision: plan.update(policyExpiresAt="2026-10-02T06:04:59Z"),
    ],
)
def test_trusted_enqueue_documents_fail_closed_on_scope_or_policy_drift(mutate):
    request, plan, decision = documents()
    mutate(request, plan, decision)
    with pytest.raises(DomainError):
        _validated_documents(
            Principal(TENANT, SUBJECT),
            request,
            plan,
            decision,
            policy_version="s08-build-v1",
        )


class Queue:
    def __init__(self, item):
        self.item = item
        self.claims = 0
        self.completions = 0
        self.requeues = 0
        self.quarantines = 0

    def claim_next(self, tenant_id):
        assert tenant_id == TENANT
        self.claims += 1
        return self.item

    def complete(self, item):
        assert item is self.item
        self.completions += 1

    def requeue_if_unconsumed(self, item, error_code):
        assert item is self.item
        assert error_code == "RES-0006"
        self.requeues += 1
        return True

    def quarantine_if_unconsumed(self, item, error_code):
        assert item is self.item
        assert error_code == "SYS-0001"
        self.quarantines += 1
        return True


class Service:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def execute(self, principal, request, plan, decision, **kwargs):
        self.calls.append(
            (principal, deepcopy(request), deepcopy(plan), deepcopy(decision), kwargs)
        )
        if self.error:
            raise self.error
        return BuildExecutionResult("evd", "a" * 64, True, True)


def test_product_flag_is_checked_before_claim_and_exact_one_does_not_mean_truthy():
    for environment in ({}, {PRODUCT_ENABLE_SETTING: "0"}, {PRODUCT_ENABLE_SETTING: "true"}):
        queue = Queue(intent())
        with pytest.raises(DomainError, match="not enabled"):
            BuildExecutionWorker(queue, Service(), environment=environment).once(TENANT)
        assert queue.claims == 0


def test_worker_calls_service_with_persisted_authority_then_completes():
    queued = intent()
    queue = Queue(queued)
    service = Service()
    result = BuildExecutionWorker(queue, service, environment={PRODUCT_ENABLE_SETTING: "1"}).once(
        TENANT
    )
    assert result.lease_released is True
    assert queue.claims == queue.completions == 1
    principal, request, plan, decision, kwargs = service.calls[0]
    assert principal == Principal(TENANT, SUBJECT)
    assert (request, plan, decision) == (queued.request, queued.plan, queued.decision)
    assert kwargs == {
        "policy_version": queued.policy_version,
        "run_id": RUN,
        "evidence_id": EVIDENCE,
        "actor_id": SUBJECT,
    }


def test_worker_failure_requeues_only_through_the_unconsumed_boundary():
    queue = Queue(intent())
    service = Service(DomainError("RES-0006", "fence unavailable", 503, retryable=True))
    with pytest.raises(DomainError) as caught:
        BuildExecutionWorker(queue, service, environment={PRODUCT_ENABLE_SETTING: "1"}).once(TENANT)
    assert caught.value.code == "RES-0006"
    assert queue.claims == 1
    assert queue.requeues == 1
    assert queue.quarantines == 0
    assert queue.completions == 0


def test_worker_preserves_original_base_exception_when_requeue_fails():
    class BrokenQueue(Queue):
        def quarantine_if_unconsumed(self, item, error_code):
            super().quarantine_if_unconsumed(item, error_code)
            raise RuntimeError("database unavailable")

    queue = BrokenQueue(intent())
    service = Service(KeyboardInterrupt("stop"))
    with pytest.raises(KeyboardInterrupt, match="stop"):
        BuildExecutionWorker(queue, service, environment={PRODUCT_ENABLE_SETTING: "1"}).once(TENANT)
    assert queue.requeues == 0
    assert queue.quarantines == 1
    assert queue.completions == 0


def test_permanent_domain_refusal_uses_terminal_quarantine_not_retry():
    queue = Queue(intent())
    error = DomainError("SYS-0001", "permanent refusal", 503, retryable=False)
    with pytest.raises(DomainError, match="permanent refusal"):
        BuildExecutionWorker(queue, Service(error), environment={PRODUCT_ENABLE_SETTING: "1"}).once(
            TENANT
        )
    assert queue.requeues == 0
    assert queue.quarantines == 1
    assert queue.completions == 0
