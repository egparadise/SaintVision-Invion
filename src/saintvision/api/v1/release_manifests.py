"""Read the recorded release manifests and the acceptances granted against them.

``GET /v1/release-manifests`` and ``GET /v1/release-manifests/{release_id}``.

**Why this exists.** The re-score records ``S12-FE`` at 50 with the reason
"서버 route 부재로 ``ReleaseManifest.operatorSignOff=false`` 유지" (DEF-S12): the
tables, the service and their tests were all present, and nothing served them, so
the screen had no way to ask whether a person had signed a release off and kept
the field hard-coded false. These two routes answer the question. They do not
make it true -- see ``pilot.operator_sign_off``.

**Read only, deliberately.** Creating a signature or an acceptance is a security
boundary: ``acceptance_records.accepted_by_user_id`` is a foreign key to
``users`` precisely so the system cannot sign its own acceptance, and a write
route would have to decide what evidence of a human decision looks like over
HTTP. That is a Codex contract, requested in
``docs/vault/30_Development/S12-BE_release_manifest_읽기_route_설계_메모.md``;
nothing here accepts a body.

**Tenant scope, not project scope.** ``release_manifests`` and
``acceptance_records`` carry ``tenant_id`` and no ``project_id`` -- a release is
a property of the deployment, not of one project inside it. So the scope here is
the verified principal's tenant, applied by ``get_session``'s ``SET LOCAL``
inside the request transaction, and every query also names ``tenant_id``
explicitly rather than relying on row-level security alone. A release recorded
by another tenant is a 404, not a 403: "exists but not yours" answers a question
the caller is not allowed to ask.
"""

from __future__ import annotations

from typing import Mapping

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ...errors import RES_RELEASE_NOT_FOUND, VAL_CURSOR, VAL_SCHEMA, InvError
from ...identity.principal import Principal
from ...services import pilot as pilot_service
from .. import schemas
from ..deps import get_principal, get_session
from ..problem import (
    RES_NOT_FOUND,
    VAL_REQUEST,
    CanonicalProblem,
    read_bounded_body,
    require_absent_body,
    translate,
)

#: The decorators below repeat these literals rather than interpolating the
#: constants. ``tools/route_coverage.py`` reads the surface from the source, and
#: a path it cannot see is a route the coverage report does not know exists --
#: the quietest way for a served endpoint to be absent from the inventory.
LIST_PATH = "/release-manifests"
DETAIL_PATH = "/release-manifests/{release_id}"

#: Every ``InvError`` these two readers can reach, and its canonical form. A
#: code not listed becomes ``SYS-0002`` by the shared module's rule, so the
#: table is the statement of what is reachable rather than a convenience.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    RES_RELEASE_NOT_FOUND: (RES_NOT_FOUND, 404, False),
    VAL_CURSOR: (VAL_REQUEST, 422, False),
    VAL_SCHEMA: (VAL_REQUEST, 422, False),
}

router = APIRouter(prefix="/v1", tags=["release-manifests"])


def _bounded_cursor(cursor: str | None) -> str | None:
    """A cursor is an opaque release id, and an unbounded one is refused.

    The cursor goes into a ``release_id <`` comparison. Length and character
    class are checked here rather than trusted because an unchecked opaque
    string is how a reader becomes a probe.
    """

    if cursor is None:
        return None
    value = cursor.strip()
    if not value or len(value) > 64 or not all(
        char.isalnum() or char in "_-" for char in value
    ):
        raise InvError(VAL_CURSOR, "cursor is not a release identifier", status=422)
    return value


@router.get(
    "/release-manifests",
    response_model=schemas.ReleaseManifestPageResponse,
    response_model_by_alias=True,
)
async def list_release_manifests(
    request: Request,
    limit: int = Query(default=pilot_service.RELEASE_PAGE_DEFAULT, ge=1, le=pilot_service.RELEASE_PAGE_MAX),
    cursor: str | None = Query(default=None),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> schemas.ReleaseManifestPageResponse:
    """Every release recorded for this tenant, newest first, bounded.

    A tenant that has recorded nothing gets ``items: []``. That is the honest
    answer and it is not a 404: an empty pilot and a tenant the caller cannot
    see would otherwise be indistinguishable from the outside.
    """

    require_absent_body(await read_bounded_body(request))
    try:
        page = pilot_service.release_manifest_page(
            session,
            tenant_id=principal.tenant_id,
            limit=limit,
            cursor=_bounded_cursor(cursor),
        )
    except InvError as error:
        raise translate(error, table=TRANSLATION, detail="Releases cannot be listed.") from None
    return schemas.ReleaseManifestPageResponse.model_validate(page)


@router.get(
    "/release-manifests/{release_id}",
    response_model=schemas.ReleaseManifestDetailResponse,
    response_model_by_alias=True,
)
async def read_release_manifest(
    request: Request,
    release_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> schemas.ReleaseManifestDetailResponse:
    """One release, its pinned components, and every acceptance decision on it.

    ``operatorSignOff`` is computed from those decisions and is false unless an
    ``accepted`` one pins this manifest's own hash. The accepting person is not
    in the response: ``RunRecordResponse`` set the rule that a read surface
    reports identifiers and digests rather than people, and an audit column is
    not a directory.
    """

    require_absent_body(await read_bounded_body(request))
    try:
        detail = pilot_service.release_manifest_detail(
            session, tenant_id=principal.tenant_id, release_id=release_id
        )
    except InvError as error:
        raise translate(error, table=TRANSLATION, detail="No such release manifest.") from None
    return schemas.ReleaseManifestDetailResponse.model_validate(detail)


__all__ = ["router", "LIST_PATH", "DETAIL_PATH", "TRANSLATION", "CanonicalProblem"]
