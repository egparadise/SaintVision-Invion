"""PG-free trust-boundary tests for the AC-11 security artifact importer.

The fixtures here are the shape the producer actually writes, read out of the real artifact
of run 36943527856: five environment keys and no comparability group, the counts inside
``payload`` rather than at the top level, ``toolFiles`` copied from the reviewed allowlist.
r1's stub was richer than reality on all three counts, which is why it agreed with an
importer the aggregator refuses (#313).
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import aggregate_ac11_evidence as aggregator  # noqa: E402
import import_ac11_security_scan as tool  # noqa: E402


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


RUN_ID = "36943527856"
ARTIFACT_ID = "11200951947"
NOW = datetime(2026, 10, 2, 3, 0, tzinfo=timezone.utc)
#: The envelope is about a tree the aggregator has to be able to read, so the fixtures are
#: about this checkout rather than about ``"a" * 40``.
SOURCE = git("rev-parse", "HEAD")
TREE = git("rev-parse", "HEAD^{tree}")
SCAN_ALLOWLIST = json.loads(
    (ROOT / tool.SCAN_ALLOWLIST_REPO_PATH).read_text(encoding="utf-8")
)
SCOPE = sorted({path for row in SCAN_ALLOWLIST["scanners"] for path in row["scopePaths"]})
#: Measured from the real artifact: the producer writes no comparability group.
PRODUCER_ENVIRONMENT = {
    "runnerImage": "Linux-X64",
    "topology": "hosted",
    "evidenceClass": "security-tools-v0",
    "credentialsRequired": False,
    "externalServicesRequired": True,
}


def tool_files(importer_blob: str | None = None) -> list[dict]:
    """The three pins the producer copies out of the reviewed allowlist.

    The importer pin is the executing blob by default so that these tests are about the
    importer's rules rather than about whether the checkout is committed; that the file on
    disk and the allowlist agree is its own test below.
    """

    return [
        copy.deepcopy(SCAN_ALLOWLIST["producer"]),
        copy.deepcopy(SCAN_ALLOWLIST["workflow"]),
        {"path": tool.IMPORTER_REPO_PATH, "blob": importer_blob or tool.importer_blob()},
    ]


#: Measured from the real artifact of run 36949022989: ``scannedPythonFiles`` is the sorted
#: list of files bandit read (207 of them there), not a count, and every summary number is
#: that list's own arithmetic.  r1's fixture used a count, so the importer agreed with a
#: payload the canonical evaluator would refuse (#313 r2).
SCANNED_FILES = [
    "services/control-plane/src/inv/build_execution.py",
    "services/control-plane/src/inv/buildkit_transport.py",
    "src/saintvision/__init__.py",
]
AUDITED = [
    {"name": "alembic", "version": "1.19.2"},
    {"name": "anyio", "version": "4.15.1"},
]
#: bandit's low and medium counts are real on the hosted lane (16 and 4), which is why its
#: exit code is 1 while no critical or high finding exists.
BANDIT_NOISE = {"lowFindingCount": 16, "mediumFindingCount": 4}


def finding(finding_id: str, severity: str = "HIGH", scanner: str = "bandit") -> dict:
    return {
        "findingId": finding_id,
        "scanner": scanner,
        "severity": severity,
        "ruleId": "B602" if scanner == "bandit" else "GHSA-0000-0000",
        "component": "services/control-plane/src/inv/build_execution.py",
        "location": "services/control-plane/src/inv/build_execution.py:12",
    }


def payload(*findings: dict, **over) -> dict:
    rows = sorted(findings, key=lambda row: row["findingId"])
    summaries = {
        "bandit": {
            **BANDIT_NOISE,
            "highFindingCount": sum(row["scanner"] == "bandit" for row in rows),
            "scannedFileCount": len(SCANNED_FILES),
        },
        "pip-audit": {
            "dependencyCount": len(AUDITED),
            "findingCount": sum(row["scanner"] == "pip-audit" for row in rows),
        },
    }
    body = {
        "scannerVersions": {row["id"]: row["version"] for row in SCAN_ALLOWLIST["scanners"]},
        "scannerExitCodes": {
            "bandit": 1,
            "pip-audit": 1 if summaries["pip-audit"]["findingCount"] else 0,
        },
        "scanInputs": [
            {"path": path, "objectId": git("rev-parse", f"HEAD:{path}")} for path in SCOPE
        ],
        "summaries": summaries,
        "auditedDependencies": copy.deepcopy(AUDITED),
        "scannedPythonFiles": list(SCANNED_FILES),
        "criticalHighFindings": rows,
        "criticalCount": sum(row["severity"] == "CRITICAL" for row in rows),
        "highCount": sum(row["severity"] == "HIGH" for row in rows),
        "unallowlistedFindingIds": sorted(row["findingId"] for row in rows),
        "expiredFindingIds": [],
        "staleAllowlistFindingIds": [],
        "severityMismatchFindingIds": [],
    }
    body.update(over)
    return body


def producer_report(body: dict | None = None, **over) -> dict:
    body = payload() if body is None else body
    report = {
        "schemaVersion": "1.0.0",
        "runPurpose": "s11-ac11-security-scan",
        "threatId": "SEC-SCAN-001",
        "sourceRunId": RUN_ID,
        "sourceHeadSha": SOURCE,
        "checkoutTreeSha": TREE,
        "cleanCheckout": True,
        "startedAt": "2026-10-02T02:50:00Z",
        "finishedAt": "2026-10-02T02:52:46Z",
        "environment": copy.deepcopy(PRODUCER_ENVIRONMENT),
        "reportAvailable": True,
        "status": "complete",
        "allowlist": {
            "path": tool.SCAN_ALLOWLIST_REPO_PATH,
            "blob": git("hash-object", tool.SCAN_ALLOWLIST_REPO_PATH),
        },
        "toolFiles": tool_files(),
        "payloadSha256": tool._canonical_sha256(body),
        "payload": body,
        "verdict": "MEASURED_PASS",
        "failureClass": "NONE",
        "cleanup": {"residueCount": 0},
    }
    report.update(over)
    return report


APPROVED_ALLOWLIST = json.loads(
    (ROOT / aggregator.ALLOWLIST_REPO_PATH).read_text(encoding="utf-8")
)


def definer_report(**over) -> dict:
    """A SEC-DEF-001 report the canonical evaluator admits.

    ``evaluate_definer``'s exit-0 branch requires the observed privileged-function set to equal
    the reviewed signature list **exactly**, so the fixture observes those twelve and nothing
    else.  The tree's own database has fifteen, which is the review gap card 221 measured and
    did not close.
    """

    document = {
        "threatId": "SEC-DEF-001",
        "sourceRunId": RUN_ID,
        "sourceHeadSha": SOURCE,
        "checkoutTreeSha": TREE,
        "toolFiles": [dict(row) for row in aggregator.DEFINER_FILES],
        "status": "matches_reviewed_policy",
        "functions": [
            {"function": signature, "problems": []}
            for signature in APPROVED_ALLOWLIST["definerPolicySignatures"]
        ],
        "unsafe": 0,
        "exitCode": 0,
    }
    document.update(over)
    return document


def rls_report(**over) -> dict:
    """A SEC-RLS-001 report the canonical evaluator admits."""

    document = {
        "threatId": "SEC-RLS-001",
        "sourceRunId": RUN_ID,
        "sourceHeadSha": SOURCE,
        "checkoutTreeSha": TREE,
        "toolFiles": [dict(row) for row in aggregator.RLS_FILES],
        "baselineAccepted": [
            {"role": entry["role"], "table": entry["table"], "rules": list(entry["rules"])}
            for entry in APPROVED_ALLOWLIST["rlsAcceptedDispositions"]
        ],
        "exitCode": 0,
        "verdict": "PASS",
        "violations": [],
        "accepted": [],
        "unmeasured": [],
        "roles": {"inv_app": {"present": True}},
        "ground_truth": {"public.projects": {"tenantScoped": True}},
    }
    document.update(over)
    return document


def vf_evidence(**over) -> dict:
    """What the browser lane's own proof carries, measured from a real run of that lane."""

    spec = APPROVED_ALLOWLIST["secVf001"]
    document = {
        "exitCode": 0,
        "subprocessExitCode": 0,
        "evidenceStatus": "complete",
        "caseIdentitiesSha256": spec["requiredCaseIdentitiesSha256"],
        "tests": dict(spec["expectedTests"]),
    }
    document.update(over)
    return document


def archive(
    report: dict | None = None,
    extra: str | None = None,
    database: tuple[dict, dict] | None = None,
) -> bytes:
    report = producer_report() if report is None else report
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
        members = [
            (tool.REPORT_MEMBER, json.dumps(report).encode()),
            (tool.JUNIT_MEMBER, b'<testsuite tests="4" failures="0"/>'),
        ]
        if database is not None:
            members.append((tool.DEFINER_MEMBER, json.dumps(database[0]).encode()))
            members.append((tool.RLS_MEMBER, json.dumps(database[1]).encode()))
        for name, content in members:
            info = zipfile.ZipInfo(name, (2026, 10, 2, 2, 52, 46))
            bundle.writestr(info, content)
        if extra is not None:
            bundle.writestr(extra, b"unexpected")
    return output.getvalue()


def metadata(payload_bytes: bytes) -> tuple[dict, dict]:
    run = {
        "id": int(RUN_ID),
        "status": "completed",
        "conclusion": "success",
        "head_sha": SOURCE,
        "event": "pull_request",
        "path": f"{tool.WORKFLOW_PATH}@refs/pull/226/merge",
        "repository": {"full_name": tool.REPOSITORY},
    }
    artifact = {
        "id": int(ARTIFACT_ID),
        "name": f"s11-ac11-security-{SOURCE}",
        "expired": False,
        "expires_at": "2026-10-31T23:58:54Z",
        "digest": "sha256:" + hashlib.sha256(payload_bytes).hexdigest(),
        "workflow_run": {"id": int(RUN_ID), "head_sha": SOURCE},
    }
    return run, artifact


def imported(report: dict | None = None, database=None, vf=None):
    blob = archive(report, database=database)
    run_metadata, artifact_metadata = metadata(blob)
    return tool.import_evidence(
        blob, run_metadata, artifact_metadata, now=NOW, vf_evidence=vf
    )


def test_import_binds_run_artifact_digest_and_member_hashes():
    blob = archive()
    run, artifact = metadata(blob)
    result = tool.import_evidence(blob, run, artifact, now=NOW)
    binding = result["scanArtifact"]
    assert binding["runId"] == RUN_ID
    assert binding["artifactId"] == ARTIFACT_ID
    assert binding["digest"] == hashlib.sha256(blob).hexdigest()
    assert binding["observedDigest"] == binding["digest"]
    assert len(binding["producerReportSha256"]) == 64
    assert len(binding["junitSha256"]) == 64


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda run, artifact: artifact.update(digest="sha256:" + "0" * 64), "digest"),
        (lambda run, artifact: artifact.update(expired=True), "expired"),
        (lambda run, artifact: run.update(conclusion="failure"), "successfully"),
        (lambda run, artifact: run.update(head_sha="f" * 40), "sourceHeadSha"),
        (lambda run, artifact: run.update(id=1), "sourceRunId"),
        (
            lambda run, artifact: run["repository"].update(full_name="fork/example"),
            "canonical",
        ),
        (lambda run, artifact: run.update(path=".github/workflows/other.yml"), "workflow"),
    ],
)
def test_import_rejects_untrusted_github_metadata(mutate, message):
    blob = archive()
    run, artifact = metadata(blob)
    mutate(run, artifact)
    with pytest.raises(tool.SecurityImportError, match=message):
        tool.import_evidence(blob, run, artifact, now=NOW)


def test_import_rejects_missing_source_run_and_non_exact_archive():
    blob = archive({"sourceHeadSha": SOURCE})
    run, artifact = metadata(blob)
    with pytest.raises(tool.SecurityImportError, match="sourceRunId"):
        tool.import_evidence(blob, run, artifact, now=NOW)

    blob = archive(extra="../outside")
    run, artifact = metadata(blob)
    with pytest.raises(tool.SecurityImportError, match="member set"):
        tool.import_evidence(blob, run, artifact, now=NOW)


def test_the_envelope_is_admissible_and_names_the_threat_reports_it_lacks():
    """Card 216: the adapter's verdict is the one the aggregator will recompute.

    Only SEC-SCAN-001 has a producer in this repository.  The aggregator requires four
    threat reports and answers NOT_OBSERVED when any is missing, so the envelope says the
    same thing -- otherwise a partial scan would be read as a pass and the run would be
    INVALID_RUN for contradicting itself.
    """

    envelope = imported()
    assert envelope["runPurpose"] == "ac11-axis-evidence"
    assert envelope["axis"] == "security-critical-high-zero"
    assert envelope["verdict"] == "NOT_OBSERVED"
    assert envelope["reason"] == (
        "no admissible report for SEC-DEF-001, SEC-RLS-001, SEC-VF-001"
    )
    assert [row["threatId"] for row in envelope["observations"]] == ["SEC-SCAN-001"]
    assert envelope["threatReportVerdicts"] == {"SEC-SCAN-001": "MEASURED_PASS"}
    assert envelope["targetRef"]["targetId"] == "s11-security-critical-high-zero-v0"
    assert envelope["artifactSha256"] == envelope["artifactObservedSha256"]
    assert envelope["artifactAvailable"] is True
    assert envelope["scanRecomputed"] == "MEASURED_PASS"


#: Paths this test answers from the working tree rather than from the commit.  The envelope is
#: bound to the importer that is *executing* and to the reviewed allowlist this checkout holds;
#: while a change is uncommitted those are the working files, not the committed ones.  Pinning
#: them from disk keeps this test about the question it asks -- is the envelope admissible --
#: and each binding is measured by its own test below.
CHECKOUT_ANSWERED = (tool.IMPORTER_REPO_PATH, aggregator.ALLOWLIST_REPO_PATH)


class CheckoutGit(aggregator.RepositoryGit):
    """The repository, answering two questions about this checkout instead of the commit."""

    def blob(self, commit: str, path: str) -> str:
        if path in CHECKOUT_ANSWERED:
            return git("hash-object", path)
        return super().blob(commit, path)


def test_the_envelope_this_adapter_writes_is_admissible_to_the_aggregator():
    """#313 F-R1: the whole chain, importer -> evaluate_axis, against the real repository.

    r1's envelope carried the producer's environment unchanged, so it reached the aggregator
    without a comparability group and was refused at the common-envelope stage with
    ``environment.comparableGroup is required`` -- INVALID_RUN, which is not an admissible
    envelope however complete the chain looks in the map.  NOT_OBSERVED is: the axis is
    evaluated and says what it lacks.
    """

    envelope = imported()
    result = aggregator.evaluate_axis(envelope, CheckoutGit(ROOT), {}, NOW)
    assert result.verdict is aggregator.Verdict.NOT_OBSERVED, result.reasons


def test_the_importer_declares_the_lane_comparability_group_the_producer_omits():
    envelope = imported()
    assert envelope["environment"]["comparableGroup"] == tool.COMPARABLE_GROUP
    # The producer's own description of the run survives next to it rather than being
    # replaced by the label.
    assert envelope["environment"]["runnerImage"] == "Linux-X64"
    assert envelope["environment"]["externalServicesRequired"] is True


def test_an_environment_outside_the_registered_lane_is_refused_not_relabelled():
    """A comparability group is a claim about how the run was produced.

    The registry requires ``topology: hosted`` and ``evidenceClass: security-tools-v0`` for
    this target, so a report from anywhere else is refused instead of being stamped
    comparable with runs that satisfy the requirement.
    """

    for field, value in (("topology", "physical-five-node"), ("evidenceClass", "other-v9")):
        report = producer_report()
        report["environment"][field] = value
        with pytest.raises(tool.SecurityImportError, match="registered requirement"):
            imported(report)


def test_a_producer_comparability_group_that_disagrees_is_refused():
    report = producer_report()
    report["environment"]["comparableGroup"] = "something-else"
    with pytest.raises(tool.SecurityImportError, match="different comparability group"):
        imported(report)


def test_four_threat_rows_with_nothing_measured_still_cannot_become_a_pass():
    """#313 F-R2, held by a different mechanism after card 221.

    r1 of #313 turned four empty rows and a top-level claim into MEASURED_PASS; the fix then
    was to refuse any report this importer could not recompute.  Card 221 gives it the
    aggregator's own evaluators instead, which is strictly stronger: the empty rows are now
    *evaluated*, refused by name, and the envelope says NOT_OBSERVED -- the one thing that must
    never happen, a pass, still cannot.
    """

    report = producer_report(
        observations=[
            {"threatId": "SEC-DEF-001"},
            {"threatId": "SEC-RLS-001"},
            {"threatId": "SEC-VF-001"},
            producer_report(),
        ],
    )
    envelope = imported(report)
    assert envelope["verdict"] == "NOT_OBSERVED"
    for threat_id in ("SEC-DEF-001", "SEC-RLS-001", "SEC-VF-001"):
        assert f"{threat_id} (INVALID_RUN)" in envelope["reason"]
    assert [row["threatId"] for row in envelope["observations"]] == ["SEC-SCAN-001"]


def test_the_four_measured_reports_recompute_a_pass_and_the_envelope_says_so():
    """Card 221: the axis can reach a verdict, and the verdict is the evaluators' own.

    Every report here is one the canonical evaluator admits, so the envelope carries four
    observations and MEASURED_PASS.  This is the shape the lane produces once the three review
    gaps card 221 measured are closed; the importer needs no further change for it.
    """

    envelope = imported(
        database=(definer_report(), rls_report()),
        vf=vf_evidence(),
    )
    assert envelope["verdict"] == "MEASURED_PASS"
    assert "reason" not in envelope
    assert sorted(row["threatId"] for row in envelope["observations"]) == [
        "SEC-DEF-001", "SEC-RLS-001", "SEC-SCAN-001", "SEC-VF-001",
    ]
    assert envelope["threatReportVerdicts"] == {
        "SEC-DEF-001": "MEASURED_PASS",
        "SEC-RLS-001": "MEASURED_PASS",
        "SEC-SCAN-001": "MEASURED_PASS",
        "SEC-VF-001": "MEASURED_PASS",
    }


def test_an_unobserved_database_report_keeps_the_axis_unobserved_and_names_it():
    """The honest middle: the boundary was measured and one row could not be verified."""

    unmeasured = rls_report(
        exitCode=3,
        verdict="UNMEASURED",
        unmeasured=[{"role": "inv_cancel_bridge_owner", "table": "public.audit_events",
                     "rule": "E4", "detail": "row identity unverifiable"}],
    )
    envelope = imported(database=(definer_report(), unmeasured), vf=vf_evidence())
    assert envelope["verdict"] == "NOT_OBSERVED"
    assert "SEC-RLS-001 recomputes NOT_OBSERVED" in envelope["reason"]
    assert envelope["threatReportVerdicts"]["SEC-DEF-001"] == "MEASURED_PASS"


def test_a_measured_database_failure_is_carried_as_a_failure():
    """A verdict is not lowered: a violation makes the axis MEASURED_FAIL."""

    violated = rls_report(
        exitCode=1,
        verdict="VIOLATIONS",
        violations=[{"role": "inv_app", "table": "public.audit_events", "rule": "E2",
                     "detail": "tenant-scoped readable table without enabled+forced RLS"}],
    )
    envelope = imported(database=(definer_report(), violated), vf=vf_evidence())
    assert envelope["verdict"] == "MEASURED_FAIL"
    assert "SEC-RLS-001 recomputes MEASURED_FAIL" in envelope["reason"]


def test_a_database_report_from_another_run_is_refused():
    """One envelope, one run: a report about another run is not this artifact's evidence."""

    with pytest.raises(tool.SecurityImportError, match="differs from the scan report"):
        imported(database=(definer_report(sourceRunId="36000000000"), rls_report()))
    with pytest.raises(tool.SecurityImportError, match="differs from the scan report"):
        imported(database=(definer_report(), rls_report(sourceHeadSha="f" * 40)))


def test_a_database_member_that_carries_the_wrong_threat_is_refused():
    with pytest.raises(tool.SecurityImportError, match="does not carry SEC-DEF-001"):
        imported(database=(rls_report(), rls_report()))


@pytest.mark.parametrize(
    "mutation",
    [
        {"caseIdentitiesSha256": "0" * 64},
        {"tests": {"failure": 0, "error": 0, "skipped": 0, "passed": 5}},
        {"evidenceStatus": "partial"},
        {"exitCode": 1},
        {"subprocessExitCode": 1},
    ],
    ids=["identity-hash", "case-count", "evidence-status", "exit-code", "subprocess-exit"],
)
def test_browser_lane_evidence_that_is_not_the_reviewed_one_is_refused(mutation):
    """SEC-VF-001 is only written when the reviewed identity hash and counts are the measured
    ones -- ``nodeIds`` alone is a tautology against ``requiredNodeIds``, so the hash is the
    binding that matters."""

    with pytest.raises(tool.SecurityImportError, match="reviewed"):
        imported(database=(definer_report(), rls_report()), vf=vf_evidence(**mutation))


def test_browser_lane_evidence_about_another_head_is_refused():
    with pytest.raises(tool.SecurityImportError, match="another source head"):
        imported(
            database=(definer_report(), rls_report()),
            vf=vf_evidence(sourceHeadSha="f" * 40),
        )


def test_the_vf_report_pins_the_five_reviewed_files():
    envelope = imported(database=(definer_report(), rls_report()), vf=vf_evidence())
    vf = [row for row in envelope["observations"] if row["threatId"] == "SEC-VF-001"][0]
    spec = APPROVED_ALLOWLIST["secVf001"]
    expected = [spec["runner"], spec["workflow"], spec["nodeDependencyResolver"], *spec["testFiles"]]
    assert vf["toolFiles"] == [dict(row) for row in expected]
    assert sorted(vf["nodeIds"]) == sorted(spec["requiredNodeIds"])


def test_a_scan_verdict_that_contradicts_its_own_payload_is_refused():
    body = payload(finding("GHSA-0001", "CRITICAL"))
    report = producer_report(body)
    report["verdict"] = "MEASURED_PASS"
    with pytest.raises(tool.SecurityImportError, match="recomputes MEASURED_FAIL"):
        imported(report)


def test_a_finding_row_the_counts_do_not_admit_is_refused():
    """#313 r2 N1, probe 1: a HIGH row with ``highCount: 0`` recomputed MEASURED_PASS.

    The counts are the axis's claim -- "critical and high are zero" -- so they are recomputed
    from the rows.  r1 read the counts and the inventory lengths only, so a payload carrying a
    finding nobody counted passed, and the reason called that scan a success.
    """

    body = payload(finding("GHSA-0001", "HIGH"))
    body["criticalCount"] = 0
    body["highCount"] = 0
    body["unallowlistedFindingIds"] = []
    report = producer_report(body, verdict="MEASURED_PASS", failureClass="NONE")
    with pytest.raises(tool.SecurityImportError, match="contradicts itself"):
        imported(report)


def _empty_bandit_coverage(body: dict) -> None:
    body["scannedPythonFiles"] = []
    body["summaries"]["bandit"] = {
        "lowFindingCount": 0, "mediumFindingCount": 0,
        "highFindingCount": 0, "scannedFileCount": 0,
    }
    body["scannerExitCodes"]["bandit"] = 0


def _empty_pip_audit_coverage(body: dict) -> None:
    body["auditedDependencies"] = []
    body["summaries"]["pip-audit"] = {"dependencyCount": 0, "findingCount": 0}


@pytest.mark.parametrize(
    "empty",
    [
        _empty_bandit_coverage,
        _empty_pip_audit_coverage,
        lambda body: (_empty_bandit_coverage(body), _empty_pip_audit_coverage(body)),
    ],
    ids=["bandit-read-no-files", "pip-audit-read-no-dependencies", "both-probe-2"],
)
def test_a_scan_that_read_nothing_is_not_a_pass(empty):
    """#313 r2 N1, probe 2: zero scanned files and zero audited dependencies passed.

    Coverage of nothing is not evidence that nothing is wrong, and the canonical evaluator
    refuses an empty inventory for exactly that reason.  Each scanner is emptied on its own as
    well as together, because a check that only one of the two cases can reach is a check the
    other case does not have.
    """

    body = payload()
    empty(body)
    report = producer_report(body, verdict="MEASURED_PASS", failureClass="NONE")
    with pytest.raises(tool.SecurityImportError, match="contradicts itself"):
        imported(report)


def test_a_summary_that_disagrees_with_the_finding_rows_is_refused():
    """The per-scanner summaries and the rows are the same scan, so they must agree."""

    body = payload(finding("GHSA-0001", "HIGH"))
    body["summaries"]["bandit"]["highFindingCount"] = 0
    report = producer_report(body, verdict="MEASURED_FAIL",
                             failureClass="UNALLOWLISTED_CRITICAL_HIGH")
    with pytest.raises(tool.SecurityImportError, match="contradicts itself"):
        imported(report)


def test_the_importer_and_the_aggregator_recompute_the_payload_with_one_function():
    """#313 r2 N1: two validators of one claim drift, so there is one of them.

    The canonical function is the aggregator's; the importer calls it rather than keeping a
    shorter list of its own, which is what let the two disagree about the same bytes.
    """

    from aggregate_ac11_evidence import scan_payload_invariants

    assert tool.scan_payload_invariants is scan_payload_invariants
    findings, broken = scan_payload_invariants(payload(finding("GHSA-0001")))
    assert broken == () and list(findings) == ["GHSA-0001"]


def test_a_measured_failure_is_carried_with_the_recomputed_detail_rather_than_hidden():
    """The aggregator cannot see past the three missing reports, so the envelope says it.

    The verdict stays NOT_OBSERVED because that is what the aggregator recomputes from the
    same absence; the reason carries what the scan itself measured, so a failing scan is not
    laundered into "not observed" with nothing to read.
    """

    body = payload(
        finding("GHSA-0001", "CRITICAL"),
        finding("GHSA-0002", "CRITICAL"),
        finding("GHSA-0003", "HIGH"),
    )
    envelope = imported(
        producer_report(body, verdict="MEASURED_FAIL", failureClass="UNALLOWLISTED_CRITICAL_HIGH")
    )
    assert envelope["verdict"] == "NOT_OBSERVED"
    assert envelope["scanRecomputed"] == "MEASURED_FAIL"
    assert "recomputes MEASURED_FAIL" in envelope["reason"]
    assert "criticalCount=2" in envelope["reason"] and "highCount=1" in envelope["reason"]


def test_an_unallowlisted_finding_is_a_measured_failure():
    """The reviewed allowlist accepts nothing, so any finding at all is unallowlisted."""

    body = payload(finding("GHSA-0001", "HIGH"))
    envelope = imported(
        producer_report(body, verdict="MEASURED_FAIL", failureClass="UNALLOWLISTED_CRITICAL_HIGH")
    )
    assert envelope["scanRecomputed"] == "MEASURED_FAIL"
    assert "unallowlistedFindingIds=1" in envelope["reason"]


def test_a_scanner_exit_code_that_contradicts_its_summary_is_refused():
    """The exit codes are derived from the summaries, so one missing or wrong is a refusal.

    r1 answered NOT_OBSERVED here.  A *complete* report whose payload disagrees with itself is
    not an unobserved scan, it is evidence nobody can read -- the producer's own unavailable
    path is the one that means "not observed", and it is answered above.
    """

    for exits in ({"bandit": 1}, {"bandit": 0, "pip-audit": 0}):
        body = payload(scannerExitCodes=exits)
        report = producer_report(body, verdict="MEASURED_PASS", failureClass="NONE")
        with pytest.raises(tool.SecurityImportError, match="contradicts itself"):
            imported(report)


def test_an_unavailable_scan_report_is_not_a_pass():
    envelope = imported(
        producer_report(
            status="unavailable",
            reportAvailable=False,
            verdict="NOT_OBSERVED",
            failureClass="SCANNER_UNAVAILABLE",
        )
    )
    assert envelope["scanRecomputed"] == "NOT_OBSERVED"
    assert "reports the scan as" in envelope["reason"]


def test_a_payload_digest_that_does_not_cover_the_payload_is_refused():
    report = producer_report()
    report["payload"]["criticalCount"] = 0
    report["payloadSha256"] = "0" * 64
    with pytest.raises(tool.SecurityImportError, match="payloadSha256"):
        imported(report)


def test_a_complete_scan_report_without_a_payload_is_refused():
    report = producer_report()
    report.pop("payload")
    with pytest.raises(tool.SecurityImportError, match="no payload to recompute"):
        imported(report)


def test_an_artifact_pinned_to_a_different_importer_blob_is_refused():
    """#313 F-R3: the probe, as a test.

    The real artifact of run 36943527856 pins importer blob ``8661753330`` while the tree it
    checked out carries ``a5be99df1d``, so the envelope r1 measured was written by an
    importer that does not exist at its own ``sourceHeadSha``.  An adapter the source tree
    does not pin does not get to write evidence about that tree.
    """

    report = producer_report(toolFiles=tool_files("8661753330" + "0" * 30))
    with pytest.raises(tool.SecurityImportError, match="different importer blob"):
        imported(report)


def test_an_artifact_that_names_another_allowlist_is_refused():
    report = producer_report(allowlist={"path": "docs/other.json", "blob": "0" * 40})
    with pytest.raises(tool.SecurityImportError, match="reviewed scan allowlist"):
        imported(report)


def test_the_envelope_records_the_importer_blob_that_wrote_it():
    envelope = imported()
    assert envelope["importerFile"] == {
        "path": tool.IMPORTER_REPO_PATH,
        "blob": tool.importer_blob(),
    }
    assert tool.importer_blob() == git("hash-object", tool.IMPORTER_REPO_PATH)


def test_the_scan_allowlist_pins_the_files_this_checkout_actually_has():
    """#313 F-R3: a stale pin is an INVALID_RUN waiting for the missing producers.

    Every report copies these three pins into ``toolFiles`` and the aggregator refuses a
    report whose pins differ from the source tree -- but only once all four threat reports
    exist, which is why the drift stayed invisible.  ``0f614152`` moved the workflow and
    ``8933b6bd`` moved this importer while the pins stayed where they were.
    """

    for key in ("producer", "workflow", "importer"):
        row = SCAN_ALLOWLIST[key]
        assert row["blob"] == git("hash-object", row["path"]), f"{key} pin is stale"
    assert aggregator.SCAN_ALLOWLIST_BLOB == git(
        "hash-object", tool.SCAN_ALLOWLIST_REPO_PATH
    ), "the aggregator pins a different allowlist than this checkout has"


def test_an_unregistered_threat_id_is_refused_rather_than_carried():
    report = producer_report(
        observations=[{"threatId": "SEC-INVENTED-001"}],
    )
    with pytest.raises(tool.SecurityImportError, match="unregistered security threat id"):
        imported(report)
