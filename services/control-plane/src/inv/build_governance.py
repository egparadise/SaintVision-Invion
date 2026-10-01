"""ROOF boundary for a future rootless BuildKit adapter.

This module performs no build and exposes no HTTP route.  An adapter must call
``authorize_build`` in its short pre-dispatch transaction, perform the external
call without a business transaction, then call ``revalidate_build`` in a new
transaction before accepting a receipt.  The second call deliberately repeats
live project authority, tenant containment, policy, and provider checks.
"""

from dataclasses import dataclass
from datetime import datetime

from .business_auth import permission as business_permission
from .containment import require_execution
from .contracts import validate_contract
from .errors import DomainError
from .policy import action_digest, enforce_decision


BUILD_ACTION = "runtime.build.execute"
PROVIDER_FRESHNESS_SECONDS = 15
_AUDIT_ORDER = (
    "request_validated",
    "policy_bound",
    "builder_claimed",
    "build_started",
    "network_decision",
    "output_verified",
    "build_failed",
    "build_cancelled",
    "cleanup_verified",
)


@dataclass(frozen=True)
class BuildProviderObservation:
    builder_instance_id: str
    builder_profile_id: str
    recovery_epoch: int
    observed_at: datetime


def canonical_build_action(request: dict) -> dict:
    """Return the only action shape accepted by the build policy boundary."""

    validate_contract("BuildRequest", request)
    return {
        "action": BUILD_ACTION,
        "tenantId": request["tenantId"],
        "projectId": request["projectId"],
        "workspaceId": request["workspaceId"],
        "requestDigest": action_digest(request),
    }


def _project_authority(conn, principal, project_id: str) -> None:
    row = conn.execute(
        "SELECT * FROM inv.project_grants WHERE project_id=%s AND subject_id=%s FOR SHARE",
        (project_id, principal.subject_id),
    ).fetchone()
    if not row or not row["enabled"] or not row["can_request"]:
        raise DomainError("AUTH-0030", "Project permission is unavailable", 403)
    business_permission(conn, project_id, principal.subject_id, "can_request")


def _provider_fresh(provider: BuildProviderObservation, now: datetime) -> bool:
    if (
        not isinstance(provider.builder_instance_id, str)
        or not provider.builder_instance_id
        or not isinstance(provider.builder_profile_id, str)
        or not provider.builder_profile_id
        or type(provider.recovery_epoch) is not int
        or provider.recovery_epoch < 1
        or provider.observed_at.tzinfo is None
        or now.tzinfo is None
    ):
        return False
    age = (now - provider.observed_at).total_seconds()
    return 0 <= age <= PROVIDER_FRESHNESS_SECONDS


def _binding(
    request: dict,
    plan: dict,
    decision: dict,
    *,
    policy_version: str,
    provider: BuildProviderObservation,
) -> dict:
    expected = {
        "tenantId": request["tenantId"],
        "projectId": request["projectId"],
        "workspaceId": request["workspaceId"],
        "requestDigest": action_digest(request),
        "actionDigest": action_digest(canonical_build_action(request)),
        "policyDecisionId": decision["decisionId"],
        "policyVersion": policy_version,
        "policyExpiresAt": decision["expiresAt"],
        "builderInstanceId": provider.builder_instance_id,
        "builderProfileId": provider.builder_profile_id,
        "recoveryEpoch": provider.recovery_epoch,
    }
    if (
        not isinstance(policy_version, str)
        or not policy_version
        or any(plan.get(field) != value for field, value in expected.items())
    ):
        raise DomainError("VERIFY-0002", "Build plan authority differs", 422)
    return {
        "requestDigest": expected["requestDigest"],
        "actionDigest": expected["actionDigest"],
        "planDigest": action_digest(plan),
        "policyDecisionId": decision["decisionId"],
        "builderInstanceId": provider.builder_instance_id,
        "builderProfileId": provider.builder_profile_id,
        "recoveryEpoch": provider.recovery_epoch,
    }


def authorize_build(
    conn,
    principal,
    request: dict,
    plan: dict,
    decision: dict,
    *,
    policy_version: str,
    provider: BuildProviderObservation,
    now: datetime,
) -> dict:
    """Authorize one pre-dispatch or final-commit boundary check."""

    validate_contract("BuildRequest", request)
    validate_contract("BuildPlan", plan)
    if request["tenantId"] != principal.tenant_id:
        raise DomainError("AUTH-0011", "Decision scope does not match", 403)
    _project_authority(conn, principal, request["projectId"])
    require_execution(conn)
    action = canonical_build_action(request)
    enforce_decision(
        decision,
        action=action,
        tenant_id=principal.tenant_id,
        project_id=request["projectId"],
        subject_id=principal.subject_id,
        now=now,
    )
    if not _provider_fresh(provider, now):
        raise DomainError("RES-0003", "Build provider observation is stale", 409)
    binding = _binding(
        request,
        plan,
        decision,
        policy_version=policy_version,
        provider=provider,
    )
    return {**binding, "bindingDigest": action_digest(binding)}


def revalidate_build(
    conn,
    principal,
    request: dict,
    plan: dict,
    decision: dict,
    *,
    policy_version: str,
    provider: BuildProviderObservation,
    now: datetime,
    admitted_binding_digest: str,
) -> dict:
    """Repeat every live check after the external call and reject drift."""

    current = authorize_build(
        conn,
        principal,
        request,
        plan,
        decision,
        policy_version=policy_version,
        provider=provider,
        now=now,
    )
    if current["bindingDigest"] != admitted_binding_digest:
        raise DomainError("VERIFY-0002", "Build admission changed", 422)
    return current


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise DomainError("VERIFY-0002", "Build receipt timestamp differs", 422) from None
    if parsed.tzinfo is None:
        raise DomainError("VERIFY-0002", "Build receipt timestamp differs", 422)
    return parsed


def _build_evidence(
    request: dict,
    plan: dict,
    decision: dict,
    receipt: dict,
    *,
    run_id: str,
    evidence_id: str,
    actor_id: str,
) -> dict:
    """Validate completion, cleanup and ordered audit before emitting Evidence."""

    validate_contract("BuildRequest", request)
    validate_contract("BuildPlan", plan)
    validate_contract("PolicyDecision", decision)
    validate_contract("BuildReceipt", receipt)
    plan_digest = action_digest(plan)
    if any(
        (
            receipt["tenantId"] != request["tenantId"],
            receipt["projectId"] != request["projectId"],
            receipt["workspaceId"] != request["workspaceId"],
            receipt["traceId"] != plan["traceId"],
            receipt["planDigest"] != plan_digest,
            receipt["sourceCommitSha"] != request["sourceCommitSha"],
            receipt["sourceTreeSha"] != request["sourceTreeSha"],
            plan["policyDecisionId"] != decision["decisionId"],
        )
    ):
        raise DomainError("VERIFY-0002", "Build receipt authority differs", 422)
    started, finished = _timestamp(receipt["startedAt"]), _timestamp(receipt["finishedAt"])
    if finished < started:
        raise DomainError("VERIFY-0002", "Build receipt timestamp differs", 422)

    cleanup = receipt["cleanup"]
    if not all(
        cleanup[field] is True
        for field in ("leaseReleased", "builderClaimReleased", "cgroupRemoved")
    ):
        raise DomainError("VERIFY-0022", "Build cleanup is not verified", 409)
    if receipt["result"] != "succeeded" and cleanup["cacheDisposition"] == "retained":
        raise DomainError("VERIFY-0022", "Failed build cache is not isolated", 409)

    events = receipt["auditEvents"]
    names = [event["event"] for event in events]
    required = {
        "request_validated",
        "policy_bound",
        "builder_claimed",
        "build_started",
        "network_decision",
        "cleanup_verified",
    }
    required.add(
        "output_verified"
        if receipt["result"] == "succeeded"
        else "build_cancelled" if receipt["result"] == "cancelled" else "build_failed"
    )
    if (
        set(names) != required
        or names != sorted(names, key=_AUDIT_ORDER.index)
        or any(
            event["traceId"] != plan["traceId"]
            or event["decisionId"] != decision["decisionId"]
            or event["inputDigest"] != plan_digest
            for event in events
        )
    ):
        raise DomainError("VERIFY-0002", "Build audit binding differs", 422)
    by_name = {event["event"]: event for event in events}
    event_times = [_timestamp(event["timestamp"]) for event in events]
    terminal = (
        "output_verified"
        if receipt["result"] == "succeeded"
        else "build_cancelled" if receipt["result"] == "cancelled" else "build_failed"
    )
    output_digest = (
        receipt["outputImageDigest"].removeprefix("sha256:")
        if receipt["result"] == "succeeded"
        else None
    )
    if (
        event_times != sorted(event_times)
        or by_name["build_started"]["timestamp"] != receipt["startedAt"]
        or by_name[terminal]["timestamp"] != receipt["finishedAt"]
        or by_name[terminal]["outputDigest"] != output_digest
        or by_name["cleanup_verified"]["timestamp"] != cleanup["verifiedAt"]
        or by_name["cleanup_verified"]["outputDigest"] != action_digest(cleanup)
        or _timestamp(cleanup["verifiedAt"]) < finished
    ):
        raise DomainError("VERIFY-0002", "Build audit receipt differs", 422)

    evidence = {
        "evidenceId": evidence_id,
        "tenantId": request["tenantId"],
        "runId": run_id,
        "traceId": plan["traceId"],
        "timestamp": receipt["finishedAt"],
        "actorId": actor_id,
        "action": BUILD_ACTION,
        "policyDecisionId": decision["decisionId"],
        "inputSha256": plan_digest,
        "outputSha256": action_digest(receipt),
        "result": "succeeded" if receipt["result"] == "succeeded" else "failed",
    }
    validate_contract("EvidenceEnvelope", evidence)
    return evidence


def finalize_build(
    conn,
    principal,
    request: dict,
    plan: dict,
    decision: dict,
    receipt: dict,
    *,
    policy_version: str,
    provider: BuildProviderObservation,
    now: datetime,
    admitted_binding_digest: str,
    run_id: str,
    evidence_id: str,
    actor_id: str,
) -> dict:
    """Revalidate live authority before any completion Evidence can exist."""

    revalidate_build(
        conn,
        principal,
        request,
        plan,
        decision,
        policy_version=policy_version,
        provider=provider,
        now=now,
        admitted_binding_digest=admitted_binding_digest,
    )
    return _build_evidence(
        request,
        plan,
        decision,
        receipt,
        run_id=run_id,
        evidence_id=evidence_id,
        actor_id=actor_id,
    )
