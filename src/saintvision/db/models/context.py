"""Immutable Context and RunRecord (S09-DB).

ADR-009 requires that a ContextBundle preserve item version and hash **and** a
redacted content snapshot. Mutable item IDs alone cannot reproduce what the
model actually saw.

P7 (PREP-CLAUDE-001) observed that storing the snapshot inside each bundle
duplicates the same text across every bundle, every retry and the whole project
lifetime — multiplicatively, not linearly. So the content lives once in
``context_snapshots``, keyed by its hash, and bundles reference it.

**Deviation from PREP-CLAUDE-001, recorded deliberately.** The prep draft made
``content_hash`` a global primary key. That is wrong for two reasons and the
key is ``(tenant_id, content_hash)`` here instead:

* Cross-tenant deduplication is a covert channel. A tenant that inserts content
  and observes whether a row already existed learns that another tenant holds
  the same document.
* A shared row has a shared lifetime. One tenant's retention deletion would
  reach into another tenant's bundle.

Within one tenant the duplication that actually hurts — a repeatedly referenced
document, a retried run — is still collapsed, which was the point.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, Sha256, TenantId, Utc

CONTEXT_ITEM_KINDS = ("document", "code", "message", "tool_output", "summary")

#: Provisional. PLAN-STORAGE-001 has no figure for this and PREP-CLAUDE-001
#: recorded it as unknown pending a look at real document sizes. Enforced in the
#: service, not as a column constraint, so raising it is not a migration.
SNAPSHOT_SOFT_LIMIT_BYTES = 1_000_000


class ContextSnapshot(Base):
    """Redacted content, stored once per tenant and never modified.

    ``content_hash`` is the SHA-256 of the content **after** redaction. Hashing
    before would leave a probe for recovering the original: anyone holding a
    candidate plaintext could confirm it by hash.

    Immutability is definitional rather than enforced by a trigger — the hash is
    part of the key, so changed content is a different row by construction.
    """

    __tablename__ = "context_snapshots"
    __table_args__ = (
        CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        CheckConstraint("content_hash = lower(content_hash)", name="hash_is_lowercase"),
        Index("ix_context_snapshots_first_seen_at", "first_seen_at"),
    )

    tenant_id: Mapped[TenantId] = mapped_column(primary_key=True)
    content_hash: Mapped[Sha256] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    byte_size: Mapped[int] = mapped_column(BigInteger)
    first_seen_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class ContextBundle(Base):
    """What a Run was given, fixed at the moment it was given.

    ``bundle_hash`` is computed from the ordered ``(ordinal, content_hash)``
    sequence of its items, not from a concatenation of the text. That makes
    reproduction checkable item by item: a mismatch names which item changed
    instead of only reporting that something did.

    No embedding column. ADR-009 forbids fixing a vector dimension before the
    model is chosen, and the model is not chosen. Retrieval today is lexical and
    metadata filtering; calling PostgreSQL full text search "BM25" would be a
    different claim than the one this implements.
    """

    __tablename__ = "context_bundles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"]
        ),
        UniqueConstraint("tenant_id", "bundle_id", name="uq_context_bundles_tenant_id_bundle_id"),
        CheckConstraint("item_count >= 0", name="item_count_non_negative"),
        CheckConstraint("total_bytes >= 0", name="total_bytes_non_negative"),
        CheckConstraint("bundle_hash = lower(bundle_hash)", name="hash_is_lowercase"),
        CheckConstraint(
            "retrieval_strategy IN ('lexical','metadata','hybrid','explicit')",
            name="retrieval_strategy_allowed",
        ),
        Index("ix_context_bundles_tenant_id_run_id", "tenant_id", "run_id"),
        Index("ix_context_bundles_bundle_hash", "bundle_hash"),
    )

    bundle_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    run_id: Mapped[InvId] = mapped_column()
    bundle_hash: Mapped[Sha256]
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    #: How the items were selected. "explicit" means the caller named them.
    retrieval_strategy: Mapped[str] = mapped_column(String(16), default="explicit")
    #: Versions in force when the bundle was built (공통 계약 §13).
    component_versions: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    #: Declared token cost of the bundle, for budget accounting.
    token_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    built_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class ContextBundleItem(Base):
    """One entry in a bundle: which item, which version, which snapshot.

    ``item_id`` is the mutable source. ``item_version`` and ``content_hash``
    are what make the reference reproducible — the source can change afterwards
    and the bundle still says exactly what was read.
    """

    __tablename__ = "context_bundle_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "bundle_id"],
            ["context_bundles.tenant_id", "context_bundles.bundle_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "content_hash"],
            ["context_snapshots.tenant_id", "context_snapshots.content_hash"],
        ),
        CheckConstraint("ordinal >= 0", name="ordinal_non_negative"),
        CheckConstraint("item_version >= 1", name="item_version_positive"),
        CheckConstraint(
            "kind IN ('document','code','message','tool_output','summary')",
            name="kind_allowed",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_in_range",
        ),
        Index("ix_context_bundle_items_tenant_id_content_hash", "tenant_id", "content_hash"),
    )

    tenant_id: Mapped[TenantId] = mapped_column(primary_key=True)
    bundle_id: Mapped[InvId] = mapped_column(primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: The mutable source item this was read from.
    item_id: Mapped[str] = mapped_column(String(255))
    item_version: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[Sha256] = mapped_column()
    kind: Mapped[str] = mapped_column(String(16))
    #: Where it came from, for the 출처 requirement of G2.
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Retrieval confidence when a ranked strategy produced it; NULL when the
    #: caller named the item explicitly.
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    #: Whether redaction actually removed something. Useful when a run behaved
    #: oddly and the question is whether the model saw a truncated document.
    redacted: Mapped[bool] = mapped_column(default=False)


class RunRecord(Base):
    """The sealed, immutable account of a finished Run.

    Kept for the project lifetime (PLAN-DB-001), unlike the 90 day artifact and
    log retention. Sealing is one-way: ``sealed_at`` is set once and the
    application role has no UPDATE on this table, so a record cannot be
    rewritten after the fact.

    It pins versions and the resolved artifact digests, which is what makes a
    finished run reproducible rather than merely described.
    """

    __tablename__ = "run_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["runs.tenant_id", "runs.run_id"]
        ),
        UniqueConstraint("tenant_id", "record_id", name="uq_run_records_tenant_id_record_id"),
        # One sealed record per run. A second would mean the history was
        # rewritten rather than appended to.
        UniqueConstraint("run_id", name="uq_run_records_run_id"),
        CheckConstraint(
            "final_state IN ('succeeded','failed','cancelled')",
            name="final_state_is_terminal",
        ),
        Index("ix_run_records_tenant_id_sealed_at", "tenant_id", "sealed_at"),
    )

    record_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    run_id: Mapped[InvId] = mapped_column()
    final_state: Mapped[str] = mapped_column(String(16))
    termination_reason: Mapped[str] = mapped_column(String(24))
    evidence_id: Mapped[InvId | None] = mapped_column(nullable=True)
    bundle_id: Mapped[InvId | None] = mapped_column(nullable=True)
    bundle_hash: Mapped[Sha256 | None] = mapped_column(nullable=True)
    workload_spec_sha256: Mapped[Sha256] = mapped_column()
    #: Prompt, context, harness, graph, policy, agent and model versions
    #: (공통 계약 §13). A run whose versions are unknown is not reproducible.
    component_versions: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    sealed_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class RunRecordArtifact(Base):
    """An artifact pinned into a RunRecord at its resolved digest (S09-ST).

    ADR-010 requires that the object version and digest resolved during
    execution be fixed into the RunRecord. Storing only the ``inv://`` name
    would let a later overwrite silently change what a finished run referred to.

    ``role`` is what makes "diff·테스트·trace Artifact 연결" queryable rather
    than a naming convention people remember to follow.
    """

    __tablename__ = "run_record_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "record_id"],
            ["run_records.tenant_id", "run_records.record_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "artifact_id"],
            ["artifacts.tenant_id", "artifacts.artifact_id"],
        ),
        CheckConstraint(
            "role IN ('diff','test_report','trace','log','model','dataset','other')",
            name="role_allowed",
        ),
        CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        Index("ix_run_record_artifacts_tenant_id_role", "tenant_id", "role"),
    )

    tenant_id: Mapped[TenantId] = mapped_column(primary_key=True)
    record_id: Mapped[InvId] = mapped_column(primary_key=True)
    artifact_id: Mapped[InvId] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(16))
    uri: Mapped[str] = mapped_column(Text)
    #: Resolved at execution time and frozen here.
    checksum_sha256: Mapped[Sha256] = mapped_column()
    object_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    byte_size: Mapped[int] = mapped_column(BigInteger, default=0)
