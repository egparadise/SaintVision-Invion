"""PG-free mutation tests for AC-11 user-device accessibility import."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import aggregate_ac11_evidence as aggregate  # noqa: E402
import collect_ac11_accessibility_e2e as collector  # noqa: E402
import import_ac11_accessibility_evidence as tool  # noqa: E402


SOURCE = "a" * 40
TREE = "b" * 40
RUN_ID = "36990000000"
NOW = datetime(2026, 10, 2, 1, 0, tzinfo=timezone.utc)


def _observations() -> list[dict]:
    return [
        collector._observation(metric, 1, 1 if metric == "manualAcceptanceMissingCount" else 0,
                               "manual-acceptance-not-supplied" if metric == "manualAcceptanceMissingCount" else "unused")
        for metric in collector.CRITERIA
    ]


def _producer() -> dict:
    payload = {
        "journeyIds": sorted(collector.EXPECTED_JOURNEYS),
        "browserPhysicalCaseCount": 6,
        "invariantIds": sorted(collector.EXPECTED_INVARIANTS),
        "inputDigests": {},
        "observations": _observations(),
    }
    return {
        "schemaVersion": collector.SCHEMA_VERSION,
        "runPurpose": collector.RUN_PURPOSE,
        "axis": collector.AXIS,
        "sourceRunId": RUN_ID,
        "sourceHeadSha": SOURCE,
        "checkoutTreeSha": TREE,
        "cleanCheckout": True,
        "startedAt": "2026-10-02T00:00:00Z",
        "finishedAt": "2026-10-02T00:20:00Z",
        "environment": {"runnerImage": "ubuntu", "browser": "Chrome 140"},
        "targetRef": {
            "commit": collector.TARGET_COMMIT,
            "path": collector.TARGET_PATH,
            "blob": collector.TARGET_BLOB,
            "criteria": collector.CRITERIA,
        },
        "verdict": "MEASURED_FAIL",
        "acceptanceClaim": False,
        "payload": payload,
        "payloadSha256": collector.canonical_sha256(payload),
    }


def _archive(report: dict | None = None) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as bundle:
        bundle.writestr(tool.REPORT_MEMBER, json.dumps(report or _producer()))
        bundle.writestr(tool.JUNIT_MEMBER, "<testsuite tests='5'/>")
    return stream.getvalue()


def _metadata(archive: bytes) -> tuple[dict, dict]:
    run = {
        "id": int(RUN_ID),
        "status": "completed",
        "conclusion": "success",
        "head_sha": SOURCE,
        "repository": {"full_name": tool.REPOSITORY},
        "path": tool.WORKFLOW_PATH + "@refs/heads/feature",
        "event": "workflow_dispatch",
    }
    artifact = {
        "id": 10990000000,
        "name": f"s11-ac11-accessibility-{SOURCE}",
        "expired": False,
        "expires_at": "2026-11-01T00:00:00Z",
        "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
        "workflow_run": {"id": int(RUN_ID), "head_sha": SOURCE},
    }
    return run, artifact


def _manual() -> dict:
    return {
        "schemaVersion": "1.0.0",
        "runPurpose": tool.MANUAL_PURPOSE,
        "sourceHeadSha": SOURCE,
        "startedAt": "2026-10-02T00:30:00Z",
        "finishedAt": "2026-10-02T00:45:00Z",
        "device": {
            "class": "desktop",
            "operatingSystem": "Windows 11",
            "displayMode": "standard",
            "keyboard": "physical",
        },
        "browser": {"name": "Edge", "version": "140", "engine": "Blink"},
        "assistiveTechnologies": [
            {"kind": "screen-reader", "product": "NVDA", "version": "2026.1"}
        ],
        "scenarios": [
            {"scenarioId": name, "result": "PASS"}
            for name in sorted(tool.EXPECTED_SCENARIOS)
        ],
        "overallResult": "PASS",
        "performedBy": {"kind": "human", "binding": "self-attested-session"},
    }


def _receipt_value() -> dict:
    return {
        "kind": "human",
        "binding": "oidc-fresh-auth-v1",
        "subjectSha256": "1" * 64,
        "tenantSha256": "2" * 64,
        "issuerSha256": "3" * 64,
        "clientIdSha256": "4" * 64,
        "authTime": int(NOW.timestamp()),
        "amr": ["mfa"],
        "tokenExpiresAt": int(NOW.timestamp()) + 300,
        "jwksSha256": "5" * 64,
        "verifiedAt": "2026-10-02T01:00:00Z",
    }


def _receipt(**changes):
    value = _receipt_value()
    value.update(changes)
    return tool._seal_performer_receipt(value, NOW)


def _import(*, manual: dict | None = None, receipt=None, run_mutation=None,
            artifact_mutation=None) -> dict:
    archive = _archive()
    run, artifact = _metadata(archive)
    if run_mutation:
        run_mutation(run)
    if artifact_mutation:
        artifact_mutation(artifact)
    return tool.import_evidence(
        archive,
        run,
        artifact,
        manual_session=manual,
        performer_receipt=receipt,
        now=NOW,
    )


def test_absent_manual_record_remains_fail_closed():
    result = _import()
    observations = {row["metric"]: row for row in result["observations"]}
    assert result["verdict"] == "MEASURED_FAIL"
    assert observations["manualAcceptanceMissingCount"]["value"] == 1
    assert result["manualAcceptance"] is None


def test_exact_sha_fresh_human_record_is_the_only_path_to_zero():
    result = _import(manual=_manual(), receipt=_receipt())
    observations = {row["metric"]: row for row in result["observations"]}
    assert result["verdict"] == "MEASURED_PASS"
    assert observations["manualAcceptanceMissingCount"] == collector._observation(
        "manualAcceptanceMissingCount", 1, 0, "manual-acceptance-failed"
    )
    assert result["manualAcceptance"]["importAuthorizationReceipt"]["binding"] == "oidc-fresh-auth-v1"
    assert "opaque-not-persisted" not in json.dumps(result)


@pytest.mark.parametrize("mutation", ["fake-sha", "missing-scenario", "extra-key", "duplicate-scenario"])
def test_manual_schema_and_identity_mutations_are_rejected(mutation: str):
    manual = _manual()
    if mutation == "fake-sha":
        manual["sourceHeadSha"] = "c" * 40
    elif mutation == "missing-scenario":
        manual["scenarios"].pop()
    elif mutation == "extra-key":
        manual["secret"] = "must-not-be-accepted"
    else:
        manual["scenarios"][-1] = copy.deepcopy(manual["scenarios"][0])
    with pytest.raises(tool.AccessibilityImportError):
        _import(manual=manual, receipt=_receipt())


def test_measured_manual_failure_cannot_become_pass():
    manual = _manual()
    manual["scenarios"][0]["result"] = "FAIL"
    manual["overallResult"] = "FAIL"
    result = _import(manual=manual, receipt=_receipt())
    observation = next(
        row for row in result["observations"] if row["metric"] == "manualAcceptanceMissingCount"
    )
    assert result["verdict"] == "MEASURED_FAIL"
    assert observation["errorsByClass"] == {"manual-acceptance-failed": 1}


def test_forged_or_stale_performer_receipt_is_rejected():
    with pytest.raises(tool.AccessibilityImportError, match="subjectSha256"):
        _receipt(subjectSha256="not-a-digest")
    with pytest.raises(tool.AccessibilityImportError, match="stale"):
        _receipt(verifiedAt="2026-10-01T01:00:00Z")


def test_handwritten_receipt_cannot_create_a_pass():
    with pytest.raises(tool.AccessibilityImportError, match="fresh token verification"):
        _import(manual=_manual(), receipt=_receipt_value())


def test_manual_session_must_follow_hosted_run_and_fresh_auth_must_follow_session():
    manual = _manual()
    manual["startedAt"] = "2026-10-02T00:19:59Z"
    with pytest.raises(tool.AccessibilityImportError, match="predates the hosted"):
        _import(manual=manual, receipt=_receipt())
    with pytest.raises(tool.AccessibilityImportError, match="after the manual session"):
        _import(manual=_manual(), receipt=_receipt(authTime=int(NOW.timestamp()) - 3600))


@pytest.mark.parametrize(
    "value",
    ["2026-10-02 00:30:00Z", "2026-10-02T00:30:00+00:00", "2026-10-02T00:30:00", "2026-10-02T00:30:00.1234567Z"],
)
def test_manual_timestamps_are_strict_utc_rfc3339(value: str):
    manual = _manual()
    manual["startedAt"] = value
    with pytest.raises(tool.AccessibilityImportError, match="strict UTC RFC3339"):
        _import(manual=manual, receipt=_receipt())


def test_manual_lower_bound_placeholder_duplicate_and_non_string_identity_are_rejected():
    mutations = []
    placeholder = _manual(); placeholder["browser"]["name"] = "replace_with_browser"; mutations.append(placeholder)
    todo = _manual(); todo["device"]["operatingSystem"] = "TODO"; mutations.append(todo)
    duplicate = _manual(); duplicate["assistiveTechnologies"].append(copy.deepcopy(duplicate["assistiveTechnologies"][0])); mutations.append(duplicate)
    wrong_type = _manual(); wrong_type["scenarios"][0]["scenarioId"] = ["not", "a", "string"]; mutations.append(wrong_type)
    for manual in mutations:
        with pytest.raises(tool.AccessibilityImportError):
            _import(manual=manual, receipt=_receipt())


def test_registered_manual_time_lower_bound_is_independent_of_hosted_provenance():
    manual = _manual()
    manual["startedAt"] = "2026-10-01T23:59:59Z"
    with pytest.raises(tool.AccessibilityImportError, match="predates the registered target"):
        tool.validate_manual_session(manual, SOURCE)


@pytest.mark.parametrize(
    ("run_mutation", "artifact_mutation"),
    [
        (lambda row: row.__setitem__("head_sha", "c" * 40), None),
        (None, lambda row: row["workflow_run"].__setitem__("head_sha", "c" * 40)),
        (None, lambda row: row.__setitem__("digest", "sha256:" + "0" * 64)),
        (None, lambda row: row.__setitem__("expired", True)),
        (None, lambda row: row.__setitem__("expires_at", "2026-10-01T00:00:00Z")),
        (lambda row: row.__setitem__("path", "wrong.yml@refs/heads/x"), None),
        (lambda row: row.__setitem__("event", "push"), None),
    ],
)
def test_provenance_mutations_are_rejected(run_mutation, artifact_mutation):
    with pytest.raises(tool.AccessibilityImportError):
        _import(manual=_manual(), receipt=_receipt(), run_mutation=run_mutation,
                artifact_mutation=artifact_mutation)


def test_future_manual_finished_at_is_rejected():
    manual = _manual()
    manual["finishedAt"] = "2026-10-02T01:00:01Z"
    with pytest.raises(tool.AccessibilityImportError, match="future"):
        _import(manual=manual, receipt=_receipt())


def test_duplicate_json_key_is_rejected(tmp_path: Path):
    path = tmp_path / "manual.json"
    path.write_text('{"schemaVersion":"1.0.0","schemaVersion":"2.0.0"}', encoding="utf-8")
    with pytest.raises(tool.AccessibilityImportError, match="duplicate key"):
        tool._json_file(path, "manual session")


def test_product_verifier_and_canonical_fresh_auth_are_used(tmp_path: Path):
    jwks = tmp_path / "jwks.json"
    jwks.write_text("{}", encoding="utf-8")
    identity = SimpleNamespace(
        principal=SimpleNamespace(
            tenant_id="11111111-1111-1111-1111-111111111111",
            subject_id="oidc:" + "a" * 64,
        ),
        expires_at=int(NOW.timestamp()) + 300,
        auth_time=int(NOW.timestamp()),
        amr=("mfa",),
        issuer="https://idp.example/realms/saintvision",
        client_id="saintvision-web",
    )
    verifier = SimpleNamespace(verify=lambda token: identity)
    receipt = tool.verify_human_token(
        "opaque-not-persisted",
        tenant_id=identity.principal.tenant_id,
        issuer=identity.issuer,
        audience="saintvision-api",
        client_id=identity.client_id,
        jwks_file=jwks,
        now=NOW,
        token_verifier=verifier,
    )
    assert receipt.value["binding"] == "oidc-fresh-auth-v1"
    identity.amr = ("pwd",)
    with pytest.raises(tool.AccessibilityImportError, match="fresh interactive"):
        tool.verify_human_token(
            "opaque-not-persisted",
            tenant_id=identity.principal.tenant_id,
            issuer=identity.issuer,
            audience="saintvision-api",
            client_id=identity.client_id,
            jwks_file=jwks,
            now=NOW,
            token_verifier=verifier,
        )


class _Git:
    def tree(self, commit: str) -> str:
        assert commit == SOURCE
        return TREE

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return descendant == SOURCE and ancestor in {tool.REGISTRY_COMMIT, collector.TARGET_COMMIT}

    def blob(self, commit: str, path: str) -> str:
        if path == tool.REGISTRY_PATH:
            return tool.REGISTRY_BLOB
        if path == collector.TARGET_PATH:
            return collector.TARGET_BLOB
        raise AssertionError((commit, path))

    def show(self, commit: str, path: str) -> str:
        if path == tool.REGISTRY_PATH:
            return (ROOT / path).read_text(encoding="utf-8")
        raise AssertionError((commit, path))

    def list_paths(self, commit: str, prefix: str) -> list[str]:
        return []


def test_imported_pass_is_consumed_by_ac11_aggregator():
    result = _import(manual=_manual(), receipt=_receipt())
    evaluated = aggregate.evaluate_axis(result, _Git(), {}, NOW)
    assert evaluated.verdict is aggregate.Verdict.MEASURED_PASS
    assert evaluated.reasons == ()


def test_registry_and_manifest_contract_are_pinned():
    assert aggregate.TARGET_REGISTRY_BLOB == tool.REGISTRY_BLOB
    assert tool.EMITTED_AXES == (collector.AXIS,)
    assert aggregate.REQUIRED_TARGET_BY_AXIS[collector.AXIS] == tool.TARGET_ID
    assert tool.REGISTRY_BLOB == "eeb43dc262f5de1816237ef85fc902cdca4ab6fd"
    patch = json.loads(
        (ROOT / "docs/ac11-axis-sources-accessibility-patch-v1.json").read_text(encoding="utf-8")
    )["replacement"]
    assert patch["importer"] == "tools/import_ac11_accessibility_evidence.py"
    assert patch["importerEmitsAxes"] == list(tool.EMITTED_AXES)
    assert patch["envelopeShape"] == "axis-evidence"


def test_published_manual_schema_is_strict_and_matches_scenarios():
    schema = json.loads(
        (ROOT / "docs/vault/30_Development/Evidence/ac11-accessibility-manual-session-v1.schema.json")
        .read_text(encoding="utf-8")
    )
    assert schema["additionalProperties"] is False
    scenario = schema["properties"]["scenarios"]
    assert scenario["minItems"] == scenario["maxItems"] == len(tool.EXPECTED_SCENARIOS)
    assert set(scenario["items"]["properties"]["scenarioId"]["enum"]) == tool.EXPECTED_SCENARIOS
    assert schema["properties"]["performedBy"]["properties"]["binding"]["const"] == "self-attested-session"
    import re
    assert re.fullmatch(schema["properties"]["startedAt"]["pattern"], "2026-10-02T00:00:00Z")
    assert not re.fullmatch(schema["properties"]["startedAt"]["pattern"], "2026-10-02T00:00:00+00:00")


def test_windows_runbook_separates_python310_download_from_supported_import_runtime():
    runbook = (
        ROOT / "docs/vault/40_Operations/AC-11_사용자_기기_접근성_수동_인수_절차.md"
    ).read_text(encoding="utf-8")

    assert "사용자 PC의 기본 Python 3.10에서 실행하지 않는다" in runbook
    assert "Python 3.12 또는 3.14 환경에서만 실행한다" in runbook
    assert "importer `--help`가 Python 3.10에서 보이는 것은 import 실행 호환성을 뜻하지 않는다" in runbook
    assert "어느 전제라도\n없으면 import를 시도하지 않고 `NOT_OBSERVED`를 유지한다" in runbook
