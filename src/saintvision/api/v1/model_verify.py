"""W3: verify a model version from a kernel-recorded measurement (design #209 v1.1 §6).

``POST /projects/{project_id}/models/{model_id}/versions/{version}/verify``

The caller asks for a *measurement* to be applied, not for a value to be
believed: the body is ``{"measurementId"}`` and nothing else. A digest, a size
or a URI in the body is a schema violation (422), because a route that accepts
them is a route that can be talked into ``verified_at`` without a trusted
worker having read the bytes. What the route consumes is the kernel's record
of one signed node observation (``inv.model_version_measurements``, written
only by the kernel's accept path, PR A-2) and what it writes is the binding
0054 created: ``verified_at`` and ``verified_measurement_id`` together.

**Write grade is ``canApprove``**, live, as release and the retention pin.

**Three spans**, in this order:

1. a short transaction: live ``canApprove`` (bounded, card 84 F1);
2. no transaction: the kernel observation ``GET .../measurements/{id}`` with
   the caller's own bearer, no redirects, a bounded read, and the strict
   ``ModelMeasurementObservation`` contract (unknown key refused). The kernel
   unreachable, a redirect, an oversize or invalid answer is
   ``SYS-0001/503/retryable``; a kernel 404 is this route's 404;
3. one atomic write transaction (bounded): IDEM-6 advisory lock → live
   ``canApprove`` → the clock, read once → ledger replay or reserve → parent
   ``models`` read then ``model_versions`` ``FOR UPDATE / populate_existing``
   (the shared ``_locked_version``: pin, release and verify lock in the same
   order) → live ``canApprove`` again → the observation is re-bound to the
   path and the locked row (tenant, project, model, version id, URI,
   measurement id; any mismatch is the same 404) → the storage snapshot the
   measurement names is re-checked against the business catalogue (the
   location resolves from the row's URI, is ``kind='model'``, ``ready``, at the
   exact version and path; its contribution is ``active`` at the exact version
   on the exact node; a ``ready`` replica exists there) → freshness
   (``observedAt <= recordedAt <= now`` and no older than
   ``Settings.model_measurement_max_age_seconds``) → ``verify_model_version``
   with the measurement id and the *observed* digest → audit → ledger.

Every drift, mismatch or stale case is ``GRAPH-0002/409`` with a fixed detail
that carries no value from either side; missing, other tenant's and other
version's are one 404.

**The row the service judged is the row this transaction locked**: the route
asserts identity, as W4 does, so a path that verifies a pre-lock copy cannot
exist silently.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Mapping

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ...config import Settings
from ...db.models.lineage import ModelVersion
from ...db.models.locality import DataReplica
from ...db.models.storage import DataLocation, StorageContribution
from ...db.session import make_session_factory, tenant_scope
from ...errors import (
    AUTH_PROJECT_SCOPE,
    GRAPH_IDEMPOTENCY_CONFLICT,
    RES_ARTIFACT_NOT_FOUND,
    VAL_SCHEMA,
    InvError,
)
from ...identity.principal import Principal
from ...services import projects as project_service
from ...services.audit import record_event
from ...services.lineage import verify_model_version
from ...services.resolver import resolve_location
from .. import schemas
from ..deps import (
    get_principal,
    get_settings,
    replay_or_reserve,
    serialise_idempotent_write,
    store_idempotent_response,
)
from ..lock_wait import bounded_lock_wait
from ..problem import (
    AUTH_PROJECT,
    GRAPH_PRECONDITION,
    RES_NOT_FOUND,
    SYS_UPSTREAM_UNAVAILABLE,
    CanonicalProblem,
    read_bounded_body,
    strict_json_object,
    translate,
    validate_strict,
)
from .model_release import _RefuseRedirect, _locked_version
from .model_versions import _require_idempotency_key

VERIFY_PATH = "/projects/{project_id}/models/{model_id}/versions/{version}/verify"

#: The idempotency ledger's ``endpoint`` for this route (IDEM-2).
ENDPOINT = "POST /v1/projects/{project_id}/models/{model_id}/versions/{version}/verify"

#: Every ``InvError`` reachable from the calls below, and its canonical form.
#: ``VAL-SCHEMA`` here is ``verify_model_version`` refusing a measurement that
#: does not prove this version (other version, other digest, other size, a
#: second measurement after the first): a state precondition, so 409.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
    RES_ARTIFACT_NOT_FOUND: (RES_NOT_FOUND, 404, False),
    GRAPH_IDEMPOTENCY_CONFLICT: (GRAPH_PRECONDITION, 409, False),
    VAL_SCHEMA: (GRAPH_PRECONDITION, 409, False),
}

#: Fixed details: none of them carries a value from the observation, the row
#: or the catalogue, so a refusal cannot be used to read any of them.
NOT_FOUND_DETAIL = "No such model version."
MEASUREMENT_NOT_FOUND_DETAIL = "No such measurement."
SNAPSHOT_DETAIL = "The measurement does not match the current storage snapshot of the model version."
STALE_DETAIL = "The measurement is not fresh enough to verify the model version."
OBSERVATION_DETAIL = "The model measurement observation could not be read."

#: Bounds on the kernel observation fetch, the same rule as #167's commitment.
OBSERVATION_TIMEOUT_SECONDS = 5.0
MAX_OBSERVATION_BYTES = 65536


def fetch_measurement(
    *, base_url: str, credential: str, project_id: str, model_id: str, version: str, measurement_id: str
) -> dict[str, Any]:
    """GET the kernel's measurement observation with the caller's credential.

    Same opener discipline as ``model_release.fetch_commitment``: http/https
    only, every redirect refused (the redirect handler would copy the bearer
    to the new origin), one bounded read.
    """
    base = base_url.rstrip("/")
    if urllib.parse.urlsplit(base).scheme not in ("http", "https"):
        raise ValueError("kernel base URL must be http or https")
    url = (
        f"{base}/v1/projects/{project_id}/models/{model_id}/versions/{version}"
        f"/measurements/{measurement_id}"
    )
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url,
        headers={"Authorization": f"Bearer {credential}", "Accept": "application/json"},
        method="GET",
    )
    opener = urllib.request.build_opener(_RefuseRedirect)
    with opener.open(request, timeout=OBSERVATION_TIMEOUT_SECONDS) as response:
        raw = response.read(MAX_OBSERVATION_BYTES + 1)
    if len(raw) > MAX_OBSERVATION_BYTES:
        raise ValueError("kernel observation exceeds the permitted size")
    return json.loads(raw)


class _KernelNotFound(Exception):
    """The kernel answered 404: there is no such measurement for this caller."""


def _fetch_or_not_found(fetcher, **kwargs):
    try:
        return fetcher(**kwargs)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise _KernelNotFound() from None
        raise


async def _observation(
    request: Request, *, project_id: str, model_id: str, version: str, measurement_id: str
) -> schemas.ModelMeasurementObservation:
    """The observation, strictly validated, or a canonical refusal."""
    fetcher = getattr(request.app.state, "model_measurement_fetcher", None) or fetch_measurement
    base_url = request.app.state.settings.kernel_base_url
    if not base_url:
        raise CanonicalProblem(
            SYS_UPSTREAM_UNAVAILABLE, 503, "Model measurement observation is not configured.", retryable=True
        )
    credential = (request.headers.get("authorization") or "").split(" ", 1)[-1].strip()
    try:
        body = await run_in_threadpool(
            lambda: _fetch_or_not_found(
                fetcher,
                base_url=base_url,
                credential=credential,
                project_id=project_id,
                model_id=model_id,
                version=version,
                measurement_id=measurement_id,
            )
        )
    except _KernelNotFound:
        raise CanonicalProblem(RES_NOT_FOUND, 404, MEASUREMENT_NOT_FOUND_DETAIL) from None
    except (urllib.error.URLError, OSError, ValueError, TypeError, json.JSONDecodeError):
        raise CanonicalProblem(SYS_UPSTREAM_UNAVAILABLE, 503, OBSERVATION_DETAIL, retryable=True) from None
    if not isinstance(body, Mapping):
        raise CanonicalProblem(SYS_UPSTREAM_UNAVAILABLE, 503, OBSERVATION_DETAIL, retryable=True)
    try:
        return validate_strict(schemas.ModelMeasurementObservation, body)
    except CanonicalProblem:
        # ``validate_strict`` answers a *request* failure (422); this body is
        # the kernel's, so an invalid one is an upstream we cannot decide on.
        raise CanonicalProblem(SYS_UPSTREAM_UNAVAILABLE, 503, OBSERVATION_DETAIL, retryable=True) from None


def _require_approval(session: Session, *, principal: Principal, project_id: str) -> None:
    """Live project access plus the approval grade, or a canonical refusal."""
    try:
        permission = project_service.require_project_access(
            session, tenant_id=principal.tenant_id, project_id=project_id, user_id=principal.user_id
        )
    except InvError as error:
        raise translate(error, table=TRANSLATION, detail="This project is not accessible.") from None
    if not permission.get("canApprove"):
        raise CanonicalProblem(AUTH_PROJECT, 403, "Verifying a model version requires approval permission.")


def _rebind_identity(
    observation: schemas.ModelMeasurementObservation,
    *,
    principal: Principal,
    project_id: str,
    model_id: str,
    row: ModelVersion,
    measurement_id: str,
) -> None:
    """The observation must describe the row this request named and locked.

    A mismatch is the same 404 as a missing row: saying "that measurement
    exists but is for something else" would disclose existence.
    """
    if (
        observation.measurement_id != measurement_id
        or observation.tenant_id != principal.tenant_id
        or observation.project_id != project_id
        or observation.model_id != model_id
        or observation.version_id != row.model_version_id
        or observation.uri != row.uri
    ):
        raise CanonicalProblem(RES_NOT_FOUND, 404, NOT_FOUND_DETAIL)


def _require_current_snapshot(
    session: Session, observation: schemas.ModelMeasurementObservation, *, tenant_id: uuid.UUID, row: ModelVersion
) -> None:
    """The storage the measurement names is still exactly what the catalogue holds.

    Design §3/§6: one immutable ``DataLocation`` of ``kind='model'`` that the
    row's URI resolves to, ``ready``, at the exact version and relative path;
    its contribution ``active`` at the exact version on the exact node; and a
    ``ready`` replica on that node. Anything else is one 409 with no value.
    """
    try:
        location = resolve_location(session, tenant_id=tenant_id, uri=row.uri)
    except (InvError, ValueError):
        raise CanonicalProblem(GRAPH_PRECONDITION, 409, SNAPSHOT_DETAIL) from None
    if (
        location.kind != "model"
        or not location.ready
        or location.location_id != observation.location_id
        or int(location.version) != observation.location_version
        or location.relative_path != observation.relative_path
        or location.contribution_id != observation.contribution_id
    ):
        raise CanonicalProblem(GRAPH_PRECONDITION, 409, SNAPSHOT_DETAIL)
    contribution = session.get(StorageContribution, observation.contribution_id)
    if (
        contribution is None
        or contribution.tenant_id != tenant_id
        or contribution.status != "active"
        or int(contribution.version) != observation.contribution_version
        or contribution.node_id != observation.node_id
    ):
        raise CanonicalProblem(GRAPH_PRECONDITION, 409, SNAPSHOT_DETAIL)
    replica = session.scalars(
        select(DataReplica).where(
            DataReplica.tenant_id == tenant_id,
            DataReplica.location_id == observation.location_id,
            DataReplica.node_id == observation.node_id,
            DataReplica.state == "ready",
        )
    ).first()
    if replica is None:
        raise CanonicalProblem(GRAPH_PRECONDITION, 409, SNAPSHOT_DETAIL)


def _require_fresh(
    observation: schemas.ModelMeasurementObservation, *, now: dt.datetime, max_age_seconds: int
) -> None:
    """``observedAt <= recordedAt <= now`` and no older than the window."""
    if observation.observed_at > observation.recorded_at or observation.recorded_at > now:
        raise CanonicalProblem(GRAPH_PRECONDITION, 409, STALE_DETAIL)
    if now - observation.observed_at > dt.timedelta(seconds=max_age_seconds):
        raise CanonicalProblem(GRAPH_PRECONDITION, 409, STALE_DETAIL)


def _response(row: ModelVersion, *, newly_verified: bool) -> schemas.ModelVerifyResponse:
    return schemas.ModelVerifyResponse(
        modelVersionId=row.model_version_id,
        modelId=row.model_id,
        version=row.version,
        stage=row.stage,
        verifiedAt=row.verified_at,
        verifiedMeasurementId=row.verified_measurement_id,
        contentSha256=row.content_sha256,
        newlyVerified=newly_verified,
    )


async def verify_model_version_route(
    project_id: str,
    model_id: str,
    version: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    settings: Settings = Depends(get_settings),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Any:
    """Bind the version to the measurement the caller names, once per key."""
    factory = make_session_factory(request.app.state.engine)

    # (1) Permission first, in its own short, bounded transaction.
    with factory() as session:
        with session.begin():
            with tenant_scope(session, principal.tenant_id), bounded_lock_wait(
                session, timeout_ms=settings.business_lock_timeout_ms
            ):
                _require_approval(session, principal=principal, project_id=project_id)

    key = _require_idempotency_key(idempotency_key)
    payload = strict_json_object(
        await read_bounded_body(request),
        content_type=request.headers.get("content-type"),
        content_encoding=request.headers.get("content-encoding"),
    )
    proposal = validate_strict(schemas.ModelVerifyRequest, payload)
    measurement_id = proposal.measurement_id
    ledger_payload = {
        "modelId": model_id,
        "version": version,
        "request": proposal.model_dump(by_alias=True, mode="json"),
    }

    # (2) The observation, with no transaction open.
    observation = await _observation(
        request, project_id=project_id, model_id=model_id, version=version, measurement_id=measurement_id
    )

    # (3) One atomic, bounded transaction in the §6 order.
    with factory() as session:
        with session.begin():
            with tenant_scope(session, principal.tenant_id), bounded_lock_wait(
                session, timeout_ms=settings.business_lock_timeout_ms
            ):
                serialise_idempotent_write(
                    session,
                    tenant_id=principal.tenant_id,
                    endpoint=ENDPOINT,
                    idempotency_key=key,
                    project_id=project_id,
                )
                _require_approval(session, principal=principal, project_id=project_id)
                # Read once, after the body the caller paced and after the wait
                # for the serialisation point (Codex #191 F3 / #196 F2).
                now: dt.datetime = request.app.state.clock()
                try:
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
                except InvError as error:
                    raise translate(
                        error, table=TRANSLATION, detail="That idempotency key was used with a different request."
                    ) from None
                if replayed is not None:
                    return replayed
                row = _locked_version(
                    session, tenant_id=principal.tenant_id, project_id=project_id, model_id=model_id, version=version
                )
                # Re-checked after the lock: a revocation during the wait must not write.
                _require_approval(session, principal=principal, project_id=project_id)
                _rebind_identity(
                    observation,
                    principal=principal,
                    project_id=project_id,
                    model_id=model_id,
                    row=row,
                    measurement_id=measurement_id,
                )
                _require_current_snapshot(session, observation, tenant_id=principal.tenant_id, row=row)
                _require_fresh(observation, now=now, max_age_seconds=settings.model_measurement_max_age_seconds)
                already = row.verified_measurement_id
                try:
                    verified = verify_model_version(
                        session,
                        tenant_id=principal.tenant_id,
                        model_version_id=row.model_version_id,
                        measurement_id=measurement_id,
                        content_sha256=observation.sha256,
                        now=now,
                    )
                except InvError as error:
                    raise translate(error, table=TRANSLATION, detail=SNAPSHOT_DETAIL) from None
                if verified is not row:
                    raise RuntimeError("verify_model_version did not act on the locked model version row")
                newly_verified = already is None
                body = _response(verified, newly_verified=newly_verified).model_dump(by_alias=True, mode="json")
                record_event(
                    session,
                    now=now,
                    actor_type="user",
                    actor_id=principal.user_id,
                    action="model_version.verify",
                    outcome="allow",
                    tenant_id=principal.tenant_id,
                    trace_id=getattr(request.state, "trace_id", None),
                    target_type="model_version",
                    target_id=verified.model_version_id,
                    detail={
                        "projectId": project_id,
                        "modelId": model_id,
                        "version": verified.version,
                        "measurementId": measurement_id,
                        "newlyVerified": newly_verified,
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
                    response_status=200,
                    response_body=body,
                    now=now,
                    ttl_seconds=settings.idempotency_ttl_seconds,
                    project_id=project_id,
                )
    return body


def register(router: APIRouter) -> None:
    """Add the route with ``add_api_route`` (``BusinessDispatch`` reads ``routes``)."""
    router.add_api_route(
        VERIFY_PATH,
        verify_model_version_route,
        methods=["POST"],
        status_code=200,
        response_model=schemas.ModelVerifyResponse,
        tags=["model-registry"],
        name="verify_model_version",
    )
