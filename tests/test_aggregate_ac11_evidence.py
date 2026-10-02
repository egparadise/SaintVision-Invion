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
        {"threatId": "SEC-RLS-001", **rls_report(allowlist)},
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


CTID_FP = "5d41402abc4b2a76b9719d911017c592"


def rls_table(identity: dict | None = None, **overrides) -> dict:
    """One tenant-scoped, readable, clean table as the collector records it.

    The fixtures used to be a stub (``{"present": True}``) because nothing read them.  The
    evaluator now re-derives E1..E5 from these observations, so a test that wants a violation has
    to carry the observation that produces it -- which is the point: three findings in a row were
    reports whose conclusions nothing cross-checked (#322 r2).
    """

    table = {
        "tenant_scoped": True,
        "rls_enabled": True,
        "rls_forced": True,
        "privileges": {"select": "table", "insert": "table", "update": None, "delete": None},
        "policies": [{"name": "tenant_isolation", "cmd": "ALL", "permissive": "PERMISSIVE",
                      "roles": ["inv_app"], "using": True, "with_check": True}],
        "visible": {
            "guc_unset": {"rows": 0},
            "guc_tenant_a": {"rows": 1},
            "guc_tenant_a_foreign_rows": {"rows": 0},
            "guc_unknown_tenant": {"rows": 0},
            "guc_not_uuid": {"denied": "22P02"},
            "identity": copy.deepcopy(identity) if identity is not None else {
                "method": "ctid",
                "owner_a": {"rows": 1, "fp": CTID_FP},
                "role_a": {"rows": 1, "fp": CTID_FP},
                "match": True,
            },
        },
    }
    for key, value in overrides.items():
        if key in {"guc_unset", "guc_tenant_a", "guc_tenant_a_foreign_rows", "guc_unknown_tenant"}:
            table["visible"][key] = value
        else:
            table[key] = value
    return table


#: The tables every fixture report measures: its own plus the ones the reviewed allowlist and the
#: pinned readable-key scope anchor on.  A report that omits them is refused, which is the point
#: of the anchors (#322 r2 F-R6).
ANCHOR_TABLES = ("public.projects", "public.tenants",
                 "public.discovery_credential_issue_budgets", "public.audit_events")


def default_tables() -> dict:
    return {name: rls_table() for name in ANCHOR_TABLES}


def rls_role_entry(tables: dict | None = None, **overrides) -> dict:
    entry = {
        "present": True,
        "superuser": False,
        "bypassrls": False,
        "login": False,
        "inherit": True,
        "member_of": [],
        "functions": {},
        "tables": copy.deepcopy(tables) if tables is not None else default_tables(),
    }
    entry.update(overrides)
    return entry


def rls_roles(tables: dict | None = None, *, role: str = "inv_app", **role_overrides) -> dict:
    """The whole measured population, with ``role`` carrying the interesting observation.

    The evaluator requires exactly ``RLS_REQUIRED_ROLES`` and ``present: true`` for each
    (#322 r2 F-R5): a report that drops a role, or calls it absent, shrinks what its verdict
    covers without saying so.  So a fixture about one role still has to carry the other seven.
    """

    interesting = copy.deepcopy(tables) if tables is not None else default_tables()
    # Every role measures the same tables -- that is what the collector does, and the evaluator
    # now requires it (#322 r2 F-R6).  The *values* differ per role; the key set may not.
    shared = {}
    for name, table in interesting.items():
        # Whether a table has a tenant column is a property of the table, not of the role.
        shared[name] = (copy.deepcopy(table) if table.get("tenant_scoped") is False
                        else rls_table())
    roles = {name: rls_role_entry(shared) for name in sorted(tool.RLS_REQUIRED_ROLES)}
    roles[role] = rls_role_entry(interesting, **role_overrides)
    return roles


def rls_ground_truth(*tables: str) -> dict:
    return {
        name: {"total": {"rows": 2}, "tenant_a": {"rows": 1}, "other_tenants": {"rows": 1}}
        for name in (tables or ANCHOR_TABLES)
    }


def rls_report(allowlist: dict, exit_code: int = 0, roles: dict | None = None,
               ground_truth: dict | None = None) -> dict:
    roles = copy.deepcopy(roles) if roles is not None else rls_roles()
    tables = [name for entry in roles.values() for name in entry.get("tables", {})]
    value = {
        # The whole top-level key set the producer writes: the schema refuses an extra or a
        # missing one, so a fixture thinner than the real report is not a report (#322 r2 F-R6).
        "threatId": "SEC-RLS-001",
        "sourceRunId": "36370000000",
        "sourceHeadSha": SOURCE,
        "checkoutTreeSha": TREE,
        "cleanCheckout": True,
        "reportAvailable": True,
        "runPurpose": "s11-ac11-security-threat-reports",
        "schemaVersion": "1.0.0",
        "startedAt": "2026-10-02T05:32:03.335160Z",
        "finishedAt": "2026-10-02T05:32:08.135160Z",
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
        "measuredRoles": sorted(roles),
        "roles": roles,
        "ground_truth": ground_truth if ground_truth is not None else rls_ground_truth(*tables),
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


def rls_rule_observation(rule: str) -> dict:
    """Roles whose observations actually produce ``rule`` for inv_app / public.projects."""

    if rule == "E1":
        return rls_roles(superuser=True)
    overrides = {
        "E2": {"rls_forced": False},
        "E3": {"guc_unset": {"rows": 1}},
        "E4": {"guc_tenant_a_foreign_rows": {"rows": 1}},
        "E5": {"guc_unknown_tenant": {"rows": 1}},
    }.get(rule)
    if overrides is None:
        return rls_roles()
    return rls_roles({**default_tables(), "public.projects": rls_table(**overrides)})


@pytest.mark.parametrize("rule", sorted(tool.RLS_RULES))
def test_each_unaccepted_rls_rule_is_critical(rule, allowlist):
    """Every rule the report carries unaccepted is a measured failure.

    The row is no longer invented: each case carries the observation that produces it, because
    the evaluator re-derives E1..E5 and refuses a violation the numbers do not support.  E6 is
    the exception and says so -- it is about SECURITY DEFINER functions, which this report does
    not observe, so it is carried as reported (``RLS_RECOMPUTED_RULES`` leaves it out).
    """

    roles = rls_rule_observation(rule)
    report = rls_report(allowlist, 1, roles=roles)
    row = ({"rule": rule, "function": "public.forged()"} if rule == "E6"
           else {"rule": rule, "role": "inv_app",
                 **({} if rule == "E1" else {"table": "public.projects"})})
    report.update(verdict="VIOLATIONS", violations=[row])
    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.MEASURED_FAIL


def test_rls_accepted_expiry_and_baseline_exact_match(allowlist):
    # The accepted row is a real derivation: public.tenants is observed without forced RLS, and
    # the reviewed baseline accepts E2 there.  An accepted row nothing derives is refused.
    roles = rls_roles({**default_tables(), "public.tenants": rls_table(rls_forced=False)})
    report = rls_report(allowlist, roles=roles)
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
    roles = rls_roles({**default_tables(), "public.projects": rls_table(
        {"method": "unverifiable", "reason": "ctid denied 42501; identity columns not readable"}
    )}) if exit_code == 3 else None
    report = rls_report(allowlist, exit_code, roles=roles)
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
    """The registered pair, carrying a full observation with ``identity`` in it."""

    return rls_roles({**default_tables(), table: rls_table(identity, guc_tenant_a={"rows": 2})},
                     role=role)


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
        # #322 r2 F-R4: role_a.rows was only checked for being an integer, so a claimed match
        # over a different number of rows passed -- impossible, since the fingerprint is taken
        # over the row set.
        pytest.param(
            identity_roles({**OWNER_VERIFIED_IDENTITY, "role_a": {"rows": 0, "fp": OWNER_FP}}),
            tool.Verdict.INVALID_RUN,
            id="match-over-zero-role-rows",
        ),
        pytest.param(
            identity_roles({**OWNER_VERIFIED_IDENTITY, "role_a": {"rows": 1, "fp": OWNER_FP}}),
            tool.Verdict.INVALID_RUN,
            id="match-over-one-role-row",
        ),
        pytest.param(
            identity_roles({**OWNER_VERIFIED_IDENTITY, "role_a": {"rows": 3, "fp": OWNER_FP}}),
            tool.Verdict.INVALID_RUN,
            id="match-over-three-role-rows",
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

    report = rls_report(allowlist, roles=roles)
    assert tool.evaluate_rls(report, allowlist, NOW) is expected


def strip(report: dict, path: tuple) -> dict:
    """The report with one key removed at ``path`` (tuple of keys), for the sweep below."""

    value = copy.deepcopy(report)
    cursor = value
    for key in path[:-1]:
        cursor = cursor[key]
    del cursor[path[-1]]
    return value


def required_key_paths(report: dict) -> list[tuple]:
    """Every key the evaluator requires, as a path into the report.

    Generated from the report rather than listed, so a field added to the collector's output
    appears here automatically instead of being forgotten (#322 r2 F-R5 asked for the sweep).
    """

    paths: list[tuple] = [("measuredRoles",), ("roles",), ("ground_truth",), ("exitCode",),
                          ("verdict",), ("toolFiles",), ("baselineAccepted",), ("violations",),
                          ("accepted",), ("unmeasured",)]
    for table_name in report["ground_truth"]:
        paths.append(("ground_truth", table_name))
        for field in report["ground_truth"][table_name]:
            paths.append(("ground_truth", table_name, field))
    for role_name, role_report in report["roles"].items():
        paths.append(("roles", role_name))
        for field in role_report:
            paths.append(("roles", role_name, field))
        for table_name, table in role_report["tables"].items():
            paths.append(("roles", role_name, "tables", table_name))
            for field in table:
                paths.append(("roles", role_name, "tables", table_name, field))
            for cell in table.get("visible", {}):
                paths.append(("roles", role_name, "tables", table_name, "visible", cell))
                if cell != "identity":
                    paths.append(
                        ("roles", role_name, "tables", table_name, "visible", cell,
                         next(iter(table["visible"][cell])))
                    )
    return paths


def test_removing_any_required_key_refuses_the_report(allowlist):
    """Sweep: every required key, removed one at a time, must make the report inadmissible.

    This is the shape of all four #322 r2 findings in one test.  The evaluator used to treat a
    missing observation as a zero, so deleting ``guc_unset``, deleting every cell, emptying
    ``tables`` or saying ``present: false`` each produced MEASURED_PASS -- a report could pass by
    carrying **less**.  The paths are generated from the report, so a new field is swept too.
    """

    report = rls_report(allowlist)
    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.MEASURED_PASS
    paths = required_key_paths(report)
    assert len(paths) > 100, "the sweep must actually cover the report"
    def passes(path: tuple) -> bool:
        try:
            return tool.evaluate_rls(strip(report, path), allowlist, NOW) is tool.Verdict.MEASURED_PASS
        except ValueError:
            # The aggregator's own refusal: ``aggregate``/``evaluate_axis`` turn it into
            # INVALID_RUN with the message as the reason, so it is a refusal, not a pass.
            return False

    survivors = [path for path in paths if passes(path)]
    assert survivors == []


def _at(report, path: tuple):
    cursor = report
    for key in path:
        cursor = cursor[key]
    return cursor


def _insert(report: dict, path: tuple, key: str, value) -> dict:
    out = copy.deepcopy(report)
    _at(out, path)[key] = value
    return out


def _duplicate(report: dict, path: tuple) -> dict:
    """The list at ``path`` with its first item appended again."""

    out = copy.deepcopy(report)
    target = _at(out, path)
    target.append(copy.deepcopy(target[0]))
    return out


def test_an_extra_key_anywhere_in_the_report_is_refused(allowlist):
    """``additionalProperties: false`` at every level, swept rather than asserted once.

    An extra key is either a field this evaluator does not understand or a field someone added to
    carry a claim nothing checks; both are refusals (#322 r2 F-R6).  The sweep walks every object
    in a real-shaped report and inserts one key into it.
    """

    report = rls_report(allowlist)
    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.MEASURED_PASS
    paths = [path for path in _dict_paths(report)]
    assert len(paths) > 100, f"the sweep must cover the report, got {len(paths)}"
    survivors = []
    for path in paths:
        forged = _insert(report, path, "zzExtra", 1)
        try:
            verdict = tool.evaluate_rls(forged, allowlist, NOW)
        except ValueError:
            continue
        if verdict is tool.Verdict.MEASURED_PASS:
            survivors.append(path)
    assert survivors == []


def _dict_paths(value, prefix=()) -> list[tuple]:
    out = []
    if isinstance(value, dict):
        out.append(prefix)
        for key, child in value.items():
            out.extend(_dict_paths(child, prefix + (key,)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            out.extend(_dict_paths(child, prefix + (index,)))
    return out


def _list_paths(value, prefix=()) -> list[tuple]:
    out = []
    if isinstance(value, dict):
        for key, child in value.items():
            out.extend(_list_paths(child, prefix + (key,)))
    elif isinstance(value, list):
        if value:
            out.append(prefix)
        for index, child in enumerate(value):
            out.extend(_list_paths(child, prefix + (index,)))
    return out


def test_duplicating_any_list_item_is_refused(allowlist):
    """A repeated entry is not a longer list of facts, it is the same fact twice.

    ``measuredRoles`` was the one F-R6 found, but the same applies to the tool pins and the
    baseline dispositions, so the sweep duplicates the first item of every non-empty list in the
    report.
    """

    report = rls_report(allowlist)
    report["violations"] = []
    paths = _list_paths(report)
    assert paths, "the report must carry lists to duplicate"
    survivors = []
    for path in paths:
        forged = _duplicate(report, path)
        try:
            verdict = tool.evaluate_rls(forged, allowlist, NOW)
        except ValueError:
            continue
        if verdict is tool.Verdict.MEASURED_PASS:
            survivors.append(path)
    assert survivors == []


def test_ground_truth_must_correspond_to_the_measured_tables_both_ways(allowlist):
    """A truth row for a table nothing measured, and a measured table with no truth row.

    Both directions, because the derivation reads the owner's tenant-A count out of
    ``ground_truth``: a ghost row is a claim about nothing, and a gap is a judged table whose
    comparison has no owner side (#322 r2 F-R6).
    """

    ghost = rls_report(allowlist)
    ghost["ground_truth"]["public.ghost"] = {
        "total": {"rows": 9}, "tenant_a": {"rows": 9}, "other_tenants": {"rows": 0},
    }
    assert tool.evaluate_rls(ghost, allowlist, NOW) is tool.Verdict.INVALID_RUN

    gap = rls_report(allowlist)
    del gap["ground_truth"]["public.tenants"]
    assert tool.evaluate_rls(gap, allowlist, NOW) is tool.Verdict.INVALID_RUN


def test_every_role_must_measure_the_same_tables(allowlist):
    """One role measuring fewer tables is a smaller report wearing a complete one's verdict."""

    narrowed = rls_report(allowlist)
    del narrowed["roles"]["inv_kernel"]["tables"]["public.tenants"]
    assert tool.evaluate_rls(narrowed, allowlist, NOW) is tool.Verdict.INVALID_RUN

    widened = rls_report(allowlist)
    widened["roles"]["inv_kernel"]["tables"]["public.extra"] = rls_table()
    assert tool.evaluate_rls(widened, allowlist, NOW) is tool.Verdict.INVALID_RUN


def test_a_row_may_not_name_something_the_report_did_not_measure(allowlist):
    """A judged row about an unmeasured role or table is a claim with no observation behind it."""

    for row in (
        {"rule": "E2", "role": "inv_nonexistent", "table": "public.projects"},
        {"rule": "E2", "role": "inv_app", "table": "public.nowhere"},
    ):
        report = rls_report(allowlist, 1)
        report.update(verdict="VIOLATIONS", violations=[row])
        assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.INVALID_RUN


def test_dropping_a_table_with_its_truth_is_caught_only_where_something_anchors_it(allowlist):
    """The residual this evaluator cannot close, written down instead of left implied.

    A report that drops a table **together with** its ground-truth row and every row that names
    it is internally consistent, and the evaluator cannot know how many tables the migrated
    database has -- that number lives in the database, not in the report or the reviewed
    allowlist.  Two anchors catch the cases that matter today: the tables the reviewed allowlist
    accepts dispositions for, and the table the pinned readable-key scope names.  Beyond those,
    the pair deletion is accepted, and closing it exactly would need the expected table set to
    come from the reviewed source -- an AC-11 definition change, which this card does not make
    (#322 r2 F-R6).
    """

    def without(table_name: str) -> dict:
        report = rls_report(allowlist)
        for role_report in report["roles"].values():
            role_report["tables"].pop(table_name, None)
        report["ground_truth"].pop(table_name, None)
        report["baselineAccepted"] = [
            row for row in report["baselineAccepted"] if row["table"] != table_name
        ]
        return report

    # Anchored: the readable-key scope names this one, so its absence is a refusal.
    assert tool.evaluate_rls(without("public.audit_events"), allowlist, NOW) is \
        tool.Verdict.INVALID_RUN
    # Anchored through baselineAccepted: dropping the table *and* its disposition no longer
    # matches the reviewed allowlist, which is checked exactly.
    assert tool.evaluate_rls(without("public.tenants"), allowlist, NOW) is tool.Verdict.INVALID_RUN
    # Not anchored: this is the residual, and it is accepted today.
    assert tool.evaluate_rls(without("public.projects"), allowlist, NOW) is \
        tool.Verdict.MEASURED_PASS


def test_the_one_role_no_migration_creates_may_be_absent_and_the_others_may_not(allowlist):
    """``inv_runtime_dev`` is absent in the producer's database; the other seven may not be.

    Measured on the hosted report: seven roles exist and ``inv_runtime_dev`` -- a developer login
    no migration creates -- comes back ``{"present": false}``.  A role that does not exist cannot
    bypass RLS, so that is a fact; but if any other role could be reported absent, a forger could
    shrink the population a MEASURED_PASS covers (#322 r2 F-R5).  An absent role also carries
    nothing but that one key.
    """

    report = rls_report(allowlist)
    report["roles"]["inv_runtime_dev"] = {"present": False}
    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.MEASURED_PASS

    report["roles"]["inv_runtime_dev"] = {"present": False, "superuser": True}
    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.INVALID_RUN

    for role in sorted(tool.RLS_REQUIRED_ROLES - tool.RLS_OPTIONAL_ROLES):
        hidden = rls_report(allowlist)
        hidden["roles"][role] = {"present": False}
        assert tool.evaluate_rls(hidden, allowlist, NOW) is tool.Verdict.INVALID_RUN, role


def test_ground_truth_must_have_the_shape_that_table_actually_has(allowlist):
    """A tenant-scoped table has a tenant-A truth; a table without a tenant column does not.

    The derivation compares the role's tenant-A count with the owner's, so a scoped table whose
    truth carries only ``total`` is a missing observation -- and the evaluator refuses it instead
    of reading the absence as zero.
    """

    scoped_without_tenant_truth = rls_report(allowlist)
    scoped_without_tenant_truth["ground_truth"]["public.projects"] = {"total": {"rows": 2}}
    assert tool.evaluate_rls(scoped_without_tenant_truth, allowlist, NOW) is tool.Verdict.INVALID_RUN

    # An unscoped readable table carries total alone, and claiming a tenant truth for it is also
    # a shape the collector never writes.
    unscoped = rls_roles({
        **default_tables(),
        "inv.control_epoch": rls_table(
            tenant_scoped=False,
            visible={"guc_unset": {"rows": 1}, "guc_tenant_a": {"rows": 1},
                     "guc_unknown_tenant": {"rows": 1}, "guc_not_uuid": {"rows": 1}},
        ),
    })
    truth = rls_ground_truth()
    truth["inv.control_epoch"] = {"total": {"rows": 1}}
    report = rls_report(allowlist, roles=unscoped, ground_truth=truth)
    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.MEASURED_PASS

    truth["inv.control_epoch"] = {"total": {"rows": 1}, "tenant_a": {"rows": 1},
                                  "other_tenants": {"rows": 0}}
    assert tool.evaluate_rls(
        rls_report(allowlist, roles=unscoped, ground_truth=truth), allowlist, NOW
    ) is tool.Verdict.INVALID_RUN


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        pytest.param(
            "one-cell-deleted",
            lambda r: strip(r, ("roles", "inv_app", "tables", "public.projects", "visible",
                                "guc_unset")),
            id="one-cell-deleted",
        ),
        pytest.param(
            "tenant-a-cell-deleted",
            lambda r: strip(r, ("roles", "inv_app", "tables", "public.projects", "visible",
                                "guc_tenant_a")),
            id="tenant-a-cell-deleted",
        ),
        pytest.param(
            "every-cell-deleted",
            lambda r: _replace(r, ("roles", "inv_app", "tables", "public.projects", "visible"),
                               {}),
            id="every-cell-deleted",
        ),
        pytest.param(
            "tables-emptied",
            lambda r: _replace(r, ("roles", "inv_app", "tables"), {}),
            id="tables-emptied",
        ),
        pytest.param(
            "role-called-absent",
            lambda r: _replace(r, ("roles", "inv_app"), {"present": False}),
            id="role-called-absent",
        ),
        pytest.param(
            "role-dropped",
            lambda r: strip(r, ("roles", "inv_app")),
            id="role-dropped",
        ),
        pytest.param(
            "negative-row-count",
            lambda r: _replace(r, ("roles", "inv_app", "tables", "public.projects", "visible",
                                   "guc_unset"), {"rows": -1}),
            id="negative-row-count",
        ),
        pytest.param(
            "row-count-is-a-string",
            lambda r: _replace(r, ("roles", "inv_app", "tables", "public.projects", "visible",
                                   "guc_unset"), {"rows": "0"}),
            id="row-count-is-a-string",
        ),
        pytest.param(
            "row-count-is-a-boolean",
            lambda r: _replace(r, ("roles", "inv_app", "tables", "public.projects", "visible",
                                   "guc_unset"), {"rows": False}),
            id="row-count-is-a-boolean",
        ),
        pytest.param(
            "cell-carries-an-extra-key",
            lambda r: _replace(r, ("roles", "inv_app", "tables", "public.projects", "visible",
                                   "guc_unset"), {"rows": 0, "note": "fine"}),
            id="cell-carries-an-extra-key",
        ),
        pytest.param(
            "visible-carries-an-unknown-cell",
            lambda r: _replace(r, ("roles", "inv_app", "tables", "public.projects", "visible",
                                   "guc_future"), {"rows": 0}),
            id="visible-carries-an-unknown-cell",
        ),
        pytest.param(
            "unreadable-table-carries-a-probe",
            lambda r: _replace(r, ("roles", "inv_app", "tables", "public.projects",
                                   "privileges"),
                               {"select": None, "insert": None, "update": None, "delete": None}),
            id="unreadable-table-carries-a-probe",
        ),
        pytest.param(
            "ground-truth-does-not-cover-a-judged-table",
            lambda r: strip(r, ("ground_truth", "public.projects")),
            id="ground-truth-missing",
        ),
        pytest.param(
            "identity-method-is-unknown",
            lambda r: _replace(r, ("roles", "inv_app", "tables", "public.projects", "visible",
                                   "identity"), {"method": "trust-me", "match": True}),
            id="identity-method-is-unknown",
        ),
    ],
)
def test_a_missing_or_malformed_observation_is_never_a_zero(label, mutate, allowlist):
    """#322 r2 F-R5: each of these produced MEASURED_PASS by being read as "nothing to see".

    A count that is absent, negative, a string, a boolean, or carried beside an extra key is not
    an observation of zero rows; a role that calls itself absent, or disappears, is not a
    measured population.  Validating the shape **before** deriving numbers is what makes every
    one of these a refusal rather than a default.
    """

    report = mutate(rls_report(allowlist))
    assert tool.evaluate_rls(report, allowlist, NOW) is not tool.Verdict.MEASURED_PASS
    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.INVALID_RUN


def _replace(report: dict, path: tuple, value) -> dict:
    out = copy.deepcopy(report)
    cursor = out
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    return out


@pytest.mark.parametrize(
    "forge",
    [
        pytest.param("measured-roles-differ", id="measured-roles-differ"),
        pytest.param("invented-violation", id="invented-violation"),
        pytest.param("hidden-violation", id="hidden-violation"),
        pytest.param("invented-unmeasured", id="invented-unmeasured"),
        pytest.param("hidden-unmeasured", id="hidden-unmeasured"),
        pytest.param("accepted-row-nothing-derives", id="accepted-row-nothing-derives"),
        pytest.param("role-without-tables", id="role-without-tables"),
    ],
)
def test_every_rls_row_must_be_derivable_from_the_observations(forge, allowlist):
    """A report may not claim a row its own observations do not produce, or hide one they do.

    This is the class the three findings of #322 r2 belong to: the evaluator used to read a
    conclusion (``verdict``, ``match``, a list) and not the numbers beside it.  Each case below
    forges exactly one of those relations.
    """

    leaking = rls_roles({**default_tables(),
                         "public.runs": rls_table(guc_tenant_a_foreign_rows={"rows": 1})})
    truth = rls_ground_truth(*ANCHOR_TABLES, "public.runs")
    row = {"rule": "E4", "role": "inv_app", "table": "public.runs"}

    if forge == "measured-roles-differ":
        report = rls_report(allowlist)
        report["measuredRoles"] = sorted(set(report["measuredRoles"]) - {"inv_app"})
    elif forge == "invented-violation":
        report = rls_report(allowlist, 1)
        report.update(verdict="VIOLATIONS", violations=[dict(row)])
    elif forge == "hidden-violation":
        report = rls_report(allowlist, roles=leaking, ground_truth=truth)
    elif forge == "invented-unmeasured":
        report = rls_report(allowlist, 3)
        report.update(verdict="UNMEASURED", unmeasured=[dict(row)])
    elif forge == "hidden-unmeasured":
        roles = rls_roles({**default_tables(), "public.projects": rls_table(
            {"method": "unverifiable", "reason": "ctid denied 42501"}
        )})
        report = rls_report(allowlist, roles=roles)
    elif forge == "accepted-row-nothing-derives":
        report = rls_report(allowlist)
        report["accepted"] = [{"rule": "E2", "role": "inv_app", "table": "public.tenants"}]
    else:
        roles = rls_roles()
        del roles["inv_app"]["tables"]
        report = rls_report(allowlist, roles=roles, ground_truth=rls_ground_truth())

    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.INVALID_RUN


def test_the_collector_and_the_evaluator_derive_the_same_rows(allowlist):
    """The two implementations of E1..E5 must agree, and this test is where drift shows.

    The evaluator re-derives the rules rather than trusting the report (#322 r2), so there are
    now two implementations: ``collect_rls_evidence.evaluate`` writes the report and
    ``aggregate_ac11_evidence._rls_recomputation`` checks it.  Here the collector's own output is
    fed to the evaluator: if either side changes its precedence, this stops passing instead of
    turning every future hosted report into INVALID_RUN.
    """

    import importlib.util
    import sys

    path = ROOT / "tools" / "collect_rls_evidence.py"
    spec = importlib.util.spec_from_file_location("collect_rls_evidence", path)
    collector = importlib.util.module_from_spec(spec)
    sys.modules["collect_rls_evidence"] = collector
    spec.loader.exec_module(collector)

    roles = rls_roles({
        # The anchor tables plus one that leaks a foreign row; the audit table carries an
        # unverifiable identity, so the collector derives an E4 violation and an E4 unmeasured row.
        **default_tables(),
        "public.runs": rls_table(guc_tenant_a_foreign_rows={"rows": 1}),
        "public.audit_events": rls_table(
            {"method": "unverifiable", "reason": "ctid denied 42501; identity columns not readable"}
        ),
    })
    observation = {
        "roles": copy.deepcopy(roles),
        "ground_truth": rls_ground_truth(
            *[name for entry in roles.values() for name in entry["tables"]]
        ),
        "definer_functions": {},
    }
    violations = [
        row for row in collector.evaluate(observation)
        if row["rule"] in tool.RLS_RECOMPUTED_RULES
    ]
    unmeasured = collector.unverified_identities(observation)
    assert [(row["rule"], row["table"]) for row in violations] == [("E4", "public.runs")]
    assert [(row["rule"], row["table"]) for row in unmeasured] == [("E4", "public.audit_events")]

    report = rls_report(allowlist, 1, roles=roles, ground_truth=observation["ground_truth"])
    report.update(verdict="VIOLATIONS", violations=violations, unmeasured=unmeasured)
    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.MEASURED_FAIL


def test_a_recomputed_identity_mismatch_cannot_hide_in_an_unmeasured_report(allowlist):
    """A measured mismatch is a violation, not an absence of observation (#322 r2 F-R3).

    An UNMEASURED report reads as "nothing was observed to be wrong", so a report carrying a
    recomputed ``match: false`` under exit 3 is refused rather than passed through as
    NOT_OBSERVED -- otherwise a forger could downgrade a violation into a quiet gap.
    """

    mismatch = identity_roles(
        {**OWNER_VERIFIED_IDENTITY, "role_a": {"rows": 2, "fp": OTHER_FP}, "match": False}
    )
    report = rls_report(allowlist, 3, roles=mismatch)
    report.update(
        verdict="UNMEASURED",
        unmeasured=[{"rule": "E4", "role": "inv_cancel_bridge_owner",
                     "table": "public.audit_events"}],
    )
    assert tool.evaluate_rls(report, allowlist, NOW) is tool.Verdict.INVALID_RUN

    # The same observation reported honestly is a measured failure, which is admissible.
    violation = rls_report(allowlist, 1, roles=mismatch)
    violation.update(
        verdict="VIOLATIONS",
        violations=[{"rule": "E4", "role": "inv_cancel_bridge_owner",
                     "table": "public.audit_events"}],
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
