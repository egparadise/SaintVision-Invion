"""The AC-11 security allowlist is generated only from exact reviewed inputs."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import write_ac11_security_allowlist as tool  # noqa: E402


def loaded(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def inputs():
    return (
        loaded(tool.DEFAULT_SOURCE),
        loaded(tool.DEFAULT_POLICY),
        loaded(tool.DEFAULT_BASELINE),
    )


def test_committed_allowlist_is_exact_generated_output():
    source, policy, baseline = inputs()
    expected = tool.build_allowlist(source, policy, baseline)
    assert tool.render(expected) == tool.DEFAULT_OUTPUT.read_text(encoding="utf-8")
    assert set(expected["definerPolicySignatures"]) == set(policy["functions"])
    assert len(expected["definerPolicySignatures"]) == 15


def test_sec_vf_001_stays_bound_to_the_browser_lane_not_the_scan_lane():
    """The scan producer and SEC-VF-001 browser proof are different authorities."""

    source, policy, baseline = inputs()
    generated = tool.build_allowlist(source, policy, baseline)
    workflow = generated["secVf001"]["workflow"]
    assert workflow["path"] == ".github/workflows/desktop-browser.yml"
    assert workflow["path"] != ".github/workflows/ac11-security-scan.yml"
    assert workflow["blob"] == tool.git_blob((ROOT / workflow["path"]).read_bytes())


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "revision"])
def test_definer_review_cannot_shrink_expand_duplicate_or_change_revision(mutation):
    source, policy, baseline = inputs()
    if mutation == "missing":
        source["definerReview"]["signatures"].pop()
    elif mutation == "extra":
        source["definerReview"]["signatures"].append("public.unreviewed()")
    elif mutation == "duplicate":
        source["definerReview"]["signatures"].append(
            source["definerReview"]["signatures"][-1]
        )
    else:
        source["definerReview"]["policyRevision"] = "0058_release_acceptance_evidence"
    with pytest.raises(ValueError):
        tool.build_allowlist(source, policy, baseline)


@pytest.mark.parametrize("mutation", ["missing", "invented", "rules", "duplicate"])
def test_rls_decisions_must_exactly_cover_the_collector_baseline(mutation):
    source, policy, baseline = inputs()
    rows = source["rlsAcceptedDispositions"]
    if mutation == "missing":
        rows.pop()
    elif mutation == "invented":
        rows.append(
            {
                "role": "inv_app",
                "table": "public.projects",
                "rules": ["E4"],
                "disposition": "false-positive-with-proof",
                "proof": "invented",
            }
        )
    elif mutation == "rules":
        rows[-1]["rules"] = ["E3", "E4"]
    else:
        rows.append(copy.deepcopy(rows[-1]))
    with pytest.raises(ValueError):
        tool.build_allowlist(source, policy, baseline)


def test_inv_audit_reader_visibility_is_expiring_not_a_false_positive():
    source, policy, baseline = inputs()
    generated = tool.build_allowlist(source, policy, baseline)
    reader = next(
        row
        for row in generated["rlsAcceptedDispositions"]
        if row["role"] == "inv_audit_reader"
    )
    assert reader["table"] == "public.audit_events"
    assert reader["rules"] == ["E3", "E4", "E5"]
    assert reader["disposition"] == "accepted-with-expiry"
    assert reader["expiresAt"] == "2026-11-30T23:59:59+09:00"


def test_inv_app_tenant_registry_exception_was_removed_with_the_grant():
    source, policy, baseline = inputs()
    generated = tool.build_allowlist(source, policy, baseline)
    identities = {
        (row["role"], row["table"])
        for row in generated["rlsAcceptedDispositions"]
    }
    assert ("inv_app", "public.tenants") not in identities
    assert ("inv_discovery_issuer", "public.tenants") in identities

    migration = (
        ROOT / "migrations/versions/0066_tenant_registry_revoke.py"
    ).read_text(encoding="utf-8")
    helper = (ROOT / "src/saintvision/db/rls.py").read_text(encoding="utf-8")
    assert 'revision = "0066_tenant_registry_revoke"' in migration
    assert 'down_revision = "0064_model_version_run_fk"' in migration
    assert "REVOKE SELECT ON public.tenants FROM inv_app" in migration
    assert "GRANT SELECT ON tenants" not in helper
    assert "Restoring inv_app cross-tenant registry SELECT requires a reviewed forward fix" in migration


def test_no_product_path_reads_public_tenant_registry_as_inv_app():
    """Card 264 ratchet: new product use requires a new least-privilege design.

    Operator provisioning and security measurement live under ``tools`` and use an
    owner/admin DSN.  The product trees have no tenant-registry query; explanatory
    strings about the boundary are allowed but executable SQL is not.
    """

    query = re.compile(
        r"(?:from|join)\s+(?:public\.)?tenants\b",
        re.IGNORECASE,
    )
    matches = []
    for parent in (ROOT / "src", ROOT / "services"):
        for path in parent.rglob("*.py"):
            if query.search(path.read_text(encoding="utf-8")):
                matches.append(path.relative_to(ROOT).as_posix())
    assert matches == []


def test_audit_reader_review_matches_the_only_grant_and_has_no_product_caller():
    """Card 254 re-review: the privilege is dormant and its DDL boundary is unchanged.

    The exact product-source occurrence set is a ratchet.  Those three references are explanatory
    docstrings/comments, not a connection or role-assumption path; adding any product reference
    forces this reviewed disposition back through security review before its next expiry.
    """

    migration = (ROOT / "migrations/versions/0047_audit_events_isolation.py").read_text(
        encoding="utf-8"
    )
    assert "ALTER ROLE inv_audit_reader NOLOGIN NOSUPERUSER" in migration
    assert "NOINHERIT NOBYPASSRLS" in migration
    assert "inv_audit_reader already has members" in migration
    assert "CREATE POLICY audit_events_audit_read ON audit_events FOR SELECT TO inv_audit_reader" in migration
    assert "USING (true)" in migration
    assert "GRANT SELECT ON audit_events TO inv_audit_reader" in migration
    assert "REVOKE SELECT ON audit_events FROM inv_app" in migration

    later_migrations = [
        path for path in (ROOT / "migrations/versions").glob("*.py")
        if path.name > "0047_audit_events_isolation.py"
        and "inv_audit_reader" in path.read_text(encoding="utf-8")
    ]
    assert later_migrations == []

    product_refs = {
        path.relative_to(ROOT).as_posix()
        for parent in (ROOT / "src", ROOT / "services")
        for path in parent.rglob("*.py")
        if re.search(r"\binv_audit_reader\b", path.read_text(encoding="utf-8"))
    }
    assert product_refs == {
        "src/saintvision/db/models/__init__.py",
        "src/saintvision/db/models/operations.py",
        "src/saintvision/services/audit.py",
    }
