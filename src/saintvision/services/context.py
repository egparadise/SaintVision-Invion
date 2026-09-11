"""ContextBundle assembly and snapshot deduplication (S09-DB).

The rule that shapes everything here: **hash after redaction**. Hashing the
original would leave a probe — anyone holding a candidate plaintext could
confirm it against the stored hash — and the snapshot itself would then be a
redacted copy filed under the original's identity.

Deduplication is per tenant. Sharing rows across tenants would turn a hash
lookup into a way to learn that another tenant holds the same document, and
would tie two tenants' retention together. Within a tenant it still collapses
the case that actually multiplies: one document referenced by many bundles,
across many retries, for the project's lifetime.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..adapters.reference import recognised_secrets
from ..db.models import (
    SNAPSHOT_SOFT_LIMIT_BYTES,
    ContextBundle,
    ContextBundleItem,
    ContextSnapshot,
)
from ..errors import CTX_ITEM_TOO_LARGE, CTX_SNAPSHOT_MISSING, VAL_SCHEMA, InvError
from ..ids import new_id

RETRIEVAL_STRATEGIES = ("lexical", "metadata", "hybrid", "explicit")


@dataclass(frozen=True, slots=True)
class ContextItem:
    """One thing to put in a bundle, already redacted by the caller.

    ``content`` must be post-redaction. ``redacted`` remains the caller's
    declaration and is recorded as such — it says what the caller claims.

    What changed: the claim is no longer the only thing standing between a
    credential and the permanent record. ``build_bundle`` refuses content that
    still carries a secret this platform recognises, whatever the declaration
    says. See :func:`_refuse_recognised_secrets` for what that does and does
    not establish.
    """

    item_id: str
    item_version: int
    kind: str
    content: str
    source_uri: str | None = None
    confidence: float | None = None
    redacted: bool = False

    def validate(self) -> None:
        if self.item_version < 1:
            raise InvError(VAL_SCHEMA, "item_version must be at least 1")
        if self.kind not in ("document", "code", "message", "tool_output", "summary"):
            raise InvError(VAL_SCHEMA, "unknown context item kind")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise InvError(VAL_SCHEMA, "confidence must be between 0 and 1")


def _refuse_recognised_secrets(items: list[ContextItem]) -> None:
    """Refuse items whose content still carries a secret we can recognise.

    The module's contract has always said content must arrive post-redaction,
    and until now that was only a sentence. A caller could pass a bearer token
    with ``redacted=True`` and the token would be hashed, stored, deduplicated
    within its tenant by that hash, and pinned into a RunRecord that is by design
    never rewritten.

    Refusing rather than redacting, deliberately: this function is not in the
    path that feeds the model, so silently rewriting the content here would
    make the stored record disagree with what the model was actually given —
    and a record of context that does not match the context is worse than no
    record. The caller redacts before it both sends and stores.

    **Recognising is not proving.** This catches the patterns in ADR-014's
    first pass — private keys, bearer headers, presigned URLs, API keys,
    ``token=`` assignments. Content that passes has not been shown to be free
    of secrets, only free of those. Nothing downstream may treat a stored
    bundle as certified clean.
    """
    for ordinal, item in enumerate(items):
        for field in ("content", "item_id", "source_uri"):
            value = getattr(item, field)
            if value is None and field == "source_uri":
                continue
            if not isinstance(value, str):
                raise InvError(VAL_SCHEMA, f"context item at position {ordinal}: invalid {field}")
            labels = recognised_secrets(value)
            if labels:
                # Only server-owned labels and an ordinal may reach the error.
                # Identifiers and source URIs can themselves contain credentials.
                raise InvError(
                    VAL_SCHEMA,
                    f"context item at position {ordinal} contains {', '.join(labels)} "
                    f"in {field}; content and metadata must be redacted before "
                    "storage, and declaring redacted=True does not make it so",
                )


def content_hash(content: str) -> str:
    """SHA-256 of the redacted content, lowercase hex."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def bundle_hash(pairs: Iterable[tuple[int, str]]) -> str:
    """Hash the ordered ``(ordinal, content_hash)`` sequence.

    Not a hash of the concatenated text. Hashing the structure means a
    reproduction mismatch can name the item that differs, and it means two
    bundles with the same items in a different order are correctly different.
    """
    digest = hashlib.sha256()
    for ordinal, item_hash in sorted(pairs):
        digest.update(f"{ordinal}:{item_hash}\n".encode("utf-8"))
    return digest.hexdigest()


def store_snapshot(
    session: Session, *, tenant_id: uuid.UUID, content: str, now: dt.datetime
) -> tuple[str, bool]:
    """Store content once per tenant. Returns ``(hash, was_new)``.

    ``ON CONFLICT DO NOTHING`` rather than select-then-insert: two runs
    referencing the same document concurrently would both pass a prior check
    and one would fail on the primary key.
    """
    byte_size = len(content.encode("utf-8"))
    if byte_size > SNAPSHOT_SOFT_LIMIT_BYTES:
        # PREP-CLAUDE-001 recorded the real limit as unknown pending a look at
        # actual document sizes. Refusing loudly beats silently truncating what
        # the model was shown.
        raise InvError(
            CTX_ITEM_TOO_LARGE,
            f"context item exceeds the {SNAPSHOT_SOFT_LIMIT_BYTES} byte snapshot limit",
            extra={"byteSize": byte_size},
        )

    digest = content_hash(content)
    result = session.execute(
        pg_insert(ContextSnapshot)
        .values(
            tenant_id=tenant_id,
            content_hash=digest,
            content=content,
            byte_size=byte_size,
            first_seen_at=now,
        )
        .on_conflict_do_nothing(index_elements=["tenant_id", "content_hash"])
        .returning(ContextSnapshot.content_hash)
    )
    return digest, result.scalar_one_or_none() is not None


def build_bundle(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    run_id: str,
    items: list[ContextItem],
    now: dt.datetime,
    retrieval_strategy: str = "explicit",
    component_versions: dict[str, str] | None = None,
    token_estimate: int | None = None,
) -> ContextBundle:
    """Assemble a bundle, storing each item's snapshot once.

    Item order is the caller's and is preserved as ``ordinal``: the order the
    model saw things in is part of what happened.
    """
    if retrieval_strategy not in RETRIEVAL_STRATEGIES:
        raise InvError(VAL_SCHEMA, "unknown retrieval strategy")
    for item in items:
        item.validate()
    # Before anything is written. Snapshots are stored by content hash and
    # shared by every bundle in the tenant that references them, and a sealed
    # RunRecord is never rewritten — so a secret that gets in is not something
    # a later pass can take out.
    _refuse_recognised_secrets(items)

    bundle_id = new_id("bundle")
    pairs: list[tuple[int, str]] = []
    total_bytes = 0

    # Snapshots first. They have no dependency on the bundle, and storing them
    # issues queries — which autoflush any pending rows. Items added before the
    # bundle exists would be flushed into a foreign key violation.
    digests: list[str] = []
    for ordinal, item in enumerate(items):
        digest, _ = store_snapshot(session, tenant_id=tenant_id, content=item.content, now=now)
        digests.append(digest)
        pairs.append((ordinal, digest))
        total_bytes += len(item.content.encode("utf-8"))

    bundle = ContextBundle(
        bundle_id=bundle_id,
        tenant_id=tenant_id,
        run_id=run_id,
        bundle_hash=bundle_hash(pairs),
        item_count=len(items),
        total_bytes=total_bytes,
        retrieval_strategy=retrieval_strategy,
        component_versions=component_versions or {},
        token_estimate=token_estimate,
        built_at=now,
    )
    session.add(bundle)
    # The parent must be on disk before its children reference it.
    session.flush()

    for ordinal, (item, digest) in enumerate(zip(items, digests)):
        session.add(
            ContextBundleItem(
                tenant_id=tenant_id,
                bundle_id=bundle_id,
                ordinal=ordinal,
                item_id=item.item_id,
                item_version=item.item_version,
                content_hash=digest,
                kind=item.kind,
                source_uri=item.source_uri,
                confidence=item.confidence,
                redacted=item.redacted,
            )
        )
    session.flush()
    return bundle


def read_bundle(
    session: Session, *, tenant_id: uuid.UUID, bundle_id: str
) -> list[tuple[ContextBundleItem, str]]:
    """Return the bundle's items with their content, in order.

    A missing snapshot is an error rather than a gap: the bundle claims to be
    reproducible, and silently returning fewer items would make it lie.
    """
    rows = session.execute(
        select(ContextBundleItem, ContextSnapshot.content)
        .join(
            ContextSnapshot,
            (ContextSnapshot.tenant_id == ContextBundleItem.tenant_id)
            & (ContextSnapshot.content_hash == ContextBundleItem.content_hash),
            isouter=True,
        )
        .where(
            ContextBundleItem.tenant_id == tenant_id,
            ContextBundleItem.bundle_id == bundle_id,
        )
        .order_by(ContextBundleItem.ordinal)
    ).all()

    out: list[tuple[ContextBundleItem, str]] = []
    for item, content in rows:
        if content is None:
            raise InvError(
                CTX_SNAPSHOT_MISSING,
                "a bundle item's snapshot is missing",
                cause_ref=bundle_id,
                extra={"ordinal": item.ordinal},
            )
        out.append((item, content))
    return out


def verify_bundle(session: Session, *, tenant_id: uuid.UUID, bundle_id: str) -> bool:
    """Recompute the bundle hash from its items and compare.

    Cheap enough to run on read, and it is the only thing that turns "we stored
    a hash" into "the stored content still matches it".
    """
    bundle = session.get(ContextBundle, bundle_id)
    if bundle is None or bundle.tenant_id != tenant_id:
        raise InvError(CTX_SNAPSHOT_MISSING, "bundle not found", cause_ref=bundle_id)
    items = read_bundle(session, tenant_id=tenant_id, bundle_id=bundle_id)
    recomputed = bundle_hash([(item.ordinal, content_hash(content)) for item, content in items])
    return recomputed == bundle.bundle_hash


def collect_orphan_snapshots(
    session: Session, *, tenant_id: uuid.UUID | None = None, limit: int = 1000
) -> int:
    """Delete snapshots no bundle item references.

    Judged by ``NOT EXISTS`` rather than a reference count column, as CR-07
    proposed for artifact pins and P7 repeated for the same reason: a counter
    drifts and then has to be reconciled, while a query is simply correct. It
    costs more per run, and a garbage collector is the right place to pay that.

    Runs as the owner — the application role has no DELETE here.
    """
    referenced = select(ContextBundleItem.content_hash).where(
        ContextBundleItem.tenant_id == ContextSnapshot.tenant_id,
        ContextBundleItem.content_hash == ContextSnapshot.content_hash,
    )
    condition = ~referenced.exists()
    if tenant_id is not None:
        condition = condition & (ContextSnapshot.tenant_id == tenant_id)

    doomed = session.execute(
        select(ContextSnapshot.tenant_id, ContextSnapshot.content_hash)
        .where(condition)
        .limit(limit)
    ).all()
    if not doomed:
        return 0
    for snapshot_tenant, snapshot_hash in doomed:
        session.execute(
            delete(ContextSnapshot).where(
                ContextSnapshot.tenant_id == snapshot_tenant,
                ContextSnapshot.content_hash == snapshot_hash,
            )
        )
    return len(doomed)


def deduplication_ratio(session: Session, *, tenant_id: uuid.UUID) -> dict[str, Any]:
    """How much the shared store is saving, for the ops report.

    Reported rather than assumed: P7 argued deduplication would pay off, and
    this is what would show it did not.
    """
    references, distinct, stored_bytes = session.execute(
        text(
            "SELECT "
            "(SELECT count(*) FROM context_bundle_items WHERE tenant_id = :t), "
            "(SELECT count(*) FROM context_snapshots WHERE tenant_id = :t), "
            "(SELECT coalesce(sum(byte_size), 0) FROM context_snapshots WHERE tenant_id = :t)"
        ),
        {"t": tenant_id},
    ).one()
    return {
        "references": references,
        "distinctSnapshots": distinct,
        "storedBytes": int(stored_bytes),
        "reuseFactor": (references / distinct) if distinct else 0.0,
    }
