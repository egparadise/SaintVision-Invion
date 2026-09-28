"""PG-free contract and mutation tests for S11-ST storage fault evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import import_s11_storage_failure_evidence as importer  # noqa: E402
import run_s11_storage_failure_pg_free as producer  # noqa: E402


SOURCE = "a" * 40
TREE = "b" * 40
PRODUCER_BLOB = "c" * 40
VERIFIER_BLOB = "d" * 40


class FakeGit:
    source_tree = TREE
    producer_blob = PRODUCER_BLOB

    def tree(self, commit: str) -> str:
        assert commit == SOURCE
        return self.source_tree

    def blob(self, commit: str, path: str) -> str:
        assert commit == SOURCE
        if path == producer.PRODUCER_PATH:
            return self.producer_blob
        assert path == producer.BACKUP_VERIFIER_PATH
        return VERIFIER_BLOB


def compact_sha(values: tuple[str, ...]) -> str:
    payload = json.dumps(list(values), ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def matching_case(identity: str) -> dict:
    return producer._receipt(identity, copy.deepcopy(producer.EXPECTED[identity]))


def report(executor=matching_case) -> dict:
    return producer.build_report(
        executor,
        source_run_id="36390000000",
        source_head_sha=SOURCE,
        checkout_tree_sha=TREE,
        producer_blob=PRODUCER_BLOB,
        backup_verifier_blob=VERIFIER_BLOB,
        clean_checkout=True,
        started_at="2026-09-28T07:00:00Z",
        finished_at="2026-09-28T07:01:00Z",
    )


def test_reviewed_identity_hashes_are_exact():
    assert tuple(sorted(producer.UNIVERSE_CASES)) == producer.UNIVERSE_CASES
    assert tuple(sorted(producer.PG_FREE_CASES)) == producer.PG_FREE_CASES
    assert compact_sha(producer.UNIVERSE_CASES) == producer.UNIVERSE_SHA256
    assert compact_sha(producer.PG_FREE_CASES) == producer.PG_FREE_SHA256
    assert len(producer.UNIVERSE_CASES) == 22
    assert len(producer.PG_FREE_CASES) == 12


def test_positive_report_imports_as_reference_only_pass():
    raw = report()
    evidence = importer.import_evidence(raw, producer.junit_xml(raw), FakeGit())
    assert evidence["referenceOnly"] is True
    assert evidence["axis"] is None and evidence["targetRef"] is None
    assert evidence["verdict"] == "MEASURED_PASS"
    assert evidence["metrics"] == {
        "attemptedCaseCount": 12,
        "classificationMismatchCount": 0,
        "falseSuccessCount": 0,
        "unexpectedErrorCount": 0,
        "committedObjectLossCount": None,
        "cleanupResidueCount": None,
        "partialResidueCount": None,
        "tempResidueCount": None,
        "quotaOvershootBytes": None,
        "observedCaseCountByMetric": {
            "quotaOvershootBytes": 0,
            "committedObjectLossCount": 0,
            "partialResidueCount": 0,
            "tempResidueCount": 0,
            "cleanupResidueCount": 0,
        },
    }


def test_default_linux_executor_covers_the_full_pg_free_tier():
    # Windows verifies the same closed contract with the pure executor above;
    # hosted Backend on Linux exercises LocalObjects and all fault injections.
    raw = report(producer.execute_case if sys.platform == "linux" else matching_case)
    evidence = importer.import_evidence(raw, producer.junit_xml(raw), FakeGit())
    assert raw["caseCount"] == 12
    if sys.platform == "linux":
        assert evidence["verdict"] == "MEASURED_FAIL"
        assert evidence["metrics"]["classificationMismatchCount"] == 7
        assert sum(case["actualSurface"].get("kind") == "osError" for case in raw["cases"]) == 7
    else:
        assert evidence["verdict"] == "MEASURED_PASS"


def test_product_finding_is_preserved_as_measured_fail():
    def executor(identity: str) -> dict:
        value = matching_case(identity)
        if identity == "OBJ-04/local/write-enospc":
            value["actualSurface"] = {"kind": "osError", "errno": 28}
            value["matched"] = False
            value["observedFindingCount"] = 1
        return value

    raw = report(executor)
    evidence = importer.import_evidence(raw, producer.junit_xml(raw), FakeGit())
    assert evidence["verdict"] == "MEASURED_FAIL"
    assert evidence["metrics"]["classificationMismatchCount"] == 1


@pytest.mark.parametrize("identity", producer.PG_FREE_CASES[:2])
def test_retention_and_backup_fault_cases_execute_hermetically(identity):
    case = producer.execute_case(identity)
    assert case["caseIdentity"] == identity
    assert case["actualSurface"] == {"kind": "osError", "errno": 5}
    assert case["matched"] is False
    assert case["observedFindingCount"] == 1
    assert case["beforeSha256"] == case["afterSha256"]
    assert case["partialResidueCount"] == 1


@pytest.mark.parametrize("identity", producer.PG_FREE_CASES[2:4])
def test_backup_fault_cases_call_the_reviewed_verifier(identity, monkeypatch):
    calls = []
    original = producer.verify_physical_backup_archive

    def observed(path):
        calls.append(Path(path).read_bytes())
        return original(path)

    monkeypatch.setattr(producer, "verify_physical_backup_archive", observed)
    case = producer.execute_case(identity)
    assert calls and case["matched"] is True and case["observedFindingCount"] == 0


def test_backup_fault_cannot_pass_if_the_verifier_is_removed(monkeypatch):
    monkeypatch.setattr(producer, "verify_physical_backup_archive", lambda _path: None)
    case = producer.execute_case("BAK-03/local/backup-exit0-empty")
    assert case["actualSurface"] == {"kind": "success"}
    assert case["matched"] is False and case["observedFindingCount"] == 1


def test_backup_verifier_accepts_only_structural_physical_archive(tmp_path):
    artifact = tmp_path / "base.tar"
    content = {
        "PG_VERSION": b"16\n",
        "backup_label": b"START WAL LOCATION: 0/1000000 (file 000000010000000000000001)\n",
        "global/pg_control": b"x" * 8192,
    }
    with tarfile.open(artifact, "w") as archive:
        for name, data in content.items():
            source = tmp_path / name.replace("/", "-")
            source.write_bytes(data)
            archive.add(source, arcname=name)
    receipt = producer.verify_physical_backup_archive(artifact)
    assert receipt.byte_size == artifact.stat().st_size and receipt.member_count == 3

    artifact.write_bytes(b"truncated")
    with pytest.raises(producer.BackupArtifactInvalid):
        producer.verify_physical_backup_archive(artifact)


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (lambda value: value.update(executionLayer="hosted"), "execution layer"),
        (lambda value: value.update(tierCaseIdentitiesSha256="0" * 64), "identity hash"),
        (lambda value: value.update(universeCaseIdentitiesSha256="0" * 64), "identity hash"),
        (lambda value: value.update(cleanCheckout=False), "clean checkout"),
        (lambda value: value.update(checkoutTreeSha="d" * 40), "checkout tree"),
        (lambda value: value["producerFile"].update(blob="d" * 40), "producer or injector"),
        (lambda value: value["backupVerifierFile"].update(blob="e" * 40), "backup verifier"),
        (lambda value: value.update(startedAt="2026-09-28T08:00:00Z"), "precedes"),
        (lambda value: value.update(caseCount=11), "case count"),
        (lambda value: value["cases"].pop(), "case count"),
        (lambda value: value["cases"].__setitem__(1, copy.deepcopy(value["cases"][0])), "identities"),
        (lambda value: value["cases"][0].update(provider="s3"), "provider"),
        (lambda value: value["cases"][0].update(injectionObserved=False), "injection"),
        (lambda value: value["cases"][0].update(expectedSurface={"kind": "success"}), "expected surface"),
        (lambda value: value["cases"][0].update(observedFindingCount=1), "finding fields"),
        (lambda value: value["cases"][0].update(cleanupResidueCount=-1), "numeric receipt"),
        (lambda value: value.update(operatorToken="secret"), "exact reviewed key set"),
    ],
)
def test_raw_report_mutations_fail_closed(mutation, expected):
    raw = report()
    junit = producer.junit_xml(raw)
    mutation(raw)
    with pytest.raises(importer.EvidenceImportError, match=expected):
        importer.import_evidence(raw, junit, FakeGit())


def test_secret_bearing_nested_key_is_rejected():
    raw = report()
    raw["cases"][0]["actualSurface"]["credentialDigest"] = "redacted"
    with pytest.raises(importer.EvidenceImportError, match="forbidden"):
        importer.import_evidence(raw, producer.junit_xml(report()), FakeGit())


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (lambda root: root.set("tests", "11"), "counts"),
        (lambda root: root.findall("testcase")[0].set("name", "unknown"), "identities"),
        (lambda root: root.remove(root.findall("testcase")[-1]), "identities"),
    ],
)
def test_junit_mutations_fail_closed(mutation, expected):
    import xml.etree.ElementTree as ET

    raw = report()
    root = ET.fromstring(producer.junit_xml(raw))
    mutation(root)
    with pytest.raises(importer.EvidenceImportError, match=expected):
        importer.import_evidence(raw, ET.tostring(root), FakeGit())


def test_junit_failure_count_must_match_case_failures():
    import xml.etree.ElementTree as ET

    raw = report()
    root = ET.fromstring(producer.junit_xml(raw))
    root.set("failures", "1")
    with pytest.raises(importer.EvidenceImportError, match="counts"):
        importer.import_evidence(raw, ET.tostring(root), FakeGit())


def test_junit_failure_identity_must_match_raw_finding():
    import xml.etree.ElementTree as ET

    def executor(identity: str) -> dict:
        value = matching_case(identity)
        if identity == producer.PG_FREE_CASES[0]:
            value["actualSurface"] = {"kind": "unexpected", "class": "InjectedError"}
            value["matched"] = False
            value["observedFindingCount"] = 1
        return value

    raw = report(executor)
    root = ET.fromstring(producer.junit_xml(raw))
    first = root.findall("testcase")[0]
    failure = first.find("failure")
    first.remove(failure)
    ET.SubElement(root.findall("testcase")[1], "failure", message="moved")
    with pytest.raises(importer.EvidenceImportError, match="failures differ"):
        importer.import_evidence(raw, ET.tostring(root), FakeGit())


def test_actual_surface_and_content_digest_are_closed():
    raw = report()
    raw["cases"][0]["actualSurface"] = {"kind": "problem", "code": "FAKE", "status": 500, "retryable": True}
    raw["cases"][0]["matched"] = False
    raw["cases"][0]["observedFindingCount"] = 1
    with pytest.raises(importer.EvidenceImportError, match="code is invalid"):
        importer.import_evidence(raw, producer.junit_xml(raw), FakeGit())
    raw = report()
    raw["cases"][0]["afterSha256"] = "short"
    with pytest.raises(importer.EvidenceImportError, match="digest"):
        importer.import_evidence(raw, producer.junit_xml(raw), FakeGit())


@pytest.mark.parametrize(
    "actual",
    [
        {"kind": "problem", "code": "STORE-0005", "status": 503, "retryable": True},
        {"kind": "osError", "errno": 30},
    ],
)
def test_well_formed_product_surfaces_outside_expected_table_are_findings(actual):
    raw = report()
    case = raw["cases"][0]
    case["actualSurface"] = actual
    case["matched"] = False
    case["observedFindingCount"] = 1
    raw["findingCount"] = 1
    evidence = importer.import_evidence(raw, producer.junit_xml(raw), FakeGit())
    assert evidence["verdict"] == "MEASURED_FAIL"
    assert evidence["metrics"]["classificationMismatchCount"] == 1


@pytest.mark.parametrize("field", ["partialResidueCount", "tempResidueCount", "quotaOvershootBytes"])
def test_nonzero_observed_residue_or_quota_is_measured_fail(field):
    raw = report()
    case = raw["cases"][0]
    case[field] = 1
    case["matched"] = False
    case["observedFindingCount"] = 1
    raw["findingCount"] = 1
    evidence = importer.import_evidence(raw, producer.junit_xml(raw), FakeGit())
    assert evidence["verdict"] == "MEASURED_FAIL"
    assert evidence["metrics"][field] == 1


def test_unobserved_numeric_receipts_remain_null_in_raw_and_are_not_counted_as_observed():
    raw = report()
    evidence = importer.import_evidence(raw, producer.junit_xml(raw), FakeGit())
    assert all(raw["cases"][0][name] is None for name in (
        "quotaOvershootBytes", "committedObjectLossCount", "partialResidueCount",
        "tempResidueCount", "cleanupResidueCount",
    ))
    assert set(evidence["metrics"]["observedCaseCountByMetric"].values()) == {0}
    assert all(evidence["metrics"][name] is None for name in (
        "quotaOvershootBytes", "committedObjectLossCount", "partialResidueCount",
        "tempResidueCount", "cleanupResidueCount",
    ))
