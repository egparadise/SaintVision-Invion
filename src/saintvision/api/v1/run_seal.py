"""W1: seal the record of a finished run (G-04·G-05 design §5-2, PR 7 of 8).

``POST /projects/{project_id}/runs/{run_id}/record``

``seal_run_record`` has existed in ``services/records.py`` since S09 with no
HTTP request path. This module is that path, on the Codex seal contract
(design v1.2.1 §5-2): **the integrity values are the server's, not the
caller's.** The set of artifacts sealed, their digests, the component versions,
the bundle and its hash are all derived from rows this transaction has locked
-- the request may only say which *role* each server-derived artifact gets.
A request cannot add an artifact, leave one out, or name a digest.

**One READ COMMITTED transaction, in this order and no other:**

1. ``tenant_scope`` + a cheap live ``canApprove`` preflight (its own short
   transaction, before the body the caller paces is read);
2. the ``(tenant, project, endpoint, Idempotency-Key)`` serialisation point
   (transaction-scoped advisory lock, IDEM-6) and the ledger: exact replay, or
   ``GRAPH-0002/409`` for the same key with a different request;
3. the ``runs`` row ``FOR UPDATE`` + ``populate_existing``, re-bound to the
   path's project through its workload, and re-checked to be terminal with
   its final fields present;
4. live ``canApprove`` **again** (a revocation during the wait must not seal);
5. the bundle and the workload read from the locked run's rows, then the run's
   artifacts locked in ``artifact_id`` order and re-checked (active, verified,
   this run) -- **all of them** are the sealed set; a role mapping for an id
   outside that set is ``GRAPH-0002/409``, an unmapped artifact is ``other``;
6. the existing record, if any: the canonical seal intent (the sorted
   ``(artifact_id, role, checksum)`` set plus the derived values) is compared
   with the stored record and pins -- identical is the natural idempotent
   success, different is ``GRAPH-0002/409``; otherwise the record, the pins,
   the audit row and the ledger row are written in this transaction.

``uq_run_records_run_id`` is the last defence, not the serialisation: with
the run row locked, two sealers cannot both reach step 6, so an
``IntegrityError`` here would be our bug and is answered as ``GRAPH-0002/409``
with the transaction rolled back (no partial pins). A lock wait past the
budget or a deadlock is ``SYS-0001/503/retryable=true``.

The clock is read once, after the serialisation point and the live
permission (Codex #191 F3), and stamps the record, the audit row and the
ledger row.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Mapping

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...config import Settings
from ...db.models import Artifact, ContextBundle, EvidenceEnvelope, Run, RunRecordArtifact, Workload
from ...db.session import make_session_factory, tenant_scope
from ...errors import (
    AUTH_PROJECT_SCOPE,
    GRAPH_IDEMPOTENCY_CONFLICT,
    RES_ARTIFACT_NOT_FOUND,
    RES_RUN_NOT_FOUND,
    VAL_SCHEMA,
    InvError,
)
from ...identity.principal import Principal
from ...runs.state import is_terminal
from ...services import projects as project_service
from ...services import records as record_service
from ...services.audit import record_event
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
from .project_scope import NO_SUCH_RUN
from .run_records import _response as record_response

SEAL_PATH = "/projects/{project_id}/runs/{run_id}/record"

#: The idempotency ledger's ``endpoint`` for this route (IDEM-2): a constant.
ENDPOINT = "POST /v1/projects/{project_id}/runs/{run_id}/record"

#: What an ``Idempotency-Key`` may be (the ledger column is ``String(128)``).
IDEMPOTENCY_KEY_PATTERN = r"[A-Za-z0-9._:-]{1,128}"

#: The role an artifact is sealed under when the request maps none.
DEFAULT_ROLE = "other"

#: Every ``InvError`` reachable from the calls below, and its canonical form.
#: ``VAL-SCHEMA`` from the service is a *state* precondition here (not
#: terminal, unverified artifact, foreign bundle), hence ``GRAPH-0002``.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
    RES_RUN_NOT_FOUND: (RES_NOT_FOUND, 404, False),
    RES_ARTIFACT_NOT_FOUND: (GRAPH_PRECONDITION, 409, False),
    VAL_SCHEMA: (GRAPH_PRECONDITION, 409, False),
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
            AUTH_PROJECT, 403, "Sealing a run record requires approval permission."
        )


def _require_idempotency_key(raw: str | None) -> str:
    if raw is None or not re.fullmatch(IDEMPOTENCY_KEY_PATTERN, raw):
        raise CanonicalProblem(
            VAL_REQUEST,
            422,
            "An Idempotency-Key header of up to 128 identifier characters is required.",
        )
    return raw


def _locked_run(session: Session, *, tenant_id, project_id: str, run_id: str) -> Run:
    """The run row, locked and refreshed, bound to the path's project (step 3).

    ``FOR UPDATE`` on the run is the serialisation of every sealer: a second
    request waits here and then sees the first one's record in step 6.
    """
    run = session.scalars(
        select(Run)
        .where(Run.run_id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if run is None or run.tenant_id != tenant_id:
        raise CanonicalProblem(RES_NOT_FOUND, 404, NO_SUCH_RUN)
    workload = session.get(Workload, run.workload_id, populate_existing=True)
    if workload is None or workload.tenant_id != tenant_id or workload.project_id != project_id:
        raise CanonicalProblem(RES_NOT_FOUND, 404, NO_SUCH_RUN)
    if not is_terminal(run.state) or not run.termination_reason:
        raise CanonicalProblem(
            GRAPH_PRECONDITION, 409, "Only a finished run can be sealed."
        )
    return run


def _latest_bundle(session: Session, *, tenant_id, run_id: str) -> ContextBundle | None:
    return session.scalars(
        select(ContextBundle)
        .where(ContextBundle.tenant_id == tenant_id, ContextBundle.run_id == run_id)
        .order_by(ContextBundle.built_at.desc(), ContextBundle.bundle_id.desc())
        .limit(1)
    ).first()


def _evidence_versions(session: Session, *, tenant_id, run: Run) -> dict[str, str]:
    """The component versions the run's evidence recorded, if any."""
    if run.evidence_id is None:
        return {}
    envelope = session.scalars(
        select(EvidenceEnvelope)
        .where(EvidenceEnvelope.tenant_id == tenant_id, EvidenceEnvelope.evidence_id == run.evidence_id)
        .order_by(EvidenceEnvelope.recorded_at.desc())
        .limit(1)
    ).first()
    return dict(envelope.component_versions or {}) if envelope is not None else {}


def _locked_artifacts(session: Session, *, tenant_id, run_id: str) -> list[Artifact]:
    """The run's sealable artifacts, locked in ``artifact_id`` order (step 5).

    Locked because they are the mutable rows the record will copy from; the
    fixed order is the lock order every sealer uses, so two sealers cannot
    deadlock on each other's artifacts.
    """
    rows = list(
        session.scalars(
            select(Artifact)
            .where(Artifact.tenant_id == tenant_id, Artifact.run_id == run_id)
            .order_by(Artifact.artifact_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).all()
    )
    return [
        row for row in rows
        if row.status == "active" and row.checksum_sha256 is not None and row.run_id == run_id
    ]


def _roles(proposal: schemas.RunRecordSealRequest, artifacts: list[Artifact]) -> dict[str, str]:
    """Each server-derived artifact's role: the request's mapping or ``other``.

    A mapping for an artifact outside the server-derived set is refused: the
    caller cannot add to the sealed set, so a mapping that names something
    else is a request about a different run or a stale view of this one.
    """
    ids = {artifact.artifact_id for artifact in artifacts}
    unknown = sorted(set(proposal.roles) - ids)
    if unknown:
        raise CanonicalProblem(
            GRAPH_PRECONDITION,
            409,
            "The role mapping names an artifact that is not part of this run's sealable set.",
        )
    return {artifact.artifact_id: proposal.roles.get(artifact.artifact_id, DEFAULT_ROLE) for artifact in artifacts}


def _intent(*, artifacts: list[Artifact], roles: dict[str, str], bundle, workload, versions) -> dict[str, Any]:
    """The canonical seal intent: what this request would write, in a form
    that can be compared with what an earlier request wrote."""
    return {
        "pins": sorted((a.artifact_id, roles[a.artifact_id], a.checksum_sha256) for a in artifacts),
        "bundleId": bundle.bundle_id if bundle is not None else None,
        "bundleHash": bundle.bundle_hash if bundle is not None else None,
        "workloadSpecSha256": workload.spec_sha256,
        "componentVersions": dict(sorted(versions.items())),
    }


def _stored_intent(session: Session, *, tenant_id, record) -> dict[str, Any]:
    pins = session.scalars(
        select(RunRecordArtifact).where(
            RunRecordArtifact.tenant_id == tenant_id, RunRecordArtifact.record_id == record.record_id
        )
    ).all()
    return {
        "pins": sorted((p.artifact_id, p.role, p.checksum_sha256) for p in pins),
        "bundleId": record.bundle_id,
        "bundleHash": record.bundle_hash,
        "workloadSpecSha256": record.workload_spec_sha256,
        "componentVersions": dict(sorted((record.component_versions or {}).items())),
    }


async def seal_run_record(
    project_id: str,
    run_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    settings: Settings = Depends(get_settings),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Any:
    """Seal the run's record from the server's own rows, once per key."""
    factory = make_session_factory(request.app.state.engine)

    # (1) Permission first, in its own short transaction, before the body.
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
    proposal = validate_strict(schemas.RunRecordSealRequest, payload)
    ledger_payload = {"runId": run_id, "request": proposal.model_dump(by_alias=True, mode="json")}

    # (2..6) One atomic transaction in the §5-2 order.
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
                run = _locked_run(
                    session, tenant_id=principal.tenant_id, project_id=project_id, run_id=run_id
                )
                _require_approval(session, principal=principal, project_id=project_id)
                workload = session.get(Workload, run.workload_id)
                bundle = _latest_bundle(session, tenant_id=principal.tenant_id, run_id=run.run_id)
                versions = _evidence_versions(session, tenant_id=principal.tenant_id, run=run)
                if bundle is not None:
                    for name, value in (bundle.component_versions or {}).items():
                        versions.setdefault(name, value)
                artifacts = _locked_artifacts(session, tenant_id=principal.tenant_id, run_id=run.run_id)
                roles = _roles(proposal, artifacts)
                intent = _intent(artifacts=artifacts, roles=roles, bundle=bundle, workload=workload, versions=versions)

                # (6) an existing record: the natural idempotent success or the 409
                existing = None
                try:
                    existing = record_service.get_record(session, tenant_id=principal.tenant_id, run_id=run.run_id)
                except InvError as error:
                    if error.code != RES_RUN_NOT_FOUND:
                        raise translate(error, table=TRANSLATION) from None
                if existing is not None:
                    stored = _stored_intent(session, tenant_id=principal.tenant_id, record=existing)
                    if stored != intent:
                        raise CanonicalProblem(
                            GRAPH_PRECONDITION,
                            409,
                            "This run is already sealed with a different record.",
                        )
                    record = existing
                    created = False
                else:
                    try:
                        record = record_service.seal_run_record(
                            session,
                            tenant_id=principal.tenant_id,
                            run_id=run.run_id,
                            now=now,
                            component_versions=intent["componentVersions"],
                            artifacts=[
                                record_service.ArtifactPin(artifact.artifact_id, roles[artifact.artifact_id])
                                for artifact in artifacts
                            ],
                            bundle_id=bundle.bundle_id if bundle is not None else None,
                        )
                    except IntegrityError as error:
                        # The last defence fired: with the run locked this is
                        # our bug, and the caller is told the run is sealed
                        # rather than shown a raw 500; the transaction rolls
                        # back, so no pin is left behind.
                        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
                        if constraint == "uq_run_records_run_id" or "uq_run_records_run_id" in str(error.orig):
                            raise CanonicalProblem(
                                GRAPH_PRECONDITION, 409, "This run is already sealed."
                            ) from None
                        raise
                    except InvError as error:
                        raise translate(error, table=TRANSLATION) from None
                    created = True
                body = record_response(record).model_dump(by_alias=True, mode="json")
                record_event(
                    session,
                    now=now,
                    actor_type="user",
                    actor_id=principal.user_id,
                    action="run_record.seal",
                    outcome="allow",
                    tenant_id=principal.tenant_id,
                    trace_id=getattr(request.state, "trace_id", None),
                    target_type="run_record",
                    target_id=record.record_id,
                    detail={
                        "projectId": project_id,
                        "runId": run.run_id,
                        "created": created,
                        "artifactCount": len(artifacts),
                        "bundleId": intent["bundleId"],
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
        SEAL_PATH,
        seal_run_record,
        methods=["POST"],
        status_code=200,
        response_model=schemas.RunRecordResponse,
        tags=["run-records"],
        name="seal_run_record",
    )
