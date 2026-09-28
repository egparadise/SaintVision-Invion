from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.aggregate_ac11_evidence import REQUIRED_TARGET_BY_AXIS, Verdict, evaluate_axis
from tools.import_ac11_composite_long_soak import (
    CASE_IDENTITIES,
    CASE_IDENTITIES_SHA256,
    EvidenceImportError,
    FAULT_CLASSES,
    FAULT_CLASSES_SHA256,
    HOSTED_STORAGE_SHA256,
    REGISTRY_BLOB,
    REGISTRY_PATH,
    STORAGE_PHYSICAL_SHA256,
    _canonical_sha,
    import_report,
    readiness,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "a" * 40
TREE = "b" * 40
ARTIFACT = "c" * 64
DOC_COMMIT = "938ad3eb1c1664890c714f6ec86f409b7dab65b9"
DOC_PATH = "docs/vault/30_Development/S11_AC11_composite_long_soak_target_v0.md"
DOC_BLOB = "0bf74f90557a237b50ebdf571ed9e3dac89ea23b"


class FakeGit:
    def __init__(self, *, registered: bool = True, document_blob: str = DOC_BLOB):
        registry = json.loads((ROOT / REGISTRY_PATH).read_text(encoding="utf-8"))
        if not registered:
            registry["targets"] = [
                row for row in registry["targets"]
                if row.get("targetId") != "s11-ac11-composite-long-soak-v0"
            ]
        self.registry = json.dumps(registry)
        self.document_blob = document_blob

    def tree(self, commit: str) -> str:
        assert commit == SOURCE
        return TREE

    def blob(self, commit: str, path: str) -> str:
        if path == REGISTRY_PATH:
            assert commit == SOURCE
            return REGISTRY_BLOB
        if path == DOC_PATH and commit in {DOC_COMMIT, SOURCE}:
            return self.document_blob
        raise AssertionError((commit, path))

    def show(self, commit: str, path: str) -> str:
        assert commit == SOURCE and path == REGISTRY_PATH
        return self.registry

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return descendant == SOURCE and ancestor in {DOC_COMMIT, SOURCE}


def _fixture() -> tuple[dict, dict, dict]:
    registry = json.loads((ROOT / REGISTRY_PATH).read_text(encoding="utf-8"))
    target = next(row for row in registry["targets"] if row["axis"] == "long-soak")
    metrics = {name: rule["value"] for name, rule in target["criteria"].items()}
    report = {
        "schemaVersion": "1.0.0",
        "runPurpose": "s11-ac11-composite-long-soak",
        "sourceRunId": "physical-24h-fixture",
        "sourceHeadSha": SOURCE,
        "checkoutTreeSha": TREE,
        "cleanCheckout": True,
        "startedAt": "2026-09-01T00:00:00Z",
        "finishedAt": "2026-09-02T00:00:00Z",
        "artifactSha256": ARTIFACT,
        "artifactObservedSha256": ARTIFACT,
        "artifactExpiresAt": "2026-10-02T00:00:00Z",
        "inventoryRevision": "inventory-five-node-r1",
        "environment": {**target["requiredEnvironment"], "comparableGroup": "physical-five-node-r1"},
        "operatorResources": ["G-19", "G-24"],
        "caseIdentities": list(CASE_IDENTITIES),
        "faultClasses": list(FAULT_CLASSES),
        "cases": [
            {"caseIdentity": identity, "verdict": "PASS", "faultClass": None}
            for identity in CASE_IDENTITIES
        ],
        "metrics": metrics,
        "cleanup": {"residueCount": 0},
        "externalObserverReceipt": {
            "kind": "external-monotonic-v1",
            "inventoryRevision": "inventory-five-node-r1",
            "coveragePpm": metrics["externalObserverCoveragePpm"],
            "redacted": True,
        },
        "storageReferenceSha256": "",
        "hostedReferenceSha256": "",
    }
    storage = {
        "kind": "s11-storage-physical-reference",
        "referenceOnly": True,
        "targetId": "s11-storage-soak-physical-reference-v0",
        "verdict": "MEASURED_PASS",
        "sourceHeadSha": SOURCE,
        "inventoryRevision": report["inventoryRevision"],
        "startedAt": report["startedAt"],
        "finishedAt": report["finishedAt"],
        "caseIdentitiesSha256": STORAGE_PHYSICAL_SHA256,
        "artifactSha256": "d" * 64,
    }
    hosted = {
        "kind": "s11-storage-reference-evidence",
        "referenceOnly": True,
        "executionLayer": "hosted-minio-postgresql",
        "verdict": "MEASURED_PASS",
        "sourceHeadSha": SOURCE,
        "caseIdentitiesSha256": HOSTED_STORAGE_SHA256,
        "artifactSha256": "e" * 64,
        "artifactObservedSha256": "e" * 64,
        "artifactAvailable": True,
        "artifactExpiresAt": "2026-10-02T00:00:00Z",
        "runConclusion": "success",
    }
    report["storageReferenceSha256"] = _canonical_sha(storage)
    report["hostedReferenceSha256"] = _canonical_sha(hosted)
    assert _canonical_sha(report["caseIdentities"]) == CASE_IDENTITIES_SHA256
    assert _canonical_sha(report["faultClasses"]) == FAULT_CLASSES_SHA256
    return report, storage, hosted


def test_valid_physical_report_is_accepted_by_the_ac11_aggregator() -> None:
    report, storage, hosted = _fixture()
    git = FakeGit()
    envelope = import_report(report, storage, hosted, git)
    assert envelope["verdict"] == "MEASURED_PASS"
    result = evaluate_axis(envelope, git, {}, datetime(2026, 9, 3, tzinfo=timezone.utc))
    assert result.verdict is Verdict.MEASURED_PASS


def test_registry_blob_and_required_axis_are_repin_bound() -> None:
    raw = (ROOT / REGISTRY_PATH).read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert blob == REGISTRY_BLOB
    registry = json.loads(raw)
    assert sum(row.get("targetId") == "s11-ac11-composite-long-soak-v0" for row in registry["targets"]) == 1
    assert REQUIRED_TARGET_BY_AXIS["long-soak"] == "s11-ac11-composite-long-soak-v0"


def test_missing_operator_resources_remain_blocked_external() -> None:
    report, storage, hosted = _fixture()
    report["operatorResources"] = ["G-19"]
    assert import_report(report, storage, hosted, FakeGit()) == {
        "axis": "long-soak", "verdict": "BLOCKED_EXTERNAL", "blocker": "G-24"
    }


def test_absent_registry_target_is_not_registered() -> None:
    assert readiness(SOURCE, {"G-19", "G-24"}, FakeGit(registered=False)) == {
        "axis": "long-soak", "verdict": "NOT_REGISTERED", "reason": "target is absent"
    }


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda r, s, h: r["caseIdentities"].pop(), "case identities"),
        (lambda r, s, h: r["cases"].__setitem__(1, copy.deepcopy(r["cases"][0])), "identity or verdict"),
        (lambda r, s, h: r["cases"][0].update(verdict="FAIL", faultClass="UNKNOWN"), "unknown fault class"),
        (lambda r, s, h: r["environment"].update(eligibleNodeCount=5), "physical environment"),
        (lambda r, s, h: s.update(sourceHeadSha="f" * 40), "same run window"),
        (lambda r, s, h: h.update(sourceHeadSha="f" * 40), "same-source reference"),
        (lambda r, s, h: r["metrics"].update(requiredCaseCount=13), "derived metrics"),
        (lambda r, s, h: r["externalObserverReceipt"].update(coveragePpm=1), "observer receipt"),
    ],
)
def test_identity_topology_child_and_receipt_mutations_fail_closed(mutation, message: str) -> None:
    report, storage, hosted = _fixture()
    mutation(report, storage, hosted)
    report["storageReferenceSha256"] = _canonical_sha(storage)
    report["hostedReferenceSha256"] = _canonical_sha(hosted)
    with pytest.raises(EvidenceImportError, match=message):
        import_report(report, storage, hosted, FakeGit())


def test_child_digest_substitution_fails_closed() -> None:
    report, storage, hosted = _fixture()
    storage["artifactSha256"] = "0" * 64
    with pytest.raises(EvidenceImportError, match="storage reference digest"):
        import_report(report, storage, hosted, FakeGit())


def test_target_source_document_drift_fails_closed() -> None:
    report, storage, hosted = _fixture()
    with pytest.raises(EvidenceImportError, match="source document blob"):
        import_report(report, storage, hosted, FakeGit(document_blob="0" * 40))
