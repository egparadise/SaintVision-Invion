"""Produce and read adapter conformance records (G-03 stage two, design #218 v1.2).

Two halves, and the boundary between them is the point:

* **producing** (§3): the server runs ``run_conformance`` against the product's
  in-process fixture adapter (``adapters.reference.ReferenceAdapter``) and
  stores what came out, under the tool name the record stands in for. Never a
  ``CliAdapter``, never a tool from ``agents.BY_NAME``, never a subprocess and
  never a credential other than the suite's dummy reference: the platform
  holds no real credential and a real ``install`` changes the host. The row
  says so itself -- ``subject = "fixture-adapter"``, ``provenance =
  "in-server"`` -- so a consumer cannot read "the suite passed against the
  fixture" as "the installed CLI conforms" (§3-3).
* **reading** (§2-8): the latest record per (host, adapter), and every stored
  row is re-checked against the invariants before it is handed out. A row that
  breaks one is not repaired or partially served; it is refused, so the API is
  never more plausible than the database.

Nothing here runs inside a request. The read routes import ``latest_records``
and ``StoredRecordInvalid``; the producer is called by the operator command
``tools/record_fixture_conformance.py``.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..adapters import agents
from ..adapters.conformance import CHECKLIST, ConformanceReport, run_conformance
from ..adapters.contract import CONTRACT_VERSION
from ..adapters.reference import ReferenceAdapter
from ..db.models import (
    CONFORMANCE_PROVENANCES,
    CONFORMANCE_SUBJECTS,
    OUTCOME_KEYS,
    AdapterConformanceRecord,
)
from ..ids import new_id

#: The only credential reference the suite may be handed here (§3-2). It is the
#: suite's own default and it is not a credential.
DUMMY_CREDENTIAL_REF = "conformance://dummy"

FIXTURE_SUBJECT = "fixture-adapter"
IN_SERVER = "in-server"


class StoredRecordInvalid(ValueError):
    """A stored row violates §2-8. The message names the rule, never the row."""


class ProducerRefused(ValueError):
    """The producer will not run: wrong adapter, credential or host identity."""


@dataclass(frozen=True, slots=True)
class Outcome:
    name: str
    passed: bool
    skipped: bool


@dataclass(frozen=True, slots=True)
class Recorded:
    """One validated record, as the routes consume it. No ``host_id``: the
    read boundary is decided by it and the consumer has no use for it."""

    record_id: str
    adapter: str
    subject: str
    provenance: str
    contract_version: str
    suite_contract_version: str
    total: int
    passed: int
    failed: int
    skipped: int
    outcomes: tuple[Outcome, ...]
    recorded_at: dt.datetime


# ----------------------------------------------------------- invariants


def expected_check_names(suite_contract_version: str) -> tuple[str, ...]:
    """The check names a record of this suite version must carry, in order.

    One suite version exists, so this is the live ``CHECKLIST``. The PR that
    raises the suite contract decides how older rows are compared (§6).
    """
    if suite_contract_version != CONTRACT_VERSION:
        raise StoredRecordInvalid("suite contract version is not one this reader knows")
    return tuple(spec.name for spec in CHECKLIST)


def validate_outcomes(
    checks: Any, *, total: int, passed: int, failed: int, skipped: int, suite_contract_version: str
) -> tuple[Outcome, ...]:
    """Every §2-8 invariant, or ``StoredRecordInvalid`` naming the one broken.

    Shared by the producer (before INSERT) and the reader (before serving), so
    the two cannot disagree about what a well-formed record is.
    """
    if not isinstance(checks, list):
        raise StoredRecordInvalid("checks is not an array")
    outcomes: list[Outcome] = []
    for item in checks:
        if not isinstance(item, dict) or set(item) != OUTCOME_KEYS:
            raise StoredRecordInvalid("a check outcome does not carry exactly name, passed, skipped")
        name, ok, skip = item["name"], item["passed"], item["skipped"]
        if not isinstance(name, str) or not name:
            raise StoredRecordInvalid("a check outcome has no name")
        if not isinstance(ok, bool) or not isinstance(skip, bool):
            raise StoredRecordInvalid("a check outcome flag is not a boolean")
        if ok and skip:
            raise StoredRecordInvalid("a check outcome is both passed and skipped")
        outcomes.append(Outcome(name=name, passed=ok, skipped=skip))

    names = tuple(o.name for o in outcomes)
    if names != expected_check_names(suite_contract_version):
        raise StoredRecordInvalid("check names or order differ from the suite's list")

    counted = _count(outcomes)
    if (total, passed, failed, skipped) != counted:
        raise StoredRecordInvalid("stored counts do not match the stored outcomes")
    return tuple(outcomes)


def _count(outcomes: Iterable[Outcome]) -> tuple[int, int, int, int]:
    """(total, passed, failed, skipped) recounted from the outcomes; ``failed``
    is derived, never an input (§2-8)."""
    items = list(outcomes)
    passed = sum(1 for o in items if o.passed and not o.skipped)
    skipped = sum(1 for o in items if o.skipped)
    failed = sum(1 for o in items if not o.passed and not o.skipped)
    return len(items), passed, failed, skipped


# -------------------------------------------------------------- producing


def outcomes_from_report(report: ConformanceReport) -> tuple[Outcome, ...]:
    """The stored shape of a report: name, passed, skipped -- and no ``detail``.

    ``skipped`` checks are recorded with ``passed=False`` so that the pair is
    never both true; the suite marks a skipped check ``passed=True``, which is
    its own convention for ``conformant`` and not a measurement.
    """
    return tuple(
        Outcome(name=c.name, passed=bool(c.passed) and not c.skipped, skipped=bool(c.skipped))
        for c in report.checks
    )


def record_fixture_conformance(
    session: Session,
    *,
    adapter: str,
    host_id: uuid.UUID,
    now: dt.datetime,
    credential_ref: str = DUMMY_CREDENTIAL_REF,
) -> AdapterConformanceRecord:
    """Run the suite against the fixture adapter and store one record for ``adapter``.

    ``adapter`` is the tool name the record stands in for and must be one of
    ``agents.TOOLS``; the thing measured is always ``ReferenceAdapter`` (§3-2).
    The counts are recounted from the report's checks, never taken from a
    caller, and ``failed`` is derived (§2-8, T14).
    """
    if adapter not in agents.BY_NAME:
        raise ProducerRefused("adapter is not one of the platform's tools")
    if credential_ref != DUMMY_CREDENTIAL_REF:
        raise ProducerRefused("the fixture conformance run takes no credential")
    if not isinstance(host_id, uuid.UUID):
        raise ProducerRefused("host identity is not configured")
    if now.tzinfo is None:
        raise ProducerRefused("recorded_at must be timezone-aware")

    report = run_conformance(ReferenceAdapter(), credential_ref=credential_ref)
    outcomes = outcomes_from_report(report)
    total, passed, failed, skipped = _count(outcomes)
    checks = [{"name": o.name, "passed": o.passed, "skipped": o.skipped} for o in outcomes]
    # The producer holds itself to the reader's rule before it writes.
    validate_outcomes(
        checks,
        total=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        suite_contract_version=CONTRACT_VERSION,
    )
    row = AdapterConformanceRecord(
        record_id=new_id("conformance_record"),
        host_id=host_id,
        adapter=adapter,
        contract_version=report.contract_version,
        suite_contract_version=CONTRACT_VERSION,
        subject=FIXTURE_SUBJECT,
        provenance=IN_SERVER,
        total=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        checks=checks,
        recorded_at=now,
    )
    assert row.subject in CONFORMANCE_SUBJECTS and row.provenance in CONFORMANCE_PROVENANCES
    session.add(row)
    session.flush()
    return row


# ---------------------------------------------------------------- reading


def to_recorded(row: AdapterConformanceRecord) -> Recorded:
    """Validate one stored row and lift it; ``StoredRecordInvalid`` otherwise."""
    if row.subject not in CONFORMANCE_SUBJECTS or row.provenance not in CONFORMANCE_PROVENANCES:
        raise StoredRecordInvalid("subject or provenance is not a value this stage produces")
    if row.adapter not in agents.BY_NAME:
        raise StoredRecordInvalid("adapter is not one of the platform's tools")
    if row.recorded_at is None or row.recorded_at.tzinfo is None:
        raise StoredRecordInvalid("recorded_at is missing or naive")
    outcomes = validate_outcomes(
        row.checks,
        total=row.total,
        passed=row.passed,
        failed=row.failed,
        skipped=row.skipped,
        suite_contract_version=row.suite_contract_version,
    )
    return Recorded(
        record_id=row.record_id,
        adapter=row.adapter,
        subject=row.subject,
        provenance=row.provenance,
        contract_version=row.contract_version,
        suite_contract_version=row.suite_contract_version,
        total=row.total,
        passed=row.passed,
        failed=row.failed,
        skipped=row.skipped,
        outcomes=outcomes,
        recorded_at=row.recorded_at,
    )


def latest_records(
    session: Session, *, host_id: uuid.UUID, adapters: Sequence[str]
) -> dict[str, Recorded]:
    """The latest record of each adapter on this host, keyed by adapter.

    "Latest" is ``recorded_at DESC, record_id DESC`` -- the index's order --
    so a tie on the timestamp resolves the same way on every read (§2-3).
    Records of other hosts are never considered. An adapter with no record is
    absent from the result: absence is the fact.
    """
    if not adapters:
        return {}
    table = AdapterConformanceRecord
    statement = (
        select(table)
        .where(table.host_id == host_id, table.adapter.in_(list(adapters)))
        .order_by(table.adapter, table.recorded_at.desc(), table.record_id.desc())
        .distinct(table.adapter)
    )
    found: dict[str, Recorded] = {}
    for row in session.execute(statement).scalars():
        found[row.adapter] = to_recorded(row)
    return found
