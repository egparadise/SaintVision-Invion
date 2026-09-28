"""W4: extend a model version's retention pin (G-04·G-05 design §2, §5-3).

``POST /projects/{project_id}/models/{model_id}/versions/{version}/retention-pin``

``pin_retention`` has existed in ``services/lineage.py`` since S10-ST and no
HTTP request has ever reached it. Its rule is one sentence -- *extend, never
shorten* -- and its signature is unchanged here: the route supplies the
boundary and the locking; the service decides the value.

**Write grade is ``canApprove``**, live against the database, as ``model_release``
and ``model_versions`` do it. A retention pin is what makes a version
releasable, so it is the approval grade, not membership.

**The lock contract (Codex F3, design §5-3), in one READ COMMITTED transaction
and in this order and no other:**

1. idempotency serialisation point (advisory lock on the key; IDEM-6),
2. live ``canApprove``,
3. the ledger: exact replay, or ``GRAPH-0002/409`` for the same key with a
   different request,
4. parent ``models`` row read and bound to the path's project, then the one
   ``model_versions`` row ``FOR UPDATE`` with ``populate_existing`` -- the same
   ``_locked_version`` #167's release uses, so pin, release and (later) verify
   always lock in the order *parent read, then the version row*,
5. live ``canApprove`` **again** (a revocation between the two spans, or
   during the lock wait, must not write),
6. ``max(current, until)``: ``pin_retention`` is handed the id of the row this
   transaction has just locked and refreshed, and reads it back through the
   session's identity map -- the route asserts it received that very object,
   so a path that reads a pre-lock value cannot exist silently,
7. audit and the ledger row, in the same transaction as the write.

A shorter or equal ``until`` is a 200 no-op that changes nothing (the service
never shortens); the response says ``extended: false`` so a caller can tell.

**Lock waits are bounded** by the lane's one helper (``api/lock_wait.py``, card
84): ``SET LOCAL lock_timeout`` from ``Settings.business_lock_timeout_ms``. Ordinary
contention (a release or another pin committing) waits and then proceeds on the
committed row; a wait that exceeds the budget, or a deadlock, is answered
``SYS-0001/503/retryable=true`` with nothing written and no value from the
database in the answer.

**Two transaction spans.** The permission is checked in its own short
transaction, the body is read with no transaction open (the caller controls how
slowly it arrives), and the write is the one transaction above.

**The clock is read after the lock** (Codex #191 F3, #196 F2). ``Depends(get_now)``
would stamp the request before the body the caller paced and before the wait
for the row lock; after a long contention the ledger's ``expires_at`` could
already be in the past and the audit row older than the write. The app clock
is read once, after the advisory lock and the live permission, and that one
instant is used for the ledger, the audit row and nothing else.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Mapping

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from ...config import Settings
from ...db.session import make_session_factory, tenant_scope
from ...errors import (
    AUTH_PROJECT_SCOPE,
    GRAPH_IDEMPOTENCY_CONFLICT,
    RES_ARTIFACT_NOT_FOUND,
    InvError,
)
from ...identity.principal import Principal
from ...services import projects as project_service
from ...services.audit import record_event
from ...services.lineage import pin_retention
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
    CanonicalProblem,
    read_bounded_body,
    strict_json_object,
    translate,
    validate_strict,
)
from .model_release import _locked_version
from .model_versions import _require_idempotency_key

PIN_PATH = "/projects/{project_id}/models/{model_id}/versions/{version}/retention-pin"

#: The idempotency ledger's ``endpoint`` for this route (IDEM-2): a constant, so
#: a renamed path cannot silently start a new key space.
ENDPOINT = "POST /v1/projects/{project_id}/models/{model_id}/versions/{version}/retention-pin"

#: Every ``InvError`` reachable from the calls below, and its canonical form.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
    RES_ARTIFACT_NOT_FOUND: (RES_NOT_FOUND, 404, False),
    GRAPH_IDEMPOTENCY_CONFLICT: (GRAPH_PRECONDITION, 409, False),
}


def _require_approval(session: Session, *, principal: Principal, project_id: str) -> None:
    """Live project access plus the approval grade, or a canonical refusal."""
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
            AUTH_PROJECT, 403, "Pinning a model version's retention requires approval permission."
        )


def _response(row, *, extended: bool) -> schemas.RetentionPinResponse:
    return schemas.RetentionPinResponse(
        modelVersionId=row.model_version_id,
        modelId=row.model_id,
        version=row.version,
        stage=row.stage,
        retentionPinnedUntil=row.retention_pinned_until,
        extended=extended,
    )


async def pin_model_version_retention(
    project_id: str,
    model_id: str,
    version: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    settings: Settings = Depends(get_settings),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Any:
    """Extend the retention pin to ``until``, once per idempotency key."""
    factory = make_session_factory(request.app.state.engine)

    # (1) Permission first, in its own short transaction, with nothing held
    # open while the body arrives.
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
    proposal = validate_strict(schemas.RetentionPinRequest, payload)
    # The path is part of what the key identifies: the same key for another
    # version is a conflict, not a replay of the first version's answer.
    ledger_payload = {
        "modelId": model_id,
        "version": version,
        "request": proposal.model_dump(by_alias=True, mode="json"),
    }

    # (2) One atomic transaction, in the §5-3 order.
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
                # Read once, here: after the body the caller paced and after
                # the wait for the serialisation point, so every stamp this
                # request writes is the time it actually did the work.
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
                        error,
                        table=TRANSLATION,
                        detail="That idempotency key was used with a different request.",
                    ) from None
                if replayed is not None:
                    return replayed
                row = _locked_version(
                    session,
                    tenant_id=principal.tenant_id,
                    project_id=project_id,
                    model_id=model_id,
                    version=version,
                )
                # Re-checked after the lock: a revocation during the wait must
                # not extend anything.
                _require_approval(session, principal=principal, project_id=project_id)
                before = row.retention_pinned_until
                try:
                    pinned = pin_retention(
                        session,
                        tenant_id=principal.tenant_id,
                        model_version_id=row.model_version_id,
                        until=proposal.until,
                    )
                except InvError as error:
                    raise translate(error, table=TRANSLATION) from None
                if pinned is not row:
                    # The route<->service invariant of §5-3: the service must
                    # have judged the row this transaction locked and refreshed,
                    # not another load of it.
                    raise RuntimeError("pin_retention did not act on the locked model version row")
                extended = pinned.retention_pinned_until != before
                body = _response(pinned, extended=extended).model_dump(by_alias=True, mode="json")
                record_event(
                    session,
                    now=now,
                    actor_type="user",
                    actor_id=principal.user_id,
                    action="model_version.retention_pin",
                    outcome="allow",
                    tenant_id=principal.tenant_id,
                    trace_id=getattr(request.state, "trace_id", None),
                    target_type="model_version",
                    target_id=pinned.model_version_id,
                    detail={
                        "projectId": project_id,
                        "modelId": model_id,
                        "version": pinned.version,
                        "requestedUntil": proposal.until.isoformat(),
                        "retentionPinnedUntil": pinned.retention_pinned_until.isoformat(),
                        "extended": extended,
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
        PIN_PATH,
        pin_model_version_retention,
        methods=["POST"],
        status_code=200,
        response_model=schemas.RetentionPinResponse,
        tags=["model-registry"],
        name="pin_model_version_retention",
    )
