"""Record that a released model version went to an environment (card 261).

AC-10 calls the thing this writes the **deployment digest**: the exact content
that went out, recorded at the moment it went out. The table has existed since
``0004`` and ``record_deployment`` since S10-ST, and until this card **no product
path called it** -- the digest was a column nothing filled in. That is what this
route closes, and the design it implements is card 257 §4-3·§4-3-1.

Three things the caller does not get to say:

* **the digest.** It comes from the model version and the approval is checked
  against it. Approving one build does not authorise shipping a different one
  under the same version name;
* **the image.** ``container_images`` carries no project, so the server cannot
  prove an image belongs to this project and does not accept what it cannot
  prove;
* **the project of the approval.** It is derived -- ``approvals.run_id`` ->
  ``runs.workload_id`` -> ``workloads.project_id`` -- and must equal the path's.
  Without that a same-tenant approval from another project would authorise this
  project's deployment, because a digest alone does not say whose build it was.

**This records; it does not deploy.** No kernel permit is issued and no bytes
move. Whether the thing is actually running is the operator's observation, and
``G-23`` (deployment digest operational acceptance) stays outside this repository.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from ...config import Settings
from ...errors import (
    AUTH_APPROVAL_DIGEST_MISMATCH,
    AUTH_PROJECT_SCOPE,
    GRAPH_IDEMPOTENCY_CONFLICT,
    RES_ARTIFACT_NOT_FOUND,
    VAL_SCHEMA,
    InvError,
)
from ...identity.principal import Principal
from ..audit_action import long_template_action
from ...services import projects as project_service
from ...services.audit import record_event
from ...services.lineage import apply_deployment, locked_deployment_authority
from .. import schemas
from ..deps import (
    get_now,
    get_principal,
    get_settings,
    get_write_session,
    replay_or_reserve,
    serialise_idempotent_write,
    store_idempotent_response,
)
from ..problem import (
    AUTH_PROJECT,
    GRAPH_PRECONDITION,
    Mapped,
    RES_NOT_FOUND,
    CanonicalProblem,
    translate,
)
from .lineage_query import _version_in_project
from .model_versions import _require_idempotency_key

PATH = "/projects/{project_id}/models/{model_id}/versions/{version}/deployments"

#: The ledger's ``endpoint`` and the denial audit's action: one bounded template
#: with no identifier in it, so a renamed path cannot silently start a new key
#: space and an audit row cannot carry a project, model or approval id.
ENDPOINT = "POST /v1/projects/{project_id}/models/{model_id}/versions/{version}/deployments"
#: The audit column is bounded at 64 characters and this template is 79, so the
#: recorder records the name-and-digest form instead of the template verbatim --
#: the same fallback the release route documents. It still carries no identifier.
AUDIT_ACTION = long_template_action(
    "POST",
    "/v1/projects/{project_id}/models/{model_id}/versions/{version}/deployments",
    "record_model_deployment",
)

NO_SUCH_VERSION = "No such model version."

#: Six approval failures are one public answer. ``AUTH_APPROVAL_DIGEST_MISMATCH``
#: is raised for an absent approval, another tenant's, another project's, a
#: decision that is not an approval, one outside its validity, and one given for
#: different content -- and all six become ``GRAPH-0002`` 409 here. A distinct
#: code per cause would confirm that an approval id exists to someone who cannot
#: see it, which is the oracle the lineage subjects already refuse to be. It is
#: a **state** refusal, not an authorisation one: the caller's grade was checked
#: separately and passed.
TRANSLATION: Mapped = {
    AUTH_APPROVAL_DIGEST_MISMATCH: (GRAPH_PRECONDITION, 409, False),
    VAL_SCHEMA: (GRAPH_PRECONDITION, 409, False),
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
    GRAPH_IDEMPOTENCY_CONFLICT: (GRAPH_PRECONDITION, 409, False),
    RES_ARTIFACT_NOT_FOUND: (RES_NOT_FOUND, 404, False),
}


def _authorised(session: Session, *, principal: Principal, project_id: str) -> dict:
    """One judgement of this caller against this project, read fresh every time.

    ``canApprove`` is the grade, not ``canRequest``. The row this route writes
    says "this content went out under that approval" -- a decision-grade
    statement about what the project shipped, which asking for work cannot make.

    ``effective_permission`` returns false grades **without raising** for an
    archived project or a suspended user, so the boolean is *read*; "no
    exception" is never taken as permission.
    """
    permission = project_service.require_project_access(
        session,
        tenant_id=principal.tenant_id,
        project_id=project_id,
        user_id=principal.user_id,
    )
    if not permission.get("canApprove"):
        raise InvError(AUTH_PROJECT_SCOPE, "project is not accessible to this principal")
    return permission


def _body(deployment) -> dict:
    return schemas.ModelDeploymentResponse(
        deploymentId=deployment.deployment_id,
        modelVersionId=deployment.model_version_id,
        environment=deployment.environment,
        status=deployment.status,
        deployedDigest=deployment.deployed_digest,
        approvalId=deployment.approval_id,
        imageId=deployment.image_id,
        deployedAt=deployment.deployed_at,
        supersededAt=deployment.superseded_at,
    ).model_dump(by_alias=True, mode="json")


def record_model_deployment(
    request: Request,
    project_id: str,
    model_id: str,
    version: str,
    payload: schemas.ModelDeploymentRequest,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_write_session),
    settings: Settings = Depends(get_settings),
    now: dt.datetime = Depends(get_now),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    """Record one deployment of a released version.

    The order below is the contract (card 257 §4-3-1), and it is the order card
    250 and card 253 already fixed for a write in this lane.
    """
    key = _require_idempotency_key(idempotency_key)
    body = payload.model_dump(by_alias=True, mode="json")
    # The ledger compares a canonical body, so the path's identity goes into it:
    # without this, the same key on a different version would replay the stored
    # answer for the first one.
    ledger_payload = {**body, "modelId": model_id, "version": version}

    try:
        # [1] Before anything is locked.
        _authorised(session, principal=principal, project_id=project_id)

        # [2] The serialisation point comes before any resource row, so the lock
        # order in this lane stays one: this key, then the version, then the
        # approval.
        serialise_idempotent_write(
            session,
            tenant_id=principal.tenant_id,
            endpoint=ENDPOINT,
            idempotency_key=key,
            project_id=project_id,
        )

        # [3] Re-judge before the replay decision: a caller who lost the grade
        # while waiting for that lock must not be handed a stored success.
        _authorised(session, principal=principal, project_id=project_id)

        replayed = replay_or_reserve(
            session,
            principal=principal,
            endpoint=ENDPOINT,
            idempotency_key=key,
            payload=ledger_payload,
            now=now,
            ttl_seconds=settings.idempotency_ttl_seconds,
            project_id=project_id,
        )
        if replayed is not None:
            return replayed

        # [4] The path resolves to one row through the parent model, and absent,
        # another project's and another tenant's are one 404.
        row = _version_in_project(
            session,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            model_id=model_id,
            version=version,
        )

        # [5] Lock the version and the approval and judge them. Writes nothing.
        authority = locked_deployment_authority(
            session,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            model_version_id=row.model_version_id,
            environment=payload.environment,
            approval_id=payload.approval_id,
            now=now,
        )

        # [6] And once more, immediately before the write: the two row locks are
        # another wait, and a revocation can land during them. This is the step
        # the service could not offer before card 261 split it.
        _authorised(session, principal=principal, project_id=project_id)

        deployment = apply_deployment(
            session,
            authority=authority,
            deployed_by_user_id=principal.user_id,
            now=now,
        )
    except InvError as error:
        raise translate(error, table=TRANSLATION) from None

    body_out = _body(deployment)
    # One allow row in the same transaction as the insert and the ledger, so the
    # three commit together or not at all. The detail carries no digest: it is
    # derived from the version, and the identifiers are enough to find it.
    record_event(
        session,
        now=now,
        actor_type="user",
        actor_id=principal.user_id,
        action="model.deployment.record",
        outcome="allow",
        tenant_id=principal.tenant_id,
        trace_id=getattr(request.state, "trace_id", None),
        target_type="deployment",
        target_id=deployment.deployment_id,
        detail={
            "projectId": project_id,
            "modelVersionId": deployment.model_version_id,
            "environment": deployment.environment,
        },
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    store_idempotent_response(
        session,
        principal=principal,
        endpoint=ENDPOINT,
        idempotency_key=key,
        payload=ledger_payload,
        response_status=201,
        response_body=body_out,
        now=now,
        ttl_seconds=settings.idempotency_ttl_seconds,
        project_id=project_id,
    )
    return body_out


def register(router: APIRouter) -> None:
    """Add the route to an existing router, prefix and all.

    Same reason as the release and lineage routes: ``BusinessDispatch`` reads
    ``projects.router.routes``, and a nested ``include_router`` leaves only a
    lazy placeholder there.
    """
    router.add_api_route(
        PATH,
        record_model_deployment,
        methods=["POST"],
        status_code=201,
        response_model=schemas.ModelDeploymentResponse,
        tags=["lineage"],
        name="record_model_deployment",
    )
