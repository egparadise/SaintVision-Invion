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


def test_inv_audit_reader_visibility_exception_is_removed_not_extended():
    source, policy, baseline = inputs()
    generated = tool.build_allowlist(source, policy, baseline)
    assert all(
        row["role"] != "inv_audit_reader"
        for row in generated["rlsAcceptedDispositions"]
    )
    assert all(
        row["role"] != "inv_audit_reader" for row in baseline["accepted"]
    )
    assert all(
        row["disposition"] != "accepted-with-expiry"
        for row in generated["rlsAcceptedDispositions"]
    )


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
    assert "irreversible = True" in migration
    assert "REVOKE SELECT ON public.tenants FROM inv_app" in migration
    assert "GRANT SELECT ON tenants" not in helper
    downgrade = migration.split("def downgrade():", 1)[1]
    assert "REVOKE SELECT ON public.tenants FROM inv_app" in downgrade
    assert "GRANT SELECT" not in downgrade


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


def test_audit_reader_grant_and_unconditional_policy_are_removed_without_a_product_caller():
    """Card 268 turns the dormant privilege into an exact least-privilege ratchet."""

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

    revoke = (ROOT / "migrations/versions/0067_audit_reader_revoke.py").read_text(
        encoding="utf-8"
    )
    assert 'revision = "0067_audit_reader_revoke"' in revoke
    assert 'down_revision = "0066_tenant_registry_revoke"' in revoke
    assert "irreversible = True" in revoke
    for operation in (
        "DROP POLICY IF EXISTS audit_events_audit_read ON public.audit_events",
        "REVOKE SELECT ON public.audit_events FROM inv_audit_reader",
        "REVOKE USAGE ON SCHEMA public FROM inv_audit_reader",
    ):
        assert revoke.count(operation) == 2, operation
    assert "GRANT" not in revoke.split("def downgrade():", 1)[1]

    later_migrations = [
        path for path in (ROOT / "migrations/versions").glob("*.py")
        if path.name > "0047_audit_events_isolation.py"
        and "inv_audit_reader" in path.read_text(encoding="utf-8")
    ]
    assert later_migrations == [ROOT / "migrations/versions/0067_audit_reader_revoke.py"]

    product_refs = {
        path.relative_to(ROOT).as_posix()
        for parent in (ROOT / "src", ROOT / "services")
        for path in parent.rglob("*.py")
        if re.search(r"\binv_audit_reader\b", path.read_text(encoding="utf-8"))
    }
    assert product_refs == set()
