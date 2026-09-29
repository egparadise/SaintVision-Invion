"""Read lineage: forward from a model version, backward from a dataset digest.

``trace_model`` has existed and been tested since S10-DB landed, and no HTTP
request could reach it (#144/#146). The reverse direction -- "which model
versions were built from these bytes" -- had no function at all. These two routes
are that request path, and nothing here writes a row or an audit entry.

**What these routes can and cannot prove.** Only ``models`` and ``datasets``
carry ``project_id``; ``code_commits``, ``container_images``, ``eval_runs`` and
``approvals`` carry none, at any depth. So a project member can be served dataset
and deployment detail, and for the rest only a count -- and ``fullyTraceable`` is
therefore false for almost every real model version. ``traceabilityLimitedByScope``
exists so that false is legible as a permission boundary rather than as a
recording gap. Lifting it needs either a tenant-wide lineage grade or a
``project_id`` backfill, both out of this card's scope.

**Query parsing.** Constrained FastAPI annotations are avoided on purpose:
FastAPI validates them before the handler runs and its ``RequestValidationError``
handler adds a top-level ``fields`` key the canonical ``ProblemDetails`` forbids.
The allowed keys are an exact set, a repeated key is refused rather than
resolved, and a body -- on a GET -- is refused rather than discarded.
"""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.models.lineage import Model, ModelVersion
from ...errors import (
    AUTH_PROJECT_SCOPE,
    RES_ARTIFACT_NOT_FOUND,
    VAL_CURSOR,
    VAL_SCHEMA,
    InvError,
)
from ...identity.principal import Principal
from ...ids import is_id
from ...services import projects as project_service
from ...services.lineage import models_from_dataset_digest, trace_model_for_project
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

#: Reading is a membership question. ``canRequest`` and ``canApprove`` are grades
#: for *doing* things, and requiring one of them here would say that reading
#: lineage needs approval authority -- a boundary that is simply wrong, and one
#: the release route (#167) deliberately draws differently.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    VAL_SCHEMA: (VAL_REQUEST, 422, False),
    VAL_CURSOR: (VAL_REQUEST, 422, False),
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
    RES_ARTIFACT_NOT_FOUND: (RES_NOT_FOUND, 404, False),
}

TRACE_PATH = "/projects/{project_id}/models/{model_id}/versions/{version}/lineage"
REVERSE_PATH = (
    "/projects/{project_id}/lineage/dataset-versions/by-digest/{content_sha256}"
    "/model-versions"
)

#: Page size bounds. ``clamp_limit`` is not reused: it trims an over-large limit
#: to the maximum, so a caller who asked for 10000 is told nothing and believes
#: they received that page size. Here an out-of-range limit is refused.
DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _query(request: Request, allowed: frozenset[str]) -> dict[str, str]:
    """The query string as an exact set, with repeats refused.

    ``query_params.get()`` picks one value out of ``?limit=1&limit=2`` without
    saying so. There is no defensible rule for which one it should be, so an
    ambiguous request is refused instead. An unknown key is refused too: ignoring
    it lets a mistyped filter look like an applied one.
    """
    seen: dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        if key not in allowed:
            raise CanonicalProblem(
                VAL_REQUEST, 422, "The request has an unsupported query parameter."
            )
        if key in seen:
            raise CanonicalProblem(
                VAL_REQUEST, 422, "A query parameter was given more than once."
            )
        seen[key] = value
    return seen


def _limit(raw: str | None) -> int:
    if raw is None:
        return DEFAULT_LIMIT
    if not raw.isdecimal() or len(raw) > 4:
        raise CanonicalProblem(VAL_REQUEST, 422, "limit must be a decimal number.")
    value = int(raw)
    if not (1 <= value <= MAX_LIMIT):
        raise CanonicalProblem(
            VAL_REQUEST, 422, f"limit must be between 1 and {MAX_LIMIT}."
        )
    return value


def _cursor(raw: str | None) -> str | None:
    if raw is None:
        return None
    if not is_id(raw):
        raise CanonicalProblem(VAL_REQUEST, 422, "cursor is not a valid identifier.")
    return raw


def _membership(session: Session, *, principal: Principal, project_id: str) -> None:
    """Live project access, at read grade.

    ``Principal.require_project`` is a sign-in snapshot and says so itself: a
    membership revoked since the token was issued still passes it, which is the
    whole span during which revocation matters.
    """
    try:
        project_service.require_project_access(
            session,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            user_id=principal.user_id,
        )
    except InvError as error:
        raise translate(
            error, table=TRANSLATION, detail="This project is not accessible."
        ) from None


def _version_in_project(
    session: Session, *, tenant_id: uuid.UUID, project_id: str, model_id: str, version: str
) -> ModelVersion:
    """Resolve ``(project, model, version)`` to one row through the parent.

    ``model_versions`` has no ``project_id``, so the parent ``models`` row is the
    only way to bind the path's project. No ``FOR UPDATE``: this route changes
    nothing, and an exclusive lock on a read path would work against the very
    index this card adds.

    Absent, another project's and another tenant's are one 404 -- the rule
    ``require_project_access`` already states for projects, applied here so a
    path variable cannot be used to probe for existence.
    """
    parent = session.get(Model, model_id, populate_existing=True)
    if parent is None or parent.tenant_id != tenant_id or parent.project_id != project_id:
        raise CanonicalProblem(RES_NOT_FOUND, 404, "No such model version.")
    row = session.scalars(
        select(ModelVersion).where(
            ModelVersion.model_id == model_id, ModelVersion.version == version
        )
    ).one_or_none()
    if row is None or row.tenant_id != tenant_id:
        raise CanonicalProblem(RES_NOT_FOUND, 404, "No such model version.")
    return row


async def read_model_lineage(
    project_id: str,
    model_id: str,
    version: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> Any:
    """The forward traceback for one model version.

    ``get_session`` opens the transaction and the tenant scope before this runs,
    which is right here: there is no outbound call to keep out of a transaction,
    so one read is one transaction.
    """
    require_absent_body(await read_bounded_body(request))
    _query(request, frozenset())
    _membership(session, principal=principal, project_id=project_id)
    row = _version_in_project(
        session,
        tenant_id=principal.tenant_id,
        project_id=project_id,
        model_id=model_id,
        version=version,
    )
    try:
        trace = trace_model_for_project(
            session,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            model_version_id=row.model_version_id,
        )
    except InvError as error:
        raise translate(error, table=TRANSLATION, detail="No such model version.") from None
    return schemas.ModelLineageTraceResponse(
        modelVersionId=trace["modelVersionId"],
        version=trace["version"],
        stage=trace["stage"],
        contentSha256=trace["contentSha256"],
        producedByRunId=trace["producedByRunId"],
        datasets=trace["datasets"],
        deployments=trace["deployments"],
        missing=trace["missing"],
        unresolved=trace["unresolved"],
        truncated=trace["truncated"],
        fullyTraceable=trace["fullyTraceable"],
        traceabilityLimitedByScope=trace["traceabilityLimitedByScope"],
        detailedKinds=trace["detailedKinds"],
        countOnlyKinds=trace["countOnlyKinds"],
    )


async def read_model_versions_by_dataset_digest(
    project_id: str,
    content_sha256: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> Any:
    """Model versions built from the bytes with this digest.

    The digest is not lower-cased on the way in. The column's CHECK admits
    lowercase only, so an uppercase digest is a client mistake, and normalising
    it quietly would imply a case-insensitive comparison that does not exist.
    """
    require_absent_body(await read_bounded_body(request))
    query = _query(request, frozenset({"limit", "cursor"}))
    limit = _limit(query.get("limit"))
    cursor = _cursor(query.get("cursor"))
    _membership(session, principal=principal, project_id=project_id)
    try:
        page = models_from_dataset_digest(
            session,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            content_sha256=content_sha256,
            limit=limit,
            cursor=cursor,
        )
    except InvError as error:
        detail = (
            "No such dataset version."
            if error.code == RES_ARTIFACT_NOT_FOUND
            else "content digest must be 64 lowercase hex characters."
        )
        raise translate(error, table=TRANSLATION, detail=detail) from None
    return schemas.ModelVersionByDatasetDigestPageResponse(
        contentSha256=page["contentSha256"],
        datasetVersionIds=page["datasetVersionIds"],
        items=page["items"],
        nextCursor=page["nextCursor"],
        unresolvedModelVersions=page["unresolvedModelVersions"],
        truncated=page["truncated"],
        complete=page["complete"],
    )


def register(router: APIRouter) -> None:
    """Add both routes to an existing router.

    Same reason as the release route: ``BusinessDispatch`` reads
    ``projects.router.routes``, and a nested ``include_router`` leaves only a
    lazy placeholder there.
    """
    router.add_api_route(
        TRACE_PATH,
        read_model_lineage,
        methods=["GET"],
        response_model=schemas.ModelLineageTraceResponse,
        tags=["lineage"],
        name="read_model_lineage",
    )
    router.add_api_route(
        REVERSE_PATH,
        read_model_versions_by_dataset_digest,
        methods=["GET"],
        response_model=schemas.ModelVersionByDatasetDigestPageResponse,
        tags=["lineage"],
        name="read_model_versions_by_dataset_digest",
    )
