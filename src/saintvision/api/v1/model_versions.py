"""W2: register one model build under a project's model (G-04·G-05 design §2).

``POST /projects/{project_id}/models/{model_id}/versions``

``register_model_version`` has existed in ``services/lineage.py`` since S10-ST
and no HTTP request has ever reached it. This module is that request path. Its
signature is unchanged: the service decides what a registration means -- the
digest rule, the draft stage, the parent lookup -- and this route supplies the
boundary around it.

**Write grade is ``canApprove``**, checked live against the database rather than
against the sign-in snapshot, the way ``model_release`` does it. Registering a
version is what every later step (verify, pin, release, deploy) is built on, so
the grade is the approval grade rather than membership.

**The path is bound to a row before anything is written.** ``model_versions``
has no ``project_id``; the parent ``models`` row is the only thing that can say
which project a version belongs to. An absent model, another tenant's model and
another project's model all answer with the same 404, because a path variable
that can distinguish them is an existence oracle.

**Two transaction spans, not one.** The permission is checked in its own short
transaction, the body is then read with no transaction open, and the write is
one atomic transaction that re-checks the permission it no longer holds. The
design says "1 tx" for the write and that is what the second span is; the split
exists because the caller controls how slowly the body arrives, and holding a
transaction open across that hands them a way to pin one.

**What this route deliberately does not accept.** ``register_model_version``
also takes ``produced_by_run_id`` and ``lineage``, and neither is in the request
model:

* ``produced_by_run_id`` has no foreign key, so an unbound value would attach
  this version to a run in another project -- a false provenance claim. Binding
  it needs ``project_scope.run_in_project`` (PR 1 of 8, #184), which this branch
  does not contain because the base is fixed at #175.
* ``lineage`` edges are written by ``record_lineage``, which does not check that
  the subject row exists. Exposing it here would let a caller write edges that
  point at nothing, and ``trace_model`` would then report a version as traceable
  by kinds whose subjects are absent.

Both are follow-ups with an owner decision attached, not omissions. Tests pin
the refusal so re-adding either field has to be deliberate.

**The stored address is derived, not accepted** (Codex #191 F2). The row's URI is
``inv://models/<model name>@<version>``, built here from the parent model's name
and the requested version. A caller-supplied string was stored verbatim, which
meant a credential-bearing ``https://`` URL, a ``javascript:`` scheme and another
model version's address were all valid registrations -- and the kernel manifest's
join key assumes the URI's version is the row's version. Deriving removes the
class rather than filtering it.

**The clock is read after the lock** (Codex #191 F3). ``Depends(get_now)`` is
evaluated before the handler runs, and this handler then reads a body the caller
paces and waits on an advisory lock. A request that took a minute to arrive would
have stamped ``created_at``, the audit and the ledger's ``expires_at`` with a time
from before it waited.

**Lock waits are bounded** (card 84, ``api/lock_wait.py``). The advisory lock and
any row lock in the write transaction wait at most ``Settings.business_lock_timeout_ms``
(``SET LOCAL lock_timeout``); a wait past that, or a deadlock, is
``SYS-0001/503/retryable=true`` with no value from the database in the answer. The
bound is the lane's, not this route's -- every write route uses the same helper.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Mapping

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...config import Settings
from ...db.models.lineage import Model
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
from ...services.lineage import register_model_version
from ...storage.pathsafe import build_uri
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
    VAL_REQUEST,
    CanonicalProblem,
    read_bounded_body,
    strict_json_object,
    translate,
    validate_strict,
)

REGISTER_PATH = "/projects/{project_id}/models/{model_id}/versions"

#: The idempotency ledger's ``endpoint`` for this route (IDEM-2). A constant
#: rather than the request's path, so two projects' keys cannot collide through
#: the ledger and a renamed path cannot silently start a new key space.
ENDPOINT = "POST /v1/projects/{project_id}/models/{model_id}/versions"

#: The same answer for every way the path can fail to name a model. Held here so
#: the three raise sites cannot drift apart.
NO_SUCH_MODEL = "No such model."

#: What an ``Idempotency-Key`` may be. The ledger column is ``String(128)``, so a
#: longer key would be a database error rather than a request error; the
#: character set is narrowed to what identifiers are actually made of, which
#: also keeps the lock material unambiguous (the separator cannot appear in a
#: key).
IDEMPOTENCY_KEY_PATTERN = r"[A-Za-z0-9._:-]{1,128}"

#: Unique constraints this route can reach, and what the caller may be told.
#:
#: Both are entirely inside the path's model, which the route binds to the path's
#: project before calling the service, so a conflict on either is a conflict the
#: caller already named: nothing is disclosed that they did not bring.
#:
#: The digest constraint used to be ``(tenant_id, content_sha256)`` and its detail
#: had to be vague, because a member of one project could learn that a digest
#: existed in another. Migration ``0052`` narrowed it to
#: ``(model_id, content_sha256)`` (Codex #191 F1), which is why the detail can now
#: say what actually happened.
UNIQUE_CONFLICTS: Mapping[str, str] = {
    "uq_model_versions_model_id_version": (
        "This model already has a version with that name."
    ),
    "uq_model_versions_model_id_content_sha256": (
        "This model already has a version with that content digest."
    ),
}
# ``uq_model_versions_tenant_id_version_id`` is deliberately absent: a collision
# on a generated ULID is our defect, not a duplicate the caller sent, so it
# propagates rather than being reported as their conflict.

#: Every ``InvError`` reachable from the calls below, and its canonical form. A
#: code missing here becomes ``SYS-0002``; a test enumerates the reachable codes
#: and fails if this table does not cover them.
#:
#: ``VAL-SCHEMA`` is a *request* error at this call site -- the service raises it
#: for a digest that is not lowercase hex -- which is the opposite of what the
#: same code means in ``model_release``, where it reports a state precondition.
#: That is why the table is per route.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
    VAL_SCHEMA: (VAL_REQUEST, 422, False),
    RES_ARTIFACT_NOT_FOUND: (RES_NOT_FOUND, 404, False),
    GRAPH_IDEMPOTENCY_CONFLICT: (GRAPH_PRECONDITION, 409, False),
}


def _require_approval(session: Session, *, principal: Principal, project_id: str) -> None:
    """Live project access plus the approval grade, or a canonical refusal.

    ``Principal.require_project`` is the sign-in snapshot and says so itself: a
    membership revoked since then would still pass it.
    """
    try:
        permission = project_service.require_project_access(
            session,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            user_id=principal.user_id,
        )
    except InvError as error:
        raise translate(
            error, table=TRANSLATION, detail="This project is not accessible."
        ) from None
    if not permission.get("canApprove"):
        raise CanonicalProblem(
            AUTH_PROJECT, 403, "Registering a model version requires approval permission."
        )


def _require_idempotency_key(raw: str | None) -> str:
    """The key is required on every write in this lane (IDEM-1).

    Optional would mean two shapes of this route: one that can be retried safely
    and one that cannot, chosen by the caller after the fact.
    """
    if raw is None or not re.fullmatch(IDEMPOTENCY_KEY_PATTERN, raw):
        raise CanonicalProblem(
            VAL_REQUEST,
            422,
            "An Idempotency-Key header of up to 128 identifier characters is required.",
        )
    return raw


def _model_in_project(
    session: Session, *, tenant_id: uuid.UUID, project_id: str, model_id: str
) -> Model:
    """Resolve ``(project, model)`` to one row, or the one 404.

    Read without ``FOR UPDATE``: the parent is not modified here, and the row
    this request creates does not exist yet, so there is nothing to lock. The
    serialisation this write needs is the idempotency advisory lock, which is
    already held by the time this runs.
    """
    model = session.get(Model, model_id, populate_existing=True)
    if model is None or model.tenant_id != tenant_id or model.project_id != project_id:
        raise CanonicalProblem(RES_NOT_FOUND, 404, NO_SUCH_MODEL)
    return model


def _unique_conflict(error: IntegrityError) -> CanonicalProblem | None:
    """Turn a unique violation into the canonical 409, or return None.

    The constraints are the second defence the design counts on, so the caller
    has to be told the registration conflicted -- a raw 500 would report our bug
    for their duplicate.

    Only the constraints named in ``UNIQUE_CONFLICTS`` become 409. A unique
    violation this module does not know about is left to propagate (Codex #191,
    non-blocking): matching on the state code alone would dress a constraint added
    later as "your digest is a duplicate", which is our defect reported as the
    caller's mistake. Anything that is not a unique violation propagates for the
    same reason.
    """
    original = error.orig
    constraint = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint is None:
        # Not every driver fills ``diag``; the constraint name is in the message
        # in that case, and matching it is better than reporting a 500.
        text = str(original)
        constraint = next((name for name in UNIQUE_CONFLICTS if name in text), None)
    if constraint in UNIQUE_CONFLICTS:
        return CanonicalProblem(GRAPH_PRECONDITION, 409, UNIQUE_CONFLICTS[constraint])
    return None


def _derived_uri(model: Model, version: str) -> str:
    """The canonical address of the version being registered (Codex #191 F2).

    Built from the parent model's name and the requested version, which is all
    ``inv://models/<name>@<version>`` contains, so there is nothing for a caller
    to supply and nothing to validate. ``build_uri`` is the product's own builder
    (ADR-010) rather than an f-string here, so this address and the resolver's
    grammar cannot drift.

    A model name or version that the grammar cannot express is a request error,
    not a 500: the version comes from this request, and a name that cannot be
    addressed is a registration that could never be resolved.
    """
    try:
        return build_uri("model", name=model.name, version=version)
    except ValueError:
        raise CanonicalProblem(
            VAL_REQUEST,
            422,
            "This model and version cannot be addressed: a name must not contain "
            "'@' or '/' and a version must not contain '/'.",
        ) from None


def _response(row) -> schemas.ModelVersionResponse:
    return schemas.ModelVersionResponse(
        modelVersionId=row.model_version_id,
        modelId=row.model_id,
        version=row.version,
        stage="draft",
        contentSha256=row.content_sha256,
        byteSize=int(row.byte_size or 0),
        uri=row.uri,
        createdAt=row.created_at,
    )


async def register_version(
    project_id: str,
    model_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    settings: Settings = Depends(get_settings),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Any:
    """Register a draft model version, once per idempotency key.

    The body is parsed here rather than declared as a parameter: FastAPI
    validates a declared model before the handler runs and its
    ``RequestValidationError`` handler adds a top-level ``fields`` key that the
    canonical schema forbids. The clock is read for the same kind of reason: a
    dependency would fix the time before the body and the lock, so it is read
    once, after both.
    """
    factory = make_session_factory(request.app.state.engine)

    # (1) Permission first, in its own short transaction. A caller who may not
    # write learns nothing from how their key or their body is judged, and
    # nothing is held open while the body arrives.
    with factory() as session:
        with session.begin():
            with tenant_scope(session, principal.tenant_id):
                _require_approval(session, principal=principal, project_id=project_id)

    key = _require_idempotency_key(idempotency_key)
    payload = strict_json_object(
        await read_bounded_body(request),
        content_type=request.headers.get("content-type"),
        content_encoding=request.headers.get("content-encoding"),
    )
    proposal = validate_strict(schemas.ModelVersionRegisterRequest, payload)

    # The path is part of what the key identifies: the same key used for a
    # different model is a conflict, not a replay of the first model's answer.
    ledger_payload = {
        "modelId": model_id,
        "request": proposal.model_dump(by_alias=True, mode="json"),
    }

    # (2) One atomic transaction: serialise, re-check, bind, register, record.
    with factory() as session:
        with session.begin():
            with tenant_scope(session, principal.tenant_id), bounded_lock_wait(
                session, timeout_ms=settings.business_lock_timeout_ms
            ):
                # IDEM-6: the serialisation point comes before any resource row,
                # in every route, so the lock order in this lane is one order.
                serialise_idempotent_write(
                    session,
                    tenant_id=principal.tenant_id,
                    endpoint=ENDPOINT,
                    idempotency_key=key,
                    project_id=project_id,
                )
                # Re-checked after the lock: a membership revoked between the
                # two spans must not be able to write, and must not be able to
                # read a stored response either.
                _require_approval(session, principal=principal, project_id=project_id)
                # Read once, here: after the body the caller paced and after the
                # wait for the lock, so every stamp this request writes is the
                # time it actually did the work (Codex #191 F3).
                now = request.app.state.clock()
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
                        error,
                        table=TRANSLATION,
                        detail="That idempotency key was used with a different request.",
                    ) from None
                if replayed is not None:
                    # Exact replay: the stored body, and the status this route
                    # always returns, which is the status that was stored.
                    return replayed
                model = _model_in_project(
                    session,
                    tenant_id=principal.tenant_id,
                    project_id=project_id,
                    model_id=model_id,
                )
                try:
                    row = register_model_version(
                        session,
                        tenant_id=principal.tenant_id,
                        model_id=model_id,
                        version=proposal.version,
                        content_sha256=proposal.content_sha256,
                        uri=_derived_uri(model, proposal.version),
                        now=now,
                        byte_size=proposal.byte_size,
                    )
                except IntegrityError as error:
                    conflict = _unique_conflict(error)
                    if conflict is None:
                        raise
                    raise conflict from None
                except InvError as error:
                    raise translate(error, table=TRANSLATION) from None
                body = _response(row).model_dump(by_alias=True, mode="json")
                record_event(
                    session,
                    now=now,
                    actor_type="user",
                    actor_id=principal.user_id,
                    action="model_version.register",
                    outcome="allow",
                    tenant_id=principal.tenant_id,
                    trace_id=getattr(request.state, "trace_id", None),
                    target_type="model_version",
                    target_id=row.model_version_id,
                    # Identifiers and the digest, which are values the caller
                    # named. ``uri`` is caller-written text and is not recorded,
                    # for the reason ``storage`` states for a declared path.
                    detail={
                        "projectId": project_id,
                        "modelId": model_id,
                        "version": row.version,
                        "contentSha256": row.content_sha256,
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
                    response_body=body,
                    now=now,
                    ttl_seconds=settings.idempotency_ttl_seconds,
                    project_id=project_id,
                )
    return body


def register(router: APIRouter) -> None:
    """Add the route to the projects router.

    ``inv.business_surface.BusinessDispatch`` selects business traffic by
    reading ``projects.router.routes``, and ``include_router`` on an
    ``APIRouter`` leaves only a lazy placeholder there, so the route has to be
    added with ``add_api_route`` to be served at all.
    """
    router.add_api_route(
        REGISTER_PATH,
        register_version,
        methods=["POST"],
        status_code=201,
        response_model=schemas.ModelVersionResponse,
        tags=["model-registry"],
        name="register_model_version",
    )
