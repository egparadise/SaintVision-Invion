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
        if path == "migrations/versions/0001_base.py":
            return 'revision = "0001_base"\ndown_revision = None\ndef downgrade():\n    raise RuntimeError("restore")\n'
        if path == "migrations/versions/0002_head.py":
            return 'revision = "0002_head"\ndown_revision = "0001_base"\ndef downgrade():\n    pass\n'
        raise AssertionError((commit, path))

    def list_paths(self, commit: str, prefix: str) -> list[str]:
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
    ]


def security_envelope(allowlist: dict) -> dict:
    value = envelope("security-critical-high-zero")
    value["observations"] = security_reports(allowlist)
    value["targetRef"] = target("security-critical-high-zero", {})
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
