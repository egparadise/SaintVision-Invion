"""PG-free contract and mutation tests for the AC-11 stage-1 aggregator."""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import aggregate_ac11_evidence as tool  # noqa: E402


SOURCE = "a" * 40
TREE = "b" * 40
TARGET = "c" * 40
BLOB = "d" * 40
REGISTRY_BLOB = tool.TARGET_REGISTRY_BLOB
NOW = datetime(2026, 9, 28, 3, 0, tzinfo=timezone.utc)
APPROVED_ALLOWLIST = json.loads(tool.DEFAULT_ALLOWLIST.read_text(encoding="utf-8"))
SCAN_ALLOWLIST = json.loads(
    (ROOT / tool.SCAN_ALLOWLIST_REPO_PATH).read_text(encoding="utf-8")
)
TOOL_BLOBS = {
    item["path"]: item["blob"]
    for item in [
        *tool.DEFINER_FILES,
        *tool.RLS_FILES,
        APPROVED_ALLOWLIST["secVf001"]["runner"],
        APPROVED_ALLOWLIST["secVf001"]["workflow"],
        APPROVED_ALLOWLIST["secVf001"]["nodeDependencyResolver"],
        *APPROVED_ALLOWLIST["secVf001"]["testFiles"],
    ]
}
TOOL_BLOBS[tool.ALLOWLIST_REPO_PATH] = tool.ALLOWLIST_BLOB
TOOL_BLOBS[tool.SCAN_ALLOWLIST_REPO_PATH] = tool.SCAN_ALLOWLIST_BLOB
for row in (
    SCAN_ALLOWLIST["producer"],
    SCAN_ALLOWLIST["workflow"],
    SCAN_ALLOWLIST["importer"],
):
    TOOL_BLOBS[row["path"]] = row["blob"]
for scanner in SCAN_ALLOWLIST["scanners"]:
    for path in scanner["scopePaths"]:
        TOOL_BLOBS[path] = BLOB
TARGET_CRITERIA = {
    tool.REQUIRED_TARGET_BY_AXIS.get(axis, "target-" + axis): (
        {} if axis == "security-critical-high-zero" else {"sampleCount": {"operator": "gte", "value": 1}}
    )
    for axis in tool.REQUIRED_AXES
}
TARGET_ENVIRONMENTS = {
    tool.REQUIRED_TARGET_BY_AXIS.get(axis, "target-" + axis): {"topology": "hosted-synthetic"}
    for axis in tool.REQUIRED_AXES
}
TARGET_AXES = {
    tool.REQUIRED_TARGET_BY_AXIS.get(axis, "target-" + axis): axis
    for axis in tool.REQUIRED_AXES
}


class FakeGit:
    ancestor = True
    target_blob = REGISTRY_BLOB
    source_blob = REGISTRY_BLOB
    source_tree = TREE

    def tree(self, commit: str) -> str:
        return self.source_tree

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return self.ancestor

    def blob(self, commit: str, path: str) -> str:
        if path == tool.TARGET_REGISTRY_PATH:
            return self.target_blob if commit == TARGET else self.source_blob
        if path.startswith("docs/targets/"):
            return BLOB
        assert commit == SOURCE and path in TOOL_BLOBS
        return TOOL_BLOBS[path]

    def show(self, commit: str, path: str) -> str:
        if path == tool.TARGET_REGISTRY_PATH:
            targets = []
            for target_id, criteria in TARGET_CRITERIA.items():
                axis = TARGET_AXES[target_id]
                targets.append({
                    "targetId": target_id,
                    "axis": axis,
                    "sourceDocument": {
                        "commit": TARGET,
                        "path": f"docs/targets/{axis}.md",
                        "blob": BLOB,
                    },
                    "criteria": criteria,
                    "requiredEnvironment": TARGET_ENVIRONMENTS[target_id],
                })
            return json.dumps({"schemaVersion": tool.SCHEMA_VERSION, "targets": targets})
        if path == tool.SCAN_ALLOWLIST_REPO_PATH:
            return json.dumps(SCAN_ALLOWLIST)
        if path == "requirements-core.txt":
            return "fastapi==0.141.1\npydantic==2.13.5\n"
        if path == "migrations/versions/0001_base.py":
            return 'revision = "0001_base"\ndown_revision = None\ndef downgrade():\n    raise RuntimeError("restore")\n'
        if path == "migrations/versions/0002_head.py":
            return 'revision = "0002_head"\ndown_revision = "0001_base"\ndef downgrade():\n    pass\n'
        raise AssertionError((commit, path))

    def list_paths(self, commit: str, prefix: str) -> list[str]:
        if prefix == "services/control-plane/src":
            return ["services/control-plane/src/inv/sample.py"]
        if prefix == "src/saintvision":
            return ["src/saintvision/sample.py"]
        assert prefix == "migrations/versions"
        return ["migrations/versions/0001_base.py", "migrations/versions/0002_head.py"]


@pytest.fixture
def allowlist() -> dict:
    return json.loads(tool.DEFAULT_ALLOWLIST.read_text(encoding="utf-8"))


def target(
    axis: str,
    criteria: dict | None = None,
    required_environment: dict | None = None,
) -> dict:
    actual = {} if axis == "security-critical-high-zero" else (
        criteria or {"sampleCount": {"operator": "gte", "value": 1}}
    )
    target_id = tool.REQUIRED_TARGET_BY_AXIS.get(axis, "target-" + axis)
    if actual != TARGET_CRITERIA.get(target_id):
        target_id += "--" + str(len(TARGET_CRITERIA))
        TARGET_CRITERIA[target_id] = copy.deepcopy(actual)
        TARGET_AXES[target_id] = axis
    TARGET_ENVIRONMENTS[target_id] = copy.deepcopy(
        required_environment or {"topology": "hosted-synthetic"}
    )
    return {
        "commit": TARGET,
        "path": tool.TARGET_REGISTRY_PATH,
        "blob": REGISTRY_BLOB,
        "targetId": target_id,
        "criteria": actual,
    }


def envelope(axis: str, verdict: str = "MEASURED_PASS") -> dict:
    value = {
        "axis": axis,
        "schemaVersion": "1.0.0",
        "runPurpose": "ac11-axis-evidence",
        "sourceRunId": "36370000000",
        "sourceHeadSha": SOURCE,
        "checkoutTreeSha": TREE,
        "artifactSha256": "e" * 64,
        "artifactObservedSha256": "e" * 64,
        "artifactAvailable": True,
        "artifactExpiresAt": "2030-01-01T00:00:00Z",
        "cleanCheckout": True,
        "runConclusion": "success",
        "environment": {
            "comparableGroup": "hosted-ubuntu-pg16",
            "topology": "hosted-synthetic",
        },
        "startedAt": "2026-09-28T01:00:00Z",
        "finishedAt": "2026-09-28T01:01:00Z",
        "targetRef": target(axis),
        "verdict": verdict,
        "observations": [
            {
                "metric": "sampleCount",
                "value": 1,
                "unit": "count",
                "n": 1,
                "successCount": 1,
                "failureCount": 0,
                "skipCount": 0,
                "errorsByClass": {},
            }
        ],
        "cleanup": {"residueCount": 0},
    }
    if axis == "migration-reversible-segment":
        value["reversibleSegment"] = {
            "startingRevision": "0002_head",
            "endingRevision": "0001_base",
            "reversibleTailCount": 1,
        }
    return value


class ZeroTailGit(FakeGit):
    def show(self, commit: str, path: str) -> str:
        if path == "migrations/versions/0002_head.py":
            return 'revision = "0002_head"\ndown_revision = "0001_base"\ndef downgrade():\n    raise RuntimeError("restore")\n'
        return super().show(commit, path)


def security_reports(allowlist: dict) -> list[dict]:
    vf = allowlist["secVf001"]
    vf_files = [vf["runner"], vf["workflow"], vf["nodeDependencyResolver"], *vf["testFiles"]]
    return [
        {
            "threatId": "SEC-DEF-001",
            "exitCode": 0,
            "toolFiles": copy.deepcopy(tool.DEFINER_FILES),
            "status": "matches_reviewed_policy",
            "unsafe": 0,
            "functions": [
                {"function": signature, "problems": []}
                for signature in allowlist["definerPolicySignatures"]
            ],
        },
        {
            "threatId": "SEC-RLS-001",
            "exitCode": 0,
            "toolFiles": copy.deepcopy(tool.RLS_FILES),
            "baselineAccepted": [
                {"role": row["role"], "table": row["table"], "rules": copy.deepcopy(row["rules"])}
                for row in allowlist["rlsAcceptedDispositions"]
            ],
            "verdict": "PASS",
            "violations": [],
            "accepted": [],
            "unmeasured": [],
            "roles": {"inv_app": {"present": True}},
            "ground_truth": {"public.projects": {"tenantScoped": True}},
        },
        {
            "threatId": "SEC-VF-001",
            "exitCode": 0,
            "toolFiles": copy.deepcopy(vf_files),
            "nodeIds": copy.deepcopy(vf["requiredNodeIds"]),
            "subprocessExitCode": 0,
            "evidenceStatus": "complete",
            "caseIdentitiesSha256": vf["requiredCaseIdentitiesSha256"],
            "tests": copy.deepcopy(vf["expectedTests"]),
        },
        security_scan_report(),
    ]


def security_scan_report() -> dict:
    scanner_specs = {row["id"]: row for row in SCAN_ALLOWLIST["scanners"]}
    payload = {
        "scannerVersions": {
            key: scanner_specs[key]["version"] for key in sorted(scanner_specs)
        },
        "scannerExitCodes": {"pip-audit": 0, "bandit": 0},
        "scanInputs": [
            {"path": path, "objectId": BLOB}
            for path in sorted(
                {path for row in scanner_specs.values() for path in row["scopePaths"]}
            )
        ],
        "auditedDependencies": [
            {"name": "fastapi", "version": "0.141.1"},
            {"name": "pydantic", "version": "2.13.5"},
        ],
        "scannedPythonFiles": [
            "services/control-plane/src/inv/sample.py",
            "src/saintvision/sample.py",
        ],
        "summaries": {
            "bandit": {
                "lowFindingCount": 0,
                "mediumFindingCount": 0,
                "highFindingCount": 0,
                "scannedFileCount": 2,
            },
            "pip-audit": {"dependencyCount": 2, "findingCount": 0},
        },
        "criticalHighFindings": [],
        "criticalCount": 0,
        "highCount": 0,
        "unallowlistedFindingIds": [],
        "expiredFindingIds": [],
        "staleAllowlistFindingIds": [],
        "severityMismatchFindingIds": [],
    }
    return {
        "schemaVersion": tool.SCHEMA_VERSION,
        "runPurpose": "s11-ac11-security-scan",
        "threatId": "SEC-SCAN-001",
        "sourceRunId": "36440000000",
        "sourceHeadSha": SOURCE,
        "checkoutTreeSha": TREE,
        "cleanCheckout": True,
        "environment": {
            "runnerImage": "Linux-X64",
            "topology": "hosted",
            "evidenceClass": "security-tools-v0",
            "credentialsRequired": False,
            "externalServicesRequired": True,
        },
        "startedAt": "2026-09-28T02:00:00Z",
        "finishedAt": "2026-09-28T02:01:00Z",
        "reportAvailable": True,
        "status": "complete",
        "allowlist": {
            "path": tool.SCAN_ALLOWLIST_REPO_PATH,
            "blob": tool.SCAN_ALLOWLIST_BLOB,
        },
        "toolFiles": [
            copy.deepcopy(SCAN_ALLOWLIST["producer"]),
            copy.deepcopy(SCAN_ALLOWLIST["workflow"]),
            copy.deepcopy(SCAN_ALLOWLIST["importer"]),
        ],
        "scanArtifact": {
            "repository": "egparadise/SaintVision-Invion",
            "workflowPath": ".github/workflows/ac11-security-scan.yml",
            "runId": "36440000000",
            "artifactId": "10970000000",
            "artifactName": f"s11-ac11-security-{SOURCE}",
            "digest": "9" * 64,
            "observedDigest": "9" * 64,
            "expiresAt": "2030-01-01T00:00:00Z",
            "runConclusion": "success",
            "producerReportSha256": "8" * 64,
            "junitSha256": "7" * 64,
        },
        "payloadSha256": tool._canonical_sha256(payload),
        "payload": payload,
        "verdict": "MEASURED_PASS",
        "failureClass": "NONE",
    }


def security_envelope(allowlist: dict) -> dict:
    value = envelope("security-critical-high-zero")
    value["observations"] = security_reports(allowlist)
    value["targetRef"] = target("security-critical-high-zero", {})
    # The envelope names the importer that wrote it, bound to the source tree (#313 F-R3).
    value["importerFile"] = copy.deepcopy(SCAN_ALLOWLIST["importer"])
    return value


def rls_report(allowlist: dict, exit_code: int = 0) -> dict:
    value = {
        "exitCode": exit_code,
        "toolFiles": copy.deepcopy(tool.RLS_FILES),
        "baselineAccepted": [
            {"role": row["role"], "table": row["table"], "rules": copy.deepcopy(row["rules"])}
            for row in allowlist["rlsAcceptedDispositions"]
        ],
        "verdict": "PASS",
        "violations": [],
        "accepted": [],
        "unmeasured": [],
        "roles": {"inv_app": {"present": True}},
        "ground_truth": {"public.projects": {"tenantScoped": True}},
    }
    return value


def manifest(allowlist: dict) -> dict:
    axes = []
    for axis in tool.REQUIRED_AXES:
        axes.append(security_envelope(allowlist) if axis == "security-critical-high-zero" else envelope(axis))
    return {
        "schemaVersion": "1.0.0",
        "runPurpose": "ac11-release-gate",
        "releaseSha": SOURCE,
        "axes": axes,
    }


def axis_result(value: dict, allowlist: dict, git: FakeGit | None = None) -> tool.AxisResult:
    return tool.evaluate_axis(value, git or FakeGit(), allowlist, NOW)


def test_all_eight_recomputed_pass_is_the_only_done_state(allowlist):
    result = tool.aggregate(manifest(allowlist), FakeGit(), allowlist, NOW)
    assert result["verdict"] == "MEASURED_PASS"
    assert result["done"] is True
    assert len(result["axes"]) == 8


def test_missing_axis_is_invalid_and_not_done(allowlist):
    value = manifest(allowlist)
    value["axes"].pop()
    result = tool.aggregate(value, FakeGit(), allowlist, NOW)
    assert result["verdict"] == "INVALID_RUN" and result["done"] is False
    assert "missing required axes" in result["reasons"][0]


def test_unknown_pass_string_is_invalid(allowlist):
    value = envelope(tool.REQUIRED_AXES[0], "PASS")
    assert axis_result(value, allowlist).verdict is tool.Verdict.INVALID_RUN


def test_all_not_applicable_never_opens_gate(allowlist):
    value = manifest(allowlist)
    for item in value["axes"]:
        item["verdict"] = "NOT_APPLICABLE"
        item["observations"] = []
        item["structuralException"] = {"reason": "no-reversible-tail", "reversibleTailCount": 0}
    result = tool.aggregate(value, FakeGit(), allowlist, NOW)
    assert result["done"] is False
    assert result["verdict"] == "INVALID_RUN"


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda row: row.update(cleanCheckout=False), "cleanCheckout"),
        (lambda row: row.update(runConclusion="cancelled"), "cancelled"),
        (lambda row: row.update(checkoutTreeSha="f" * 40), "checkoutTreeSha"),
        (lambda row: row.update(artifactAvailable=False), "unavailable"),
        (lambda row: row.update(artifactObservedSha256="f" * 64), "digest"),
        (lambda row: row.update(artifactExpiresAt="2020-01-01T00:00:00Z"), "expired"),
        (lambda row: row.update(finishedAt="2026-09-28T00:59:00Z"), "precedes"),
    ],
)
def test_invalid_envelope_cannot_be_relabelled_pass(allowlist, mutation, reason):
    value = envelope(tool.REQUIRED_AXES[1])
    mutation(value)
    result = axis_result(value, allowlist)
    assert result.verdict is tool.Verdict.INVALID_RUN
    assert reason in result.reasons[0]


def test_pre_schema_evidence_is_reference_only(allowlist):
    value = envelope(tool.REQUIRED_AXES[1])
    value["schemaVersion"] = "0.9.0"
    value.pop("checkoutTreeSha")
    value.pop("cleanCheckout")
    result = axis_result(value, allowlist)
    assert result.verdict is tool.Verdict.NOT_OBSERVED
    assert result.reference_only is True


def test_target_must_be_ancestor_and_same_blob(allowlist):
    git = FakeGit()
    git.ancestor = False
    assert axis_result(envelope(tool.REQUIRED_AXES[1]), allowlist, git).verdict is tool.Verdict.INVALID_RUN
    git.ancestor = True
    git.source_blob = "f" * 40
    assert axis_result(envelope(tool.REQUIRED_AXES[1]), allowlist, git).verdict is tool.Verdict.INVALID_RUN


def test_registry_blob_is_pinned_not_merely_stable_on_branch(allowlist):
    loose_blob = "9" * 40

    class LooseRegistryGit(FakeGit):
        target_blob = loose_blob
        source_blob = loose_blob

    value = envelope(tool.REQUIRED_AXES[1])
    value["targetRef"]["blob"] = loose_blob
    assert axis_result(value, allowlist, LooseRegistryGit()).verdict is tool.Verdict.INVALID_RUN


def test_release_sha_binds_every_axis_to_one_release(allowlist):
    value = manifest(allowlist)
    value["axes"][0]["sourceHeadSha"] = "f" * 40
    result = tool.aggregate(value, FakeGit(), allowlist, NOW)
    assert result["verdict"] == "INVALID_RUN"
    assert "sourceHeadSha differs from releaseSha" in result["reasons"][0]

    missing = manifest(allowlist)
    missing.pop("releaseSha")
    result = tool.aggregate(missing, FakeGit(), allowlist, NOW)
    assert result["verdict"] == "INVALID_RUN"
    assert "releaseSha" in result["reasons"][0]


@pytest.mark.parametrize(
    ("axis", "required_environment", "wrong_environment"),
    [
        (
            "physical-five-node-ac05-placement-load",
            {"topology": "physical-five-node", "eligibleNodeCount": 4, "excludedNodeCount": 1},
            {"topology": "hosted-synthetic", "eligibleNodeCount": 0, "excludedNodeCount": 0},
        ),
        (
            "actual-pitr-rpo-rto-retention",
            {
                "topology": "physical",
                "failureDomain": "separate",
                "archiveKind": "operational",
                "sameHost": False,
            },
            {
                "topology": "same-host",
                "failureDomain": "same",
                "archiveKind": "logical-dump",
                "sameHost": True,
            },
        ),
    ],
)
def test_target_environment_class_rejects_synthetic_substitution(
    axis, required_environment, wrong_environment, allowlist
):
    value = envelope(axis)
    value["targetRef"] = target(
        axis,
        {"sampleCount": {"operator": "gte", "value": 1}},
        required_environment,
    )
    value["environment"] = {"comparableGroup": "untrusted", **wrong_environment}
    result = axis_result(value, allowlist)
    assert result.verdict is tool.Verdict.INVALID_RUN
    assert "registered requirement" in result.reasons[0]


def test_repository_registry_targets_match_current_tree_and_pitr_is_weekly_registered():
    registry_path = ROOT / tool.TARGET_REGISTRY_PATH
    content = registry_path.read_bytes()
    actual_blob = __import__("hashlib").sha1(
        f"blob {len(content)}\0".encode() + content
    ).hexdigest()
    assert actual_blob == tool.TARGET_REGISTRY_BLOB

    registry = json.loads(content.decode("utf-8"))
    git = tool.RepositoryGit(ROOT)
    for registered in registry["targets"]:
        document = registered["sourceDocument"]
        assert git.blob("HEAD", document["path"]) == document["blob"]

    assert all(row["targetId"] != "s11-actual-pitr-v0" for row in registry["targets"])
    pitr = next(
        row
        for row in registry["targets"]
        if row["targetId"] == "s11-st-actual-pitr-archive-failure-v0"
    )
    assert pitr["criteria"]["consecutiveWeeklyRestoreSmokeWeeks"] == {
        "operator": "gte",
        "value": 2,
    }
    assert pitr["criteria"]["maxRestoreSmokeGapDays"] == {"operator": "lte", "value": 7}
    assert pitr["criteria"]["recoveryAfterWalArchiveFaultPassCount"] == {
        "operator": "gte",
        "value": 1,
    }
    restore = next(
        row
        for row in registry["targets"]
        if row["targetId"] == "s11-irreversible-restore-forward-v0"
    )
    assert restore["criteria"]["negativeFixturePassCount"] == {
        "operator": "eq",
        "value": 4,
    }
    reversible = next(
        row
        for row in registry["targets"]
        if row["targetId"] == "s11-migration-reversible-roundtrip-v1"
    )
    assert reversible["axis"] == "migration-reversible-segment"
    assert reversible["criteria"] == {
        "catalogMismatchCount": {"operator": "eq", "value": 0},
        "reversibleRoundtripPassCount": {"operator": "eq", "value": 1},
        "sentinelMismatchCount": {"operator": "eq", "value": 0},
    }


def test_required_target_map_rejects_old_pitr_target(allowlist):
    value = envelope("actual-pitr-rpo-rto-retention")
    value["targetRef"]["targetId"] = "s11-actual-pitr-v0"
    result = axis_result(value, allowlist)
    assert result.verdict is tool.Verdict.INVALID_RUN
    assert "required target" in result.reasons[0]


def test_empty_n_and_bad_failure_denominator_are_invalid(allowlist):
    empty = envelope(tool.REQUIRED_AXES[1])
    empty["observations"] = []
    assert axis_result(empty, allowlist).verdict is tool.Verdict.INVALID_RUN
    zero = envelope(tool.REQUIRED_AXES[1])
    zero["observations"][0].update(n=0, successCount=0)
    assert axis_result(zero, allowlist).verdict is tool.Verdict.INVALID_RUN
    mismatch = envelope(tool.REQUIRED_AXES[1])
    mismatch["observations"][0].update(successCount=0, failureCount=1, errorsByClass={"57014": 0})
    assert axis_result(mismatch, allowlist).verdict is tool.Verdict.INVALID_RUN


def test_zero_expected_count_value_must_equal_failure_count(allowlist):
    value = envelope(tool.REQUIRED_AXES[1], "MEASURED_PASS")
    value["targetRef"] = target(
        tool.REQUIRED_AXES[1],
        {"cleanupResidueCount": {"operator": "eq", "value": 0}},
    )
    value["observations"][0].update(
        metric="cleanupResidueCount",
        value=0,
        n=1,
        successCount=0,
        failureCount=1,
        skipCount=0,
        errorsByClass={"residue": 1},
    )
    assert axis_result(value, allowlist).verdict is tool.Verdict.INVALID_RUN


def test_target_violation_is_fail_but_false_pass_is_invalid(allowlist):
    value = envelope(tool.REQUIRED_AXES[1], "MEASURED_FAIL")
    value["observations"][0]["value"] = 0
    assert axis_result(value, allowlist).verdict is tool.Verdict.MEASURED_FAIL
    value["verdict"] = "MEASURED_PASS"
    assert axis_result(value, allowlist).verdict is tool.Verdict.INVALID_RUN


def test_p95_success_only_population_is_invalid(allowlist):
    value = envelope(tool.REQUIRED_AXES[3])
    value["targetRef"] = target(tool.REQUIRED_AXES[3], {"requestP95Ms": {"operator": "lte", "value": 2000}})
    value["observations"][0].update(metric="requestP95Ms", value=1200, population="success")
    assert axis_result(value, allowlist).verdict is tool.Verdict.INVALID_RUN


@pytest.mark.parametrize(
    ("problem", "expected"),
    [
        ("runtime_role_bypasses_rls", tool.Verdict.MEASURED_FAIL),
        ("definition_differs_from_policy", tool.Verdict.MEASURED_FAIL),
        ("migration_revision_mismatch", tool.Verdict.INVALID_RUN),
        ("runtime_role_missing", tool.Verdict.NOT_OBSERVED),
        ("unknown_problem", tool.Verdict.INVALID_RUN),
    ],
)
def test_definer_problem_mapping_is_fail_closed(problem, expected, allowlist):
    functions = [
        {"function": signature, "problems": [problem] if index == 0 else []}
        for index, signature in enumerate(allowlist["definerPolicySignatures"])
    ]
    report = {
        "exitCode": 1,
        "toolFiles": copy.deepcopy(tool.DEFINER_FILES),
        "status": "requires_review",
        "unsafe": 1,
        "functions": functions,
    }
    assert tool.evaluate_definer(report, allowlist) is expected


@pytest.mark.parametrize(
    ("exit_code", "expected"),
    [(0, tool.Verdict.MEASURED_PASS), (2, tool.Verdict.NOT_OBSERVED), (7, tool.Verdict.INVALID_RUN)],
)
def test_definer_exit_mapping(exit_code, expected, allowlist):
    report = {
        "exitCode": exit_code,
        "toolFiles": copy.deepcopy(tool.DEFINER_FILES),
        "status": "unavailable" if exit_code == 2 else "matches_reviewed_policy",
        "unsafe": 0,
        "functions": [
            {"function": signature, "problems": []}
            for signature in allowlist["definerPolicySignatures"]
        ],
    }
    assert tool.evaluate_definer(report, allowlist) is expected


@pytest.mark.parametrize("rule", sorted(tool.RLS_RULES))
def test_each_unaccepted_rls_rule_is_critical(rule, allowlist):
    report = rls_report(allowlist, 1)
    report.update(verdict="VIOLATIONS", violations=[{"rule": rule, "role": "unlisted", "table": "public.secret"}])
    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.MEASURED_FAIL


def test_rls_accepted_expiry_and_baseline_exact_match(allowlist):
    report = rls_report(allowlist)
    report["accepted"] = [{"rule": "E2", "role": "inv_app", "table": "public.tenants"}]
    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.MEASURED_PASS
    expired = datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert tool.evaluate_rls(report, allowlist, expired) is tool.Verdict.MEASURED_FAIL
    assert tool.evaluate_rls(report, allowlist, expired) is tool.Verdict.MEASURED_FAIL
    report["baselineAccepted"] = []
    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.INVALID_RUN


@pytest.mark.parametrize(
    ("exit_code", "expected"),
    [(2, tool.Verdict.NOT_OBSERVED), (3, tool.Verdict.NOT_OBSERVED), (9, tool.Verdict.INVALID_RUN)],
)
def test_rls_unmeasured_and_unknown_exit_mapping(exit_code, expected, allowlist):
    report = rls_report(allowlist, exit_code)
    if exit_code == 3:
        report.update(verdict="UNMEASURED", unmeasured=[{"rule": "E4", "role": "inv_app", "table": "public.projects"}])
    assert tool.evaluate_rls(report, allowlist, NOW) is expected


OWNER_FP = "9b74c9897bac770ffc029102a200c5de"
OTHER_FP = "0cc175b9c0f1b6a831c399e269772661"
OWNER_VERIFIED_IDENTITY = {
    "method": "owner-verified-key", "columns": ["tenant_id", "event_id"],
    "ownerDistinctness": {"rows": 2, "distinct": 2, "nullRows": 0},
    "owner_a": {"rows": 2, "fp": OWNER_FP}, "role_a": {"rows": 2, "fp": OWNER_FP},
    "match": True,
}


def identity_roles(identity: dict, role: str = "inv_cancel_bridge_owner",
                   table: str = "public.audit_events") -> dict:
    return {role: {"present": True, "tables": {table: {"visible": {"identity": identity}}}}}


@pytest.mark.parametrize(
    ("roles", "expected"),
    [
        pytest.param(
            identity_roles(OWNER_VERIFIED_IDENTITY),
            tool.Verdict.MEASURED_PASS,
            id="registered-and-measured",
        ),
        pytest.param(
            identity_roles({**OWNER_VERIFIED_IDENTITY,
                            "ownerDistinctness": {"rows": 0, "distinct": 0, "nullRows": 0}}),
            tool.Verdict.INVALID_RUN,
            id="vacuous-zero-rows",
        ),
        pytest.param(
            identity_roles({**OWNER_VERIFIED_IDENTITY,
                            "ownerDistinctness": {"rows": 2, "distinct": 1, "nullRows": 0}}),
            tool.Verdict.INVALID_RUN,
            id="repeated-key",
        ),
        pytest.param(
            identity_roles({**OWNER_VERIFIED_IDENTITY,
                            "ownerDistinctness": {"rows": 2, "distinct": 2, "nullRows": 1}}),
            tool.Verdict.INVALID_RUN,
            id="null-bearing-key",
        ),
        pytest.param(
            identity_roles({**OWNER_VERIFIED_IDENTITY, "columns": ["tenant_id"]}),
            tool.Verdict.INVALID_RUN,
            id="unregistered-columns",
        ),
        pytest.param(
            identity_roles(OWNER_VERIFIED_IDENTITY, role="inv_app", table="public.projects"),
            tool.Verdict.INVALID_RUN,
            id="unregistered-pair",
        ),
        # #322 r2 F-R3: the report's own observations are recomputed, so these synthesised
        # reports cannot claim a pass.  Each one changes a single thing.
        pytest.param(
            identity_roles({**OWNER_VERIFIED_IDENTITY,
                            "role_a": {"rows": 2, "fp": OTHER_FP}, "match": False}),
            tool.Verdict.INVALID_RUN,
            id="mismatch-claimed-as-pass",
        ),
        pytest.param(
            identity_roles({**OWNER_VERIFIED_IDENTITY, "role_a": {"rows": 2, "fp": OTHER_FP}}),
            tool.Verdict.INVALID_RUN,
            id="match-true-but-fingerprints-differ",
        ),
        pytest.param(
            identity_roles({**OWNER_VERIFIED_IDENTITY, "match": False}),
            tool.Verdict.INVALID_RUN,
            id="match-false-but-fingerprints-equal",
        ),
        pytest.param(
            identity_roles({**OWNER_VERIFIED_IDENTITY, "owner_a": {"rows": 0, "fp": OWNER_FP}}),
            tool.Verdict.INVALID_RUN,
            id="owner-observed-zero-rows",
        ),
        pytest.param(
            identity_roles({**OWNER_VERIFIED_IDENTITY, "role_a": {"rows": 2, "fp": "aa"}}),
            tool.Verdict.INVALID_RUN,
            id="fingerprint-is-not-a-digest",
        ),
        pytest.param(
            identity_roles({k: v for k, v in OWNER_VERIFIED_IDENTITY.items() if k != "role_a"}),
            tool.Verdict.INVALID_RUN,
            id="no-role-observation",
        ),
    ],
)
def test_an_owner_verified_key_identity_must_be_registered_and_non_vacuous(
    roles, expected, allowlist
):
    """The evaluator asks the readable-key questions itself (#322 r2).

    The collector refuses these cases too, but a report is evidence about a tree rather than a
    promise from the tool that wrote it: an identity measured over zero rows, a repeated or
    NULL-bearing key, or a pair the reviewed scope does not list makes the report inadmissible
    here as well -- otherwise one pinned-but-patched collector would be enough to turn a vacuous
    comparison into a PASS axis.
    """

    report = rls_report(allowlist)
    report["roles"] = copy.deepcopy(roles)
    assert tool.evaluate_rls(report, allowlist, NOW) is expected


def test_a_recomputed_identity_mismatch_cannot_hide_in_an_unmeasured_report(allowlist):
    """A measured mismatch is a violation, not an absence of observation (#322 r2 F-R3).

    An UNMEASURED report reads as "nothing was observed to be wrong", so a report carrying a
    recomputed ``match: false`` under exit 3 is refused rather than passed through as
    NOT_OBSERVED -- otherwise a forger could downgrade a violation into a quiet gap.
    """

    mismatch = identity_roles(
        {**OWNER_VERIFIED_IDENTITY, "role_a": {"rows": 2, "fp": OTHER_FP}, "match": False}
    )
    report = rls_report(allowlist, 3)
    report.update(
        verdict="UNMEASURED",
        unmeasured=[{"rule": "E4", "role": "inv_app", "table": "public.projects"}],
        roles=copy.deepcopy(mismatch),
    )
    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.INVALID_RUN

    # The same observation reported honestly is a measured failure, which is admissible.
    violation = rls_report(allowlist, 1)
    violation.update(
        verdict="VIOLATIONS",
        violations=[{"rule": "E4", "role": "inv_cancel_bridge_owner",
                     "table": "public.audit_events"}],
        roles=copy.deepcopy(mismatch),
    )
    assert tool.evaluate_rls(violation, allowlist, NOW) is tool.Verdict.MEASURED_FAIL


def test_security_requires_all_registered_reports_and_exact_vf_inventory(allowlist):
    missing = security_envelope(allowlist)
    missing["verdict"] = "NOT_OBSERVED"
    missing["observations"].pop()
    assert axis_result(missing, allowlist).verdict is tool.Verdict.NOT_OBSERVED
    false_pass = copy.deepcopy(missing)
    false_pass["verdict"] = "MEASURED_PASS"
    assert axis_result(false_pass, allowlist).verdict is tool.Verdict.INVALID_RUN
    wrong_nodes = security_envelope(allowlist)
    wrong_nodes["observations"][2]["nodeIds"].pop()
    assert axis_result(wrong_nodes, allowlist).verdict is tool.Verdict.INVALID_RUN


def test_security_report_cannot_claim_reviewed_blob_when_source_tree_differs(allowlist):
    git = FakeGit()
    original = TOOL_BLOBS["tools/check_definer_functions.py"]
    TOOL_BLOBS["tools/check_definer_functions.py"] = "0" * 40
    try:
        assert axis_result(security_envelope(allowlist), allowlist, git).verdict is tool.Verdict.INVALID_RUN
    finally:
        TOOL_BLOBS["tools/check_definer_functions.py"] = original


def test_security_scan_missing_or_payload_sha_mismatch_is_not_observed(allowlist):
    missing = security_envelope(allowlist)
    missing["observations"] = [
        row for row in missing["observations"] if row["threatId"] != "SEC-SCAN-001"
    ]
    missing["verdict"] = "NOT_OBSERVED"
    assert axis_result(missing, allowlist).verdict is tool.Verdict.NOT_OBSERVED

    mismatch = security_envelope(allowlist)
    scan = mismatch["observations"][3]
    scan["payload"]["highCount"] = 1
    mismatch["verdict"] = "NOT_OBSERVED"
    assert axis_result(mismatch, allowlist).verdict is tool.Verdict.NOT_OBSERVED


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda row: row.update(sourceHeadSha="f" * 40), tool.Verdict.NOT_OBSERVED),
        (lambda row: row.update(checkoutTreeSha="f" * 40), tool.Verdict.NOT_OBSERVED),
        (lambda row: row.update(cleanCheckout=False), tool.Verdict.NOT_OBSERVED),
        (lambda row: row.pop("sourceRunId"), tool.Verdict.INVALID_RUN),
        (
            lambda row: row["environment"].update(credentialsRequired=True),
            tool.Verdict.INVALID_RUN,
        ),
        (
            lambda row: row.update(finishedAt="2026-07-01T00:00:00Z"),
            tool.Verdict.NOT_OBSERVED,
        ),
        (
            lambda row: row["scanArtifact"].update(observedDigest="6" * 64),
            tool.Verdict.NOT_OBSERVED,
        ),
        (
            lambda row: row["scanArtifact"].update(expiresAt="2020-01-01T00:00:00Z"),
            tool.Verdict.NOT_OBSERVED,
        ),
        (
            lambda row: row["scanArtifact"].update(
                artifactName=f"s11-ac11-security-{'f' * 40}"
            ),
            tool.Verdict.NOT_OBSERVED,
        ),
        (
            lambda row: row["scanArtifact"].update(runConclusion="failure"),
            tool.Verdict.NOT_OBSERVED,
        ),
        (
            lambda row: row["environment"].update(topology="physical"),
            tool.Verdict.INVALID_RUN,
        ),
        (
            lambda row: row.update(finishedAt="2026-09-28T01:59:59Z"),
            tool.Verdict.NOT_OBSERVED,
        ),
    ],
)
def test_security_scan_run_source_and_artifact_provenance_is_fail_closed(
    mutation, expected
):
    report = security_scan_report()
    mutation(report)
    assert (
        tool.evaluate_security_scan(report, SCAN_ALLOWLIST, NOW, FakeGit(), SOURCE)
        is expected
    )


@pytest.mark.parametrize("forgery", ["scanned-file", "audited-dependency"])
def test_security_scan_resigned_payload_cannot_hide_registered_input(forgery):
    report = security_scan_report()
    if forgery == "scanned-file":
        report["payload"]["scannedPythonFiles"].pop()
        report["payload"]["summaries"]["bandit"]["scannedFileCount"] -= 1
    else:
        report["payload"]["auditedDependencies"].pop()
        report["payload"]["summaries"]["pip-audit"]["dependencyCount"] -= 1
    report["payloadSha256"] = tool._canonical_sha256(report["payload"])
    assert (
        tool.evaluate_security_scan(report, SCAN_ALLOWLIST, NOW, FakeGit(), SOURCE)
        is tool.Verdict.INVALID_RUN
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row["payload"]["scannerVersions"].update(bandit="0.0.0"),
        lambda row: row["payload"]["scannerExitCodes"].update(bandit=2),
        lambda row: row.update(runPurpose="unregistered"),
        lambda row: row["allowlist"].update(blob="0" * 40),
        lambda row: row["payload"]["summaries"]["pip-audit"].update(dependencyCount=1),
        lambda row: row["payload"].update(scannedPythonFiles=[]),
        lambda row: row.update(failureClass="STALE_ALLOWLIST"),
    ],
)
def test_security_scan_registered_shape_guards_are_mutation_sensitive(mutation):
    report = security_scan_report()
    mutation(report)
    report["payloadSha256"] = tool._canonical_sha256(report["payload"])
    assert (
        tool.evaluate_security_scan(report, SCAN_ALLOWLIST, NOW, FakeGit(), SOURCE)
        is tool.Verdict.INVALID_RUN
    )


def test_security_scan_unavailable_report_is_not_observed():
    report = security_scan_report()
    report.update(reportAvailable=False, status="unavailable", verdict="NOT_OBSERVED")
    assert (
        tool.evaluate_security_scan(report, SCAN_ALLOWLIST, NOW, FakeGit(), SOURCE)
        is tool.Verdict.NOT_OBSERVED
    )


def test_security_scan_unallowlisted_high_is_measured_fail(allowlist):
    value = security_envelope(allowlist)
    scan = value["observations"][3]
    finding = {
        "findingId": "bandit:B999:services/control-plane/src/inv/example.py:7",
        "scanner": "bandit",
        "severity": "HIGH",
        "ruleId": "B999",
        "component": "services/control-plane/src/inv/example.py",
        "location": "7",
    }
    scan["payload"]["criticalHighFindings"] = [finding]
    scan["payload"]["highCount"] = 1
    scan["payload"]["summaries"]["bandit"]["highFindingCount"] = 1
    scan["payload"]["scannerExitCodes"]["bandit"] = 1
    scan["payload"]["unallowlistedFindingIds"] = [finding["findingId"]]
    scan["payloadSha256"] = tool._canonical_sha256(scan["payload"])
    scan["verdict"] = "MEASURED_FAIL"
    scan["failureClass"] = "UNALLOWLISTED_CRITICAL_HIGH"
    value["verdict"] = "MEASURED_FAIL"
    assert axis_result(value, allowlist).verdict is tool.Verdict.MEASURED_FAIL


def test_security_scan_reviewed_exception_requires_reason_and_unexpired_exact_identity():
    finding = {
        "findingId": "pip-audit:example:1:CVE-2099-0001",
        "scanner": "pip-audit",
        "severity": "HIGH",
        "ruleId": "CVE-2099-0001",
        "component": "example",
        "location": "1",
    }
    scan = security_scan_report()
    scan["payload"]["criticalHighFindings"] = [finding]
    scan["payload"]["highCount"] = 1
    scan["payload"]["summaries"]["pip-audit"]["findingCount"] = 1
    scan["payload"]["scannerExitCodes"]["pip-audit"] = 1
    reviewed = copy.deepcopy(SCAN_ALLOWLIST)
    reviewed["acceptedFindings"] = [
        {
            "findingId": finding["findingId"],
            "severity": "HIGH",
            "reason": "reviewed compatibility exception",
            "expiresAt": "2030-01-01T00:00:00Z",
        }
    ]
    scan["payloadSha256"] = tool._canonical_sha256(scan["payload"])
    assert (
        tool.evaluate_security_scan(scan, reviewed, NOW, FakeGit(), SOURCE)
        is tool.Verdict.MEASURED_PASS
    )

    expired = copy.deepcopy(reviewed)
    expired["acceptedFindings"][0]["expiresAt"] = "2020-01-01T00:00:00Z"
    scan["payload"]["expiredFindingIds"] = [finding["findingId"]]
    scan["payloadSha256"] = tool._canonical_sha256(scan["payload"])
    scan["verdict"] = "MEASURED_FAIL"
    scan["failureClass"] = "EXPIRED_ALLOWLIST"
    assert (
        tool.evaluate_security_scan(scan, expired, NOW, FakeGit(), SOURCE)
        is tool.Verdict.MEASURED_FAIL
    )

    missing_reason = copy.deepcopy(reviewed)
    missing_reason["acceptedFindings"][0]["reason"] = ""
    with pytest.raises(ValueError, match="reason is required"):
        tool.validate_scan_allowlist(missing_reason)


def test_security_envelope_must_name_an_importer_the_source_tree_contains(allowlist):
    """#313 F-R3: the adapter that wrote the envelope has to exist at sourceHeadSha.

    The allowlist's three pins are compared against the source tree below, but only after
    all four threat reports are present -- so an envelope written by an importer the tree
    does not contain was accepted as long as three reports were still missing.
    """

    absent = security_envelope(allowlist)
    absent.pop("importerFile")
    assert axis_result(absent, allowlist).verdict is tool.Verdict.INVALID_RUN

    drifted = security_envelope(allowlist)
    drifted["importerFile"]["blob"] = "0" * 40
    assert axis_result(drifted, allowlist).verdict is tool.Verdict.INVALID_RUN

    elsewhere = security_envelope(allowlist)
    elsewhere["importerFile"]["path"] = "tools/not_pinned_anywhere.py"
    assert axis_result(elsewhere, allowlist).verdict is tool.Verdict.INVALID_RUN

    # It is checked before the missing-report answer, so it cannot hide behind NOT_OBSERVED.
    partial = security_envelope(allowlist)
    partial["verdict"] = "NOT_OBSERVED"
    partial["observations"].pop()
    partial["importerFile"]["blob"] = "0" * 40
    assert axis_result(partial, allowlist).verdict is tool.Verdict.INVALID_RUN


def test_security_scan_tool_or_scope_object_drift_is_invalid(allowlist):
    tool_drift = security_envelope(allowlist)
    tool_drift["observations"][3]["toolFiles"][0]["blob"] = "0" * 40
    assert axis_result(tool_drift, allowlist).verdict is tool.Verdict.INVALID_RUN

    scope_drift = security_envelope(allowlist)
    scope_drift["observations"][3]["payload"]["scanInputs"][0]["objectId"] = "0" * 40
    scope_drift["observations"][3]["payloadSha256"] = tool._canonical_sha256(
        scope_drift["observations"][3]["payload"]
    )
    assert axis_result(scope_drift, allowlist).verdict is tool.Verdict.INVALID_RUN


def test_allowlist_schema_and_disposition_duplicates_are_invalid(allowlist):
    broken = copy.deepcopy(allowlist)
    broken["extra"] = True
    result = tool.aggregate(manifest(allowlist), FakeGit(), broken, NOW)
    assert result["verdict"] == "INVALID_RUN" and result["done"] is False
    duplicate = copy.deepcopy(allowlist)
    duplicate["rlsAcceptedDispositions"].append(copy.deepcopy(duplicate["rlsAcceptedDispositions"][0]))
    result = tool.aggregate(manifest(allowlist), FakeGit(), duplicate, NOW)
    assert result["verdict"] == "INVALID_RUN"


def test_cleanup_residue_cannot_be_pass(allowlist):
    value = envelope(tool.REQUIRED_AXES[1])
    value["cleanup"]["residueCount"] = 1
    assert axis_result(value, allowlist).verdict is tool.Verdict.INVALID_RUN


@pytest.mark.parametrize("residue", [-1, False])
def test_cleanup_residue_rejects_negative_and_boolean_values(residue, allowlist):
    value = envelope(tool.REQUIRED_AXES[1])
    value["cleanup"]["residueCount"] = residue
    assert axis_result(value, allowlist).verdict is tool.Verdict.INVALID_RUN


def test_observation_counts_and_values_reject_booleans(allowlist):
    boolean_count = envelope(tool.REQUIRED_AXES[1])
    boolean_count["observations"][0]["n"] = True
    assert axis_result(boolean_count, allowlist).verdict is tool.Verdict.INVALID_RUN

    boolean_value = envelope(tool.REQUIRED_AXES[1])
    boolean_value["observations"][0]["value"] = True
    assert axis_result(boolean_value, allowlist).verdict is tool.Verdict.INVALID_RUN


def test_only_reversible_axis_accepts_declared_zero_tail(allowlist):
    value = envelope(tool.REQUIRED_AXES[0], "NOT_APPLICABLE")
    value["observations"] = []
    value["structuralException"] = {"reason": "no-reversible-tail", "reversibleTailCount": 0}
    value.pop("reversibleSegment")
    assert axis_result(value, allowlist, ZeroTailGit()).verdict is tool.Verdict.NOT_APPLICABLE
    value["axis"] = tool.REQUIRED_AXES[1]
    assert axis_result(value, allowlist, ZeroTailGit()).verdict is tool.Verdict.INVALID_RUN


def test_zero_tail_is_conditionally_excluded_only_when_restore_passes(allowlist):
    value = manifest(allowlist)
    reversible = value["axes"][0]
    reversible.update(
        verdict="NOT_APPLICABLE",
        observations=[],
        structuralException={"reason": "no-reversible-tail", "reversibleTailCount": 0},
    )
    reversible.pop("reversibleSegment")
    result = tool.aggregate(value, ZeroTailGit(), allowlist, NOW)
    assert result["verdict"] == "MEASURED_PASS" and result["done"] is True

    restore = value["axes"][1]
    restore["verdict"] = "MEASURED_FAIL"
    restore["observations"][0]["value"] = 0
    result = tool.aggregate(value, ZeroTailGit(), allowlist, NOW)
    assert result["verdict"] == "MEASURED_FAIL" and result["done"] is False


def test_zero_tail_claim_is_invalid_when_git_graph_has_reversible_tail(allowlist):
    value = envelope(tool.REQUIRED_AXES[0], "NOT_APPLICABLE")
    value.update(
        observations=[],
        structuralException={"reason": "no-reversible-tail", "reversibleTailCount": 0},
    )
    value.pop("reversibleSegment")
    assert axis_result(value, allowlist, FakeGit()).verdict is tool.Verdict.INVALID_RUN


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("startingRevision", "0001_base"),
        ("endingRevision", "base"),
        ("reversibleTailCount", 2),
    ],
)
def test_measured_reversible_segment_must_match_source_graph(field, value, allowlist):
    evidence = envelope(tool.REQUIRED_AXES[0])
    evidence["reversibleSegment"][field] = value
    assert axis_result(evidence, allowlist, FakeGit()).verdict is tool.Verdict.INVALID_RUN


def test_looser_envelope_criteria_cannot_override_git_registry(allowlist):
    value = envelope(tool.REQUIRED_AXES[1])
    value["targetRef"]["criteria"]["sampleCount"]["value"] = 0
    assert axis_result(value, allowlist).verdict is tool.Verdict.INVALID_RUN


def test_skip_is_not_pass_and_producer_must_agree(allowlist):
    value = envelope(tool.REQUIRED_AXES[1], "NOT_OBSERVED")
    value["observations"][0].update(successCount=0, skipCount=1)
    assert axis_result(value, allowlist).verdict is tool.Verdict.NOT_OBSERVED
    value["verdict"] = "MEASURED_PASS"
    assert axis_result(value, allowlist).verdict is tool.Verdict.INVALID_RUN


def test_empty_definer_catalogue_and_empty_rls_scope_are_invalid(allowlist):
    definer = security_reports(allowlist)[0]
    definer.update(functions=[], unsafe=0)
    assert tool.evaluate_definer(definer, allowlist) is tool.Verdict.INVALID_RUN

    rls = rls_report(allowlist)
    rls["roles"] = {}
    assert tool.evaluate_rls(rls, allowlist, NOW) is tool.Verdict.INVALID_RUN


def test_vf_requires_complete_unskipped_case_identity_set(allowlist):
    report = security_reports(allowlist)[2]
    report["tests"] = {"failure": 0, "error": 0, "skipped": 1, "passed": 5}
    assert tool.evaluate_vf(report, allowlist) is tool.Verdict.INVALID_RUN
    report = security_reports(allowlist)[2]
    report["caseIdentitiesSha256"] = "0" * 64
    assert tool.evaluate_vf(report, allowlist) is tool.Verdict.INVALID_RUN


def test_false_fail_is_rejected_when_observations_recompute_pass(allowlist):
    value = envelope(tool.REQUIRED_AXES[1], "MEASURED_FAIL")
    assert axis_result(value, allowlist).verdict is tool.Verdict.INVALID_RUN
