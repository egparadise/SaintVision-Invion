"""Why a workspace cannot run yet, and who resolves each reason.

**Execution results are not here.** ``inv.result_view.ResultView`` is the
authoritative reader for what a Run produced, and the kernel app serves
``/v1/runs/{id}/result``, ``/artifacts`` and ``/artifacts/content``. This side
briefly had its own versions on the same paths — two applications answering one
URL with different answers, which is worse than either being wrong, because
whichever is deployed behind the path decides and nothing reports the
disagreement. They are gone.

The distinction worth keeping is that a result reader answers "what happened"
and this answers "why nothing can happen yet". The second is a business-surface
question: it spans project membership, an operator's kernel links, a workspace
lifecycle and a tool installed on a machine, and no single one of those is the
kernel's to report.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...identity.principal import Principal
from ...services import execution_readiness as readiness_service
from .. import schemas
from ..deps import get_principal, get_session

router = APIRouter(prefix="/v1", tags=["readiness"])


@router.get(
    "/workspaces/{workspace_id}/execution-readiness",
    response_model=schemas.WorkspaceExecutionReadinessResponse,
    response_model_exclude_unset=True,
)
def read_execution_readiness(
    workspace_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    """Every precondition for running work here, and who resolves each unmet one.

    Reported together rather than one at a time: the failure a user otherwise
    meets is whichever precondition the execution path checked first, described
    as an authorisation error — which is the right words for exactly one of the
    conditions, and sends people to change a role that was never the problem.
    """
    return readiness_service.workspace_readiness(
        session,
        tenant_id=principal.tenant_id,
        workspace_id=workspace_id,
        user_id=principal.user_id,
    )
