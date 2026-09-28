"""PG-free contract tests for the hosted S11-ST fault-evidence lane."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import import_s11_storage_failure_hosted_evidence as importer  # noqa: E402
import run_s11_storage_failure_hosted as producer  # noqa: E402


SOURCE = "a" * 40
TREE = "b" * 40
BLOBS = {
    producer.PRODUCER_PATH: "c" * 40,
    producer.RECOVERY_PROBE_PATH: "d" * 40,
    producer.HARNESS_PATH: "e" * 40,
}


class FakeGit:
    def tree(self, commit: str) -> str:
        assert commit == SOURCE
        return TREE

    def blob(self, commit: str, path: str) -> str:
        assert commit == SOURCE
        return BLOBS[path]


def compact_sha(values: tuple[str, ...]) -> str:
    return hashlib.sha256(
        json.dumps(list(values), ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def matching_case(identity: str) -> dict:
    attempted = 8 if identity.endswith("concurrent-8") else 1
    values = copy.deepcopy(producer.EXPECTED_INVARIANTS[identity])
    if identity.startswith("BAK-"):
        values["settingsSha256"] = "f" * 64
    return producer._receipt(
        identity,
        copy.deepcopy(producer.EXPECTED[identity]),
        attempted_count=attempted,
        **values,
    )


def environment() -> dict:
    return {
        "topology": "hosted-single-runner",
        "runnerOs": "linux",
        "runnerArch": "x86_64",
        "pythonVersion": "3.12.11",
        "postgresqlVersion": "16.10",
        "minioImageDigest": "sha256:" + "1" * 64,
        "archiveImageDigest": "sha256:" + "2" * 64,
        "minioExposure": "loopback-only",
        "archiveNetworkInternal": True,
        "archivePublishedPortCount": 0,
        "githubSecretCount": 0,
        "artifactRetentionDays": 30,
    }


def report(executor=matching_case) -> dict:
    return producer.build_report(
        executor,
        source_run_id="36399999999-1",
        source_head_sha=SOURCE,
        checkout_tree_sha=TREE,
        clean_checkout=True,
        producer_blob=BLOBS[producer.PRODUCER_PATH],
        recovery_probe_blob=BLOBS[producer.RECOVERY_PROBE_PATH],
        harness_blob=BLOBS[producer.HARNESS_PATH],
        started_at="2026-09-28T08:00:00Z",
        finished_at="2026-09-28T08:01:00Z",
        environment=environment(),
    )


def test_frozen_hosted_identity_hash_is_exact_and_within_universe():
    assert tuple(sorted(producer.HOSTED_CASES)) == producer.HOSTED_CASES
    assert compact_sha(producer.HOSTED_CASES) == producer.HOSTED_SHA256
    assert len(producer.HOSTED_CASES) == 10
    assert set(producer.HOSTED_CASES).issubset(producer.UNIVERSE_CASES)


def test_positive_report_imports_as_reference_only_pass():
    raw = report()
    evidence = importer.import_evidence(raw, producer.junit_xml(raw), FakeGit())
    assert evidence["referenceOnly"] is True
    assert evidence["axis"] is None and evidence["targetRef"] is None
    assert evidence["verdict"] == "MEASURED_PASS"
    assert evidence["caseIdentitiesSha256"] == producer.HOSTED_SHA256
    assert evidence["cleanup"] == {"performed": True, "residueCount": 0}
    assert evidence["metrics"] == {
        "attemptedCaseCount": 10,
        "classificationMismatchCount": 0,
        "falseSuccessCount": 0,
        "unexpectedErrorCount": 0,
        "quotaOvershootBytes": 0,
        "committedObjectLossCount": 0,
        "partialResidueCount": 0,
        "tempResidueCount": 0,
        "cleanupResidueCount": 0,
        "observedCaseCountByMetric": {
            "quotaOvershootBytes": 3,
            "committedObjectLossCount": 8,
            "partialResidueCount": 8,
            "tempResidueCount": 8,
            "cleanupResidueCount": 10,
        },
    }


def test_product_finding_is_preserved_as_measured_fail_without_invalidating_run():
    def executor(identity: str) -> dict:
        value = matching_case(identity)
        if identity == "OBJ-03/s3/metadata-digest":
            value["actualSurface"] = {"kind": "success"}
            value["matched"] = False
            value["observedFindingCount"] = 1
        return value

    raw = report(executor)
    evidence = importer.import_evidence(raw, producer.junit_xml(raw), FakeGit())
    assert raw["findingCount"] == 1
    assert evidence["verdict"] == "MEASURED_FAIL"
    assert evidence["metrics"]["falseSuccessCount"] == 1


def test_importer_cli_returns_zero_for_valid_measured_fail(tmp_path, monkeypatch):
    raw = report()
    raw["cases"][0]["actualSurface"] = {"kind": "unexpected", "class": "InjectedFinding"}
    raw["cases"][0]["matched"] = False
    raw["cases"][0]["observedFindingCount"] = 1
    raw["findingCount"] = 1
    report_path = tmp_path / "raw.json"
    junit_path = tmp_path / "raw.xml"
    output_path = tmp_path / "evidence.json"
    report_path.write_text(json.dumps(raw), encoding="utf-8")
    junit_path.write_bytes(producer.junit_xml(raw))
    monkeypatch.setattr(importer, "RepositoryGit", lambda _root: FakeGit())
    assert importer.main([
        "--report", str(report_path),
        "--junit", str(junit_path),
        "--output", str(output_path),
    ]) == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["verdict"] == "MEASURED_FAIL"


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda value: value.update(referenceOnly=False), "reference-only"),
        (lambda value: value.update(axis="long-soak"), "reference-only"),
        (lambda value: value.update(tierCaseIdentitiesSha256="0" * 64), "identity hash"),
        (lambda value: value.update(cleanCheckout=False), "clean checkout"),
        (lambda value: value.update(checkoutTreeSha="c" * 40), "checkout tree"),
        (lambda value: value["producerFile"].update(blob="0" * 40), "producerFile"),
        (lambda value: value["environment"].update(runnerOs="windows"), "runner OS"),
        (lambda value: value["environment"].update(minioImageDigest="latest"), "image digest"),
        (lambda value: value["cases"].pop(), "case count"),
        (lambda value: value["cases"].__setitem__(1, copy.deepcopy(value["cases"][0])), "identities"),
        (lambda value: value["cases"][0].update(injectionObserved=False), "injection"),
        (lambda value: value["cases"][0].update(attemptedCount=2), "attempt"),
        (lambda value: value["cases"][0].update(expectedSurface={"kind": "success"}), "expected surface"),
        (lambda value: value["cases"][0].update(settingsSha256=None), "settings receipt"),
        (lambda value: value["cases"][2].update(dbRowDelta=1), "finding fields"),
        (lambda value: value["cleanup"].update(residueCount=1), "cleanup receipt"),
        (lambda value: value.update(operatorCredential="redacted"), "forbidden"),
    ],
)
def test_raw_report_mutations_fail_closed(mutation, message):
    raw = report()
    junit = producer.junit_xml(raw)
    mutation(raw)
    with pytest.raises(importer.HostedEvidenceImportError, match=message):
        importer.import_evidence(raw, junit, FakeGit())


def test_unknown_well_formed_surface_is_a_measured_finding():
    raw = report()
    case = raw["cases"][5]
    case["actualSurface"] = {"kind": "problem", "code": "STORE-0001", "status": 503, "retryable": True}
    case["matched"] = False
    case["observedFindingCount"] = 1
    raw["findingCount"] = 1
    evidence = importer.import_evidence(raw, producer.junit_xml(raw), FakeGit())
    assert evidence["verdict"] == "MEASURED_FAIL"
    assert evidence["metrics"]["classificationMismatchCount"] == 1


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda root: root.set("tests", "9"), "identity or counts"),
        (lambda root: root.findall("testcase")[0].set("name", "unknown"), "identities"),
        (lambda root: root.findall("testcase")[0].append(ET.Element("skipped")), "result shape"),
    ],
)
def test_junit_mutations_fail_closed(mutation, message):
    raw = report()
    root = ET.fromstring(producer.junit_xml(raw))
    mutation(root)
    with pytest.raises(importer.HostedEvidenceImportError, match=message):
        importer.import_evidence(raw, ET.tostring(root), FakeGit())


def test_workflow_is_opt_in_exact_head_reference_only_and_non_cancelling():
    workflow = (ROOT / ".github/workflows/s11-storage-failure-hosted.yml").read_text(encoding="utf-8")
    assert "run-s11-storage" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "ref: ${{ env.SOURCE_HEAD_SHA }}" in workflow
    assert "fetch-depth: 0" in workflow
    assert "--publish 127.0.0.1:9000:9000" in workflow
    assert "secrets." not in workflow
    assert "referenceOnly" in workflow
    assert "axis'] is None" in workflow and "targetRef'] is None" in workflow


def test_fault_transport_preserves_real_reads_and_injects_only_one_put(monkeypatch):
    class Control:
        def __init__(self):
            self.calls = []

        def put(self, key, body, digest):
            self.calls.append((key, body, digest))
            return producer.HttpResponse(200, {}, b"")

    control = Control()
    transport = producer._FaultTransport(control, "safe-key", "success-partial", b"partial")
    monkeypatch.setattr(
        transport.delegate,
        "request",
        lambda method, url, headers, body: producer.HttpResponse(200, {"x": "y"}, b"read"),
    )
    result = transport.request("PUT", "ignored", {}, b"full")
    assert result.status == 200 and transport.observed is True
    assert control.calls[0][0] == "safe-key" and control.calls[0][1] == b"partial"
    assert transport.request("GET", "safe", {}, b"").body == b"read"
