"""Five routes for recording a release acceptance (S12-BE, #282 §3).

**The gate is the first statement in every handler, including the two GETs.** That is
not tidiness. A surface whose prerequisites are missing must not be usable as an oracle:
if the gate ran after the release lookup, a caller would learn from the status code
whether a release exists; if it ran after the ledger, a refused request would still have
reserved an idempotency key and left a receipt behind for a request that never happened.
So the order is gate, then identity and freshness and the live grant, then the ledger,
then rows -- and `INV_RELEASE_ACCEPTANCE_WRITE_ENABLED` is false by default, which is
the deployed state (§0-1.5).

Every refusal here is ``SYS-0003`` / 503 / ``retryable=false`` with one fixed sentence.
Not retryable, because no number of retries deploys an identity provider mapper or binds
a registry; one sentence, because telling an unauthenticated caller *which* prerequisite
is missing describes the deployment to them.

What the two GETs are for: a confirmer has to be able to find a proposal and read its
content without being handed an ID out of band, and has to see the exact digest they are
about to agree to. They return no user ID -- ``RunRecordResponse`` set that rule and §3
repeats it -- so the response says what was decided, never who.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import replace
from typing import Mapping

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ...config import Settings
from ...errors import (
    AUTH_PROJECT_SCOPE,
    GRAPH_IDEMPOTENCY_CONFLICT,
    GRAPH_INVALID_TRANSITION,
    RES_RELEASE_NOT_FOUND,
    VAL_SCHEMA,
    InvError,
)
from ...identity.principal import Principal
from ...services import release_acceptance as service
from ...services import release_acceptance_resolver as resolver_service
from ...services.audit import record_denial_out_of_band
from .. import schemas
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
    GRAPH_PRECONDITION,
    GRAPH_STATE_DRIFT,
    RES_NOT_FOUND,
    RES_RETRYABLE,
    SYS_PREREQUISITES_UNAVAILABLE,
    VAL_REQUEST,
    CanonicalProblem,
    canonical_response,
    read_bounded_body,
    require_absent_body,
    strict_json_object,
    translate,
    validate_strict,
)

DECISIONS_PATH = "/release-manifests/{release_id}/acceptance-decisions"
PROPOSAL_PATH = "/release-manifests/{release_id}/acceptance-decisions/{proposal_id}"
CONFIRM_PATH = "/release-manifests/{release_id}/acceptance-decisions/{proposal_id}/confirm"
WITHDRAWAL_PATH = "/release-manifests/{release_id}/acceptances/{acceptance_id}/withdrawals"
EVIDENCE_DISCOVERY_PATH = "/release-manifests/{release_id}/acceptance-evidence"

#: The sentence every refused request gets, whichever prerequisite is absent.
PREREQUISITES_DETAIL = "Release acceptance prerequisites are unavailable."

#: Printable identifier characters, 1..128 (§3). The same pattern the eval and model
#: lanes use, written here rather than imported from one of them: a shared constant
#: between unrelated routes would make a change to one a change to the other.
IDEMPOTENCY_KEY_PATTERN = r"[A-Za-z0-9._:-]{1,128}"

#: Every ``InvError`` these routes can reach. A code not listed becomes ``SYS-0002``,
#: so this table is the statement of what is reachable.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    RES_RELEASE_NOT_FOUND: (RES_NOT_FOUND, 404, False),
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
    GRAPH_INVALID_TRANSITION: (GRAPH_STATE_DRIFT, 409, False),
    GRAPH_IDEMPOTENCY_CONFLICT: (GRAPH_PRECONDITION, 409, False),
    VAL_SCHEMA: (VAL_REQUEST, 422, False),
}

router = APIRouter(prefix="/v1", tags=["release-acceptance"])


def _require_idempotency_key(raw: str | None) -> str:
    """Required on every write here. A retry whose answer was lost must not vote twice."""
    if raw is None or not re.fullmatch(IDEMPOTENCY_KEY_PATTERN, raw):
        raise CanonicalProblem(
            VAL_REQUEST,
            422,
            "An Idempotency-Key header of up to 128 identifier characters is required.",
        )
    return raw


def _gate(settings: Settings) -> None:
    """Step 0, before anything that reads a row or reserves a key."""
    try:
        service.require_prerequisites(
            enabled=settings.release_acceptance_write_enabled,
            resolver=service.active_resolver(),
        )
    except service.PrerequisitesUnavailable:
        raise CanonicalProblem(
            SYS_PREREQUISITES_UNAVAILABLE, 503, PREREQUISITES_DETAIL, retryable=False
        ) from None


def _audited(problem: CanonicalProblem) -> CanonicalProblem:
    """Mark a refusal as the one §8 names, so the shared handler records that action.

    Not an audit call. The repository has exactly one place that writes a denial --
    ``app._record_denial``, reached from the canonical handler -- and its docstring says
    why: a route is inside a transaction the refusal rolls back, and per-route recording
    drifts. So the route *names* the action and the single audit point uses it.
    """
    return replace(problem, audit_action=service.AUDIT_DENIED)


def _conflict() -> CanonicalProblem:
    return _audited(
        CanonicalProblem(
            GRAPH_STATE_DRIFT,
            409,
            "The release acceptance state changed before this request was applied.",
            retryable=False,
        )
    )


def _reference_problem(error: Exception) -> CanonicalProblem:
    """Closed, redacted resolver failures; no identifier or digest is reflected."""

    if isinstance(error, service.PrerequisitesUnavailable):
        return CanonicalProblem(
            SYS_PREREQUISITES_UNAVAILABLE,
            503,
            PREREQUISITES_DETAIL,
            retryable=False,
        )
    if isinstance(error, service.ReferenceNotFound):
        return CanonicalProblem(
            RES_NOT_FOUND,
            404,
            "No such release acceptance evidence.",
            retryable=False,
        )
    if isinstance(error, service.ReferenceRetryable):
        return CanonicalProblem(
            RES_RETRYABLE,
            503,
            "Release acceptance resolution is temporarily unavailable; retry.",
            retryable=True,
        )
    return CanonicalProblem(
        GRAPH_STATE_DRIFT,
        409,
        "The release acceptance reference changed before it was resolved.",
        retryable=False,
    )


def _refusal(
    request: Request, refused: service.Refused, *, trace_id: str
) -> JSONResponse:
    """A refusal returned as a **response**, so the transaction that recorded it commits.

    §5 requires the expiry and manifest-drift transitions to be committed and *then*
    reported, with the 409 confirmed as the idempotency receipt. Raising would roll the
    transition back, which is what the first implementation did.

    **Returning instead of raising skipped the audit**, and Codex measured it: the
    canonical handler is what calls the denial recorder, and a response never reaches it,
    so the closing left a ``proposal_invalidated`` row and no ``denied`` one. This is the
    one place a route records a denial itself, and the reason the repository's rule exists
    -- "a route is inside a transaction that the refusal rolls back" -- is exactly what
    does **not** apply here: this refusal is committed. It is written out of band anyway,
    in its own transaction, so a failure to audit cannot be mistaken for a clean refusal.

    Only the request that performed the transition is audited. A later request that
    re-reads the closed proposal gets the same 409 and writes nothing, because it denied
    nothing new -- otherwise the audit would count retries.
    """
    if refused.transitioned:
        record_denial_out_of_band(
            request.app.state.engine,
            now=request.app.state.clock(),
            actor_type=getattr(request.state, "actor_type", "anonymous"),
            actor_id=getattr(request.state, "actor_id", None),
            action=service.AUDIT_DENIED,
            outcome="deny",
            tenant_id=getattr(request.state, "tenant_id", None),
            reason_code=refused.code,
            trace_id=trace_id,
            detail={},
            source_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    problem = _audited(
        CanonicalProblem(refused.code, refused.status, refused.detail, retryable=False)
    )
    return canonical_response(problem, trace_id=trace_id)


# ------------------------------------------------------------------- evidence discovery


@router.get(
    "/release-manifests/{release_id}/acceptance-evidence",
    response_model=schemas.ReleaseAcceptanceEvidenceDiscoveryPageResponse,
    response_model_by_alias=True,
)
async def discover_acceptance_evidence(
    request: Request,
    release_id: str,
    acceptance_id_ref: str = Query(alias="acceptanceIdRef"),
    limit: int = Query(default=100, ge=1, le=resolver_service.DISCOVERY_PAGE_MAX),
    cursor: str | None = Query(default=None, min_length=1, max_length=256),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> schemas.ReleaseAcceptanceEvidenceDiscoveryPageResponse:
    """List only server-bound Evidence identities for one release criterion.

    This read surface does not enable decision writes. It requires the same fresh
    interactive human and live ``releases.accept`` grant on every page, and exposes no
    project, actor, telemetry, or caller-selected scope.
    """

    # Parse the Git prerequisite before any release lookup. The principal dependency has
    # already authenticated the caller, but an invalid deployment is one fixed 503 and
    # never an existence oracle.
    try:
        resolver_service.load_target_registry()
    except service.PrerequisitesUnavailable as error:
        raise _reference_problem(error) from None
    require_absent_body(await read_bounded_body(request))
    try:
        service.require_fresh_operator(session, principal=principal, now=now)
        return resolver_service.discovery_page(
            session,
            tenant_id=principal.tenant_id,
            release_id=release_id,
            acceptance_id_ref=acceptance_id_ref,
            limit=limit,
            cursor=cursor,
        )
    except (
        service.PrerequisitesUnavailable,
        service.ReferenceNotFound,
        service.ReferenceRetryable,
    ) as error:
        raise _reference_problem(error) from None
    except service.ReferencesUnresolvable as error:
        raise _reference_problem(error) from None
    except InvError as error:
        raise _audited(translate(error, table=TRANSLATION, detail="Not permitted.")) from None


# --------------------------------------------------------------------------- decisions


@router.post(
    DECISIONS_PATH,
    response_model=None,
    status_code=202,
)
async def decide(
    request: Request,
    release_id: str,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_write_session),
    settings: Settings = Depends(get_settings),
    now: dt.datetime = Depends(get_now),
):
    """``accepted`` opens a proposal (202); ``conditional`` and ``rejected`` are final (201).

    The body names no user and carries no re-authentication proof: identity comes from
    the verified token, which is the whole reason a second person means anything here.
    """
    _gate(settings)
    parsed = strict_json_object(
        await read_bounded_body(request),
        content_type=request.headers.get("content-type"),
        content_encoding=request.headers.get("content-encoding"),
    )
    key = _require_idempotency_key(idempotency_key)
    payload = validate_strict(schemas.ReleaseAcceptanceDecisionRequest, parsed)

    try:
        proof = service.require_fresh_operator(session, principal=principal, now=now)
    except InvError as error:
        raise _audited(translate(error, table=TRANSLATION, detail="Not permitted.")) from None

    # The canonical ledger payload includes the path ID, so one key cannot be reused
    # against another release (§3).
    endpoint = f"POST {DECISIONS_PATH}"
    canonical = {"releaseId": release_id, "request": payload.model_dump(mode="json", by_alias=True)}
    serialise_idempotent_write(
        session, tenant_id=principal.tenant_id, endpoint=endpoint, idempotency_key=key
    )
    try:
        stored = replay_or_reserve(
            session,
            principal=principal,
            endpoint=endpoint,
            idempotency_key=key,
            payload=canonical,
            now=now,
            ttl_seconds=settings.idempotency_ttl_seconds,
        )
    except InvError as error:
        raise _audited(
            translate(error, table=TRANSLATION, detail="Idempotency key reused.")
        ) from None
    if stored is not None:
        response.status_code = int(stored.get("status", 202))
        return {**stored.get("body", {}), "replayed": True}

    try:
        outcome = service.propose_or_record(
            session,
            principal=principal,
            release_id=release_id,
            request=payload,
            proof=proof,
            resolver=service.active_resolver(),
            now=now,
        )
    except (
        service.PrerequisitesUnavailable,
        service.ReferenceNotFound,
        service.ReferenceRetryable,
        service.ReferencesUnresolvable,
    ) as error:
        raise _reference_problem(error) from None
    except InvError as error:
        raise _audited(
            translate(error, table=TRANSLATION, detail="The decision was not recorded.")
        ) from None

    status = outcome.status
    model = (
        schemas.ReleaseAcceptanceProposalResponse
        if status == 202
        else schemas.ReleaseAcceptanceRecordedResponse
    )
    validated = model.model_validate(outcome.body)
    store_idempotent_response(
        session,
        principal=principal,
        endpoint=endpoint,
        idempotency_key=key,
        payload=canonical,
        response_status=status,
        response_body={"status": status, "body": validated.model_dump(mode="json", by_alias=True)},
        now=now,
        ttl_seconds=settings.idempotency_ttl_seconds,
    )
    response.status_code = status
    return validated.model_dump(mode="json", by_alias=True)


@router.get(
    DECISIONS_PATH,
    response_model=schemas.ReleaseAcceptanceProposalReviewPageResponse,
    response_model_by_alias=True,
)
async def list_pending(
    request: Request,
    release_id: str,
    state: str = Query(default=service.PENDING_STATE),
    limit: int = Query(default=20, ge=1, le=service.PENDING_PAGE_MAX),
    cursor: str | None = Query(default=None),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    now: dt.datetime = Depends(get_now),
) -> schemas.ReleaseAcceptanceProposalReviewPageResponse:
    """Pending proposals, so a confirmer does not need an ID passed out of band.

    Gated like the writes. A reader that worked while the writes were closed would be a
    way to enumerate releases on a surface the operator has not turned on.
    """
    _gate(settings)
    require_absent_body(await read_bounded_body(request))
    if state != service.PENDING_STATE:
        raise translate(
            InvError(VAL_SCHEMA, "state must be pending_second_operator"),
            table=TRANSLATION,
            detail="Unsupported state filter.",
        )
    try:
        service.require_fresh_operator(session, principal=principal, now=now)
        page = service.pending_page(
            session,
            tenant_id=principal.tenant_id,
            release_id=release_id,
            limit=limit,
            cursor=cursor,
        )
    except InvError as error:
        raise _audited(translate(error, table=TRANSLATION, detail="Not permitted.")) from None
    return schemas.ReleaseAcceptanceProposalReviewPageResponse.model_validate(page)


@router.get(
    PROPOSAL_PATH,
    response_model=schemas.ReleaseAcceptanceProposalReviewResponse,
    response_model_by_alias=True,
)
async def read_pending(
    request: Request,
    release_id: str,
    proposal_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    now: dt.datetime = Depends(get_now),
) -> schemas.ReleaseAcceptanceProposalReviewResponse:
    """The exact content a confirmer agrees to, including the digest they must send back."""
    _gate(settings)
    require_absent_body(await read_bounded_body(request))
    try:
        service.require_fresh_operator(session, principal=principal, now=now)
        proposal = service.pending_proposal(
            session,
            tenant_id=principal.tenant_id,
            release_id=release_id,
            proposal_id=proposal_id,
        )
    except InvError as error:
        raise _audited(translate(error, table=TRANSLATION, detail="No such proposal.")) from None
    return schemas.ReleaseAcceptanceProposalReviewResponse.model_validate(proposal)


@router.post(CONFIRM_PATH, response_model=None, status_code=201)
async def confirm(
    request: Request,
    release_id: str,
    proposal_id: str,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_write_session),
    settings: Settings = Depends(get_settings),
    now: dt.datetime = Depends(get_now),
):
    """The distinct second operator, confirming one exact proposal and manifest."""
    _gate(settings)
    parsed = strict_json_object(
        await read_bounded_body(request),
        content_type=request.headers.get("content-type"),
        content_encoding=request.headers.get("content-encoding"),
    )
    key = _require_idempotency_key(idempotency_key)
    payload = validate_strict(schemas.ReleaseAcceptanceConfirmationRequest, parsed)

    try:
        proof = service.require_fresh_operator(session, principal=principal, now=now)
    except InvError as error:
        raise _audited(translate(error, table=TRANSLATION, detail="Not permitted.")) from None

    endpoint = f"POST {CONFIRM_PATH}"
    canonical = {
        "releaseId": release_id,
        "proposalId": proposal_id,
        "request": payload.model_dump(mode="json", by_alias=True),
    }
    serialise_idempotent_write(
        session, tenant_id=principal.tenant_id, endpoint=endpoint, idempotency_key=key
    )
    try:
        stored = replay_or_reserve(
            session,
            principal=principal,
            endpoint=endpoint,
            idempotency_key=key,
            payload=canonical,
            now=now,
            ttl_seconds=settings.idempotency_ttl_seconds,
        )
    except InvError as error:
        raise _audited(
            translate(error, table=TRANSLATION, detail="Idempotency key reused.")
        ) from None
    if stored is not None:
        status = int(stored.get("status", 201))
        if status >= 400:
            # A refused receipt replays as that refusal, with no ``replayed`` key: a
            # ProblemDetails has an exact ten-key shape and is not a success body.
            return JSONResponse(
                stored.get("body", {}),
                status_code=status,
                media_type="application/problem+json",
                headers={"Cache-Control": "no-store"},
            )
        response.status_code = status
        return {**stored.get("body", {}), "replayed": True}

    try:
        outcome = service.confirm(
            session,
            principal=principal,
            release_id=release_id,
            proposal_id=proposal_id,
            request=payload,
            proof=proof,
            resolver=service.active_resolver(),
            now=now,
        )
    except (
        service.PrerequisitesUnavailable,
        service.ReferenceNotFound,
        service.ReferenceRetryable,
        service.ReferencesUnresolvable,
    ) as error:
        raise _reference_problem(error) from None
    except InvError as error:
        raise _audited(
            translate(error, table=TRANSLATION, detail="The proposal was not confirmed.")
        ) from None

    if outcome.refused is not None:
        # The transition this request recorded -- a lifecycle event, an emptied slot, an
        # audit row -- stays, because this returns rather than raises. The 409 is confirmed
        # as the receipt in the same transaction, so a replay of the same key gets it back
        # and a different key re-reads the closed state and produces the same answer (§5).
        trace_id = getattr(request.state, "trace_id", "")
        body = _audited(
            CanonicalProblem(
                outcome.refused.code, outcome.refused.status, outcome.refused.detail,
                retryable=False,
            )
        ).body(trace_id=trace_id)
        store_idempotent_response(
            session,
            principal=principal,
            endpoint=endpoint,
            idempotency_key=key,
            payload=canonical,
            response_status=outcome.refused.status,
            response_body={"status": outcome.refused.status, "body": body},
            now=now,
            ttl_seconds=settings.idempotency_ttl_seconds,
        )
        return _refusal(request, outcome.refused, trace_id=trace_id)

    validated = schemas.ReleaseAcceptanceRecordedResponse.model_validate(outcome.body)
    store_idempotent_response(
        session,
        principal=principal,
        endpoint=endpoint,
        idempotency_key=key,
        payload=canonical,
        response_status=outcome.status,
        response_body={
            "status": outcome.status,
            "body": validated.model_dump(mode="json", by_alias=True),
        },
        now=now,
        ttl_seconds=settings.idempotency_ttl_seconds,
    )
    response.status_code = outcome.status
    return validated.model_dump(mode="json", by_alias=True)


@router.post(WITHDRAWAL_PATH, response_model=None, status_code=201)
async def withdraw(
    request: Request,
    release_id: str,
    acceptance_id: str,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_write_session),
    settings: Settings = Depends(get_settings),
    now: dt.datetime = Depends(get_now),
):
    """One fresh operator stops a decision counting. Append-only, nothing deleted."""
    _gate(settings)
    parsed = strict_json_object(
        await read_bounded_body(request),
        content_type=request.headers.get("content-type"),
        content_encoding=request.headers.get("content-encoding"),
    )
    key = _require_idempotency_key(idempotency_key)
    payload = validate_strict(schemas.ReleaseAcceptanceWithdrawalRequest, parsed)

    try:
        service.require_fresh_operator(session, principal=principal, now=now)
    except InvError as error:
        raise _audited(translate(error, table=TRANSLATION, detail="Not permitted.")) from None

    endpoint = f"POST {WITHDRAWAL_PATH}"
    canonical = {
        "releaseId": release_id,
        "acceptanceId": acceptance_id,
        "request": payload.model_dump(mode="json", by_alias=True),
    }
    serialise_idempotent_write(
        session, tenant_id=principal.tenant_id, endpoint=endpoint, idempotency_key=key
    )
    try:
        stored = replay_or_reserve(
            session,
            principal=principal,
            endpoint=endpoint,
            idempotency_key=key,
            payload=canonical,
            now=now,
            ttl_seconds=settings.idempotency_ttl_seconds,
        )
    except InvError as error:
        raise _audited(
            translate(error, table=TRANSLATION, detail="Idempotency key reused.")
        ) from None
    if stored is not None:
        response.status_code = int(stored.get("status", 201))
        return {**stored.get("body", {}), "replayed": True}

    try:
        result = service.withdraw(
            session,
            principal=principal,
            release_id=release_id,
            acceptance_id=acceptance_id,
            request=payload,
            now=now,
        )
    except InvError as error:
        raise _audited(
            translate(error, table=TRANSLATION, detail="The decision was not withdrawn.")
        ) from None
    validated = schemas.ReleaseAcceptanceWithdrawalResponse.model_validate(result)
    store_idempotent_response(
        session,
        principal=principal,
        endpoint=endpoint,
        idempotency_key=key,
        payload=canonical,
        response_status=201,
        response_body={"status": 201, "body": validated.model_dump(mode="json", by_alias=True)},
        now=now,
        ttl_seconds=settings.idempotency_ttl_seconds,
    )
    response.status_code = 201
    return validated.model_dump(mode="json", by_alias=True)


__all__ = [
    "router",
    "DECISIONS_PATH",
    "PROPOSAL_PATH",
    "CONFIRM_PATH",
    "WITHDRAWAL_PATH",
    "EVIDENCE_DISCOVERY_PATH",
    "PREREQUISITES_DETAIL",
    "TRANSLATION",
]
