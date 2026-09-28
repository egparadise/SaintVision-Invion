"""Release a model version, binding an importer's declaration to the manifest.

VF-CL-03 closed a blocker whose wording was precise: the import adapter had no
request path. It still has none if a service call is buried where no HTTP
request reaches it, so this module is the request path -- and it is the only one
in the business model-registry lane, because ``register_model_version``,
``verify_model_version`` and ``pin_retention`` remain unreachable over HTTP.

**Why release and not draft.** The declaration this route compares against is
the kernel's committed ``ModelManifest``, which does not exist while a version
is a draft. ``release_model_version`` is already the checking step -- it refuses
an unverified, unpinned or untraceable version -- so the comparison belongs
beside those refusals rather than before them.

**Where it is mounted.** The handler is declared here and added to the
``projects`` router by ``register()``, because
``inv.business_surface.BusinessDispatch`` selects business traffic by reading
``projects.router.routes`` (plus settings and adapters). A new top-level router
would be registered on the business app and never receive a request in the
deployed topology, and the dispatch list is a kernel-owned file. Nesting a
router does not work either: ``include_router`` on an ``APIRouter`` records a
lazy placeholder, so the route object is not in ``routes`` when dispatch reads
it. ``add_api_route`` puts the real route there, with no kernel change.

**The kernel credential.** The observation is fetched with the caller's own
bearer token, not a service identity, so the kernel applies its authorisation to
the same principal. A service identity here would let this route read
commitments the caller could not read for themselves.

That choice puts the credential on the wire, so the transport is fail-closed
around it: only http/https, **no redirects at all** (Python's redirect handler
copies ``Authorization`` onto the new request, so a 30x from the kernel to
another origin would hand the caller's bearer to that origin), and a bounded
read. Every one of those refusals is the same ``SYS-0001`` and carries no value
from the response.

**Why a thread.** In the canonical topology the kernel and this app are the same
process behind ``BusinessDispatch``, so this GET can be a self-call. ``urllib``
is synchronous, and calling it directly from an async handler would block the
event loop that has to serve the very request being made -- the call would sit
there until its own timeout. The fetch therefore runs in a worker thread, which
is what the kernel already does for its blocking work. The alternative was to
call the kernel's observation object in-process and skip HTTP; that would mean
reaching into kernel-owned code and rebuilding its identity object, so the
kernel's own authorisation would no longer be the single gate on the
observation.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Mapping

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ...config import Settings
from ...adapters.model_import import (
    MODEL_IMPORT_DECLARATION_MISMATCH,
    require_exact_declaration,
)
from ...db.models.lineage import Model, ModelVersion
from ...db.session import make_session_factory, tenant_scope
from ...errors import AUTH_PROJECT_SCOPE, VAL_SCHEMA, InvError
from ...identity.principal import Principal
from ...services import projects as project_service
from ...services.audit import record_event
from ...services.lineage import release_model_version, trace_model
from .. import schemas
from ..deps import get_now, get_principal, get_settings
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

#: The declaration fields compared against the manifest. Kept beside the route
#: so the request model, the comparison and the audit record cannot disagree.
DECLARED = ("licensePolicy", "classification")

#: This route's translation table. Every business code reachable from the calls
#: below appears here; ``tests`` enumerate them and fail if one is missing.
#:
#: ``VAL-SCHEMA`` is a *state precondition* at this call site --
#: ``release_model_version`` raises it for an unverified, unpinned or
#: untraceable version -- so it becomes ``GRAPH-0002``. The same code means a
#: malformed request on other routes, which is why the table is per route and
#: not a global rule.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    VAL_SCHEMA: (GRAPH_PRECONDITION, 409, False),
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
    MODEL_IMPORT_DECLARATION_MISMATCH: ("MODEL-0009", 409, False),
}

#: How long the kernel observation fetch may take. A business request that hangs
#: on the kernel is worse than one that refuses: the caller can retry a 503.
OBSERVATION_TIMEOUT_SECONDS = 5.0

#: The most the observation may weigh. ``ModelCommitObservation`` is fifteen short
#: fields; 64 KiB is the kernel's own request ceiling and is generous here. An
#: unbounded ``read()`` would let an upstream decide how much memory this process
#: spends.
MAX_OBSERVATION_BYTES = 65536


class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect instead of following it.

    ``HTTPRedirectHandler`` copies the request headers onto the redirected
    request, ``Authorization`` included, so following a 30x to another origin
    would disclose the caller's bearer token to that origin. There is no
    legitimate reason for the kernel to redirect this GET.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        raise urllib.error.HTTPError(
            req.full_url, code, "redirect refused", headers, fp
        )


def fetch_commitment(
    *, base_url: str, credential: str, project_id: str, model_id: str, version: str
) -> dict[str, Any]:
    """GET the kernel's commitment observation with the caller's credential.

    ``urllib`` rather than a client library: the runtime dependency list has no
    HTTP client, and adding one for a single GET would widen the deployment
    surface more than the call is worth. What that costs is an opener that has to
    be assembled deliberately -- the default one follows redirects and reads
    without a bound.
    """
    base = base_url.rstrip("/")
    if urllib.parse.urlsplit(base).scheme not in ("http", "https"):
        raise ValueError("kernel base URL must be http or https")
    url = (
        f"{base}/v1/projects/{project_id}"
        f"/models/{model_id}/versions/{version}/commitment"
    )
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url,
        headers={"Authorization": f"Bearer {credential}", "Accept": "application/json"},
        method="GET",
    )
    opener = urllib.request.build_opener(_RefuseRedirect)
    with opener.open(request, timeout=OBSERVATION_TIMEOUT_SECONDS) as response:
        # One byte over the bound is enough to know it is over; the rest is never
        # allocated.
        raw = response.read(MAX_OBSERVATION_BYTES + 1)
    if len(raw) > MAX_OBSERVATION_BYTES:
        raise ValueError("kernel observation exceeds the permitted size")
    return json.loads(raw)


async def _observation(
    request: Request, *, project_id: str, model_id: str, version: str
) -> dict[str, Any]:
    """The observation, strictly validated, or a canonical refusal.

    Validated even though the kernel sent it: "our own service produced it" is
    not a substitute for checking, and this is the value the release decision
    rests on.
    """
    from inv.contracts import validate_contract
    from inv.errors import DomainError

    fetcher = getattr(request.app.state, "model_commitment_fetcher", None) or fetch_commitment
    base_url = request.app.state.settings.kernel_base_url
    if not base_url:
        raise CanonicalProblem(
            SYS_UPSTREAM_UNAVAILABLE,
            503,
            "Model commitment observation is not configured.",
            retryable=True,
        )
    credential = (request.headers.get("authorization") or "").split(" ", 1)[-1].strip()
    try:
        # Blocking I/O off the event loop: in the canonical topology this is a
        # self-call, and blocking the loop would stop the request it is making.
        body = await run_in_threadpool(
            lambda: fetcher(
                base_url=base_url,
                credential=credential,
                project_id=project_id,
                model_id=model_id,
                version=version,
            )
        )
        validate_contract("ModelCommitObservation", body)
    except CanonicalProblem:
        raise
    except (
        # A contract violation is what ``validate_contract`` raises, and it is
        # the same answer as an unreachable kernel: we did not get an
        # observation we are willing to decide on.
        DomainError,
        urllib.error.URLError,
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        raise CanonicalProblem(
            SYS_UPSTREAM_UNAVAILABLE,
            503,
            "The model commitment observation could not be read.",
            retryable=True,
        ) from None
    # Unreachable while the contract pins ``committed`` to ``const: true``, and
    # kept anyway: a kernel that says "not committed" is not an outage, so it
    # must not be answered with the 503 above. Covered by a test that calls this
    # module with validation stubbed.
    if body.get("committed") is not True:
        raise CanonicalProblem(
            GRAPH_PRECONDITION,
            409,
            "The model version is not committed, so there is no declaration to compare.",
        )
    return body


def _require_approval(session: Session, *, principal: Principal, project_id: str) -> None:
    """Live project access plus the approval grade, or a canonical refusal.

    ``Principal.require_project`` is a snapshot taken at sign-in and says so
    itself; a membership revoked since then would still pass it.
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
            AUTH_PROJECT, 403, "Releasing a model version requires approval permission."
        )


def _locked_version(
    session: Session, *, tenant_id: uuid.UUID, project_id: str, model_id: str, version: str
) -> ModelVersion:
    """Resolve ``(project, model, version)`` to one locked row.

    ``model_versions`` has no ``project_id``, so the parent ``models`` row is
    the only way to bind the path's project -- and the absent, the other
    project's and the other tenant's all answer with the same 404, which is the
    rule ``require_project_access`` already states for projects.
    """
    parent = session.get(Model, model_id, populate_existing=True)
    if parent is None or parent.tenant_id != tenant_id or parent.project_id != project_id:
        raise CanonicalProblem(RES_NOT_FOUND, 404, "No such model version.")
    # ``populate_existing``: if this session already holds the row (a parent
    # relationship load, an earlier read), the locked SELECT overwrites it with
    # the committed state the lock now guards, instead of returning the stale
    # identity-map copy. W4's pin and #167's release both act on this row.
    row = session.scalars(
        select(ModelVersion)
        .where(ModelVersion.model_id == model_id, ModelVersion.version == version)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if row is None or row.tenant_id != tenant_id:
        raise CanonicalProblem(RES_NOT_FOUND, 404, "No such model version.")
    return row


def _rebind_identity(
    observation: Mapping[str, Any], *, project_id: str, model_id: str, version: str
) -> None:
    """The observation must describe the row this request named, not another.

    Mismatch answers 404 rather than a mismatch-specific code: telling the
    caller "that observation exists but is for something else" is the existence
    disclosure the 404 policy exists to prevent.
    """
    if (
        observation.get("projectId") != project_id
        or observation.get("modelId") != model_id
        or observation.get("version") != version
    ):
        raise CanonicalProblem(RES_NOT_FOUND, 404, "No such model version.")


def _require_release_preconditions(session: Session, row: ModelVersion) -> None:
    """The existing refusals, before the declaration is even looked at.

    ``release_model_version`` checks these too and this deliberately repeats
    them, for order rather than for safety: a caller whose version is not
    verified must be told that, not told their declaration differs, or they will
    read the answer as "fix the declaration and it will release".
    """
    if row.verified_at is None:
        raise CanonicalProblem(
            GRAPH_PRECONDITION, 409, "An unverified model version cannot be released."
        )
    if row.retention_pinned_until is None:
        raise CanonicalProblem(
            GRAPH_PRECONDITION,
            409,
            "A model version must be retention pinned before release.",
        )
    trace = trace_model(
        session, tenant_id=row.tenant_id, model_version_id=row.model_version_id
    )
    if trace["missing"]:
        raise CanonicalProblem(
            GRAPH_PRECONDITION,
            409,
            "The model version is not fully traceable: missing "
            + ", ".join(trace["missing"]),
            cause_ref=row.model_version_id,
        )


RELEASE_PATH = "/projects/{project_id}/models/{model_id}/versions/{version}/release"


def register(router: APIRouter) -> None:
    """Add the route to an existing router, prefix and all."""
    router.add_api_route(
        RELEASE_PATH,
        release_model,
        methods=["POST"],
        response_model=schemas.ModelReleaseResponse,
        tags=["model-registry"],
        name="release_model_version",
    )


async def release_model(
    project_id: str,
    model_id: str,
    version: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    now: dt.datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> Any:
    """Compare the importer's declaration with the manifest, then release.

    The body is read and parsed here rather than declared as a parameter:
    FastAPI validates a declared model before the handler runs, and its
    ``RequestValidationError`` handler adds a top-level ``fields`` key the
    canonical schema forbids. No annotation avoids that, so the handler owns the
    parse.

    Sessions are managed here rather than through ``get_session``, which opens a
    transaction and a tenant scope before the handler is entered. The kernel
    call must happen with no transaction open, so the work is three spans:
    permission, then HTTP, then one atomic transaction that re-checks the
    permission it no longer holds.
    """
    payload = strict_json_object(
        await read_bounded_body(request),
        content_type=request.headers.get("content-type"),
        content_encoding=request.headers.get("content-encoding"),
    )
    proposal = validate_strict(schemas.ModelReleaseRequest, payload)
    declared = proposal.model_dump(by_alias=True)

    factory = make_session_factory(request.app.state.engine)

    # Bounded as well (card 84 F1): effective_permission reads the user row FOR
    # SHARE, so a held FOR UPDATE on it would otherwise wait here forever.
    # (1) Permission, in its own short transaction, so nothing is held open
    # across the network call that follows.
    with factory() as session:
        with session.begin():
            with tenant_scope(session, principal.tenant_id), bounded_lock_wait(
                session, timeout_ms=settings.business_lock_timeout_ms
            ):
                _require_approval(session, principal=principal, project_id=project_id)

    # (2) The observation, with no transaction open.
    observation = await _observation(
        request, project_id=project_id, model_id=model_id, version=version
    )

    # (3) One atomic transaction: re-check, bind, compare, release, audit. The
    # row lock below waits at most the lane's budget (card 84).
    with factory() as session:
        with session.begin():
            with tenant_scope(session, principal.tenant_id), bounded_lock_wait(
                session, timeout_ms=settings.business_lock_timeout_ms
            ):
                _require_approval(session, principal=principal, project_id=project_id)
                row = _locked_version(
                    session,
                    tenant_id=principal.tenant_id,
                    project_id=project_id,
                    model_id=model_id,
                    version=version,
                )
                _rebind_identity(
                    observation,
                    project_id=project_id,
                    model_id=model_id,
                    version=row.version,
                )
                _require_release_preconditions(session, row)
                manifest = {field: observation[field] for field in DECLARED}
                try:
                    require_exact_declaration(manifest, declared)
                except InvError as error:
                    # Field names only. ``services.audit.redact`` has no marker
                    # for ``license`` or ``classification``, so a value placed
                    # anywhere here would not be filtered by anything: not
                    # placing it is the whole defence.
                    raise translate(error, table=TRANSLATION) from None
                try:
                    released = release_model_version(
                        session,
                        tenant_id=principal.tenant_id,
                        model_version_id=row.model_version_id,
                        now=now,
                    )
                except InvError as error:
                    raise translate(error, table=TRANSLATION) from None
                record_event(
                    session,
                    now=now,
                    actor_type="user",
                    actor_id=principal.user_id,
                    action="model_version.release",
                    outcome="allow",
                    tenant_id=principal.tenant_id,
                    trace_id=getattr(request.state, "trace_id", None),
                    target_type="model_version",
                    target_id=released.model_version_id,
                    detail={
                        "projectId": project_id,
                        "modelId": model_id,
                        "version": released.version,
                        "declarationFields": list(DECLARED),
                    },
                )
                result = schemas.ModelReleaseResponse(
                    modelVersionId=released.model_version_id,
                    modelId=released.model_id,
                    version=released.version,
                    stage="released",
                    contentSha256=released.content_sha256,
                )
    return result
