"""PG-free fail-closed tests for the AC-11 hosted migration rehearsal."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tools.migration_graph import Revision, chain


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_ac11_migration_rehearsal", ROOT / "tools" / "run_ac11_migration_rehearsal.py"
)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def _load_manifest_with_reviewed_design(monkeypatch):
    payload = json.loads(runner.MANIFEST_PATH.read_text(encoding="utf-8"))
    monkeypatch.setattr(runner, "_git", lambda *_args: payload["designRef"]["blob"])
    return runner.load_fixture_manifest()


def test_fixture_manifest_covers_graph_and_routes_all_ten_lossy_revisions_to_restore(monkeypatch):
    payload = _load_manifest_with_reviewed_design(monkeypatch)
    mapping = runner.validate_fixture_manifest(payload, chain())
    assert set(mapping) == {revision.revision for revision in chain() if not revision.irreversible}
    assert {key for key, value in mapping.items() if value == "DECLARED_LOSS_REQUIRES_RESTORE"} == runner.EXPECTED_LOSSY
    assert len(runner.EXPECTED_LOSSY) == 10


def test_noop_downgrade_is_invalid_before_any_database_call(tmp_path, monkeypatch):
    migration = tmp_path / "noop.py"
    migration.write_text(
        'revision = "noop"\ndown_revision = None\ndef downgrade():\n    pass\n',
        encoding="utf-8",
    )
    payload = {
        "schemaVersion": runner.SCHEMA_VERSION,
        "designRef": {},
        "revisions": [
            {"revision": "noop", "expected": "DECLARED_LOSS_REQUIRES_RESTORE"}
        ],
    }
    monkeypatch.setattr(runner, "EXPECTED_LOSSY", {"noop"})
    with pytest.raises(runner.RehearsalError, match="no-op downgrade"):
        runner.validate_fixture_manifest(
            payload,
            [Revision("noop", None, migration, False, None)],
        )


@pytest.mark.parametrize("body", ["...", "return", "return None"])
def test_other_noop_downgrade_forms_are_invalid(body):
    source = f'def downgrade():\n    {body}\n'
    assert runner.downgrade_body_kind(source) == "invalid-noop"


def test_successful_downgrade_claim_for_refusal_revision_is_invalid(tmp_path, monkeypatch):
    migration = tmp_path / "refusal.py"
    migration.write_text(
        'revision = "refusal"\ndown_revision = None\ndef downgrade():\n'
        '    raise RuntimeError("restore")\n',
        encoding="utf-8",
    )
    payload = {
        "schemaVersion": runner.SCHEMA_VERSION,
        "designRef": {},
        "revisions": [{"revision": "refusal", "expected": "PRESERVED"}],
    }
    monkeypatch.setattr(runner, "EXPECTED_LOSSY", set())
    with pytest.raises(runner.RehearsalError, match="reversible classification drifted"):
        runner.validate_fixture_manifest(
            payload,
            [Revision("refusal", None, migration, False, None)],
        )


def test_missing_0009_fixture_fails_closed(monkeypatch):
    payload = copy.deepcopy(_load_manifest_with_reviewed_design(monkeypatch))
    payload["revisions"] = [
        row for row in payload["revisions"]
        if row["revision"] != "0009_idempotency_and_inbox_scope"
    ]
    with pytest.raises(runner.RehearsalError, match="exactly cover reversible revisions"):
        runner.validate_fixture_manifest(payload, chain())


def test_fixture_manifest_rejects_unreachable_reviewed_design(monkeypatch):
    monkeypatch.setattr(runner, "_git", lambda *_args: "0" * 40)
    with pytest.raises(runner.RehearsalError, match="designRef blob is unreachable"):
        runner.load_fixture_manifest()


def test_catalog_fingerprint_detects_existing_object_deletion():
    expected = runner.CatalogFingerprint(
        sha256="a" * 64,
        counts={"tables": 2},
        sections={"tables": [["public", "tenants"], ["public", "projects"]]},
    )
    actual = runner.CatalogFingerprint(
        sha256="b" * 64,
        counts={"tables": 1},
        sections={"tables": [["public", "tenants"]]},
    )
    with pytest.raises(runner.CatalogMismatch, match="catalog fingerprint mismatch: tables") as exc:
        runner.compare_catalogs(expected, actual)
    assert exc.value.diagnostics == {
        "tables": {
            "expectedCount": 2,
            "actualCount": 1,
            "expectedOnlyCount": 1,
            "actualOnlyCount": 0,
            "expectedOnlySample": [{"rowSha256": runner.canonical_sha256(["public", "projects"])}],
            "actualOnlySample": [],
        }
    }


def test_catalog_diagnostics_hash_function_definitions_and_routine_specific_names():
    expected = runner.CatalogFingerprint(
        sha256="a" * 64,
        counts={"functions": 1, "routineGrants": 1},
        sections={
            "functions": [["inv", "f", "", "void", "sql", "owner", True, "", "secret body"]],
            "routineGrants": [["inv", "f", "integer", "inv_app", "EXECUTE", "NO"]],
        },
    )
    actual = runner.CatalogFingerprint(
        sha256="b" * 64,
        counts={"functions": 1, "routineGrants": 1},
        sections={
            "functions": [["inv", "f", "", "void", "sql", "owner", True, "", "changed body"]],
            "routineGrants": [["inv", "f", "uuid", "inv_app", "EXECUTE", "NO"]],
        },
    )
    diagnostics = runner.catalog_diff_diagnostics(
        expected, actual, ["functions", "routineGrants"]
    )
    serialized = str(diagnostics)
    assert "secret body" not in serialized and "changed body" not in serialized
    assert diagnostics["functions"]["expectedOnlySample"][0]["key"] == ["inv", "f", ""]
    assert diagnostics["routineGrants"]["expectedOnlySample"][0]["key"] == [
        "inv", "f", "integer", "inv_app", "EXECUTE", "NO"
    ]


def test_catalog_queries_compare_logical_columns_and_stable_routine_identities():
    columns = runner.CATALOG_QUERIES["columns"]
    grants = runner.CATALOG_QUERIES["routineGrants"]
    assert "a.attname,a.attnum" not in columns
    assert "ORDER BY n.nspname,c.relname,a.attnum" in columns
    assert "specific_name" not in grants
    assert "pg_get_function_identity_arguments" in grants


def test_catalog_constraint_normalization_only_collapses_equivalent_array_text_casts():
    direct = (
        "CHECK (status::text = ANY (ARRAY['active'::character varying, "
        "'deleted'::character varying]::text[]))"
    )
    restored = (
        "CHECK (status::text = ANY (ARRAY['active'::character varying::text, "
        "'deleted'::character varying::text]))"
    )
    normalize = runner.normalize_constraint_definition
    assert normalize(direct) == normalize(restored)
    assert normalize(direct) != normalize(direct.replace("deleted", "quarantined"))
    unrelated = "CHECK ((payload::character varying::text <> ''::text))"
    assert normalize(unrelated) == unrelated


def test_junit_declares_zero_tail_as_skip_and_restore_as_pass():
    root = ET.fromstring(runner._junit_bytes(success=True, reversible_tail=0))
    assert root.attrib == {
        "name": "s11-ac11-migration-rehearsal",
        "tests": "6",
        "failures": "0",
        "errors": "0",
        "skipped": "1",
    }
    cases = {case.attrib["name"]: case for case in root.findall("testcase")}
    assert cases["reversible-segment"].find("skipped") is not None
    assert cases["irreversible-restore-forward"].find("failure") is None
    assert {
        "negative-existing-object-deletion",
        "negative-0009-duplicate-key",
        "negative-ellipsis-noop",
    }.issubset(cases)


def test_missing_dsn_refuses_without_writing_evidence(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("INV_TEST_ADMIN_DSN", raising=False)
    report = tmp_path / "report.json"
    junit = tmp_path / "junit.xml"
    result = runner.main(
        [
            "--source-run-id", "123",
            "--source-head-sha", "a" * 40,
            "--runner-image", "test",
            "--report", str(report),
            "--junit", str(junit),
        ]
    )
    assert result == 2
    assert not report.exists() and not junit.exists()
    assert "DSN" in capsys.readouterr().err


def test_failure_diagnostics_keep_owned_reason_but_redact_arbitrary_exception_text():
    assert runner.redacted_failure_reason(runner.RehearsalError("catalog mismatch")) == "catalog mismatch"
    secret = "postgresql://user:secret@example.invalid/db"
    assert runner.redacted_failure_reason(RuntimeError(secret)) == "RuntimeError"


def test_workflow_is_opt_in_exact_head_and_non_cancelling():
    source = (ROOT / ".github" / "workflows" / "ac11-migration-rehearsal.yml").read_text(
        encoding="utf-8"
    )
    assert "run-ac11-migration" in source
    assert "ref: ${{ env.SOURCE_HEAD_SHA }}" in source
    assert "github.event.pull_request.head.sha || github.sha" in source
    assert "cancel-in-progress: false" in source
    assert "fetch-depth: 0" in source
    assert "git fetch --no-tags origin a793f258dac9b2a4951df084089bf3a3a3ae1bcc" in source
    assert 'test -z "$(git status --porcelain)"' in source
    assert "postgres:16" in source
    assert "actions/upload-artifact@v4" in source
    assert "'tests': '6'" in source
