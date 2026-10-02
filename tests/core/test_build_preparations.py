"""Card 247 build-request entry contract and migration guards."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inv.approvals import Principal
from inv.build_preparations import BuildPreparationService, _git_source_identity
from inv.contracts import validate_contract
from inv.errors import DomainError

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/versions/0061_build_preparations.py"


def test_0061_is_single_parent_force_rls_append_only_and_least_privilege():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0061_build_preparations"' in source
    assert 'down_revision = "0060_build_execution_admissions"' in source
    assert 'sa.UniqueConstraint("tenant_id", "run_id"' in source
    assert source.count("FORCE ROW LEVEL SECURITY") == 1  # helper, called for all three tables
    assert 'for table in ("build_policy_profiles", "build_preparations", "build_preparation_rate_windows")' in source
    assert "SECURITY DEFINER" not in source
    assert "SECURITY INVOKER" in source
    assert "GRANT SELECT ON inv.build_policy_profiles TO inv_kernel" in source
    assert "GRANT SELECT, INSERT ON inv.build_preparations TO inv_kernel" in source
    assert "GRANT UPDATE(queued_at) ON inv.build_preparations TO inv_kernel" in source
    assert "GRANT DELETE ON inv.build_preparations" not in source
    assert "GRANT DELETE ON inv.build_policy_profiles" not in source
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON inv.build_preparation_rate_windows" in source
    assert "35 days" in source
    assert "cannot discard retained build authority" in source


def test_public_inputs_are_strict_and_raw_authority_is_rejected():
    prepare = {
        "checkoutId": "11111111-1111-4111-8111-111111111111",
        "buildPolicyProfileId": "bpp_01M3PTP800EEMWMDYKEZZ3CWNP",
        "expectedRunVersion": 3,
        "requestedTarget": "image",
    }
    enqueue = {
        "approvalId": "apr_01M3PTP800EEMWMDYKEZZ3CWNP",
        "expectedRunVersion": 4,
    }
    validate_contract("BuildPreparationInput", prepare)
    validate_contract("BuildEnqueueInput", enqueue)
    for extra in ("BuildRequest", "BuildPlan", "PolicyDecision", "provider", "lease"):
        with pytest.raises(DomainError, match="VAL-0003"):
            validate_contract("BuildPreparationInput", {**prepare, extra: {}})


def test_review_union_is_redacted_and_generated_copies_match():
    schema = json.loads((ROOT / "contracts/v1alpha1/core.schema.json").read_text("utf-8"))
    workload = schema["$defs"]["ApprovalReviewView"]["properties"]["workload"]
    refs = {item["$ref"] for item in workload["oneOf"]}
    assert refs == {"#/$defs/WorkloadSpec", "#/$defs/BuildApprovalReviewSummary"}
    summary = schema["$defs"]["BuildApprovalReviewSummary"]
    serialized = json.dumps(summary, sort_keys=True)
    for forbidden in ("secretRefIds", "provider", "nodeId", "leaseId", "contextPath", "dockerfilePath"):
        assert forbidden not in serialized
    canonical = (ROOT / "contracts/v1alpha1/core.schema.json").read_bytes()
    assert (ROOT / "services/control-plane/src/inv/generated/core.schema.json").read_bytes() == canonical
    assert (ROOT / "services/node-agent/internal/wire/core.schema.json").read_bytes() == canonical


class _NoTransactionDatabase:
    recovery_epoch = "11111111-1111-4111-8111-111111111111"

    def transaction(self, _tenant):  # pragma: no cover - a regression must not reach it
        raise AssertionError("flag-off enqueue touched the database")


class _NoStore:
    def put(self, *_args):
        raise AssertionError("flag-off enqueue touched ObjectStore")


def test_flag_off_refuses_before_quota_approval_or_storage(monkeypatch):
    monkeypatch.delenv("INV_BUILDKIT_PRODUCT_ENABLED", raising=False)
    service = BuildPreparationService(_NoTransactionDatabase(), _NoStore())
    principal = Principal("11111111-1111-4111-8111-111111111111", "oidc:requester")
    with pytest.raises(DomainError, match="RES-0006") as refused:
        service.enqueue(
            principal,
            "prj_01M3PTP800EEMWMDYKEZZ3CWNP",
            "run_01M3PTP800EEMWMDYKEZZ3CWNP",
            "bld_01M3PTP800EEMWMDYKEZZ3CWNP",
            {"approvalId": "apr_01M3PTP800EEMWMDYKEZZ3CWNP", "expectedRunVersion": 4},
            key="flag-off",
        )
    assert refused.value.status == 503 and refused.value.retryable is True


def test_routes_are_only_prepare_and_enqueue_and_no_raw_admit_surface():
    source = (ROOT / "services/control-plane/src/inv/app.py").read_text(encoding="utf-8")
    assert '@api.post("/v1/projects/{project}/runs/{run_id}/builds", status_code=201)' in source
    assert '@api.post("/v1/projects/{project}/runs/{run_id}/builds/{build_id}/enqueue")' in source
    assert "/v1/builds/admit" not in source
    assert 'builds/admit' not in source


def test_failed_same_key_is_reserved_before_quota_and_only_saved_response_replays():
    source = (ROOT / "services/control-plane/src/inv/build_preparations.py").read_text("utf-8")
    reservation = source.index("INSERT INTO inv.idempotency")
    replay = source.index('if ledger["response"] is not None')
    quota = source.index("INSERT INTO inv.build_preparation_rate_windows")
    assert reservation < replay < quota
    assert "response IS NULL" in source


def test_dispatch_factory_runs_after_scheduled_transition_and_before_admission():
    source = (ROOT / "services/control-plane/src/inv/approvals.py").read_text("utf-8")
    scheduled = source.index('"scheduled", run["version"]')
    factory = source.index("build_authority_factory(", scheduled)
    admission = source.index("TrustedBuildAdmissionEntry(self.db).record_committed", factory)
    assert scheduled < factory < admission


def test_source_identity_is_a_real_deterministic_git_tree_and_commit():
    import base64
    import hashlib
    from inv.workspace_files import canonical

    workspace = "wsp_01M3PTP800EEMWMDYKEZZ3CWNP"
    body = b"FROM scratch\n"
    raw = canonical({
        "format": "workspace-snapshot:1", "workspaceId": workspace,
        "directories": ["src"],
        "files": [{"path": "src/Dockerfile", "executable": False,
                   "sha256": hashlib.sha256(body).hexdigest(), "sizeBytes": len(body),
                   "dataBase64": base64.b64encode(body).decode()}],
    })
    first = _git_source_identity(raw, workspace, "src", "src/Dockerfile")
    assert first == _git_source_identity(raw, workspace, "src", "src/Dockerfile")
    assert all(len(value) == 40 for value in first) and first[0] != first[1]
    with pytest.raises(DomainError, match="VERIFY-0002"):
        _git_source_identity(raw, workspace, "src", "Dockerfile")
