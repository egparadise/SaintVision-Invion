"""PG-free fail-closed tests for the AC-11 hosted migration rehearsal."""

from __future__ import annotations

import copy
import importlib.util
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


def test_fixture_manifest_covers_graph_and_routes_all_ten_lossy_revisions_to_restore():
    payload = runner.load_fixture_manifest()
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


def test_missing_0009_fixture_fails_closed():
    payload = copy.deepcopy(runner.load_fixture_manifest())
    payload["revisions"] = [
        row for row in payload["revisions"]
        if row["revision"] != "0009_idempotency_and_inbox_scope"
    ]
    with pytest.raises(runner.RehearsalError, match="exactly cover reversible revisions"):
        runner.validate_fixture_manifest(payload, chain())


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
    with pytest.raises(runner.RehearsalError, match="catalog fingerprint mismatch: tables"):
        runner.compare_catalogs(expected, actual)


def test_junit_declares_zero_tail_as_skip_and_restore_as_pass():
    root = ET.fromstring(runner._junit_bytes(success=True, reversible_tail=0))
    assert root.attrib == {
        "name": "s11-ac11-migration-rehearsal",
        "tests": "3",
        "failures": "0",
        "errors": "0",
        "skipped": "1",
    }
    cases = {case.attrib["name"]: case for case in root.findall("testcase")}
    assert cases["reversible-segment"].find("skipped") is not None
    assert cases["irreversible-restore-forward"].find("failure") is None


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


def test_workflow_is_opt_in_exact_head_and_non_cancelling():
    source = (ROOT / ".github" / "workflows" / "ac11-migration-rehearsal.yml").read_text(
        encoding="utf-8"
    )
    assert "run-ac11-migration" in source
    assert "ref: ${{ env.SOURCE_HEAD_SHA }}" in source
    assert "github.event.pull_request.head.sha || github.sha" in source
    assert "cancel-in-progress: false" in source
    assert 'test -z "$(git status --porcelain)"' in source
    assert "postgres:16" in source
    assert "actions/upload-artifact@v4" in source
