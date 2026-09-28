"""R3: read the metadata of a run's context bundle, with its hash verified.

``GET /projects/{project_id}/runs/{run_id}/context-bundle``

Read grade is live project membership (``lineage_query._membership``); the
path's project is bound to the run through its workload
(``project_scope.run_in_project``) before the bundle is looked up, so a run in
another project is the same 404 as a run that does not exist, and a bundle is
only ever the run's own.

**Which bundle.** A run may have been given more than one bundle. The sealed
record is the account of what the run was given, so when the run has a sealed
record that pins a bundle, that bundle is the one; a run without one (not
sealed yet, or sealed without a bundle) answers with its most recently built
bundle. ``sealed`` in the response says which case it is.

**What is answered.** Identifiers, digests and counts only. Each item is its
ordinal, source id, version, kind, content digest and byte length -- never the
content, and not the caller-written ``source_uri`` (free text). Exposing the
content is a separate decision (design §9): the secret scan runs at storage
time only.

``hashVerified: false`` is a fact reported with 200: the bundle is the account
of what was given, and stored content that no longer matches it is an integrity
finding, not a request error. A bundle item whose snapshot is *missing* is a
different thing -- the bundle can no longer be reproduced at all -- and is the
canonical 409.

The services are called, not re-implemented: ``read_bundle`` decides what a
missing snapshot means and ``verify_bundle`` what "still matches" means.
"""

from __future__ import annotations

from typing import Mapping

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.models import ContextBundle
from ...errors import AUTH_PROJECT_SCOPE, CTX_SNAPSHOT_MISSING, RES_RUN_NOT_FOUND, InvError
from ...identity.principal import Principal
from ...services import context as context_service
from ...services import records as record_service
from .. import schemas
from ..deps import get_principal, get_session
from ..problem import (
    AUTH_PROJECT,
    GRAPH_PRECONDITION,
    RES_NOT_FOUND,
    CanonicalProblem,
    read_bounded_body,
    require_absent_body,
    translate,
)
from .lineage_query import _membership
from .project_scope import run_in_project

BUNDLE_PATH = "/projects/{project_id}/runs/{run_id}/context-bundle"

NO_SUCH_BUNDLE = "No context bundle for this run."

#: Every ``InvError`` this route can reach, and its canonical form.
#:
#: ``CTX-SNAPSHOT-MISSING`` from ``read_bundle``/``verify_bundle`` is a state
#: precondition here (the stored bundle cannot be reproduced), so it is
#: ``GRAPH-0002``; ``RES-RUN-NOT-FOUND`` is ``get_record``'s "no sealed record"
#: and is caught, not translated, because it selects the fallback rather than
#: refusing -- it stays in the table so the enumeration of reachable codes is
#: honest.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
    RES_RUN_NOT_FOUND: (RES_NOT_FOUND, 404, False),
    CTX_SNAPSHOT_MISSING: (GRAPH_PRECONDITION, 409, False),
}


def _bundle_for_run(session: Session, *, tenant_id, run_id: str) -> tuple[ContextBundle, bool]:
    """The run's bundle: the sealed record's when it pins one, else the latest.

    Returns ``(bundle, sealed)``. The record's pin is checked against the run
    again even though sealing already did: the row this answers for must be
    the path's run, whatever the record says.
    """
    try:
        record = record_service.get_record(session, tenant_id=tenant_id, run_id=run_id)
    except InvError as error:
        if error.code != RES_RUN_NOT_FOUND:
            raise translate(error, table=TRANSLATION) from None
        record = None
    if record is not None and record.bundle_id is not None:
        bundle = session.get(ContextBundle, record.bundle_id, populate_existing=True)
        if bundle is None or bundle.tenant_id != tenant_id or bundle.run_id != run_id:
            raise CanonicalProblem(RES_NOT_FOUND, 404, NO_SUCH_BUNDLE)
        return bundle, True
    bundle = session.scalars(
        select(ContextBundle)
        .where(ContextBundle.tenant_id == tenant_id, ContextBundle.run_id == run_id)
        .order_by(ContextBundle.built_at.desc(), ContextBundle.bundle_id.desc())
        .limit(1)
    ).first()
    if bundle is None:
        raise CanonicalProblem(RES_NOT_FOUND, 404, NO_SUCH_BUNDLE)
    return bundle, False


def _item(entry, content: str) -> schemas.ContextBundleItemSummary:
    return schemas.ContextBundleItemSummary(
        ordinal=int(entry.ordinal),
        item_id=entry.item_id,
        item_version=int(entry.item_version),
        kind=entry.kind,
        content_hash=entry.content_hash,
        byte_size=len(content.encode("utf-8")),
        confidence=entry.confidence,
        redacted=bool(entry.redacted),
    )


async def read_context_bundle(
    project_id: str,
    run_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> schemas.ContextBundleResponse:
    """The run's bundle: metadata, item summaries and whether its hash still holds."""
    _membership(session, principal=principal, project_id=project_id)
    require_absent_body(await read_bounded_body(request))
    run = run_in_project(session, tenant_id=principal.tenant_id, project_id=project_id, run_id=run_id)
    bundle, sealed = _bundle_for_run(session, tenant_id=principal.tenant_id, run_id=run.run_id)
    try:
        entries = context_service.read_bundle(
            session, tenant_id=principal.tenant_id, bundle_id=bundle.bundle_id
        )
        verified = context_service.verify_bundle(
            session, tenant_id=principal.tenant_id, bundle_id=bundle.bundle_id
        )
    except InvError as error:
        raise translate(
            error, table=TRANSLATION, detail="A bundle item's snapshot is missing; the bundle cannot be reproduced."
        ) from None
    return schemas.ContextBundleResponse(
        bundle_id=bundle.bundle_id,
        run_id=bundle.run_id,
        bundle_hash=bundle.bundle_hash,
        hash_verified=bool(verified),
        sealed=sealed,
        item_count=int(bundle.item_count),
        total_bytes=int(bundle.total_bytes),
        retrieval_strategy=bundle.retrieval_strategy,
        component_versions=dict(bundle.component_versions or {}),
        token_estimate=bundle.token_estimate,
        built_at=bundle.built_at,
        items=[_item(entry, content) for entry, content in entries],
    )


def register(router: APIRouter) -> None:
    """Add the route to the projects router (same reason as ``lineage_query``)."""
    router.add_api_route(
        BUNDLE_PATH,
        read_context_bundle,
        methods=["GET"],
        response_model=schemas.ContextBundleResponse,
        tags=["run-records"],
        name="read_context_bundle",
    )
