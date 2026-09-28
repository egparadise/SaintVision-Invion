"""R1: read the sealed record of a run (G-04 design v1.1 §2, PR 1 of 8).

``GET /projects/{project_id}/runs/{run_id}/record``

Read grade is live project membership, checked the way ``lineage_query`` does
it (``require_project_access``, not the sign-in snapshot). The path's project is
bound to the run through its workload (``project_scope.run_in_project``) before
the record is read, so a run in another project is the same 404 as a run that
does not exist. The response is the strict ``RunRecordResponse``: identifiers,
digests and counts only -- no person, no free text, no evidence content.

The service is called, not re-implemented: ``records.get_record`` decides what
"no sealed record" means; this route only translates its error into the
canonical body.
"""

from __future__ import annotations

from typing import Mapping

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ...errors import AUTH_PROJECT_SCOPE, RES_RUN_NOT_FOUND, InvError
from ...identity.principal import Principal
from ...services import records as record_service
from .. import schemas
from ..deps import get_principal, get_session
from ..problem import (
    AUTH_PROJECT,
    RES_NOT_FOUND,
    read_bounded_body,
    require_absent_body,
    translate,
)
from .lineage_query import _membership
from .project_scope import run_in_project

RECORD_PATH = "/projects/{project_id}/runs/{run_id}/record"

#: Every ``InvError`` this route can reach, and its canonical form. A code not
#: listed becomes ``SYS-0002`` (the shared module's rule), and the PG-free
#: suite enumerates the reachable codes so the table stays complete.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
    RES_RUN_NOT_FOUND: (RES_NOT_FOUND, 404, False),
}


def _response(record) -> schemas.RunRecordResponse:
    return schemas.RunRecordResponse(
        record_id=record.record_id,
        run_id=record.run_id,
        final_state=record.final_state,
        termination_reason=record.termination_reason,
        evidence_id=record.evidence_id,
        bundle_id=record.bundle_id,
        bundle_hash=record.bundle_hash,
        workload_spec_sha256=record.workload_spec_sha256,
        component_versions=dict(record.component_versions or {}),
        attempt_count=int(record.attempt_count),
        sealed_at=record.sealed_at,
    )


async def read_run_record(
    project_id: str,
    run_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> schemas.RunRecordResponse:
    # Live membership first, so a non-member learns nothing from how the body is
    # judged; then the shared bounded reader refuses a body (bounded, so an
    # oversized one is 413/422 rather than an allocation), as ``model_release`` does.
    _membership(session, principal=principal, project_id=project_id)
    require_absent_body(await read_bounded_body(request))
    run = run_in_project(
        session, tenant_id=principal.tenant_id, project_id=project_id, run_id=run_id
    )
    try:
        record = record_service.get_record(
            session, tenant_id=principal.tenant_id, run_id=run.run_id
        )
    except InvError as error:
        raise translate(error, table=TRANSLATION, detail="No sealed record for this run.") from None
    return _response(record)


def register(router: APIRouter) -> None:
    """Add the route to the projects router (same reason as ``lineage_query``)."""
    router.add_api_route(
        RECORD_PATH,
        read_run_record,
        methods=["GET"],
        response_model=schemas.RunRecordResponse,
        tags=["run-records"],
        name="read_run_record",
    )
