"""G-03 phase one: say what this platform knows about adapter conformance.

``GET /projects/{project_id}/adapters/conformance``

#146 removed a fabricated conformance display from the web app and left the
honest label "미측정". This route is the backend saying the same thing for
itself, because the measurement *is* absent and the absence was only visible in
the frontend's own wording:

* ``adapters/conformance.py`` produces reports -- and has **no product caller**.
* nothing persists one. There is no table, no column and no migration for a
  conformance result.

So the response is ``status: "NOT_OBSERVED"`` plus the part of the contract that
is statically true (the contract version, the check names, the adapters the suite
would run against). No counts, no boolean: ``passed: 0`` is a measurement of
zero, and a boolean has no room for "not measured".

**This route does not run the suite.** ``run_conformance`` calls the adapter's
``install``, ``authenticate``, ``run``, ``collect`` and ``cancel``, which for
``CliAdapter`` means driving host CLI processes. A read that did that on every
request would have side effects, unbounded latency, and would let one caller
trigger a measurement another caller then reads. Who runs it and how often is a
phase-two decision with an owner; this route only reports that nobody has.

**The project in the path is the read boundary, not the owner.** Conformance is a
property of the control-plane host and does not differ per project, so the
response carries ``scope: "control-plane-host"`` -- the same word
``GET /v1/adapters`` uses -- rather than letting the path imply tenant data. The
path exists so the grade decided in #158 applies unchanged: live membership from
the database, never the sign-in snapshot.

**There is no adapter-name variant in phase one**, because with nothing recorded
there is nothing that could differ per adapter, and building it now would change
meaning in phase two. That is also why this route has no ``RES-0004``.
"""

from __future__ import annotations

from typing import Any, Mapping

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ...adapters import agents
from ...adapters.conformance import CHECKLIST
from ...adapters.contract import CONTRACT_VERSION
from ...errors import AUTH_PROJECT_SCOPE, InvError
from ...identity.principal import Principal
from ...services import projects as project_service
from .. import schemas
from ..deps import get_principal, get_session
from ..problem import (
    AUTH_PROJECT,
    read_bounded_body,
    require_absent_body,
    translate,
)

CONFORMANCE_PATH = "/projects/{project_id}/adapters/conformance"

#: Why the status is what it is. A fixed string rather than a computed one: it
#: describes the platform, not this request, so nothing about the caller can
#: change it.
NOT_OBSERVED_REASON = (
    "No conformance run is recorded; this platform does not persist conformance "
    "results yet."
)

#: Every ``InvError`` this route can reach, and its canonical form. Only one call
#: can raise: ``require_project_access``. A code not listed becomes ``SYS-0002``,
#: and a test enumerates what the call can raise so this stays complete.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
}


def _membership(session: Session, *, principal: Principal, project_id: str) -> None:
    """Live project membership, or the canonical refusal.

    ``require_project_access`` already reports the same denial whether the
    project does not exist or the caller cannot see it, so existence is not
    disclosed here either. Reading needs membership and nothing more: no grade
    beyond it is required to be told that no measurement exists.
    """
    try:
        project_service.require_project_access(
            session,
            tenant_id=principal.tenant_id,
            project_id=project_id,
            user_id=principal.user_id,
        )
    except InvError as error:
        raise translate(
            error, table=TRANSLATION, detail="This project is not accessible."
        ) from None


def _checks() -> list[schemas.ConformanceCheckDescriptor]:
    """The check list, derived from the suite's own descriptor.

    Neither parsed from source nor copied: ``CHECKLIST`` is what
    ``run_conformance`` loops over, so the list this response carries is the list
    the suite runs. The count is not fixed in the contract -- if the suite grows a
    check, the response grows an entry.
    """
    return [
        schemas.ConformanceCheckDescriptor(
            name=spec.name, capabilityGated=spec.capability is not None
        )
        for spec in CHECKLIST
    ]


async def read_conformance_status(
    project_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> Any:
    """Report that conformance has not been observed, and what it would cover."""
    # Live membership first, so a non-member learns nothing from how a body is
    # judged; then the bounded reader refuses one, as the other business reads do.
    _membership(session, principal=principal, project_id=project_id)
    require_absent_body(await read_bounded_body(request))
    return schemas.ConformanceStatusResponse(
        status="NOT_OBSERVED",
        reason=NOT_OBSERVED_REASON,
        scope="control-plane-host",
        contractVersion=CONTRACT_VERSION,
        # The adapters the suite would run against, in the platform's own order.
        # A target list, not a result: every one of them is unmeasured.
        adapters=[tool.name for tool in agents.TOOLS],
        checks=_checks(),
        recordedAt=None,
    )


def register(router: APIRouter) -> None:
    """Add the route to the projects router.

    ``inv.business_surface.BusinessDispatch`` selects business traffic by reading
    ``projects.router.routes``, and ``include_router`` on an ``APIRouter`` leaves
    only a lazy placeholder there, so the route has to be added with
    ``add_api_route`` to be served at all.
    """
    router.add_api_route(
        CONFORMANCE_PATH,
        read_conformance_status,
        methods=["GET"],
        response_model=schemas.ConformanceStatusResponse,
        tags=["adapters"],
        name="read_conformance_status",
    )
