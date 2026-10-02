"""Card 247 build-request entry contract and migration guards."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from inv.approvals import Principal
from inv.build_preparations import (
    BuildPreparationService,
    TERMINAL_ENQUEUE_CODES,
    _git_source_identity,
    validate_build_input,
)
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
    assert 'sa.Column("source_attempt", sa.Integer(), nullable=False)' in source
    assert 'sa.Column("source_recovery_epoch", postgresql.UUID(as_uuid=True), nullable=False)' in source
    assert 'sa.Column("cache_mode", sa.Text(), nullable=False)' in source
    assert 'sa.Column("source_capsule_retained_until", sa.DateTime(timezone=True), nullable=False)' in source
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
    validate_build_input("BuildPreparationInput", prepare)
    validate_build_input("BuildEnqueueInput", enqueue)
    for extra in ("BuildRequest", "BuildPlan", "PolicyDecision", "provider", "lease"):
        with pytest.raises(DomainError, match="VAL-0003"):
            validate_build_input("BuildPreparationInput", {**prepare, extra: {}})


def test_review_union_is_redacted_and_generated_copies_match():
    schema = json.loads((ROOT / "contracts/v1alpha1/core.schema.json").read_text("utf-8"))
    workload = schema["$defs"]["ApprovalReviewView"]["properties"]["workload"]
    refs = {item["$ref"] for item in workload["oneOf"]}
    assert refs == {"#/$defs/WorkloadSpec", "#/$defs/BuildApprovalReviewSummary"}
    summary = schema["$defs"]["BuildApprovalReviewSummary"]
    serialized = json.dumps(summary["properties"], sort_keys=True)
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


def test_provider_measurement_is_outside_the_final_business_transaction():
    source = (ROOT / "services/control-plane/src/inv/build_preparations.py").read_text("utf-8")
    measured = source.index("candidate = measure_candidate(")
    compiled = source.index("plan, evidence_id = compile_plan(", measured)
    dispatch = source.index("result = ApprovalStore(self.db).dispatch(", compiled)
    assert measured < compiled < dispatch


def test_prepare_rechecks_immutable_source_and_profile_without_row_locks():
    source = (ROOT / "services/control-plane/src/inv/build_preparations.py").read_text("utf-8")
    revision_query = source[source.index('"""SELECT revision,content_hash FROM inv.workspace_edits') :]
    revision_query = revision_query[: revision_query.index('"""', 3) + 3]
    profile_query = source[source.index('"""SELECT * FROM inv.build_policy_profiles', source.index("def prepare")) :]
    profile_query = profile_query[: profile_query.index('"""', 3) + 3]
    assert "FOR SHARE" not in revision_query
    assert "FOR SHARE" not in profile_query
    assert "LIMIT 1 FOR SHARE" not in source
    assert "profile_id=%s AND version=%s FOR SHARE" not in source


def test_terminal_enqueue_codes_are_an_explicit_drift_only_allowlist():
    assert TERMINAL_ENQUEUE_CODES == {"GRAPH-0003", "VERIFY-0002"}
    assert not {"AUTH-0031", "RES-0003", "RES-0006", "RES-0007"} & TERMINAL_ENQUEUE_CODES
    source = (ROOT / "services/control-plane/src/inv/build_preparations.py").read_text("utf-8")
    assert 'phase = "rejected" if row["status"] == "pending" else "expired"' in source
    assert "._audit(" in source


def test_capsule_is_scoped_re_read_and_retained_before_approval_commit():
    source = (ROOT / "services/control-plane/src/inv/build_preparations.py").read_text("utf-8")
    assert 'f"{principal.tenant_id}\\0{project_id}\\0{capsule_sha}"' in source
    assert "locator_factory(" in source
    assert 'str(uuid5(NAMESPACE_URL, f"{principal.tenant_id}/{project_id}/{capsule_sha}"))' in source
    assert "self.capsule_store.get(locator, capsule_sha, len(raw)) != raw" in source
    assert "clock_timestamp()+interval '36 days'" in source


def test_configured_app_installs_measured_plan_authority_only_under_exact_flag():
    app = (ROOT / "services/control-plane/src/inv/app.py").read_text("utf-8")
    authority = (ROOT / "services/control-plane/src/inv/build_preparations.py").read_text("utf-8")
    compose = (ROOT / "docker-compose.prod.yml").read_text("utf-8")
    assert "configured_build_plan_authority(" in app
    assert "os.environ.get(PRODUCT_ENABLE_SETTING) == PRODUCT_ENABLE_VALUE" in app
    assert 'trusted_file(os.environ["INV_WORKER_CONFIG"])' in app
    assert "class ConfiguredBuildPlanAuthority" in authority
    assert "self.transport.measure()" in authority
    assert "LeaseStore(self.db)._reserve_prepared_locked(" in authority
    assert '"buildSessionId": str(uuid4())' in authority
    assert 'return plan, new_id("evd")' in authority
    assert "INV_WORKER_CONFIG=/run/saintvision/worker.json" in compose
    assert "INV_BUILDKIT_PRODUCT_ENABLED=${INV_BUILDKIT_PRODUCT_ENABLED:-0}" in compose


def test_product_enabled_app_reads_real_worker_json_bytes_and_installs_authority(
    monkeypatch, tmp_path
):
    """Exercise the production factory boundary, not a constructor bypass."""

    import inv.app as app_module
    import inv.configuration_readiness as readiness_module

    tenant = str(uuid4())
    api_config = tmp_path / "api.json"
    worker_config = tmp_path / "worker.json"
    api_config.write_text(
        json.dumps({"identity": {}, "buildCapsuleProviderId": "fixture-capsules"}),
        encoding="utf-8",
    )
    worker_config.write_text(
        json.dumps(
            {
                "tenantId": tenant,
                "tls": {
                    "ca_file": "/run/saintvision/node-ca.pem",
                    "certificate_file": "/run/saintvision/worker.pem",
                    "key_file": "/run/saintvision/worker-key.pem",
                },
                "buildExecution": {
                    "buildctlPath": "/usr/local/bin/buildctl",
                    "address": "unix:///run/user/65532/buildkit/buildkitd.sock",
                    "sourceRoot": "/run/saintvision/build-sources",
                    "referenceHealthReceipt": "/run/saintvision/buildkit-health.json",
                    "productReceiptDirectory": "/run/saintvision/build-receipts",
                    "builderInstanceId": "builder-hosted-fixture",
                    "builderProfileId": "rootless-v1",
                    "providerRecoveryEpoch": 1,
                    "nodeId": "nod_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("INV_API_CONFIG", str(api_config))
    monkeypatch.setenv("INV_WORKER_CONFIG", str(worker_config))
    monkeypatch.setenv("INV_RUNTIME_DSN", "postgresql://not-connected")
    monkeypatch.setenv("INV_RECOVERY_EPOCH", str(uuid4()))
    monkeypatch.setenv("INV_BUILDKIT_PRODUCT_ENABLED", "1")
    monkeypatch.setattr(
        app_module, "AccessTokens", lambda **_kwargs: SimpleNamespace(tenant_id=tenant)
    )
    monkeypatch.setattr(readiness_module, "configured_s01_readiness", lambda _value: None)
    capsule_store = object()
    registry = SimpleNamespace(resolve=lambda provider_id: capsule_store)
    monkeypatch.setattr(app_module, "_configured_object_stores", lambda *_args: registry)
    captured = {}

    def configured(_database, _identity, **kwargs):
        captured.update(kwargs)
        return kwargs["build_preparations"]

    monkeypatch.setattr(app_module, "create_app", configured)
    service = app_module.create_configured_app()

    assert service is captured["build_preparations"]
    assert service.capsule_store is capsule_store
    assert service.plan_factory.node_id == "nod_01ARZ3NDEKTSV4RRFFQ69G5FAV"
    assert (
        service.plan_factory.transport.configuration.builder_instance_id
        == "builder-hosted-fixture"
    )


def test_secret_aliases_require_a_server_owned_resolver():
    source = (ROOT / "services/control-plane/src/inv/build_preparations.py").read_text("utf-8")
    assert 'if secret_aliases:' in source
    assert 'if self.secret_resolver is None:' in source
    assert '"Build secret authority unavailable"' in source


def test_source_run_recovery_authority_is_rechecked_before_prepare_and_enqueue():
    source = (ROOT / "services/control-plane/src/inv/build_preparations.py").read_text("utf-8")
    assert source.count('locked["source_state"] != "recovering"') == 1
    assert 'checkout["source_state"] != "recovering"' in source
    assert 'checkout["current_source_attempt"] != checkout["source_attempt"]' in source
    assert 'str(checkout["recovery_epoch"]) != self.db.recovery_epoch' in source
    assert 'locked["current_source_recovery_epoch"] != locked["source_recovery_epoch"]' in source


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
    source = (ROOT / "services/control-plane/src/inv/build_preparations.py").read_text("utf-8")
    assert "hashlib.sha1(framed, usedforsecurity=False)" in source
    with pytest.raises(DomainError, match="VERIFY-0002"):
        _git_source_identity(raw, workspace, "src", "Dockerfile")
