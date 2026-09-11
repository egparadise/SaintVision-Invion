"""Results, logs, artifacts, and why a workspace cannot run yet.

The read side a screen binds to. Two rules, both aimed at the same failure.

**Nothing is ever substituted for a fact that is missing.** A digest nobody
computed is ``null`` with a stated reason beside it — never a zero hash. A size
nobody measured is ``null`` — never ``0``, never a round number. An Evidence id
that does not exist is ``null``. This is not defensive style: the studio screen
that calls these endpoints was found rendering a fixed hash, 1,024 bytes and an
invented Evidence id whenever the server did not answer, and an API that returns
plausibly-shaped emptiness is half of how that happens.

**A refusal says who can lift it.** `execution-readiness` reports all five
preconditions at once with the owner of each, because "you are not allowed" and
"an operator has not finished setting this up" feel identical to whoever is
blocked and need different people to act.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...identity.principal import Principal
from ...services import execution_readiness as readiness_service
from ...services import results as results_service
from ..deps import get_principal, get_session

router = APIRouter(tags=["results"])


@router.get("/runs/{run_id}/result")
def read_run_result(
    run_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    """What this Run produced, with every gap named rather than filled.

    ``sealed`` distinguishes "no record yet" from "a record with empty fields",
    which is the distinction that matters when someone is deciding whether a job
    really ran.
    """
    return results_service.run_result(
        session,
        tenant_id=principal.tenant_id,
        run_id=run_id,
        user_id=principal.user_id,
    )


@router.get("/runs/{run_id}/artifacts")
def list_run_artifacts(
    run_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    """Files this Run produced.

    ``verified`` is true only when something verified them. An artifact that
    carries a digest and was never checked is the one a screen is most likely to
    present as confirmed, because it looks complete.
    """
    items = results_service.list_artifacts(
        session,
        tenant_id=principal.tenant_id,
        run_id=run_id,
        user_id=principal.user_id,
    )
    return {
        "runId": run_id,
        "artifacts": items,
        "count": len(items),
        "verifiedCount": sum(1 for a in items if a["verified"]),
    }


@router.get("/runs/{run_id}/attempts")
def read_attempt_log(
    run_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    """What happened, attempt by attempt.

    Process output lives with the node and is collected through the adapter;
    this is the record of each attempt, which is the part that survives the
    machine being turned off.
    """
    items = results_service.attempt_log(
        session,
        tenant_id=principal.tenant_id,
        run_id=run_id,
        user_id=principal.user_id,
    )
    return {"runId": run_id, "attempts": items, "count": len(items)}


@router.get("/workspaces/{workspace_id}/execution-readiness")
def read_execution_readiness(
    workspace_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    """Every precondition for running work here, and who resolves each unmet one.

    Reported together rather than one at a time: the failure a user otherwise
    meets is whichever precondition the execution path checked first, described
    as an authorisation error — which is the right words for exactly one of
    them.
    """
    return readiness_service.workspace_readiness(
        session,
        tenant_id=principal.tenant_id,
        workspace_id=workspace_id,
        user_id=principal.user_id,
    )
