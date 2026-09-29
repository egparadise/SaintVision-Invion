"""A recorded run of the adapter conformance suite (G-03 stage two, 0055).

One row is one statement: *the suite ran on this control-plane host, against the
fixture adapter, standing in for this tool, and these checks came out this way*.
Design #218 v1.2 §2.

**Host-global, not tenant data.** There is no ``tenant_id`` and no row-level
security (§2-1 (c), Codex approved): conformance is a property of the host and
does not differ per project, so the read route's live membership check is the
boundary and the row may hold nothing tenant-, project- or user-identifying and
no free text. That is why ``host_id`` is a ``uuid`` (a hostname cannot be
stored), why ``subject``/``provenance`` are closed sets, why ``checks`` never
carries the suite's ``detail`` string, and why this table is in
``APPEND_ONLY_TABLES`` and not ``TENANT_SCOPED_TABLES``.

The SQL CHECKs below are the database's copy of the invariants the producer
and the reader enforce in code (§2-8): a row whose counts do not add up, or
whose ``checks`` array is not ``total`` long, cannot exist.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, TenantId, Utc

#: What was measured. This stage produces exactly one value: the suite run
#: against the in-process fixture adapter. ``installed-cli`` is deliberately
#: not enumerated (G-25 BLOCKED_EXTERNAL); the PR that adds that producer
#: widens this tuple, the CHECK and the contract together.
CONFORMANCE_SUBJECTS: tuple[str, ...] = ("fixture-adapter",)

#: Where the record came from. One value: this server ran the suite itself.
#: ``hosted-ci-import`` waits for an importer that can bind its source.
CONFORMANCE_PROVENANCES: tuple[str, ...] = ("in-server",)

#: The keys one stored check outcome carries -- and ``detail`` is not one.
OUTCOME_KEYS: frozenset[str] = frozenset({"name", "passed", "skipped"})


class AdapterConformanceRecord(Base):
    __tablename__ = "adapter_conformance_records"
    __table_args__ = (
        CheckConstraint("subject = 'fixture-adapter'", name="subject_allowed"),
        CheckConstraint("provenance = 'in-server'", name="provenance_allowed"),
        CheckConstraint(
            "total >= 0 AND passed >= 0 AND failed >= 0 AND skipped >= 0",
            name="counts_non_negative",
        ),
        CheckConstraint("passed + failed + skipped = total", name="counts_sum_to_total"),
        CheckConstraint(
            "jsonb_typeof(checks) = 'array' AND jsonb_array_length(checks) = total",
            name="checks_match_total",
        ),
        # The one read: latest per (host, adapter), deterministic on ties.
        Index(
            "ix_adapter_conformance_records_latest",
            "host_id",
            text("adapter"),
            text("recorded_at DESC"),
            text("record_id DESC"),
        ),
    )

    record_id: Mapped[InvId] = mapped_column(primary_key=True)
    #: The control-plane host that ran the suite (``INV_CONTROL_PLANE_HOST_ID``).
    #: Reused ``TenantId`` for its uuid column type only; it is not a tenant.
    host_id: Mapped[TenantId] = mapped_column()
    adapter: Mapped[str] = mapped_column(String(64))
    contract_version: Mapped[str] = mapped_column(String(32))
    suite_contract_version: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(32))
    provenance: Mapped[str] = mapped_column(String(32))
    total: Mapped[int] = mapped_column(Integer)
    passed: Mapped[int] = mapped_column(Integer)
    failed: Mapped[int] = mapped_column(Integer)
    skipped: Mapped[int] = mapped_column(Integer)
    #: ``[{"name", "passed", "skipped"}, ...]`` in ``CHECKLIST`` order; no detail.
    checks: Mapped[list] = mapped_column(JSONB)
    recorded_at: Mapped[Utc] = mapped_column()
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
