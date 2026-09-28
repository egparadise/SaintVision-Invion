from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from xml.etree import ElementTree

import pytest

from tools.import_ac11_composite_long_soak import (
    CASE_IDENTITIES,
    EvidenceImportError,
    HOSTED_STORAGE_SHA256,
    REGISTRY_BLOB,
    REGISTRY_PATH,
    STORAGE_PHYSICAL_SHA256,
    import_report,
)
from tools.run_ac11_composite_long_soak import (
    InventoryError,
    _inventory_revision,
    blocked_physical_report,
    build_dry_run_report,
    main,
    validate_g19_inventory,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "a" * 40
TREE = "b" * 40
DOC_COMMIT = "938ad3eb1c1664890c714f6ec86f409b7dab65b9"
DOC_PATH = "docs/vault/30_Development/S11_AC11_composite_long_soak_target_v0.md"
DOC_BLOB = "0bf74f90557a237b50ebdf571ed9e3dac89ea23b"


class FakeGit:
    def __init__(self, *, source: str = SOURCE, tree: str = TREE) -> None:
        self.source = source
        self.checkout_tree = tree
        self.registry = (ROOT / REGISTRY_PATH).read_text(encoding="utf-8")

    def tree(self, commit: str) -> str:
        assert commit == self.source
        return self.checkout_tree

    def blob(self, commit: str, path: str) -> str:
        if path == REGISTRY_PATH and commit == self.source:
            return REGISTRY_BLOB
        if path == DOC_PATH and commit in {DOC_COMMIT, self.source}:
            return DOC_BLOB
        raise AssertionError((commit, path))

    def show(self, commit: str, path: str) -> str:
        assert commit == self.source and path == REGISTRY_PATH
        return self.registry

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return ancestor == DOC_COMMIT and descendant == self.source


def _node(index: int, *, colocated: bool = False) -> dict:
    return {
        "nodeId": f"nod_worker_{index}",
        "hostname": f"worker-{index}",
        "dnsName": f"worker-{index}.internal.example",
        "ip": f"10.41.0.{10 + index}",
        "installationId": f"installation-{index}",
        "os": {
            "family": "Windows" if colocated else "Ubuntu",
            "version": "24.04",
            "containerRuntime": "Docker Engine 25",
        },
        "role": "cp-colocated" if colocated else "worker",
        "certificateSHA256": f"{index + 1:064x}",
        "profile": "lan-workspace-v1",
        "hardware": {
            "cpuModel": "fixture-cpu",
            "physicalCoreCount": 4,
            "logicalThreadCount": 8,
            "gpus": [],
            "storageDevice": "fixture-disk",
            "networkInterface": "fixture-nic",
        },
        "capacity": {
            "cpuMillis": 8000,
            "memoryBytes": 16_000_000_000,
            "gpuDevices": 0,
            "storageBytes": 100_000_000_000,
            "networkBitsPerSecond": 1_000_000_000,
        },
        "allowedResources": {
            "cpuMillis": 4000,
            "memoryBytes": 8_000_000_000,
            "gpuDevices": 0,
            "storageBytes": 50_000_000_000,
        },
        "allowedFolders": [f"/srv/saintvision/node-{index}"],
        "ntp": {"configured": True, "source": "time.internal", "maxSkewSeconds": 1},
        "storageRole": "none",
    }


def _inventory() -> dict:
    return {
        "schemaVersion": "s01-readiness-inventory:1",
        "topology": "cp-colocated-plus-four-workers",
        "hostnames": {
            "controlPlane": ["cp.internal.example"],
            "portal": ["portal.internal.example"],
            "idp": ["idp.internal.example"],
        },
        "nodes": [_node(0, colocated=True), *[_node(index) for index in range(1, 5)]],
    }


def _references(inventory: dict, *, source: str = SOURCE) -> tuple[dict, dict]:
    revision = _inventory_revision(inventory)
    storage = {
        "kind": "s11-storage-physical-reference",
        "referenceOnly": True,
        "targetId": "s11-storage-soak-physical-reference-v0",
        "verdict": "NOT_OBSERVED",
        "sourceHeadSha": source,
        "inventoryRevision": revision,
        "caseIdentitiesSha256": STORAGE_PHYSICAL_SHA256,
    }
    hosted = {
        "kind": "s11-storage-reference-evidence",
        "referenceOnly": True,
        "executionLayer": "hosted-minio-postgresql",
        "verdict": "MEASURED_PASS",
        "sourceHeadSha": source,
        "caseIdentitiesSha256": HOSTED_STORAGE_SHA256,
        "artifactSha256": "c" * 64,
        "artifactObservedSha256": "c" * 64,
        "artifactAvailable": True,
        "artifactExpiresAt": "2027-01-01T00:00:00Z",
        "runConclusion": "success",
    }
    return storage, hosted


def _report() -> tuple[dict, dict, dict]:
    inventory = _inventory()
    storage, hosted = _references(inventory)
    report = build_dry_run_report(
        inventory=inventory,
        source_run_id="hosted-reference-fixture",
        source_sha=SOURCE,
        checkout_tree_sha=TREE,
        generated_at="2026-09-29T00:00:00Z",
        storage=storage,
        hosted=hosted,
    )
    return report, storage, hosted


def test_dry_run_traverses_exact_cases_but_imports_as_not_observed() -> None:
    report, storage, hosted = _report()

    envelope = import_report(report, storage, hosted, FakeGit())

    assert [case["caseIdentity"] for case in report["cases"]] == list(CASE_IDENTITIES)
    assert all(case["status"] == "DECLARED_ONLY" for case in report["cases"])
    assert report["referenceOnly"] is True
    assert report["acceptanceClaim"] is False
    assert report["execution"] == {
        "driver": "synthetic-lan-pilot-v1",
        "mode": "plan-only",
        "planned": True,
        "simulationExecuted": False,
        "physicalActions": False,
        "declaredCaseCount": 14,
        "observedCaseCount": 0,
    }
    assert len(report["casePlans"]) == len(CASE_IDENTITIES)
    assert all(
        plan["plannedPhases"]
        == ["preflight", "observe-baseline", "simulate-fault", "observe-recovery", "cleanup"]
        and plan["executedPhases"] == []
        and plan["containerPlan"]
        == {
            "declaredTransitions": ["create", "start", "stop", "remove"],
            "executedTransitions": [],
        }
        and plan["observed"] is False
        and plan["physicalActions"] is False
        for plan in report["casePlans"]
    )
    assert envelope["verdict"] == "NOT_OBSERVED"
    assert envelope["referenceOnly"] is True
    assert envelope["acceptanceClaim"] is False
    assert "reference-only" in envelope["reason"]
    assert "targetRef" not in envelope


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda report: report.update(referenceOnly=False), "cannot claim"),
        (lambda report: report.update(acceptanceClaim=True), "cannot claim"),
        (lambda report: report.update(verdict="MEASURED_PASS"), "cannot claim"),
        (lambda report: report.update(operatorResources=["G-24"]), "operator resources"),
        (lambda report: report["environment"].update(topology="physical-five-node"), "environment"),
        (lambda report: report.update(checkoutTreeSha="c" * 40), "clean source tree"),
        (lambda report: report["cases"].pop(), "exact case universe"),
        (lambda report: report["casePlans"].pop(), "plans are incomplete"),
        (lambda report: report["casePlans"][0]["executedPhases"].append("preflight"), "plan is not exact"),
        (lambda report: report["execution"].update(physicalActions=True), "execution receipt"),
    ],
)
def test_dry_run_acceptance_and_identity_mutations_fail_closed(mutate, message: str) -> None:
    report, storage, hosted = _report()
    mutate(report)
    with pytest.raises(EvidenceImportError, match=message):
        import_report(report, storage, hosted, FakeGit())


def test_reference_substitution_fails_closed() -> None:
    report, storage, hosted = _report()
    hosted["artifactSha256"] = "d" * 64
    hosted["artifactObservedSha256"] = "d" * 64
    with pytest.raises(EvidenceImportError, match="hosted reference digest"):
        import_report(report, storage, hosted, FakeGit())


def test_storage_reference_must_remain_exact_even_when_its_digest_is_rebound() -> None:
    report, storage, hosted = _report()
    storage["verdict"] = "MEASURED_PASS"
    report["storageReferenceSha256"] = hashlib_sha(storage)
    with pytest.raises(EvidenceImportError, match="storage reference is not exact"):
        import_report(report, storage, hosted, FakeGit())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(topology="five-workers-dedicated-cp"),
        lambda value: value["nodes"].pop(),
        lambda value: value["nodes"][1].update(nodeId=value["nodes"][0]["nodeId"]),
        lambda value: value["nodes"][1].update(extra="unknown"),
        lambda value: value["nodes"][1].update(profile="lan-observe-v1"),
        lambda value: value["nodes"][1]["os"].update(family="Windows"),
    ],
)
def test_target_inventory_mismatch_is_rejected_before_execution(mutate) -> None:
    inventory = _inventory()
    mutate(inventory)
    with pytest.raises(InventoryError):
        validate_g19_inventory(inventory)


def test_storage_none_allows_no_folders_but_provider_requires_one() -> None:
    inventory = _inventory()
    inventory["nodes"][1]["allowedFolders"] = []
    validate_g19_inventory(inventory)
    inventory["nodes"][1]["storageRole"] = "provider"
    with pytest.raises(InventoryError, match="authorize at least one path"):
        validate_g19_inventory(inventory)


def test_inventory_revision_uses_utf8_canonical_json() -> None:
    inventory = _inventory()
    inventory["nodes"][1]["allowedFolders"] = ["/srv/측정"]
    assert _inventory_revision(inventory) == f"sha256:{hashlib_sha(inventory)}"


def test_physical_blocked_report_never_marks_execution_started() -> None:
    report = blocked_physical_report(
        source_run_id="physical-blocked-fixture",
        blocker="G-19",
        detail="inventory missing",
    )
    assert report["verdict"] == "BLOCKED_EXTERNAL"
    assert report["acceptanceClaim"] is False
    assert report["execution"] == {"started": False, "physicalActions": False}


def test_cli_dry_run_writes_reference_report_evidence_and_junit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "rev-parse", f"{source}^{{tree}}"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    def fake_git_value(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return source
        if args == ("status", "--porcelain"):
            return ""
        if args == ("rev-parse", f"{source}^{{tree}}"):
            return tree
        raise AssertionError(args)
    monkeypatch.setattr("tools.run_ac11_composite_long_soak._git_value", fake_git_value)
    monkeypatch.setattr(
        "tools.run_ac11_composite_long_soak.RepositoryGit",
        lambda: FakeGit(source=source, tree=tree),
    )
    inventory = _inventory()
    storage, hosted = _references(inventory, source=source)
    inventory_path = tmp_path / "inventory.json"
    storage_path = tmp_path / "storage.json"
    hosted_path = tmp_path / "hosted.json"
    report_path = tmp_path / "report.json"
    evidence_path = tmp_path / "evidence.json"
    junit_path = tmp_path / "junit.xml"
    for path, value in (
        (inventory_path, inventory),
        (storage_path, storage),
        (hosted_path, hosted),
    ):
        path.write_text(json.dumps(value), encoding="utf-8")

    exit_code = main(
        [
            "--mode", "dry-run",
            "--inventory", str(inventory_path),
            "--storage-reference", str(storage_path),
            "--hosted-reference", str(hosted_path),
            "--source-run-id", "cli-hosted-fixture",
            "--source-head-sha", source,
            "--report-output", str(report_path),
            "--evidence-output", str(evidence_path),
            "--junit", str(junit_path),
        ]
    )

    assert exit_code == 0
    assert json.loads(evidence_path.read_text(encoding="utf-8"))["verdict"] == "NOT_OBSERVED"
    suite = ElementTree.parse(junit_path).getroot()
    assert suite.attrib == {
        "name": "ac11-composite-long-soak-dry-run",
        "tests": "15",
        "failures": "0",
        "skipped": "15",
    }


def test_cli_physical_missing_inventory_stops_before_any_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "tools.run_ac11_composite_long_soak._git_value",
        lambda *_args: (_ for _ in ()).throw(AssertionError("physical preflight must not read Git")),
    )
    report_path = tmp_path / "report.json"
    evidence_path = tmp_path / "evidence.json"
    exit_code = main(
        [
            "--mode", "physical",
            "--source-run-id", "physical-preflight-fixture",
            "--report-output", str(report_path),
            "--evidence-output", str(evidence_path),
        ]
    )
    assert exit_code == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["blocker"] == "G-19"
    assert report["execution"] == {"started": False, "physicalActions": False}


def test_cli_physical_invalid_inventory_reports_g19_before_g24(tmp_path: Path) -> None:
    inventory = _inventory()
    inventory["nodes"].pop()
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    report_path = tmp_path / "report.json"
    evidence_path = tmp_path / "evidence.json"
    assert main(
        [
            "--mode", "physical",
            "--inventory", str(inventory_path),
            "--source-run-id", "physical-invalid-g19-fixture",
            "--report-output", str(report_path),
            "--evidence-output", str(evidence_path),
        ]
    ) == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["blocker"] == "G-19"
    assert report["execution"] == {"started": False, "physicalActions": False}


def test_cli_physical_valid_inventory_still_blocks_without_g24_adapter(tmp_path: Path) -> None:
    inventory_path = tmp_path / "inventory.json"
    report_path = tmp_path / "report.json"
    evidence_path = tmp_path / "evidence.json"
    inventory_path.write_text(json.dumps(_inventory()), encoding="utf-8")
    exit_code = main(
        [
            "--mode", "physical",
            "--inventory", str(inventory_path),
            "--source-run-id", "physical-g24-blocked-fixture",
            "--report-output", str(report_path),
            "--evidence-output", str(evidence_path),
        ]
    )
    assert exit_code == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["blocker"] == "G-24"
    assert report["execution"] == {"started": False, "physicalActions": False}


def test_cli_refuses_to_replace_inventory_before_running(tmp_path: Path) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps(_inventory()), encoding="utf-8")
    with pytest.raises(SystemExit):
        main(
            [
                "--mode", "dry-run",
                "--inventory", str(inventory_path),
                "--storage-reference", str(tmp_path / "storage.json"),
                "--hosted-reference", str(tmp_path / "hosted.json"),
                "--source-run-id", "protected-input-fixture",
                "--report-output", str(inventory_path),
                "--evidence-output", str(tmp_path / "evidence.json"),
            ]
        )


def test_cli_refuses_to_overwrite_an_existing_output(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text("preserve-me", encoding="utf-8")
    with pytest.raises(SystemExit):
        main(
            [
                "--mode", "physical",
                "--source-run-id", "existing-output-fixture",
                "--report-output", str(report_path),
                "--evidence-output", str(tmp_path / "evidence.json"),
            ]
        )
    assert report_path.read_text(encoding="utf-8") == "preserve-me"


def test_cli_dry_run_refuses_dirty_or_non_head_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory = _inventory()
    storage, hosted = _references(inventory)
    paths = {
        "inventory": tmp_path / "inventory.json",
        "storage": tmp_path / "storage.json",
        "hosted": tmp_path / "hosted.json",
    }
    for name, value in (("inventory", inventory), ("storage", storage), ("hosted", hosted)):
        paths[name].write_text(json.dumps(value), encoding="utf-8")

    def dirty_git(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return SOURCE
        if args == ("status", "--porcelain"):
            return " M tracked-file"
        raise AssertionError(args)

    monkeypatch.setattr("tools.run_ac11_composite_long_soak._git_value", dirty_git)
    report_path = tmp_path / "report.json"
    assert main(
        [
            "--mode", "dry-run",
            "--inventory", str(paths["inventory"]),
            "--storage-reference", str(paths["storage"]),
            "--hosted-reference", str(paths["hosted"]),
            "--source-run-id", "dirty-provenance-fixture",
            "--source-head-sha", SOURCE,
            "--report-output", str(report_path),
            "--evidence-output", str(tmp_path / "evidence.json"),
        ]
    ) == 2
    assert not report_path.exists()


def test_cli_dry_run_refuses_a_clean_non_head_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory = _inventory()
    storage, hosted = _references(inventory)
    paths = {
        "inventory": tmp_path / "inventory.json",
        "storage": tmp_path / "storage.json",
        "hosted": tmp_path / "hosted.json",
    }
    for name, value in (("inventory", inventory), ("storage", storage), ("hosted", hosted)):
        paths[name].write_text(json.dumps(value), encoding="utf-8")

    def clean_head(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return SOURCE
        if args == ("status", "--porcelain"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr("tools.run_ac11_composite_long_soak._git_value", clean_head)
    report_path = tmp_path / "report.json"
    assert main(
        [
            "--mode", "dry-run",
            "--inventory", str(paths["inventory"]),
            "--storage-reference", str(paths["storage"]),
            "--hosted-reference", str(paths["hosted"]),
            "--source-run-id", "non-head-provenance-fixture",
            "--source-head-sha", "c" * 40,
            "--report-output", str(report_path),
            "--evidence-output", str(tmp_path / "evidence.json"),
        ]
    ) == 2
    assert not report_path.exists()


def test_hosted_expiry_is_bound_to_dry_run_time() -> None:
    report, storage, hosted = _report()
    hosted["artifactExpiresAt"] = (
        datetime(2026, 8, 31, tzinfo=timezone.utc) + timedelta(days=1)
    ).isoformat().replace("+00:00", "Z")
    report["hostedReferenceSha256"] = hashlib_sha(hosted)
    with pytest.raises(EvidenceImportError, match="unavailable"):
        import_report(report, storage, hosted, FakeGit())


def hashlib_sha(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
