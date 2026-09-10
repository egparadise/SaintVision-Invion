"""The seam between the business surface and the execution core.

Two implementations were merged and they overlap on eleven concepts. That
overlap is a decision waiting to be made, not a bug to patch — but it must not
widen while nobody is looking, which is what this file prevents.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import schema_seam  # noqa: E402

#: Frozen deliberately. A twelfth duplicate should fail the build and force the
#: question, rather than quietly making the eventual reconciliation larger.
KNOWN_DUPLICATES = {
    "approval_requests",
    "checkpoints",
    "consumer_inbox",
    "evidence",
    "idempotency",
    "nodes",
    "outbox",
    "projects",
    "run_attempts",
    "runs",
    "tenants",
}


def test_the_duplicated_concept_set_has_not_grown():
    found = {row["concept"] for row in schema_seam.report()["duplicated"]}
    new = found - KNOWN_DUPLICATES
    assert not new, (
        f"new duplicate concepts across the two schemas: {sorted(new)}. "
        "Two tables for one concept means two answers to the same question; "
        "decide which side owns it before adding another."
    )


def test_shrinking_the_duplicates_is_reported_not_ignored():
    """When the reconciliation happens this test tells whoever did it to update
    the frozen list, rather than leaving a stale one behind."""
    found = {row["concept"] for row in schema_seam.report()["duplicated"]}
    resolved = KNOWN_DUPLICATES - found
    assert not resolved, (
        f"these are no longer duplicated: {sorted(resolved)}. "
        "Remove them from KNOWN_DUPLICATES."
    )


def test_the_two_halves_agree_on_the_tenant_scope_guc():
    """The one integration contract that already lines up.

    Both sides scope by SET LOCAL on `inv.tenant_id`, which is why a single
    transaction can span both schemas at all. If either side changed its GUC
    the two would silently stop sharing a scope — each would still pass its own
    tests, and rows would cross.
    """
    from saintvision.db.session import TENANT_GUC

    db_py = (ROOT / "services" / "control-plane" / "src" / "inv" / "db.py").read_text(
        encoding="utf-8"
    )
    assert TENANT_GUC == "inv.tenant_id"
    assert "'inv.tenant_id'" in db_py


def test_every_schema_the_python_migrations_create_grants_the_app_role():
    """My side's invariant, checked on my side only.

    The inv schema's missing production grant path is recorded in
    docs/vault/40_Governance and belongs to its owner; this asserts I do not
    add a schema with the same gap.
    """
    versions = ROOT / "migrations" / "versions"
    created = set()
    granted = set()
    for path in sorted(versions.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "CREATE SCHEMA" in text:
            created.add(path.name)
        if "TO {APP_ROLE}" in text or "TO inv_app" in text:
            granted.add(path.name)
    # No revision of mine creates a schema; everything lives in public, which
    # is granted. The assertion is that this stays true.
    assert created == set(), (
        f"revisions creating a schema must also grant it: {sorted(created)}"
    )
    assert granted, "no revision grants the application role"
