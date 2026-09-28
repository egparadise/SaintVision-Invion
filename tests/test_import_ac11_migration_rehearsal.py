"""PG-free tests for the AC-11 migration artifact importer."""

from __future__ import annotations

import importlib.util
import json
import sys
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
ARTIFACT = "c" * 64
DESIGN_BLOB = "99776a491772c4a62e1be26644d35a365d80a030"
CRITERIA = {
    "catalogMismatchCount": {"operator": "eq", "value": 0},
    "negativeFixturePassCount": {"operator": "eq", "value": 3},
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
        }
    ],
}


def report() -> dict:
    return {
        "schemaVersion": "1.0.0",
        "runPurpose": "s11-ac11-migration-rehearsal",
        "sourceRunId": "36380000000",
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
                "verdict": "NOT_APPLICABLE",
                "structuralException": {
                    "reason": "no-reversible-tail",
                    "reversibleTailCount": 0,
                },
            },
            {
                "axis": "irreversible-restore-forward",
                "verdict": "MEASURED_PASS",
                "observationCount": 1,
                "details": {
                    "negativeFixtures": {
                        "passedCount": 3,
                        "cases": [
                            {"case": "existing-object-deletion", "verdict": "EXPECTED_FINDING"},
                            {"case": "0009-duplicate-key", "verdict": "EXPECTED_FINDING"},
                            {"case": "ellipsis-noop", "verdict": "EXPECTED_FINDING"},
                        ],
                    }
                },
            },
        ],
    }


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
        raise AssertionError((commit, path))

    def list_paths(self, commit: str, prefix: str) -> list[str]:
        raise AssertionError((commit, prefix))


def test_imported_restore_axis_is_consumed_by_stage_one_aggregator(monkeypatch):
    monkeypatch.setattr(importer, "_git", fake_git)
    imported = importer.import_report(
        report(), artifact_digest="sha256:" + ARTIFACT,
        artifact_expires_at="2026-10-28T04:00:00Z",
    )
    assert [row["axis"] for row in imported["axes"]] == [
        "migration-reversible-segment",
        "irreversible-restore-forward",
    ]
    restore = imported["axes"][1]
    result = aggregator.evaluate_axis(
        restore,
        AggregatorGit(),
        {},
        datetime(2026, 9, 28, 5, 0, tzinfo=timezone.utc),
    )
    assert result.verdict is aggregator.Verdict.MEASURED_PASS
    assert restore["artifactSha256"] == ARTIFACT


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
    ],
)
def test_importer_rejects_incomplete_or_failed_producer_evidence(monkeypatch, mutation, message):
    monkeypatch.setattr(importer, "_git", fake_git)
    value = report()
    mutation(value)
    with pytest.raises(importer.ImportError, match=message):
        importer.import_report(
            value,
            artifact_digest=ARTIFACT,
            artifact_expires_at="2026-10-28T04:00:00Z",
        )


def test_importer_rejects_non_sha256_artifact_digest(monkeypatch):
    monkeypatch.setattr(importer, "_git", fake_git)
    with pytest.raises(importer.ImportError, match="artifact digest"):
        importer.import_report(
            report(),
            artifact_digest="not-a-digest",
            artifact_expires_at="2026-10-28T04:00:00Z",
        )
