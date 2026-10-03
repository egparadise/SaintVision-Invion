"""Project-scoped catalogue surface over server-owned project bindings (card 253).

This is the half of [[S02-ST 제공 폴더·DataLocation 카탈로그 설계 (카드 250)]] that
migration ``0062`` makes possible, and it is deliberately narrow:

* **the project comes from the path, never from a body.** The request contract has
  no ``projectId`` field and forbids extras, so a caller cannot name a project the
  server has not judged. ``require_project_access`` judges it (the same refusal
  whether the project is absent or merely invisible), and ``canRequest`` is the
  grade that may register a project's inputs;
* **the contribution's owner is checked on a locked row.** Read-committed plus an
  unlocked read would let a revoke commit between the check and the insert, so the
  row is taken ``FOR UPDATE`` and owner, tenant and status are read from it;
* **authorisation is judged three times, not once** -- at the start, after the
  idempotency lock and before the replay decision, and after the row lock just
  before the insert. ``eval_runs`` states the reason for its own route and it is
  the same here: a membership revoked while the request waited for a lock must not
  be able to act. This route spends no money; it exposes one project's data to
  another project's member, which is the same shape of mistake;
* **the key is required.** A retry whose answer never arrived must not catalogue a
  second row, and a route that accepts a missing key cannot promise that.

Contributions stay tenant-wide (a folder belongs to a node), so there is no
project-scoped contribution list here -- a location carries ``contributionId`` as
a reference and that is the only link a screen needs.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid
from typing import Any, Mapping

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...config import Settings
from ...db.session import project_scope
from ...errors import (
    AUTH_PROJECT_SCOPE,
    GRAPH_IDEMPOTENCY_CONFLICT,
    RES_ARTIFACT_NOT_FOUND,
    RES_CONTRIBUTION_NOT_FOUND,
    RES_NODE_NOT_FOUND,
    VAL_PATH_UNSAFE,
    VAL_SCHEMA,
    InvError,
)
from ...services.audit import record_event
from ...services import projects as project_service
from ...services import storage as storage_service
from ...services import resolver
from ...services.replica_observation import observe_replicas
from .. import schemas
from ...identity.principal import Principal
from ..deps import (
    get_now,
    get_principal,
    get_session,
    get_settings,
    get_write_session,
    replay_or_reserve,
    serialise_idempotent_write,
    store_idempotent_response,
)
from ..problem import (
    AUTH_PROJECT,
    CanonicalProblem,
    GRAPH_PRECONDITION,
    Mapped,
    RES_NOT_FOUND,
    legacy_not_found_problem,
    translate,
)
from .model_versions import _require_idempotency_key

router = APIRouter(prefix="/v1", tags=["storage"])

#: The idempotency ledger's ``endpoint`` and the denial audit's action: one
#: constant each, with no identifier in them, so a renamed path cannot silently
#: start a new key space and an audit row cannot carry a project or a folder id.
ENDPOINT = "POST /v1/projects/{project_id}/storage/locations"
AUDIT_ACTION = ENDPOINT

#: ``data_locations`` is unique on (tenant, uri) since 0001, and 0062 did not
#: narrow that to a project. So two projects of one tenant cannot catalogue the
#: same ``inv://`` URI, and this route is the first product caller that can reach
#: the collision. It is answered as a state refusal rather than left to become a
#: 500. The message names no project: it cannot say *where* the URI is held
#: without telling one project about another's contents. Making the URI unique
#: per project is Phase 2's business, not something this route can decide.
_URI_UNIQUE = "uq_data_locations_tenant_id_uri"
URI_TAKEN_DETAIL = "this storage URI is already catalogued in this tenant"

#: What this route's calls can raise, and what the caller is told.
#:
#: ``VAL_SCHEMA`` is a *state* refusal at this call site -- the service raises it
#: for an inactive contribution or an unbuildable URI -- so it becomes
#: ``GRAPH-0002`` rather than a malformed-request 422. ``RES_CONTRIBUTION_NOT_FOUND``
#: is translated separately (:func:`_absent`) because it must also be audited.
TRANSLATION: Mapping[str, Mapped] = {
    VAL_SCHEMA: (GRAPH_PRECONDITION, 409, False),
    VAL_PATH_UNSAFE: (GRAPH_PRECONDITION, 409, False),
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
    GRAPH_IDEMPOTENCY_CONFLICT: (GRAPH_PRECONDITION, 409, False),
    RES_CONTRIBUTION_NOT_FOUND: (RES_NOT_FOUND, 404, False),
    RES_ARTIFACT_NOT_FOUND: (RES_NOT_FOUND, 404, False),
    RES_NODE_NOT_FOUND: (RES_NOT_FOUND, 404, False),
}


def _absent(error: InvError) -> CanonicalProblem:
    """The audited, oracle-free absence this route answers with.

    Two steps, and both matter:

    * the public problem comes from :func:`legacy_not_found_problem`, which maps the
      legacy absence codes to a fixed ``RES-0004`` 404 ``"No such resource."``. The
      internal code (``RES-CONTRIBUTION-NOT-FOUND``) is not canonical -- it would be
      refused by ``CanonicalProblem``'s own code pattern -- and it must not be, because
      a distinct code per cause is exactly the oracle this route refuses to be;
    * ``audit_action`` is then added, because an ``RES`` 404 is not one of the
      categories the shared handler audits by status. The handler audits any refusal
      whose problem names an action, which is the hook ``#282`` §8 added for state
      refusals, and this is one.
    """
    problem = legacy_not_found_problem(error)
    if problem is None:  # pragma: no cover - the caller only passes absence codes
        return translate(error, table=TRANSLATION)
    return dataclasses.replace(problem, audit_action=AUDIT_ACTION)


def _authorised(
    session: Session, *, principal: Principal, project_id: str
) -> dict[str, Any]:
    """One judgement of this caller against this project, read fresh every time.

    ``require_project_access`` reports the same refusal whether the project does
    not exist or the caller cannot see it, and ``effective_permission`` returns
    false grades -- without raising -- for an archived project or a suspended
    user. So the grade is *read*, never inferred from the absence of an exception.
    """
    permission = project_service.require_project_access(
        session,
        tenant_id=principal.tenant_id,
        project_id=project_id,
        user_id=principal.user_id,
    )
    if not permission.get("canRequest"):
        raise InvError(AUTH_PROJECT_SCOPE, "project is not accessible to this principal")
    return permission


def _readable(session: Session, *, principal: Principal, project_id: str) -> dict[str, Any]:
    """Read access: the grades that take part in the project's work.

    ``canRequest`` asks for work, ``canApprove`` decides on it; both need to see
    what the project's inputs are. A role in neither set -- ``viewer`` today --
    cannot read the project catalogue, and widening that is a product decision
    with its own boolean, not something this route infers.
    """
    permission = project_service.require_project_access(
        session,
        tenant_id=principal.tenant_id,
        project_id=project_id,
        user_id=principal.user_id,
    )
    if not (permission.get("canRequest") or permission.get("canApprove")):
        raise InvError(AUTH_PROJECT_SCOPE, "project is not accessible to this principal")
    return permission


def _location_body(location) -> dict:
    return schemas.ProjectDataLocationResponse(
        locationId=location.location_id,
        projectId=location.project_id,
        contributionId=location.contribution_id,
        uri=location.uri,
        kind=location.kind,
        relativePath=location.relative_path,
        byteSize=location.byte_size,
        checksumSha256=location.checksum_sha256,
        ready=location.ready,
        verifiedAt=location.verified_at,
        retentionPinnedUntil=location.retention_pinned_until,
    ).model_dump(by_alias=True, mode="json")


@router.post(
    "/projects/{project_id}/storage/locations",
    status_code=201,
    response_model=schemas.ProjectDataLocationResponse,
)
def catalogue_project_location(
    request: Request,
    project_id: str,
    payload: schemas.ProjectDataLocationRequest,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_write_session),
    settings: Settings = Depends(get_settings),
    now: dt.datetime = Depends(get_now),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    """Bind one item of a contribution the caller owns into this project.

    The order below is the contract, not an implementation detail -- see this
    module's first paragraph and the design's §3-2-2.
    """
    key = _require_idempotency_key(idempotency_key)
    body = payload.model_dump(by_alias=True, mode="json")

    try:
        # [1] The first judgement, before anything is locked.
        _authorised(session, principal=principal, project_id=project_id)

        # [2] The serialisation point comes before any resource row, so the lock
        # order across this lane stays one: this key, then the contribution row.
        serialise_idempotent_write(
            session,
            tenant_id=principal.tenant_id,
            endpoint=ENDPOINT,
            idempotency_key=key,
            project_id=project_id,
        )

        # [3] Re-judge before the replay decision: a caller who lost the project
        # while waiting for that lock must not be handed a stored success.
        _authorised(session, principal=principal, project_id=project_id)

        replayed = replay_or_reserve(
            session,
            principal=principal,
            endpoint=ENDPOINT,
            idempotency_key=key,
            payload=body,
            now=now,
            ttl_seconds=settings.idempotency_ttl_seconds,
            project_id=project_id,
        )
        if replayed is not None:
            return replayed

        # [4] The contribution row, locked, with owner and status read from it.
        storage_service.locked_contribution(
            session,
            tenant_id=principal.tenant_id,
            contribution_id=payload.contribution_id,
            owner_user_id=principal.user_id,
        )

        # [5] And once more, immediately before the write: the row lock is another
        # wait, and the same revocation can land during it.
        _authorised(session, principal=principal, project_id=project_id)

        try:
            # The savepoint is what keeps a collision recoverable: without it the
            # failed insert would poison the transaction and the refusal below
            # could not be returned at all.
            with session.begin_nested(), project_scope(session, project_id):
                location = storage_service.catalogue_location(
                    session,
                    tenant_id=principal.tenant_id,
                    contribution_id=payload.contribution_id,
                    kind=payload.kind,
                    relative_path=payload.relative_path,
                    byte_size=payload.byte_size,
                    name=payload.name or "",
                    version=payload.version or "",
                    run_id=payload.run_id or "",
                    artifact_id=payload.artifact_id or "",
                    workspace_id=payload.workspace_id or "",
                    project_id=project_id,
                    now=now,
                )
        except IntegrityError as error:
            if _URI_UNIQUE in str(getattr(error, "orig", error)):
                raise InvError(VAL_SCHEMA, URI_TAKEN_DETAIL) from None
            raise
        body_out = _location_body(location)
        # One allow row in the same transaction as the insert and the ledger, so
        # the three commit together or not at all. The detail carries no path and
        # no URI: both are built from caller-supplied text, and the identifiers
        # are enough to find the row that holds them.
        record_event(
            session,
            now=now,
            actor_type="user",
            actor_id=principal.user_id,
            action="storage.location.catalogue",
            outcome="allow",
            tenant_id=principal.tenant_id,
            trace_id=getattr(request.state, "trace_id", None),
            target_type="data_location",
            target_id=location.location_id,
            detail={
                "projectId": project_id,
                "contributionId": location.contribution_id,
                "kind": location.kind,
            },
            source_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        store_idempotent_response(
            session,
            principal=principal,
            endpoint=ENDPOINT,
            idempotency_key=key,
            payload=body,
            response_status=201,
            response_body=body_out,
            now=now,
            ttl_seconds=settings.idempotency_ttl_seconds,
            project_id=project_id,
        )
        return body_out
    except InvError as error:
        if error.code in (RES_CONTRIBUTION_NOT_FOUND, RES_NODE_NOT_FOUND):
            raise _absent(error) from None
        raise translate(error, table=TRANSLATION) from None


@router.get(
    "/projects/{project_id}/storage/locations",
    response_model=schemas.ProjectDataLocationPageResponse,
)
def list_project_locations(
    project_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    kind: str | None = Query(default=None),
    ready_only: bool = Query(default=False, alias="readyOnly"),
    limit: int | None = Query(default=None, ge=1),
    cursor: str | None = Query(default=None),
) -> dict:
    """This project's catalogued locations. Rows bound to no project are absent."""
    try:
        _readable(session, principal=principal, project_id=project_id)
        with project_scope(session, project_id):
            page = storage_service.list_project_locations(
                session,
                tenant_id=principal.tenant_id,
                project_id=project_id,
                kind=kind,
                ready_only=ready_only,
                limit=limit,
                cursor=cursor,
                default_limit=settings.page_limit_default,
                max_limit=settings.page_limit_max,
            )
    except InvError as error:
        raise translate(error, table=TRANSLATION) from None
    return page.to_dict(_location_body)


@router.get("/projects/{project_id}/storage/locations/resolve")
def resolve_project_location(
    project_id: str,
    uri: str = Query(min_length=1, max_length=2048),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    """Resolve one ``inv://`` URI **within this project**; grants no byte access."""
    try:
        _readable(session, principal=principal, project_id=project_id)
        with project_scope(session, project_id):
            location = resolver.resolve_location(
                session,
                tenant_id=principal.tenant_id,
                uri=uri,
                project_id=project_id,
            )
    except ValueError:
        raise translate(
            InvError(VAL_SCHEMA, "invalid storage URI"), table=TRANSLATION
        ) from None
    except InvError as error:
        if error.code == RES_ARTIFACT_NOT_FOUND:
            # No existence oracle and no reflection of an untrusted URI: a URI in
            # another project reads exactly like one that was never catalogued.
            raise _absent(InvError(RES_CONTRIBUTION_NOT_FOUND, "data location not found")) from None
        raise translate(error, table=TRANSLATION) from None
    return {"location": _location_body(location)}


@router.get("/projects/{project_id}/storage/locations/replica-status")
def project_replica_status(
    project_id: str,
    uri: str = Query(min_length=1, max_length=2048),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    """Recorded replica states for a location of this project.

    Recorded, not current: what the catalogue last observed, never a promise that
    the bytes are reachable now.
    """
    try:
        _readable(session, principal=principal, project_id=project_id)
        with project_scope(session, project_id):
            observation = observe_replicas(
                session,
                tenant_id=principal.tenant_id,
                reader_user_id=principal.user_id,
                uri=uri,
                project_id=project_id,
            )
    except ValueError:
        raise translate(
            InvError(VAL_SCHEMA, "invalid storage URI"), table=TRANSLATION
        ) from None
    except InvError as error:
        if error.code == RES_ARTIFACT_NOT_FOUND:
            raise _absent(InvError(RES_CONTRIBUTION_NOT_FOUND, "data location not found")) from None
        raise translate(error, table=TRANSLATION) from None
    return observation
