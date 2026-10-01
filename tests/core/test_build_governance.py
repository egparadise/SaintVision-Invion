"""PG-free ROOF binding for the future rootless BuildKit adapter."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from inv.build_governance import (
    BUILD_ACTION,
    BuildProviderObservation,
    authorize_build,
    canonical_build_action,
    finalize_build,
    revalidate_build,
)
from inv.contracts import validate_contract
from inv.errors import DomainError
from inv.policy import action_digest


ULID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
TENANT = "123e4567-e89b-12d3-a456-426614174000"
TRACE = "c" * 32
NOW = datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc)
FINAL_NOW = datetime(2026, 10, 1, 6, 1, 2, tzinfo=timezone.utc)


class _Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, *, killed=False, grant=True):
        self.killed = killed
        self.grant = grant
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((" ".join(statement.split()), params))
        if "FROM inv.project_grants" in statement:
            return _Result(
                {"enabled": True, "can_request": True, "can_approve": False} if self.grant else None
            )
        if "FROM inv.business_projects" in statement:
            return _Result(None)
        if "SELECT kill_switch FROM inv.tenant_controls" in statement:
            return _Result({"kill_switch": self.killed})
        raise AssertionError(statement)


def _principal():
    return SimpleNamespace(tenant_id=TENANT, subject_id="operator-subject")


def _request():
    return {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildRequest",
        "tenantId": TENANT,
        "projectId": f"prj_{ULID}",
        "workspaceId": f"wsp_{ULID}",
        "sourceCommitSha": "a" * 40,
        "sourceTreeSha": "b" * 40,
        "contextPath": "services/worker",
        "dockerfilePath": "services/worker/Dockerfile",
        "targetPlatform": "linux/amd64",
        "targetStage": "runtime",
        "networkPolicyId": "none",
        "cachePolicyId": "cachepol_s08-default",
        "secretRefIds": [f"sec_{ULID}"],
        "timeoutSeconds": 300,
    }


def _provider(**changes):
    values = {
        "builder_instance_id": "builder-rootless-01",
        "builder_profile_id": "buildkit-rootless-v1",
        "recovery_epoch": 7,
        "observed_at": NOW - timedelta(seconds=1),
    }
    values.update(changes)
    return BuildProviderObservation(**values)


def _decision(request=None, **changes):
    request = request or _request()
    values = {
        "decisionId": "policy-s08-build-1",
        "tenantId": TENANT,
        "projectId": request["projectId"],
        "subjectId": "operator-subject",
        "effect": "allow",
        "riskLevel": "L1",
        "actionDigest": action_digest(canonical_build_action(request)),
        "expiresAt": "2026-10-01T06:05:00Z",
        "requiredApprovals": 1,
        "approvedBy": [],
    }
    values.update(changes)
    return values


def _plan(request=None, decision=None, provider=None):
    request = request or _request()
    decision = decision or _decision(request)
    provider = provider or _provider()
    return {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildPlan",
        "tenantId": request["tenantId"],
        "projectId": request["projectId"],
        "workspaceId": request["workspaceId"],
        "traceId": TRACE,
        "requestDigest": action_digest(request),
        "actionDigest": action_digest(canonical_build_action(request)),
        "policyDecisionId": decision["decisionId"],
        "policyVersion": "s08-build-v1",
        "policyExpiresAt": decision["expiresAt"],
        "builderInstanceId": provider.builder_instance_id,
        "builderProfileId": provider.builder_profile_id,
        "recoveryEpoch": provider.recovery_epoch,
        "rootless": True,
        "privileged": False,
        "hostAccess": False,
        "networkMode": "none",
        "networkPolicyId": "none",
        "egressAllowlistDigest": "0" * 64,
        "devices": [],
        "binds": [],
        "budget": {
            "cpuMillis": 2000,
            "memoryBytes": 2 * 1024**3,
            "storageBytes": 10 * 1024**3,
        },
        "lease": {
            "leaseId": f"lse_{ULID}",
            "resourceId": f"res_{ULID}",
            "fencingToken": "123e4567-e89b-12d3-a456-426614174000:7",
            "expiresAt": "2026-10-01T06:05:00Z",
        },
        "cacheNamespaceDigest": "e" * 64,
        "secretRefsDigest": "f" * 64,
        "resolvedBaseImageDigests": ["sha256:" + "1" * 64],
    }


def _authorize(conn=None, request=None, decision=None, plan=None, provider=None, now=NOW):
    request = request or _request()
    provider = provider or _provider()
    decision = decision or _decision(request)
    plan = plan or _plan(request, decision, provider)
    return authorize_build(
        conn or _Connection(),
        _principal(),
        request,
        plan,
        decision,
        policy_version="s08-build-v1",
        provider=provider,
        now=now,
    )


def _audit_events(result, plan, decision, cleanup, output_image_digest):
    terminal = {
        "succeeded": "output_verified",
        "failed": "build_failed",
        "cancelled": "build_cancelled",
    }[result]
    names = [
        "request_validated",
        "policy_bound",
        "builder_claimed",
        "build_started",
        "network_decision",
        terminal,
        "cleanup_verified",
    ]
    timestamps = {
        "request_validated": "2026-10-01T05:59:55Z",
        "policy_bound": "2026-10-01T05:59:56Z",
        "builder_claimed": "2026-10-01T05:59:57Z",
        "build_started": "2026-10-01T06:00:00Z",
        "network_decision": "2026-10-01T06:00:01Z",
        terminal: "2026-10-01T06:01:00Z",
        "cleanup_verified": "2026-10-01T06:01:01Z",
    }
    output_digests = {
        terminal: output_image_digest.removeprefix("sha256:") if output_image_digest else None,
        "cleanup_verified": action_digest(cleanup),
    }
    return [
        {
            "event": name,
            "traceId": plan["traceId"],
            "timestamp": timestamps[name],
            "decisionId": decision["decisionId"],
            "inputDigest": action_digest(plan),
            "outputDigest": output_digests.get(name),
        }
        for name in names
    ]


def _receipt(request=None, plan=None, decision=None, result="succeeded"):
    request = request or _request()
    decision = decision or _decision(request)
    plan = plan or _plan(request, decision)
    succeeded = result == "succeeded"
    receipt = {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildReceipt",
        "tenantId": request["tenantId"],
        "projectId": request["projectId"],
        "workspaceId": request["workspaceId"],
        "traceId": plan["traceId"],
        "planDigest": action_digest(plan),
        "sourceCommitSha": request["sourceCommitSha"],
        "sourceTreeSha": request["sourceTreeSha"],
        "outputImageDigest": "sha256:" + "2" * 64 if succeeded else None,
        "outputConfigDigest": "sha256:" + "3" * 64 if succeeded else None,
        "sbomEvidenceDigest": "4" * 64 if succeeded else None,
        "scanEvidenceDigest": "5" * 64 if succeeded else None,
        "cacheInputDigest": "6" * 64,
        "cacheOutputDigest": "7" * 64 if succeeded else None,
        "networkSummaryDigest": "8" * 64,
        "startedAt": "2026-10-01T06:00:00Z",
        "finishedAt": "2026-10-01T06:01:00Z",
        "result": result,
        "cleanup": {
            "leaseReleased": True,
            "builderClaimReleased": True,
            "cgroupRemoved": True,
            "cacheDisposition": "retained" if succeeded else "quarantined",
            "verifiedAt": "2026-10-01T06:01:01Z",
        },
        "auditEvents": [],
    }
    receipt["auditEvents"] = _audit_events(
        result,
        plan,
        decision,
        receipt["cleanup"],
        receipt["outputImageDigest"],
    )
    return receipt


def _evidence(request=None, plan=None, decision=None, receipt=None):
    request = request or _request()
    decision = decision or _decision(request)
    plan = plan or _plan(request, decision)
    receipt = receipt or _receipt(request, plan, decision)
    admitted = _authorize(request=request, decision=decision, plan=plan)
    return finalize_build(
        _Connection(),
        _principal(),
        request,
        plan,
        decision,
        receipt,
        policy_version="s08-build-v1",
        provider=_provider(observed_at=FINAL_NOW - timedelta(seconds=1)),
        now=FINAL_NOW,
        admitted_binding_digest=admitted["bindingDigest"],
        run_id=f"run_{ULID}",
        evidence_id=f"evd_{ULID}",
        actor_id="operator-subject",
    )


def test_authorize_build_binds_live_authority_policy_provider_and_plan():
    conn = _Connection()
    binding = _authorize(conn)
    assert binding["bindingDigest"] == action_digest(
        {k: v for k, v in binding.items() if k != "bindingDigest"}
    )
    assert binding["builderInstanceId"] == "builder-rootless-01"
    assert "project_grants" in conn.statements[0][0]
    assert "tenant_controls" in conn.statements[-1][0]


@pytest.mark.parametrize(
    "conn,decision,provider,expected",
    [
        (_Connection(killed=True), None, None, "AUTH-0061"),
        (_Connection(grant=False), None, None, "AUTH-0030"),
        (
            _Connection(),
            _decision(effect="deny"),
            None,
            "AUTH-0012",
        ),
        (
            _Connection(),
            None,
            _provider(observed_at=NOW - timedelta(seconds=16)),
            "RES-0003",
        ),
    ],
)
def test_authorize_build_fails_closed(conn, decision, provider, expected):
    with pytest.raises(DomainError, match=expected):
        _authorize(conn, decision=decision, provider=provider)


@pytest.mark.parametrize(
    "field,value",
    [
        ("requestDigest", "0" * 64),
        ("actionDigest", "0" * 64),
        ("policyDecisionId", "other"),
        ("policyVersion", "other"),
        ("policyExpiresAt", "2026-10-01T06:04:00Z"),
        ("builderInstanceId", "other"),
        ("builderProfileId", "other"),
        ("recoveryEpoch", 8),
    ],
)
def test_authorize_build_rejects_each_plan_authority_drift(field, value):
    request = _request()
    decision = _decision(request)
    provider = _provider()
    plan = _plan(request, decision, provider)
    plan[field] = value
    with pytest.raises(DomainError, match="VERIFY-0002"):
        _authorize(request=request, decision=decision, provider=provider, plan=plan)


def test_revalidate_build_repeats_live_containment_and_rejects_drift():
    request = _request()
    decision = _decision(request)
    provider = _provider()
    plan = _plan(request, decision, provider)
    admitted = _authorize(request=request, decision=decision, provider=provider, plan=plan)
    with pytest.raises(DomainError, match="AUTH-0061"):
        revalidate_build(
            _Connection(killed=True),
            _principal(),
            request,
            plan,
            decision,
            policy_version="s08-build-v1",
            provider=provider,
            now=NOW,
            admitted_binding_digest=admitted["bindingDigest"],
        )


def test_finalize_build_cannot_emit_evidence_after_kill_switch():
    request = _request()
    decision = _decision(request)
    plan = _plan(request, decision)
    admitted = _authorize(request=request, decision=decision, plan=plan)
    with pytest.raises(DomainError, match="AUTH-0061"):
        finalize_build(
            _Connection(killed=True),
            _principal(),
            request,
            plan,
            decision,
            _receipt(request, plan, decision),
            policy_version="s08-build-v1",
            provider=_provider(observed_at=FINAL_NOW - timedelta(seconds=1)),
            now=FINAL_NOW,
            admitted_binding_digest=admitted["bindingDigest"],
            run_id=f"run_{ULID}",
            evidence_id=f"evd_{ULID}",
            actor_id="operator-subject",
        )


def test_success_receipt_emits_strict_policy_bound_evidence():
    evidence = _evidence()
    validate_contract("EvidenceEnvelope", evidence)
    assert evidence["action"] == BUILD_ACTION
    assert evidence["result"] == "succeeded"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.__setitem__("planDigest", "0" * 64),
        lambda value: value.__setitem__("sourceCommitSha", "0" * 40),
        lambda value: value.__setitem__("sourceTreeSha", "0" * 40),
        lambda value: value.__setitem__("traceId", "0" * 32),
        lambda value: value["auditEvents"][0].__setitem__("traceId", "0" * 32),
        lambda value: value["auditEvents"][0].__setitem__("decisionId", "other"),
        lambda value: value["auditEvents"][0].__setitem__("inputDigest", "0" * 64),
        lambda value: value["auditEvents"].reverse(),
        lambda value: value["auditEvents"].append(deepcopy(value["auditEvents"][0])),
    ],
)
def test_build_evidence_rejects_scope_digest_and_audit_drift(mutate):
    receipt = _receipt()
    mutate(receipt)
    with pytest.raises(DomainError, match="VERIFY-0002"):
        _evidence(receipt=receipt)


@pytest.mark.parametrize("field", ["leaseReleased", "builderClaimReleased", "cgroupRemoved"])
def test_build_evidence_requires_verified_cleanup(field):
    receipt = _receipt(result="failed")
    receipt["cleanup"][field] = False
    with pytest.raises(DomainError, match="VERIFY-0022"):
        _evidence(receipt=receipt)


@pytest.mark.parametrize(
    "result,terminal", [("failed", "build_failed"), ("cancelled", "build_cancelled")]
)
def test_non_success_receipt_requires_terminal_audit_and_quarantined_cache(result, terminal):
    receipt = _receipt(result=result)
    evidence = _evidence(receipt=receipt)
    assert evidence["result"] == "failed"

    missing = deepcopy(receipt)
    missing["auditEvents"] = [
        event for event in missing["auditEvents"] if event["event"] != terminal
    ]
    with pytest.raises(DomainError, match="VERIFY-0002"):
        _evidence(receipt=missing)

    retained = deepcopy(receipt)
    retained["cleanup"]["cacheDisposition"] = "retained"
    with pytest.raises(DomainError, match="VERIFY-0022"):
        _evidence(receipt=retained)


def test_build_evidence_rejects_reverse_time():
    receipt = _receipt()
    receipt["finishedAt"] = "2026-10-01T05:59:59Z"
    with pytest.raises(DomainError, match="VERIFY-0002"):
        _evidence(receipt=receipt)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["auditEvents"][3].__setitem__("timestamp", "2026-10-01T06:00:02Z"),
        lambda value: value["auditEvents"][5].__setitem__("outputDigest", "0" * 64),
        lambda value: value["auditEvents"][6].__setitem__("outputDigest", "0" * 64),
        lambda value: value["cleanup"].__setitem__("verifiedAt", "2026-10-01T06:01:02Z"),
        lambda value: value["auditEvents"].insert(
            6,
            {
                **deepcopy(value["auditEvents"][5]),
                "event": "build_cancelled",
                "outputDigest": None,
            },
        ),
    ],
)
def test_build_evidence_rejects_audit_receipt_drift(mutate):
    receipt = _receipt()
    mutate(receipt)
    with pytest.raises(DomainError, match="VERIFY-0002"):
        _evidence(receipt=receipt)
