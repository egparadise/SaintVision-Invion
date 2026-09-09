"""Error contract.

RFC 9457 problem details plus the project fields ``code``/``category``/
``retryable``/``traceId``/``causeRef``/``evidenceId`` (PLAN-BACKEND-001, 공통 계약 §6).

The category is derived from the code prefix so the two can never disagree, and
``retryable`` is a property of the category rather than a per-call opinion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final


class ErrorCategory(str, Enum):
    VALIDATION = "VAL"
    AUTH = "AUTH"
    CONTEXT = "CTX"
    TOOL = "TOOL"
    RESOURCE = "RES"
    NETWORK = "NET"
    GRAPH = "GRAPH"
    VERIFY = "VERIFY"
    SECURITY = "SEC"
    BUDGET = "BUDGET"


#: Default retryability per 공통 계약 §6. TOOL is retryable only after an
#: idempotency check, which the caller performs; the flag alone does not license
#: a retry of a non-idempotent side effect.
_RETRYABLE: Final[dict[ErrorCategory, bool]] = {
    ErrorCategory.VALIDATION: False,
    ErrorCategory.AUTH: False,
    ErrorCategory.CONTEXT: True,
    ErrorCategory.TOOL: True,
    ErrorCategory.RESOURCE: True,
    ErrorCategory.NETWORK: True,
    ErrorCategory.GRAPH: False,
    ErrorCategory.VERIFY: False,
    ErrorCategory.SECURITY: False,
    ErrorCategory.BUDGET: False,
}

_STATUS: Final[dict[ErrorCategory, int]] = {
    ErrorCategory.VALIDATION: 422,
    ErrorCategory.AUTH: 403,
    ErrorCategory.CONTEXT: 409,
    ErrorCategory.TOOL: 502,
    ErrorCategory.RESOURCE: 409,
    ErrorCategory.NETWORK: 503,
    ErrorCategory.GRAPH: 409,
    ErrorCategory.VERIFY: 422,
    ErrorCategory.SECURITY: 403,
    ErrorCategory.BUDGET: 429,
}

PROBLEM_CONTENT_TYPE: Final[str] = "application/problem+json"
_TYPE_BASE: Final[str] = "https://saintvision.invenio/problems/"


def category_of(code: str) -> ErrorCategory:
    """Derive the category from the code prefix. Raises on an unknown family."""
    head = code.split("-", 1)[0]
    try:
        return ErrorCategory(head)
    except ValueError:
        raise ValueError(f"error code {code!r} has no known category prefix") from None


@dataclass(slots=True)
class InvError(Exception):
    """A failure that has a contract-visible representation.

    ``message`` is the internal string; it is mapped onto the problem ``detail``
    only when ``public`` is true. Anything that could carry a secret, a path, or
    a token must stay internal (ADR-014).
    """

    code: str
    message: str
    status: int | None = None
    public: bool = True
    retryable: bool | None = None
    cause_ref: str | None = None
    evidence_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.category = category_of(self.code)
        if self.status is None:
            self.status = _STATUS[self.category]
        if self.retryable is None:
            self.retryable = _RETRYABLE[self.category]
        super().__init__(self.message)

    category: ErrorCategory = field(init=False)

    def to_problem(self, *, trace_id: str, instance: str | None = None) -> dict[str, Any]:
        problem: dict[str, Any] = {
            "type": _TYPE_BASE + self.code.lower(),
            "title": self.code,
            "status": self.status,
            "code": self.code,
            "category": self.category.value,
            "retryable": self.retryable,
            "traceId": trace_id,
        }
        if self.public:
            problem["detail"] = self.message
        if instance is not None:
            problem["instance"] = instance
        problem["causeRef"] = self.cause_ref
        problem["evidenceId"] = self.evidence_id
        problem.update(self.extra)
        return problem


# Codes used by this sprint. Kept in one place so the audit reason codes and the
# API surface cannot drift apart.
VAL_SCHEMA = "VAL-SCHEMA"
VAL_PATH_UNSAFE = "VAL-PATH-UNSAFE"
VAL_CURSOR = "VAL-CURSOR"
AUTH_MISSING_CREDENTIAL = "AUTH-MISSING-CREDENTIAL"
AUTH_INVALID_CREDENTIAL = "AUTH-INVALID-CREDENTIAL"
AUTH_TENANT_SCOPE = "AUTH-TENANT-SCOPE"
AUTH_PROJECT_SCOPE = "AUTH-PROJECT-SCOPE"
AUTH_BOOTSTRAP_TOKEN_INVALID = "AUTH-BOOTSTRAP-TOKEN-INVALID"
AUTH_BOOTSTRAP_TOKEN_CONSUMED = "AUTH-BOOTSTRAP-TOKEN-CONSUMED"
AUTH_BOOTSTRAP_TOKEN_EXPIRED = "AUTH-BOOTSTRAP-TOKEN-EXPIRED"
RES_NODE_NOT_FOUND = "RES-NODE-NOT-FOUND"
RES_CONTRIBUTION_NOT_FOUND = "RES-CONTRIBUTION-NOT-FOUND"
RES_HEARTBEAT_STALE = "RES-HEARTBEAT-STALE"
RES_PARTITION_EXHAUSTED = "RES-PARTITION-EXHAUSTED"
GRAPH_IDEMPOTENCY_CONFLICT = "GRAPH-IDEMPOTENCY-CONFLICT"
SEC_TENANT_SCOPE_UNSET = "SEC-TENANT-SCOPE-UNSET"
