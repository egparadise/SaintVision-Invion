"""PG-free tests for the AC-11 migration artifact importer."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import aggregate_ac11_evidence as aggregator  # noqa: E402


SPEC = importlib.util.spec_from_file_location(
    "import_ac11_migration_rehearsal", TOOLS / "import_ac11_migration_rehearsal.py"
)
assert SPEC and SPEC.loader
importer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = importer
SPEC.loader.exec_module(importer)


SOURCE = "a" * 40
TREE = "b" * 40
DESIGN_BLOB = "99776a491772c4a62e1be26644d35a365d80a030"
RUN_ID = "36380000000"
REVERSIBLE_HEAD = "0053_eval_suite_project_scope"
REVERSIBLE_BARRIER = "0052_model_version_digest_scope"
NOW = datetime(2026, 9, 28, 5, 0, tzinfo=timezone.utc)
CRITERIA = {
    "catalogMismatchCount": {"operator": "eq", "value": 0},
    "negativeFixturePassCount": {"operator": "eq", "value": 4},
    "restoreForwardPassCount": {"operator": "eq", "value": 1},
}
REGISTRY = {
    "schemaVersion": "1.0.0",
    "targets": [
        {
            "targetId": importer.TARGET_ID,
            "axis": "irreversible-restore-forward",
            "sourceDocument": {
                "commit": "d" * 40,
                "path": "docs/design.md",
                "blob": DESIGN_BLOB,
            },
            "criteria": CRITERIA,
            "requiredEnvironment": {
                "topology": "hosted-single-postgres-service",
                "synthetic": True,
            },
        },
        {
            "targetId": importer.REVERSIBLE_TARGET_ID,
            "axis": "migration-reversible-segment",
            "sourceDocument": {
                "commit": "d" * 40,
                "path": "docs/design.md",
                "blob": DESIGN_BLOB,
            },
            "criteria": {
                "catalogMismatchCount": {"operator": "eq", "value": 0},
                "reversibleRoundtripPassCount": {"operator": "eq", "value": 1},
                "sentinelMismatchCount": {"operator": "eq", "value": 0},
            },
            "requiredEnvironment": {
                "topology": "hosted-single-postgres-service",
                "synthetic": True,
            },
        },
    ],
}


def report() -> dict:
    return {
        "schemaVersion": "1.0.0",
        "runPurpose": "s11-ac11-migration-rehearsal",
        "sourceRunId": RUN_ID,
        "sourceHeadSha": SOURCE,
        "checkoutTreeSha": TREE,
        "cleanCheckout": True,
        "startedAt": "2026-09-28T04:00:00Z",
        "finishedAt": "2026-09-28T04:01:00Z",
        "verdict": "MEASURED_PASS",
        "failureType": None,
        "environment": {
            "runnerImage": "Linux-X64",
            "topology": "hosted-single-postgres-service",
            "synthetic": True,
            "physicalFiveNodeComparable": False,
        },
        "cleanup": {"residueCount": 0},
        "axes": [
            {
                "axis": "migration-reversible-segment",
                "verdict": "MEASURED_PASS",
                "observationCount": 1,
                "details": {
                    "startingRevision": REVERSIBLE_HEAD,
                    "endingRevision": REVERSIBLE_BARRIER,
                    "catalogEquivalent": True,
                    "sentinelPreserved": True,
                },
            },
            {
                "axis": "irreversible-restore-forward",
                "verdict": "MEASURED_PASS",
                "observationCount": 1,
                "details": {
                    "negativeFixtures": {
                        "passedCount": 4,
                        "cases": [
                            {"case": "existing-object-deletion", "verdict": "EXPECTED_FINDING"},
                            {"case": "0009-duplicate-key", "verdict": "EXPECTED_FINDING"},
                            {"case": "ellipsis-noop", "verdict": "EXPECTED_FINDING"},
                            {"case": "0053-scoped-row-refusal", "verdict": "EXPECTED_FINDING"},
                        ],
                    }
                },
            },
        ],
    }


def junit(*, failing: bool = False, reversible_tail: int = 1) -> bytes:
    root = ET.Element(
        "testsuite",
        name="s11-ac11-migration-rehearsal",
        tests="7",
        failures="1" if failing else "0",
        errors="0",
        skipped="0" if reversible_tail else "1",
    )
    names = (
        "fixture-manifest",
        "reversible-segment",
        "irreversible-restore-forward",
        "negative-existing-object-deletion",
        "negative-0009-duplicate-key",
        "negative-ellipsis-noop",
        "negative-0053-scoped-row-refusal",
    )
    for name in names:
        case = ET.SubElement(root, "testcase", classname="ac11.migration", name=name)
        if name == "reversible-segment" and not reversible_tail:
            ET.SubElement(case, "skipped", message="no reversible tail; paired restore required")
        if failing and name == "negative-0009-duplicate-key":
            ET.SubElement(case, "failure", message="wrong error")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def bundle(value: dict | None = None, junit_bytes: bytes | None = None) -> tuple[bytes, dict]:
    value = copy.deepcopy(value or report())
    junit_bytes = junit_bytes or junit()
    value["junitSha256"] = hashlib.sha256(junit_bytes).hexdigest()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(importer.REPORT_NAME, json.dumps(value, ensure_ascii=False))
        archive.writestr(importer.JUNIT_NAME, junit_bytes)
    return stream.getvalue(), value


def metadata(archive: bytes, value: dict) -> tuple[dict, dict]:
    run = {
        "id": int(RUN_ID),
        "status": "completed",
        "conclusion": "success",
        "head_sha": value["sourceHeadSha"],
    }
    artifact = {
        "id": 10952510591,
        "name": f"s11-ac11-migration-{value['sourceHeadSha']}",
        "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
        "expired": False,
        "expires_at": "2026-10-28T04:00:00Z",
        "workflow_run": {
            "id": int(RUN_ID),
            "head_sha": value["sourceHeadSha"],
        },
    }
    return run, artifact


def fake_git(*args: str) -> str:
    if args == ("rev-parse", f"{SOURCE}^{{tree}}"):
        return TREE
    if args == ("rev-parse", f"{SOURCE}:{importer.REGISTRY_PATH}"):
        return importer.REGISTRY_BLOB
    if args == ("show", f"{SOURCE}:{importer.REGISTRY_PATH}"):
        return json.dumps(REGISTRY)
    raise AssertionError(args)


class AggregatorGit:
    def tree(self, commit: str) -> str:
        return TREE

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return True

    def blob(self, commit: str, path: str) -> str:
        if path == importer.REGISTRY_PATH:
            return importer.REGISTRY_BLOB
        if path == "docs/design.md":
            return DESIGN_BLOB
        raise AssertionError((commit, path))

    def show(self, commit: str, path: str) -> str:
        if path == importer.REGISTRY_PATH:
            return json.dumps(REGISTRY)
        if path == "migrations/versions/0052_barrier.py":
            return (
                f'revision = "{REVERSIBLE_BARRIER}"\n'
                'down_revision = None\ndef downgrade():\n    raise RuntimeError("restore")\n'
            )
        if path == "migrations/versions/0053_head.py":
            return (
                f'revision = "{REVERSIBLE_HEAD}"\n'
                f'down_revision = "{REVERSIBLE_BARRIER}"\n'
                'def downgrade():\n    pass\n'
            )
        raise AssertionError((commit, path))

    def list_paths(self, commit: str, prefix: str) -> list[str]:
        assert commit == SOURCE and prefix == "migrations/versions"
        return [
            "migrations/versions/0052_barrier.py",
            "migrations/versions/0053_head.py",
        ]


def imported(monkeypatch, *, value: dict | None = None, run_mutation=None, artifact_mutation=None):
    monkeypatch.setattr(importer, "_git", fake_git)
    monkeypatch.setattr(
        importer,
        "_source_migration_segment",
        lambda _source: (REVERSIBLE_HEAD, REVERSIBLE_BARRIER, 1),
    )
    archive, bundled = bundle(value)
    run, artifact = metadata(archive, bundled)
    if run_mutation:
        run_mutation(run)
    if artifact_mutation:
        artifact_mutation(artifact)
    return importer.import_artifact(
        archive,
        run_metadata=run,
        artifact_metadata=artifact,
        now=NOW,
    )


def test_imported_restore_axis_is_consumed_by_stage_one_aggregator(monkeypatch):
    result = imported(monkeypatch)
    assert [row["axis"] for row in result["axes"]] == [
        "migration-reversible-segment",
        "irreversible-restore-forward",
    ]
    reversible, restore = result["axes"]
    reversible_evaluated = aggregator.evaluate_axis(reversible, AggregatorGit(), {}, NOW)
    evaluated = aggregator.evaluate_axis(restore, AggregatorGit(), {}, NOW)
    assert reversible_evaluated.verdict is aggregator.Verdict.MEASURED_PASS
    assert evaluated.verdict is aggregator.Verdict.MEASURED_PASS
    assert restore["artifactSha256"] == restore["artifactObservedSha256"]
    assert restore["producerReportSha256"] == result["producerReportSha256"]
    assert restore["junitSha256"] == result["junitSha256"]


def test_zero_tail_imports_only_the_graph_proved_structural_exception(monkeypatch):
    monkeypatch.setattr(importer, "_git", fake_git)
    monkeypatch.setattr(
        importer,
        "_source_migration_segment",
        lambda _source: ("0054_irreversible_head", "0054_irreversible_head", 0),
    )
    value = report()
    value["axes"][0] = {
        "axis": "migration-reversible-segment",
        "verdict": "NOT_APPLICABLE",
        "structuralException": {"reason": "no-reversible-tail", "reversibleTailCount": 0},
    }
    archive, bundled = bundle(value, junit(reversible_tail=0))
    run, artifact = metadata(archive, bundled)
    result = importer.import_artifact(
        archive, run_metadata=run, artifact_metadata=artifact, now=NOW
    )
    reversible = result["axes"][0]
    assert reversible["verdict"] == "NOT_APPLICABLE"
    assert "targetRef" not in reversible and "observations" not in reversible


def test_graph_tail_and_junit_evidence_kind_mismatch_is_rejected(monkeypatch):
    monkeypatch.setattr(importer, "_git", fake_git)
    monkeypatch.setattr(
        importer,
        "_source_migration_segment",
        lambda _source: ("0054_irreversible_head", "0054_irreversible_head", 0),
    )
    archive, bundled = bundle()
    run, artifact = metadata(archive, bundled)
    with pytest.raises(importer.EvidenceImportError, match="differs from the source graph"):
        importer.import_artifact(
            archive, run_metadata=run, artifact_metadata=artifact, now=NOW
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(verdict="MEASURED_FAIL"), "failed rehearsal"),
        (lambda value: value["cleanup"].update(residueCount=1), "cleanup"),
        (
            lambda value: value["axes"][1]["details"]["negativeFixtures"].update(
                passedCount=2
            ),
            "negative fixture",
        ),
        (
            lambda value: value["axes"][0]["details"].update(catalogEquivalent=False),
            "tail roundtrip",
        ),
        (
            lambda value: value["axes"][0].update(
                verdict="NOT_APPLICABLE",
                structuralException={"reason": "no-reversible-tail", "reversibleTailCount": 0},
            ),
            "tail roundtrip",
        ),
        (lambda value: value.pop("sourceRunId"), "sourceRunId"),
    ],
)
def test_importer_rejects_incomplete_or_failed_producer_evidence(monkeypatch, mutation, message):
    monkeypatch.setattr(importer, "_git", fake_git)
    monkeypatch.setattr(
        importer,
        "_source_migration_segment",
        lambda _source: (REVERSIBLE_HEAD, REVERSIBLE_BARRIER, 1),
    )
    value = report()
    mutation(value)
    archive, bundled = bundle(value)
    run, artifact = metadata(archive, bundled)
    with pytest.raises(importer.EvidenceImportError, match=message):
        importer.import_artifact(
            archive, run_metadata=run, artifact_metadata=artifact, now=NOW
        )


@pytest.mark.parametrize(
    ("run_mutation", "artifact_mutation", "message"),
    [
        (None, lambda value: value.update(digest="sha256:" + "0" * 64), "digest"),
        (None, lambda value: value.update(expired=True), "expired"),
        (None, lambda value: value.update(expires_at="2026-09-28T04:59:59Z"), "expired"),
        (lambda value: value.update(conclusion="failure"), None, "successfully"),
        (lambda value: value.update(head_sha="f" * 40), None, "head"),
        (None, lambda value: value["workflow_run"].update(id=36379589596), "sourceRunId"),
        (None, lambda value: value.update(name="unbound-artifact"), "name"),
    ],
)
def test_importer_rejects_unbound_github_metadata(
    monkeypatch, run_mutation, artifact_mutation, message
):
    with pytest.raises(importer.EvidenceImportError, match=message):
        imported(
            monkeypatch,
            run_mutation=run_mutation,
            artifact_mutation=artifact_mutation,
        )


def test_importer_rejects_junit_result_drift(monkeypatch):
    monkeypatch.setattr(importer, "_git", fake_git)
    monkeypatch.setattr(
        importer,
        "_source_migration_segment",
        lambda _source: (REVERSIBLE_HEAD, REVERSIBLE_BARRIER, 1),
    )
    archive, bundled = bundle(report(), junit(failing=True))
    run, artifact = metadata(archive, bundled)
    with pytest.raises(importer.EvidenceImportError, match="JUnit summary"):
        importer.import_artifact(
            archive, run_metadata=run, artifact_metadata=artifact, now=NOW
        )


def test_main_reads_zip_and_github_metadata_files(tmp_path, monkeypatch):
    monkeypatch.setattr(importer, "_git", fake_git)
    monkeypatch.setattr(
        importer,
        "_source_migration_segment",
        lambda _source: (REVERSIBLE_HEAD, REVERSIBLE_BARRIER, 1),
    )
    archive, bundled = bundle()
    run, artifact = metadata(archive, bundled)
    archive_path = tmp_path / "evidence.zip"
    run_path = tmp_path / "run.json"
    artifact_path = tmp_path / "artifact.json"
    output = tmp_path / "imported.json"
    archive_path.write_bytes(archive)
    run_path.write_text(json.dumps(run), encoding="utf-8")
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    assert importer.main(
        [
            "--artifact-zip", str(archive_path),
            "--run-metadata", str(run_path),
            "--artifact-metadata", str(artifact_path),
            "--output", str(output),
        ]
    ) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["axes"][1]["verdict"] == "MEASURED_PASS"
