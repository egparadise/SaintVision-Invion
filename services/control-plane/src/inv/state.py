"""The deterministic Run state machine, independent of AI and transport."""

from enum import StrEnum
from .errors import DomainError


class RunState(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL = {RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED}
FORWARD = {
    RunState.DRAFT: {RunState.VALIDATED},
    RunState.VALIDATED: {RunState.PLANNED},
    RunState.PLANNED: {RunState.AWAITING_APPROVAL, RunState.SCHEDULED},
    RunState.AWAITING_APPROVAL: {RunState.SCHEDULED},
    RunState.SCHEDULED: {RunState.RUNNING},
    RunState.RUNNING: {RunState.VERIFYING, RunState.RECOVERING},
    RunState.VERIFYING: {RunState.SUCCEEDED, RunState.RECOVERING},
    RunState.RECOVERING: {RunState.SCHEDULED, RunState.AWAITING_APPROVAL},
}


def check_transition(
    current: str, target: str, *, evidence_ready: bool = False
) -> None:
    try:
        before, after = RunState(current), RunState(target)
    except ValueError as error:
        raise DomainError("GRAPH-0001", "Unknown run state") from error
    if before == after:
        return
    allowed = FORWARD.get(before, set()) | (
        {RunState.FAILED, RunState.CANCELLED} if before not in TERMINAL else set()
    )
    if after not in allowed:
        raise DomainError("GRAPH-0002", f"Invalid transition {before} -> {after}")
    if after == RunState.SUCCEEDED and not evidence_ready:
        raise DomainError("VERIFY-0001", "Verified evidence is required for success")
