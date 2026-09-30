"""Fail-closed contract tests for the S04-DB C1-K collector."""

from __future__ import annotations

import base64
from copy import deepcopy
import datetime as dt
import json
from pathlib import Path

import pytest

from tools import collect_s04_kernel_approval_evidence as collector


SHA = "1" * 40
DIGEST = "a" * 64
NOW = dt.datetime(2026, 9, 30, 1, 0, tzinfo=dt.timezone.utc)


def _k1_row(**changes):
    row = {
        "claim_tenant_id": "tenant",
        "claim_project_id": "project",
        "claim_run_id": "run",
        "claim_command_id": "00000000-0000-0000-0000-000000000001",
        "claim_id": "00000000-0000-0000-0000-000000000002",
        "claim_node_id": "node",
        "claim_action_digest": "a" * 64,
        "claim_plan_digest": "b" * 64,
        "claim_policy_version": "policy:1",
        "claim_profile_version": "profile:1",
        "claim_recovery_epoch": "00000000-0000-0000-0000-000000000003",
        "claim_not_after": NOW + dt.timedelta(minutes=2),
        "claim_created_at": NOW + dt.timedelta(seconds=1),
        "dispatch_tenant_id": "tenant",
        "dispatch_approval_id": "approval",
        "dispatch_command_id": "00000000-0000-0000-0000-000000000001",
        "dispatch_created_at": NOW,
        "approval_tenant_id": "tenant",
        "approval_project_id": "project",
        "approval_run_id": "run",
        "approval_id": "approval",
        "approval_action_digest": "a" * 64,
        "approval_policy_version": "policy:1",
        "approval_recovery_epoch": "00000000-0000-0000-0000-000000000003",
        "bound_run_version": 4,
        "approval_status": "dispatched",
        "approval_expires_at": NOW + dt.timedelta(minutes=3),
    }
    row.update(changes)
    return row


def _k2_row(**changes):
    row = _k1_row()
    wire = collector._wire_claim(row)
    payload = {
        "claim": wire,
        "launch": {"opaque": True},
        "allocations": [],
        "issuedAt": NOW.isoformat(),
    }
    row["envelope"] = {
        "payload": base64.b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).decode(),
        "signature": base64.b64encode(b"s" * 64).decode(),
    }
    row["delivery_created_at"] = NOW + dt.timedelta(seconds=2)
    row.update(changes)
    return row


def _k3_row(**changes):
    row = {
        "attempt_tenant_id": "tenant",
        "attempt_project_id": "project",
        "attempt_run_id": "run",
        "attempt_node_id": "node",
        "attempt_command_id": "00000000-0000-0000-0000-000000000001",
        "execution_attempt": 1,
        "run_attempt": 1,
        "attempt_started_at": NOW + dt.timedelta(seconds=3),
        "claim_created_at": NOW + dt.timedelta(seconds=1),
        "claim_project_id": "project",
        "claim_run_id": "run",
        "claim_node_id": "node",
        "delivery_created_at": NOW + dt.timedelta(seconds=2),
        "delivery_project_id": "project",
        "delivery_run_id": "run",
        "delivery_node_id": "node",
        "dispatch_created_at": NOW,
        "approval_project_id": "project",
        "approval_run_id": "run",
        "bound_run_version": 4,
        "state_events": [
            {"state": "scheduled", "version": 5, "attempt": 0},
            {"state": "running", "version": 6, "attempt": 1},
        ],
    }
    row.update(changes)
    return row


def _database(k1=None, k2=None, k3=None):
    return {
        "identity": {
            "databaseIdentitySha256": DIGEST,
            "databaseNameSha256": "b" * 64,
            "systemIdentifierObserved": True,
            "databaseOid": "16384",
            "serverVersionNum": "160004",
            "migrationHead": "0055_example",
            "transactionIsolation": "repeatable read",
            "transactionReadOnly": "on",
            "rowSecurity": "off",
            "observerCanBypassRls": True,
            "snapshotSha256": "c" * 64,
            "observedAt": "2026-09-30T01:00:00Z",
        },
        "sourceStartedAt": "2026-09-30T01:00:00Z",
        "sourceFinishedAt": "2026-09-30T01:00:01Z",
        "k1": [_k1_row()] if k1 is None else k1,
        "k2": [_k2_row()] if k2 is None else k2,
        "k3": [_k3_row()] if k3 is None else k3,
    }


def _provenance():
    return {
        "commit_sha": SHA,
        "branch": "agent/codex/test",
        "working_tree_clean_status": True,
        "content_clean_diff": True,
        "executor": "pytest",
    }


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"approval_id": None}, "missing_approval_dispatch"),
        ({"approval_status": "approved"}, "approval_not_dispatched"),
        ({"approval_run_id": "other"}, "scope_mismatch"),
        ({"approval_action_digest": "f" * 64}, "action_digest_mismatch"),
        ({"approval_policy_version": "other"}, "policy_version_mismatch"),
        ({"approval_recovery_epoch": "other"}, "recovery_epoch_mismatch"),
        ({"approval_expires_at": NOW}, "timestamp_mismatch"),
    ],
)
def test_k1_rejects_each_approval_claim_binding_mutation(change, reason):
    result = collector.evaluate_k1([_k1_row(**change)])
    assert result["status"] == "MEASURED_FAIL"
    assert result["metrics"]["violationsByReason"][reason] == 1
    assert sum(result["metrics"]["violationsByReason"].values()) == 1


def _payload_mutation(row, mutate):
    raw = base64.b64decode(row["envelope"]["payload"])
    payload = json.loads(raw)
    mutate(payload)
    row["envelope"]["payload"] = base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode()
    return row


def test_k2_rejects_unknown_missing_duplicate_claim_keys_and_bad_signature():
    missing_claim = _k2_row(claim_id=None)
    assert (
        collector.evaluate_k2([missing_claim])["metrics"]["violationsByReason"]["missing_claim_row"]
        == 1
    )

    unknown = _payload_mutation(_k2_row(), lambda value: value["claim"].update(extra=True))
    assert (
        collector.evaluate_k2([unknown])["metrics"]["violationsByReason"]["invalid_claim_shape"]
        == 1
    )

    missing = _payload_mutation(_k2_row(), lambda value: value["claim"].pop("runId"))
    assert collector.evaluate_k2([missing])["status"] == "MEASURED_FAIL"

    row = _k2_row()
    duplicate = (
        b'{"claim":{},"claim":{},"launch":{},"allocations":[],"issuedAt":"2026-09-30T01:00:00Z"}'
    )
    row["envelope"]["payload"] = base64.b64encode(duplicate).decode()
    assert (
        collector.evaluate_k2([row])["metrics"]["violationsByReason"]["invalid_payload_encoding"]
        == 1
    )

    row = _k2_row()
    row["envelope"]["signature"] = base64.b64encode(b"short").decode()
    assert (
        collector.evaluate_k2([row])["metrics"]["violationsByReason"]["invalid_signature_encoding"]
        == 1
    )


def test_k2_rejects_changed_claim_and_naive_or_late_issued_at():
    changed = _payload_mutation(
        _k2_row(), lambda value: value["claim"].update(recoveryEpoch="other")
    )
    assert (
        collector.evaluate_k2([changed])["metrics"]["violationsByReason"]["claim_payload_mismatch"]
        == 1
    )

    naive = _payload_mutation(_k2_row(), lambda value: value.update(issuedAt="2026-09-30T01:00:00"))
    assert collector.evaluate_k2([naive])["metrics"]["violationsByReason"]["invalid_issued_at"] == 1

    late = _payload_mutation(_k2_row(), lambda value: value.update(issuedAt="2026-09-30T01:03:00Z"))
    assert collector.evaluate_k2([late])["status"] == "MEASURED_FAIL"

    scalar = _payload_mutation(_k2_row(), lambda value: value.update(issuedAt=7))
    assert (
        collector.evaluate_k2([scalar])["metrics"]["violationsByReason"]["invalid_issued_at"] == 1
    )


def test_k2_compares_not_after_as_an_instant_across_timezones():
    equivalent = _payload_mutation(
        _k2_row(),
        lambda value: value["claim"].update(notAfter="2026-09-30T10:02:00+09:00"),
    )
    assert collector.evaluate_k2([equivalent])["status"] == "MEASURED_PASS"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"delivery_created_at": None}, "missing_chain_row"),
        ({"delivery_run_id": "other"}, "scope_mismatch"),
        ({"attempt_started_at": NOW}, "timestamp_mismatch"),
        ({"run_attempt": 2}, "run_attempt_mismatch"),
        (
            {"state_events": [{"state": "running", "version": 6, "attempt": 1}]},
            "scheduled_event_mismatch",
        ),
        (
            {"state_events": [{"state": "scheduled", "version": 5, "attempt": 0}]},
            "running_event_mismatch",
        ),
    ],
)
def test_k3_rejects_each_execution_chain_mutation(change, reason):
    result = collector.evaluate_k3([_k3_row(**change)])
    assert result["status"] == "MEASURED_FAIL"
    assert result["metrics"]["violationsByReason"][reason] == 1
    assert sum(result["metrics"]["violationsByReason"].values()) == 1


@pytest.mark.parametrize("state", ["scheduled", "running"])
def test_k3_rejects_duplicate_state_events(state):
    row = _k3_row()
    matching = next(event for event in row["state_events"] if event["state"] == state)
    row["state_events"].append(deepcopy(matching))
    result = collector.evaluate_k3([row])
    assert result["status"] == "MEASURED_FAIL"
    assert result["metrics"]["violationsByReason"][f"{state}_event_mismatch"] == 1


def test_k3_scheduled_attempt_precedes_current_execution_attempt():
    row = _k3_row(
        execution_attempt=2,
        run_attempt=2,
        state_events=[
            {"state": "scheduled", "version": 5, "attempt": 1},
            {"state": "running", "version": 6, "attempt": 2},
        ],
    )
    assert collector.evaluate_k3([row])["status"] == "MEASURED_PASS"


def test_empty_rows_never_pass_and_sql_reads_only_registered_kernel_tables():
    assert collector.evaluate_k1([])["status"] == "NOT_OBSERVED"
    assert collector.evaluate_k2([])["status"] == "NOT_OBSERVED"
    assert collector.evaluate_k3([])["status"] == "NOT_OBSERVED"
    sql = collector.K1_SQL + collector.K2_SQL + collector.K3_SQL
    for table in (
        "inv.approval_requests",
        "inv.approval_dispatches",
        "inv.tool_claims",
        "inv.execution_deliveries",
        "inv.execution_attempts",
        "inv.run_attempts",
        "inv.outbox",
    ):
        assert table in sql
    assert "UPDATE " not in sql and "INSERT " not in sql and "DELETE " not in sql
    assert "policy_decision_id" not in collector.K1_SQL


def test_current_policy_decision_is_new_claim_context_not_approval_identity():
    source = Path("services/control-plane/src/inv/tooling.py").read_text(encoding="utf-8")
    assert "decision = deepcopy(policy.decision)" in source
    assert 'decision["approvedBy"] = sorted(actors)' in source
    assert 'decision["decisionId"]' in source
    assert (
        collector.evaluate_k1([_k1_row()])["metrics"]["currentPolicyDecisionBindingStatus"]
        == "RECORDED_ONLY"
    )


def test_clean_chain_is_measured_but_historical_epoch_never_false_passes():
    evidence = collector.build_evidence(
        database=_database(), provenance=_provenance(), source_env="INV_AUDIT_DSN"
    )
    assert [evidence["observations"][key]["status"] for key in ("K1", "K2", "K3")] == [
        "MEASURED_PASS",
        "MEASURED_PASS",
        "MEASURED_PASS",
    ]
    assert evidence["observations"]["K4"]["status"] == "NOT_REGISTERED"
    assert evidence["verdict"] == "NOT_OBSERVED"
    assert evidence["acceptanceClaim"] is False
    assert (
        evidence["observations"]["K2"]["metrics"]["signatureVerificationStatus"] == "RECORDED_ONLY"
    )
    assert (
        evidence["observations"]["K1"]["metrics"]["currentPolicyDecisionBindingStatus"]
        == "RECORDED_ONLY"
    )

    changed = deepcopy(evidence)
    changed["observations"]["K4"]["status"] = "MEASURED_PASS"
    changed["verdict"] = "PASS"
    changed["acceptanceClaim"] = True
    with pytest.raises(ValueError, match="K4 cannot pass"):
        collector.validate_evidence(changed)

    changed = deepcopy(evidence)
    changed["observations"]["K1"]["metrics"]["claimCount"] = 2
    with pytest.raises(ValueError, match="count identity"):
        collector.validate_evidence(changed)

    changed = deepcopy(evidence)
    changed["observations"]["K3"]["metrics"]["violationsByReason"].pop("running_event_mismatch")
    with pytest.raises(ValueError, match="count shape"):
        collector.validate_evidence(changed)

    changed = deepcopy(evidence)
    changed["observations"]["K1"]["status"] = "NOT_OBSERVED"
    with pytest.raises(ValueError, match="recomputed counts"):
        collector.validate_evidence(changed)

    changed = deepcopy(evidence)
    changed["source"]["database"]["transactionIsolation"] = "read committed"
    with pytest.raises(ValueError, match="repeatable read"):
        collector.validate_evidence(changed)

    changed = deepcopy(evidence)
    changed["source"]["database"]["transactionReadOnly"] = "off"
    with pytest.raises(ValueError, match="read only"):
        collector.validate_evidence(changed)

    changed = deepcopy(evidence)
    changed["source"]["database"]["observerCanBypassRls"] = False
    with pytest.raises(ValueError, match="FORCE RLS"):
        collector.validate_evidence(changed)


def test_database_collection_forces_complete_read_only_repeatable_read_snapshot(monkeypatch):
    commands = []
    observer_access = {"row_security": "off", "rolsuper": False, "rolbypassrls": True}

    class Result:
        def __init__(self, *, one=None, many=None):
            self.one = one
            self.many = [] if many is None else many

        def fetchone(self):
            return self.one

        def fetchall(self):
            return self.many

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement):
            commands.append(statement)
            if "FROM pg_roles" in statement:
                return Result(one=dict(observer_access))
            if "clock_timestamp()" in statement:
                return Result(one={"value": NOW})
            return Result(many=[])

        def rollback(self):
            commands.append("ROLLBACK")

    import psycopg

    monkeypatch.setattr(psycopg, "connect", lambda *_args, **_kwargs: Connection())
    monkeypatch.setattr(collector, "_database_identity", lambda _conn: _database()["identity"])
    result = collector.collect_database("postgresql://redacted")
    assert commands[:3] == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL row_security = off",
        "SET LOCAL statement_timeout = '30s'",
    ]
    assert commands[-1] == "ROLLBACK"
    assert result["k1"] == result["k2"] == result["k3"] == []

    observer_access["rolbypassrls"] = False
    with pytest.raises(PermissionError, match="FORCE RLS"):
        collector.collect_database("postgresql://redacted")


def test_evidence_excludes_identifiers_payload_and_secret(tmp_path, monkeypatch):
    secret = "postgresql://operator:never-print-this@example.invalid/db"
    monkeypatch.setenv("INV_AUDIT_DSN", secret)
    evidence = collector.build_evidence(
        database=_database(), provenance=_provenance(), source_env="INV_AUDIT_DSN"
    )
    rendered = json.dumps(evidence, ensure_ascii=False)
    for value in (
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000003",
        "never-print-this",
    ):
        assert value not in rendered
    json_path, markdown_path = collector.write_evidence(evidence, tmp_path, "sample")
    assert "never-print-this" not in json_path.read_text(encoding="utf-8")
    assert "never-print-this" not in markdown_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="overwrite"):
        collector.write_evidence(evidence, tmp_path, "sample")


def test_cli_fails_closed_without_source_or_on_database_error(monkeypatch, capsys):
    monkeypatch.delenv("INV_AUDIT_DSN", raising=False)
    assert collector.main([]) == 2
    assert "required" in capsys.readouterr().err

    monkeypatch.setenv("INV_AUDIT_DSN", "postgresql://user:secret@example.invalid/db")
    monkeypatch.setattr(collector, "_collect_provenance_at_root", lambda _executor: _provenance())

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("secret endpoint and password")

    monkeypatch.setattr(collector, "collect_database", unavailable)
    assert collector.main([]) == 2
    captured = capsys.readouterr()
    assert captured.err.strip() == "collector unavailable: RuntimeError"
    assert "secret" not in captured.err
