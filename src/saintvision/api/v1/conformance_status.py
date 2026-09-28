"""G-03: what this platform knows about adapter conformance -- now from records.

``GET /projects/{project_id}/adapters/conformance``
``GET /projects/{project_id}/adapters/{name}/conformance``

Stage one (#200) could only say ``NOT_OBSERVED``: nothing stored a report.
Stage two (design #218 v1.2, migration 0055) stores what the suite observed
when the server ran it against the product's fixture adapter, and these two
routes read that. The stage-one shape is kept exactly for the case it was
built for -- no record at all -- and a discriminated ``RECORDED`` branch is
added beside it.

**These routes still do not run the suite.** ``run_conformance`` drives the
adapter's ``install``, ``authenticate``, ``run``, ``collect`` and ``cancel``;
a read that did that would have side effects, unbounded latency, and would let
one caller trigger a measurement another reads. The producer is
``services.conformance_records.record_fixture_conformance``, called by an
operator command outside any request, and this module references neither it
nor ``run_conformance`` (a test checks the syntax tree).

**The project in the path is the read boundary, not the owner.** The records
are host-global: no ``tenant_id``, no row-level security, and nothing in a row
that identifies a tenant, a project or a person (§2-1). Live membership is
checked on every read; a non-member, an absent project and another tenant's
project are one denial.

**Which host.** Every record carries the ``host_id`` it was produced under and
the read is bound to this process's ``INV_CONTROL_PLANE_HOST_ID`` (§2-9).
With no host identity configured the read cannot say whose records it would
be reporting, so it refuses -- ``SYS-0002``, 500, not retryable -- rather than
answer ``NOT_OBSERVED`` (which would disguise a configuration fault as a
normal state) or serve another host's rows.

**Fail closed on a broken row.** A stored record that violates the report
invariants (§2-8) is not repaired or partially served; the read answers
``SYS-0002``/500 with a fixed sentence that carries none of the row (§4-3).

**Two bounded spans, like the write routes** (coordinator, card 103 addendum;
Codex card 105 W5). Each read opens the membership preflight and the record
read as separate short transactions, and each enters ``bounded_lock_wait``
beside its tenant scope, so a lock this read could wait on (a DDL lock on the
table, a long transaction on ``project_members``) is answered as
``SYS-0001/503/retryable`` after the budget instead of holding the request
open. Any other operational failure propagates unchanged: it is not
contention and must not be dressed as "retry".
"""

from __future__ import annotations

from typing import Any, Mapping

from fastapi import APIRouter, Depends, Request

from ...adapters import agents
from ...adapters.conformance import CHECKLIST
from ...adapters.contract import CONTRACT_VERSION
from ...db.session import make_session_factory, tenant_scope
from ...errors import AUTH_PROJECT_SCOPE, InvError
from ...identity.principal import Principal
from ...services import projects as project_service
from ...services.conformance_records import (
    Recorded,
    StoredRecordInvalid,
    latest_records,
)
from .. import schemas
from ..deps import get_principal
from ..lock_wait import bounded_lock_wait
from ..problem import (
    AUTH_PROJECT,
    RES_NOT_FOUND,
    SYS_UNMAPPED,
    CanonicalProblem,
    read_bounded_body,
    require_absent_body,
    translate,
)

CONFORMANCE_PATH = "/projects/{project_id}/adapters/conformance"
ADAPTER_CONFORMANCE_PATH = "/projects/{project_id}/adapters/{name}/conformance"

#: Why the status is what it is when nothing is recorded. Stage one said the
#: platform "does not persist conformance results yet"; once 0055 exists that
#: sentence is false, so the reason now states the absence and only that.
#: A fixed string: it describes the records, not this request.
NOT_OBSERVED_REASON = "No conformance run is recorded for this host and these adapters."

#: The single-adapter variant of the same fact.
ADAPTER_NOT_OBSERVED_REASON = "No conformance run is recorded for this host and this adapter."

#: The two fail-closed refusals (design §4-3, R5). Fixed sentences, and they
#: stay fixed: no row content, no check name, no exception text, no setting
#: value may be interpolated into them. Not retryable, because neither gets
#: better on a retry.
HOST_UNCONFIGURED_DETAIL = (
    "This control plane has no host identity configured, so it cannot report "
    "conformance records."
)
RECORD_INVALID_DETAIL = (
    "A stored conformance record is not well-formed; it is not reported."
)
UNKNOWN_ADAPTER_DETAIL = "No adapter with that name exists."

#: Every ``InvError`` these routes can reach, and its canonical form. Only one
#: call can raise: ``require_project_access``.
TRANSLATION: Mapping[str, tuple[str, int, bool]] = {
    AUTH_PROJECT_SCOPE: (AUTH_PROJECT, 403, False),
}


def _membership(request: Request, *, principal: Principal, project_id: str) -> None:
    """Span (1): live project membership in its own short, bounded transaction.

    ``require_project_access`` reports the same denial whether the project does
    not exist or the caller cannot see it, so existence is not disclosed here
    either. Reading needs membership and nothing more.
    """
    factory = make_session_factory(request.app.state.engine)
    settings = request.app.state.settings
    with factory() as session:
        with session.begin():
            with tenant_scope(session, principal.tenant_id), bounded_lock_wait(
                session, timeout_ms=settings.business_lock_timeout_ms
            ):
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
    """The check list, derived from the suite's own descriptor -- never copied."""
    return [
        schemas.ConformanceCheckDescriptor(
            name=spec.name, capabilityGated=spec.capability is not None
        )
        for spec in CHECKLIST
    ]


def _host_id(request: Request):
    """This process's host identity, or the fixed refusal."""
    host_id = getattr(request.app.state.settings, "control_plane_host_id", None)
    if host_id is None:
        raise CanonicalProblem(SYS_UNMAPPED, 500, HOST_UNCONFIGURED_DETAIL, retryable=False)
    return host_id


def _records(request: Request, *, principal: Principal, host_id, adapters: list[str]) -> dict[str, Recorded]:
    """Span (2): the record read in its own short, bounded transaction."""
    factory = make_session_factory(request.app.state.engine)
    settings = request.app.state.settings
    with factory() as session:
        with session.begin():
            with tenant_scope(session, principal.tenant_id), bounded_lock_wait(
                session, timeout_ms=settings.business_lock_timeout_ms
            ):
                try:
                    return latest_records(session, host_id=host_id, adapters=adapters)
                except StoredRecordInvalid:
                    # The rule that failed is in the exception; the client does
                    # not get it.
                    raise CanonicalProblem(
                        SYS_UNMAPPED, 500, RECORD_INVALID_DETAIL, retryable=False
                    ) from None


def _outcomes(record: Recorded) -> list[schemas.ConformanceCheckOutcome]:
    return [
        schemas.ConformanceCheckOutcome(name=o.name, passed=o.passed, skipped=o.skipped)
        for o in record.outcomes
    ]


def _item(record: Recorded) -> schemas.ConformanceRecordItem:
    return schemas.ConformanceRecordItem(
        adapter=record.adapter,
        subject=record.subject,
        provenance=record.provenance,
        contractVersion=record.contract_version,
        suiteContractVersion=record.suite_contract_version,
        total=record.total,
        passed=record.passed,
        failed=record.failed,
        skipped=record.skipped,
        outcomes=_outcomes(record),
        recordedAt=record.recorded_at,
    )


async def read_conformance_status(
    project_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> Any:
    """Every adapter's latest record on this host, or that there is none."""
    # Live membership first, so a non-member learns nothing from how a body is
    # judged; then the bounded reader refuses one, as the other business reads do.
    _membership(request, principal=principal, project_id=project_id)
    require_absent_body(await read_bounded_body(request))
    host_id = _host_id(request)
    # The adapters the suite would run against, in the platform's own order: a
    # target list, and the order ``records`` follows.
    adapters = [tool.name for tool in agents.TOOLS]
    found = _records(request, principal=principal, host_id=host_id, adapters=adapters)
    if not found:
        return schemas.ConformanceStatusResponse(
            status="NOT_OBSERVED",
            reason=NOT_OBSERVED_REASON,
            scope="control-plane-host",
            contractVersion=CONTRACT_VERSION,
            adapters=adapters,
            checks=_checks(),
            recordedAt=None,
        )
    records = [_item(found[name]) for name in adapters if name in found]
    return schemas.ConformanceStatusRecordedResponse(
        status="RECORDED",
        scope="control-plane-host",
        contractVersion=CONTRACT_VERSION,
        adapters=adapters,
        checks=_checks(),
        records=records,
        latestRecordedAt=max(item.recorded_at for item in records),
    )


async def read_adapter_conformance(
    project_id: str,
    name: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> Any:
    """One adapter's latest record on this host, or that there is none."""
    _membership(request, principal=principal, project_id=project_id)
    require_absent_body(await read_bounded_body(request))
    if name not in agents.BY_NAME:
        # The same code ``GET /v1/adapters/{name}`` gives an unknown name (#205);
        # the caller's string is not echoed.
        raise CanonicalProblem(RES_NOT_FOUND, 404, UNKNOWN_ADAPTER_DETAIL, retryable=False)
    host_id = _host_id(request)
    found = _records(request, principal=principal, host_id=host_id, adapters=[name])
    record = found.get(name)
    if record is None:
        return schemas.AdapterConformanceNotObservedResponse(
            status="NOT_OBSERVED",
            reason=ADAPTER_NOT_OBSERVED_REASON,
            scope="control-plane-host",
            adapter=name,
            contractVersion=CONTRACT_VERSION,
            checks=_checks(),
            recordedAt=None,
        )
    return schemas.AdapterConformanceRecordedResponse(
        status="RECORDED",
        scope="control-plane-host",
        adapter=record.adapter,
        subject=record.subject,
        provenance=record.provenance,
        contractVersion=record.contract_version,
        suiteContractVersion=record.suite_contract_version,
        total=record.total,
        passed=record.passed,
        failed=record.failed,
        skipped=record.skipped,
        outcomes=_outcomes(record),
        recordedAt=record.recorded_at,
    )


def register(router: APIRouter) -> None:
    """Add both routes to the projects router.

    ``inv.business_surface.BusinessDispatch`` selects business traffic by reading
    ``projects.router.routes``, and ``include_router`` on an ``APIRouter`` leaves
    only a lazy placeholder there, so the routes are added with
    ``add_api_route`` to be served at all.
    """
    router.add_api_route(
        CONFORMANCE_PATH,
        read_conformance_status,
        methods=["GET"],
        response_model=schemas.ConformanceStatusUnion,
        tags=["adapters"],
        name="read_conformance_status",
    )
    router.add_api_route(
        ADAPTER_CONFORMANCE_PATH,
        read_adapter_conformance,
        methods=["GET"],
        response_model=schemas.AdapterConformanceUnion,
        tags=["adapters"],
        name="read_adapter_conformance",
    )
