"""PG-free pins for the S10-ST model-version invariants (card aw, 2026-09-28).

The invariants themselves live in the database (migration 0004) and the lineage service;
these tests only pin that the declarations are still there, so a later edit that quietly
relaxes "immutable version" or "pin only extends" is caught before any PostgreSQL run.
The behavioural proof runs on hosted Backend (``tests/test_lineage.py``).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "0004_s10_lineage.py"
LINEAGE = ROOT / "src" / "saintvision" / "services" / "lineage.py"


def _migration_module():
    return ast.parse(MIGRATION.read_text(encoding="utf-8"))


def test_model_version_identity_is_unique_per_model_and_per_content():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'sa.UniqueConstraint("model_id", "version", name="uq_model_versions_model_id_version")' in source
    assert re.search(r'sa\.UniqueConstraint\(\s*"tenant_id", "content_sha256", name="uq_model_versions_tenant_id_content_sha256"', source)
    assert '"stage <> \'released\' OR (verified_at IS NOT NULL AND retention_pinned_until IS NOT NULL)"' in source


def test_application_may_only_advance_lifecycle_columns_never_identity():
    """The column-level UPDATE grant is the immutability: content_sha256, version and uri are
    absent from the list the application role may update."""
    module = _migration_module()
    policy = next(node for node in module.body if isinstance(node, ast.Assign)
                  and any(getattr(t, "id", None) == "LIFECYCLE_UPDATE_COLUMNS" for t in node.targets))
    columns = ast.literal_eval(policy.value)
    assert columns["model_versions"] == ("stage", "verified_at", "retention_pinned_until")
    assert not {"content_sha256", "version", "uri", "model_id", "tenant_id"} & set(columns["model_versions"])
    assert columns["dataset_versions"] == ("retention_pinned_until",)


def test_pin_retention_source_only_extends():
    source = LINEAGE.read_text(encoding="utf-8")
    body = source[source.index("def pin_retention("):source.index("def release_model_version(")]
    assert "if current is None or until > current:" in body
    assert "row.retention_pinned_until = until" in body
    assert "Never shortens" in body


def test_release_and_deployment_guards_are_still_in_the_service():
    source = LINEAGE.read_text(encoding="utf-8")
    for guard in (
        "an unverified model version cannot be released",
        "a model version must be retention pinned before release",
        "only a released model version can be deployed",
        "deployed_digest=version.content_sha256",
        "approval.subject_sha256 != version.content_sha256",
    ):
        assert guard in source, guard
