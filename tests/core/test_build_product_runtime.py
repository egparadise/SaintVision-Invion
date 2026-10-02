"""PG-free guards for Card 232's producer and product-loop composition."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

import inv.build_product_runtime as runtime_module
import inv.worker as worker_module
from inv.approvals import Principal
from inv.build_execution import BuildExecutionService, PRODUCT_ENABLE_SETTING
from inv.build_product_runtime import (
    BuildExecutionAdmissionStore,
    BuildProductRuntime,
    configured_tenant_product_runtime,
)
from inv.errors import DomainError
from tests.core.test_build_execution_intents import (
    EVIDENCE,
    PROJECT,
    RUN,
    SUBJECT,
    TENANT,
    documents,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/versions/0060_build_execution_admissions.py"
PROCESS = ROOT / "services/control-plane/src/inv/worker.py"
SERVICE = ROOT / "services/control-plane/src/inv/build_execution.py"


def test_migration_is_linear_force_rls_immutable_and_non_destructive():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0060_build_execution_admissions"' in source
    assert 'down_revision = "0059_build_execution_intents"' in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "CREATE POLICY build_execution_admissions_tenant_isolation" in source
    assert "GRANT SELECT, INSERT ON inv.build_execution_admissions TO inv_kernel" in source
    assert "build execution admission payload is immutable" in source
    assert "build execution admissions are not deletable" in source
    assert "OLD.status='ready' AND NEW.status='promoted'" in source
    assert "OLD.status='ready' AND NEW.status='quarantined'" in source
    assert "OLD.status='ready' AND NEW.status='ready'" in source
    assert "NEW.retry_count <> OLD.retry_count + 1" in source
    assert "next_attempt_at <= OLD.next_attempt_at" in source
    assert "SELECT count(*) FROM inv.build_execution_admissions" in source


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (DomainError("RES-0003", "stale"), True),
        (DomainError("RES-0007", "busy"), True),
        (DomainError("NODE-0033", "offline", 503, retryable=True), True),
        (DomainError("NODE-0033", "epoch changed"), False),
        (DomainError("RES-0005", "terminal state"), False),
    ],
)
def test_promotion_retry_classification_is_explicit(error, expected):
    assert runtime_module._retryable_promotion_error(error) is expected


class _Admission:
    def __init__(self):
        self.calls = 0

    def promote_next(self, tenant):
        assert tenant == TENANT
        self.calls += 1


class _Worker:
    def __init__(self):
        self.calls = 0

    def once(self, tenant):
        assert tenant == TENANT
        self.calls += 1
        return "done"


def test_flag_off_does_not_promote_or_construct_product_work():
    admissions = _Admission()
    worker = _Worker()
    runtime = BuildProductRuntime(admissions, worker, environment={})
    with pytest.raises(DomainError, match="not enabled"):
        runtime.once(TENANT)
    assert admissions.calls == worker.calls == 0


def test_enabled_tick_promotes_committed_authority_before_worker_claim():
    order = []

    class Admissions(_Admission):
        def promote_next(self, tenant):
            order.append("promote")
            return super().promote_next(tenant)

    class Worker(_Worker):
        def once(self, tenant):
            order.append("execute")
            return super().once(tenant)

    assert (
        BuildProductRuntime(Admissions(), Worker(), environment={PRODUCT_ENABLE_SETTING: "1"}).once(
            TENANT
        )
        == "done"
    )
    assert order == ["promote", "execute"]


def test_process_composes_build_lane_only_behind_exact_product_flag():
    source = PROCESS.read_text(encoding="utf-8")
    assert "os.environ.get(PRODUCT_ENABLE_SETTING) == PRODUCT_ENABLE_VALUE" in source
    assert "configured_tenant_product_runtime" in source
    assert "if build_runtime is not None" in source
    assert "executor.submit(consume_builds)" in source
    assert "INV_BUILDKIT_PRODUCT_ENABLED" not in source


def _run_process_once(monkeypatch, *, enabled):
    calls = []

    class Connection:
        def execute(self, sql):
            assert "inv.execution_deliveries" in sql

    class Database:
        def __init__(self, *_args, **_kwargs):
            pass

        @contextmanager
        def transaction(self, tenant):
            assert tenant == TENANT
            yield Connection()

    class Delivery:
        def once(self, tenant):
            assert tenant == TENANT
            calls.append("delivery")
            return "delivery"

    class BuildRuntime:
        def once(self, tenant):
            assert tenant == TENANT
            calls.append("build")
            return "build"

    config = {"tenantId": TENANT, "tls": {}}
    if enabled:
        config["buildExecution"] = {}
    monkeypatch.setattr(worker_module, "Database", Database)
    monkeypatch.setattr(worker_module, "strict_object", lambda value: value)
    monkeypatch.setattr(worker_module, "trusted_file", lambda _path: config)
    monkeypatch.setattr(worker_module, "NodeTLSClient", lambda **_kwargs: object())
    monkeypatch.setattr(worker_module, "NodeDelivery", lambda *_args: object())
    monkeypatch.setattr(worker_module, "_output_provider", lambda _config: object())
    monkeypatch.setattr(worker_module, "DeliveryWorker", lambda *_args, **_kwargs: Delivery())
    monkeypatch.setattr("sys.argv", ["worker", "--once"])
    monkeypatch.setenv("INV_WORKER_CONFIG", "ignored")
    monkeypatch.setenv("INV_RUNTIME_DSN", "ignored")
    monkeypatch.setenv("INV_RECOVERY_EPOCH", "ignored")
    if enabled:
        monkeypatch.setenv(PRODUCT_ENABLE_SETTING, "1")
        monkeypatch.setattr(
            runtime_module,
            "configured_tenant_product_runtime",
            lambda *_args, **_kwargs: BuildRuntime(),
        )
    else:
        monkeypatch.delenv(PRODUCT_ENABLE_SETTING, raising=False)
        monkeypatch.setattr(
            runtime_module,
            "configured_tenant_product_runtime",
            lambda *_args, **_kwargs: pytest.fail("flag-off constructed build runtime"),
        )
    worker_module.main()
    return calls


def test_process_once_does_not_construct_or_run_build_runtime_when_flag_off(monkeypatch):
    assert _run_process_once(monkeypatch, enabled=False) == ["delivery"]


def test_process_once_runs_product_runtime_before_delivery_when_enabled(monkeypatch):
    assert _run_process_once(monkeypatch, enabled=True) == ["build", "delivery"]


def test_admission_promotion_recomputes_all_database_document_digests():
    source = (ROOT / "services/control-plane/src/inv/build_product_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "request_sha256 = encode(sha256(convert_to(request::text,'UTF8')),'hex')" in source
    assert "plan_sha256 = encode(sha256(convert_to(plan::text,'UTF8')),'hex')" in source
    assert "decision_sha256 = encode(sha256(convert_to(decision::text,'UTF8')),'hex')" in source
    assert 'stored.get("digests_match") is not True' in source


def test_strict_product_configuration_rejects_unknown_or_missing_keys():
    with pytest.raises(ValueError, match="Exact build execution configuration"):
        configured_tenant_product_runtime(
            object(),
            TENANT,
            {"nodeId": "nod_" + "0" * 26, "unknown": True},
            tls={},
            environment={},
        )


def test_product_service_reads_lease_epoch_from_canonical_fencing_token():
    source = SERVICE.read_text(encoding="utf-8")
    assert 'plan["lease"]["fencingToken"]' in source
    assert '.rsplit(":", 1)[0]' in source
    assert 'plan["lease"].get("recoveryEpoch")' not in source


def test_product_service_passes_fencing_token_epoch_to_quarantine_preflight(monkeypatch):
    epoch = "223e4567-e89b-12d3-a456-426614174000"

    class Database:
        recovery_epoch = epoch

    class Boundary:
        records_durable_quarantine = True

        def preflight_quarantine(self, node_id, observed_epoch):
            assert node_id == "nod_" + "0" * 26
            assert observed_epoch == epoch
            raise DomainError("RES-0006", "stop after epoch assertion", 503, retryable=True)

    service = BuildExecutionService(
        Database(), object(), Boundary(), environment={PRODUCT_ENABLE_SETTING: "1"}
    )
    monkeypatch.setattr(service, "_leased_node_id", lambda *_args: "nod_" + "0" * 26)
    monkeypatch.setattr(service, "_record_preflight_unavailable", lambda **_kwargs: None)
    with pytest.raises(DomainError, match="stop after epoch assertion"):
        service.execute(
            object(),
            {"tenantId": TENANT, "projectId": PROJECT},
            {
                "buildSessionId": "7f4a1c62-9d1e-4a3b-8c55-0f21aa9b4e10",
                "lease": {
                    "leaseId": "lse_" + "0" * 26,
                    "resourceId": "res_" + "0" * 26,
                    "fencingToken": f"{epoch}:7",
                },
            },
            {"decisionId": "decision"},
            policy_version="s08-build-v1",
            run_id=RUN,
            evidence_id=EVIDENCE,
            actor_id=SUBJECT,
            intent_claim_fencing_token=1,
        )


class _Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, stored):
        self.stored = stored
        self.statements = []

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.statements.append((normalized, params))
        if normalized.startswith("SELECT * FROM inv.build_execution_admissions"):
            return _Result(self.stored)
        return _Result()


class _Database:
    recovery_epoch = "223e4567-e89b-12d3-a456-426614174000"

    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def transaction(self, tenant):
        assert tenant == TENANT
        yield self.connection


def test_record_rechecks_permission_policy_and_live_lease_before_insert(monkeypatch):
    request, plan, decision = documents()
    stored = {
        "tenant_id": TENANT,
        "project_id": PROJECT,
        "run_id": RUN,
        "request": deepcopy(request),
        "plan": deepcopy(plan),
        "decision": deepcopy(decision),
        "policy_version": "s08-build-v1",
        "evidence_id": EVIDENCE,
        "actor_id": SUBJECT,
        "status": "ready",
    }
    connection = _Connection(stored)
    calls = []
    monkeypatch.setattr(runtime_module.Control, "grant", lambda *args: calls.append("grant"))
    monkeypatch.setattr(runtime_module, "_database_now", lambda _conn: datetime.now(timezone.utc))
    monkeypatch.setattr(
        runtime_module, "enforce_decision", lambda *args, **kwargs: calls.append("policy")
    )
    monkeypatch.setattr(
        runtime_module,
        "_lock_live_build_authority",
        lambda *args, **kwargs: calls.append("lease"),
    )
    result = BuildExecutionAdmissionStore(_Database(connection)).record(
        Principal(TENANT, SUBJECT),
        request,
        plan,
        decision,
        policy_version="s08-build-v1",
        run_id=RUN,
        evidence_id=EVIDENCE,
    )
    assert result.status == "ready"
    assert calls == ["grant", "policy", "lease"]
    insert = next(sql for sql, _ in connection.statements if sql.startswith("INSERT INTO"))
    assert "inv.build_execution_admissions" in insert
    assert "ON CONFLICT DO NOTHING" in insert
