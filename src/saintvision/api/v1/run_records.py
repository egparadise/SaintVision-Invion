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

from ...db.models.context import RunRecordArtifact
from ...errors import (
    AUTH_PROJECT_SCOPE,
    RES_ARTIFACT_NOT_FOUND,
    RES_RUN_NOT_FOUND,
    VAL_SCHEMA,
    InvError,
)
from ...identity.principal import Principal
from ...ids import is_id
from ...services import records as record_service
from .. import schemas
from ..deps import get_principal, get_session
from ..problem import (
    AUTH_PROJECT,
    RES_NOT_FOUND,
    VAL_REQUEST,
    CanonicalProblem,
    read_bounded_body,
    require_absent_body,
    translate,
)
from .lineage_query import _cursor, _limit, _membership, _query
from .project_scope import run_in_project

RECORD_PATH = "/projects/{project_id}/runs/{run_id}/record"
ARTIFACTS_PATH = RECORD_PATH + "/artifacts"
VERIFY_PATH = ARTIFACTS_PATH + "/{artifact_id}/verify"

#: Every ``InvError`` these routes can reach, and its canonical form. A code
#: not listed becomes ``SYS-0002`` (the shared module's rule), and the PG-free
#: suite enumerates the reachable codes so the table stays complete.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
    RES_RUN_NOT_FOUND: (RES_NOT_FOUND, 404, False),
    #: R2: an artifact that is not pinned to this record; also a malformed role.
    RES_ARTIFACT_NOT_FOUND: (RES_NOT_FOUND, 404, False),
    VAL_SCHEMA: (VAL_REQUEST, 422, False),
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


def _sealed_record(session: Session, *, principal: Principal, project_id: str, run_id: str):
    """The run bound to the path's project, then its sealed record, or the canonical error.

    Membership is checked by the caller *before* the request body is judged
    (Codex #184 F2), so this helper starts at the binding.
    """
    run = run_in_project(
        session, tenant_id=principal.tenant_id, project_id=project_id, run_id=run_id
    )
    try:
        return record_service.get_record(
            session, tenant_id=principal.tenant_id, run_id=run.run_id
        )
    except InvError as error:
        raise translate(error, table=TRANSLATION, detail="No sealed record for this run.") from None


def _pin(row) -> schemas.RunRecordArtifactPin:
    return schemas.RunRecordArtifactPin(
        artifact_id=row.artifact_id,
        role=row.role,
        uri=row.uri,
        checksum_sha256=row.checksum_sha256,
        object_version=row.object_version,
        byte_size=int(row.byte_size or 0),
    )


async def read_run_record_artifacts(
    project_id: str,
    run_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> schemas.RunRecordArtifactPageResponse:
    """R2: one bounded page of the artifacts pinned into the record.

    ``role``, ``limit`` and ``cursor`` are the query parameters; ``limit`` and
    ``cursor`` are judged by the shared #175 helpers before any row is read,
    and an unknown role is the service's refusal (``VAL-0003``), so the route
    keeps no copy of the allowed roles. The record pins the run's whole
    artifact set, so the page is the bound (Codex #188 F2).
    """
    _membership(session, principal=principal, project_id=project_id)
    require_absent_body(await read_bounded_body(request))
    query = _query(request, allowed=frozenset({"role", "limit", "cursor"}))
    limit = _limit(query.get("limit"))
    cursor = _cursor(query.get("cursor"))
    record = _sealed_record(session, principal=principal, project_id=project_id, run_id=run_id)
    try:
        page = record_service.page_pinned_artifacts(
            session,
            tenant_id=principal.tenant_id,
            record_id=record.record_id,
            role=query.get("role"),
            limit=limit,
            cursor=cursor,
        )
    except InvError as error:
        raise translate(error, table=TRANSLATION, detail="Unknown artifact role.") from None
    return schemas.RunRecordArtifactPageResponse(
        record_id=record.record_id,
        run_id=record.run_id,
        role=query.get("role"),
        items=[_pin(row) for row in page.items],
        count=len(page.items),
        next_cursor=page.next_cursor,
    )


async def verify_run_record_artifact(
    project_id: str,
    run_id: str,
    artifact_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> schemas.ArtifactPinVerificationResponse:
    """R2: whether the artifact still matches the digest the record pinned.

    ``verified: false`` is a fact reported with 200 -- the record is the account
    of what was true at sealing, and a changed object is an integrity finding,
    not a request error. An artifact that is not pinned to this record is the
    same 404 as one that does not exist.
    """
    _membership(session, principal=principal, project_id=project_id)
    require_absent_body(await read_bounded_body(request))
    record = _sealed_record(session, principal=principal, project_id=project_id, run_id=run_id)
    if not is_id(artifact_id, "artifact"):
        raise CanonicalProblem(RES_NOT_FOUND, 404, "No such pinned artifact.")
    try:
        verified = record_service.verify_pin(
            session, tenant_id=principal.tenant_id, record_id=record.record_id, artifact_id=artifact_id
        )
    except InvError as error:
        raise translate(error, table=TRANSLATION, detail="No such pinned artifact.") from None
    pinned = session.get(RunRecordArtifact, (principal.tenant_id, record.record_id, artifact_id))
    if pinned is None or not pinned.checksum_sha256:
        # The service found the pin a moment ago; a pin that is gone now is not
        # a verified answer with a null digest (fail-open), it is no answer.
        raise CanonicalProblem(RES_NOT_FOUND, 404, "No such pinned artifact.")
    return schemas.ArtifactPinVerificationResponse(
        record_id=record.record_id,
        run_id=record.run_id,
        artifact_id=artifact_id,
        verified=bool(verified),
        pinned_checksum_sha256=pinned.checksum_sha256,
    )


def register(router: APIRouter) -> None:
    """Add the routes to the projects router (same reason as ``lineage_query``)."""
    router.add_api_route(
        RECORD_PATH,
        read_run_record,
        methods=["GET"],
        response_model=schemas.RunRecordResponse,
        tags=["run-records"],
        name="read_run_record",
    )
    router.add_api_route(
        ARTIFACTS_PATH,
        read_run_record_artifacts,
        methods=["GET"],
        response_model=schemas.RunRecordArtifactPageResponse,
        tags=["run-records"],
        name="read_run_record_artifacts",
    )
    router.add_api_route(
        VERIFY_PATH,
        verify_run_record_artifact,
        methods=["GET"],
        response_model=schemas.ArtifactPinVerificationResponse,
        tags=["run-records"],
        name="verify_run_record_artifact",
    )
