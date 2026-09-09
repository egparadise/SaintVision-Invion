"""Validate a trusted policy decision; this is not a replacement for OPA."""

from datetime import datetime
import hashlib
import json
from .errors import DomainError
from .contracts import validate_contract


def action_digest(action: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            action, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def enforce_decision(
    decision: dict | None,
    *,
    action: dict,
    tenant_id: str,
    project_id: str,
    subject_id: str,
    now: datetime
) -> None:
    # Caller must obtain decision from authenticated PDP storage, never directly from
    # model/user JSON. Nonce consumption and one-shot execution belong in a transaction.
    if not decision or now.tzinfo is None:
        raise DomainError("AUTH-0010", "Policy unavailable", 403)
    validate_contract("PolicyDecision", decision)
    expected = {
        "tenantId": tenant_id,
        "projectId": project_id,
        "subjectId": subject_id,
        "actionDigest": action_digest(action),
    }
    if any(decision.get(k) != v for k, v in expected.items()):
        raise DomainError("AUTH-0011", "Decision scope does not match", 403)
    try:
        expires = datetime.fromisoformat(decision["expiresAt"].replace("Z", "+00:00"))
        fresh = expires.tzinfo is not None and expires > now
    except (KeyError, ValueError, AttributeError):
        fresh = False
    if not fresh or decision.get("effect") not in {"allow", "require_approval"}:
        raise DomainError("AUTH-0012", "Decision expired or denied", 403)
    risk = decision.get("riskLevel")
    if risk not in {"L0", "L1", "L2", "L3"} or risk == "L3":
        raise DomainError("AUTH-0013", "Risk level is blocked", 403)
    if risk == "L2" or decision["effect"] == "require_approval":
        approved = decision.get("approvedBy", [])
        count = decision.get("requiredApprovals", 1)
        if (
            type(count) is not int
            or count not in {1, 2}
            or not isinstance(approved, list)
            or any(not isinstance(x, str) or not x for x in approved)
        ):
            raise DomainError("AUTH-0014", "Invalid approval requirement", 403)
        if len(set(approved)) < count:
            raise DomainError("AUTH-0014", "Required approvals missing", 403)
