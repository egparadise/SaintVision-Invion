"""Fail-closed contract tests for the S04/S08 operational collector."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from tools import collect_s04_s08_operational_evidence as collector
from saintvision.services import runs as run_service


SHA = "1" * 40
DIGEST = "a" * 64


def _summary(**changes):
    value = {
        "attempt_count": 1,
        "valid_count": 1,
        "violation_count": 0,
        "no_approved_before_attempt": 0,
        "approval_expired": 0,
        "approval_digest_mismatch": 0,
        "cancelled_before_attempt": 0,
    }
    value.update(changes)
    return value


def _database(c1=None, outbox=None):
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
            "snapshotSha256": "c" * 64,
            "observedAt": "2026-09-29T00:00:00Z",
        },
        "sourceStartedAt": "2026-09-29T00:00:00Z",
        "sourceFinishedAt": "2026-09-29T00:00:01Z",
        "windowStartedAt": None,
        "c1": c1 or _summary(),
        "outbox": outbox,
    }


def _provenance():
    return {
        "commit_sha": SHA,
        "branch": "agent/codex/test",
        "working_tree_clean_status": True,
        "content_clean_diff": True,
        "executor": "pytest",
    }


def test_c1_empty_is_not_observed_and_reason_totals_are_fail_closed():
    empty = collector.evaluate_c1_summary(_summary(attempt_count=0, valid_count=0))
    assert empty["status"] == "NOT_OBSERVED"

    failed = collector.evaluate_c1_summary(
        _summary(
            valid_count=0,
            violation_count=1,
            approval_expired=1,
        )
    )
    assert failed["status"] == "MEASURED_FAIL"
    assert failed["metrics"]["violationsByReason"]["approval_expired"] == 1

    with pytest.raises(ValueError, match="do not sum"):
        collector.evaluate_c1_summary(_summary(valid_count=0, violation_count=1))

    clean = collector.evaluate_c1_summary(_summary())
    assert clean["status"] == "RECORDED_ONLY"
    assert clean["metrics"]["cancelHistorySource"] == ("public.audit_events:run.cancel.requested")
    assert clean["metrics"]["cancelHistoryBindingStatus"] == "RECORDED_ONLY"


def test_core_cancel_history_action_is_exactly_shared_with_the_product_producer():
    assert collector.CANCEL_HISTORY_ACTION == run_service.CANCEL_AUDIT_ACTION
    assert collector.CANCEL_HISTORY_SOURCE == ("public.audit_events:run.cancel.requested")
    assert "LIKE 'run.cancel%" not in collector.C1_SQL
    assert "ae.action = 'run.cancel.requested'" in collector.C1_SQL


def test_c1_sql_is_core_only_and_keeps_every_preregistered_reason():
    sql = collector.C1_SQL
    for table in ("public.approvals", "public.run_attempts", "public.workloads", "public.runs"):
        assert table in sql
    assert "public.audit_events" in sql
    assert "inv.approval_requests" not in sql
    assert "recovery_epoch" not in sql
    assert "bound_run_version" not in sql
    for reason in collector.C1_REASONS:
        assert reason in sql


def test_clean_outbox_rows_are_reference_only_without_deployment_identity():
    clean = collector.evaluate_outbox_summary(
        {
            "event_count": 100,
            "published_count": 100,
            "failed_count": 0,
            "stale_pending_count": 0,
            "max_publish_attempts": 1,
        }
    )
    assert clean["status"] == "RECORDED_ONLY"

    failed = collector.evaluate_outbox_summary(
        {
            "event_count": 1,
            "published_count": 0,
            "failed_count": 1,
            "stale_pending_count": 0,
            "max_publish_attempts": 10,
        }
    )
    assert failed["status"] == "MEASURED_FAIL"

    with pytest.raises(ValueError, match="exceed"):
        collector.evaluate_outbox_summary(
            {
                "event_count": 1,
                "published_count": 1,
                "failed_count": 1,
                "stale_pending_count": 0,
                "max_publish_attempts": 1,
            }
        )


def test_evidence_binds_database_time_criteria_and_excludes_kernel_boundary():
    evidence = collector.build_evidence(
        database=_database(), provenance=_provenance(), source_env="INV_AUDIT_DSN"
    )
    assert evidence["acceptanceClaim"] is False
    assert evidence["verdict"] == "NOT_OBSERVED"
    assert evidence["observations"]["O3"]["status"] == "RECORDED_ONLY"
    assert evidence["observations"]["O3"]["metrics"]["cancelHistorySource"] == (
        "public.audit_events:run.cancel.requested"
    )
    assert evidence["excludedBoundaries"]["C1-K"]["status"] == "NOT_OBSERVED"
    assert evidence["source"]["database"]["databaseIdentitySha256"] == DIGEST
    assert '"databaseName":' not in json.dumps(evidence)

    changed = deepcopy(evidence)
    changed["criteria"]["version"] = "loose"
    with pytest.raises(ValueError, match="criteria binding"):
        collector.validate_evidence(changed)

    changed = deepcopy(evidence)
    changed["provenance"]["workingTreeClean"] = False
    with pytest.raises(ValueError, match="source tree"):
        collector.validate_evidence(changed)

    changed = deepcopy(evidence)
    changed["excludedBoundaries"]["C1-K"]["status"] = "MEASURED_PASS"
    with pytest.raises(ValueError, match="C1-K"):
        collector.validate_evidence(changed)

    changed = deepcopy(evidence)
    changed["observations"]["O3"]["status"] = "MEASURED_PASS"
    with pytest.raises(ValueError, match="cannot pass"):
        collector.validate_evidence(changed)

    changed = deepcopy(evidence)
    changed["observations"]["O3"]["metrics"]["cancelHistoryBindingStatus"] = "MEASURED_PASS"
    with pytest.raises(ValueError, match="deployment is not bound"):
        collector.validate_evidence(changed)


def test_writer_refuses_overwrite_and_redacts_configured_secret(tmp_path, monkeypatch):
    secret = "postgresql://operator:never-print-this@example.invalid/db"
    monkeypatch.setenv("INV_AUDIT_DSN", secret)
    evidence = collector.build_evidence(
        database=_database(), provenance=_provenance(), source_env="INV_AUDIT_DSN"
    )
    json_path, markdown_path = collector.write_evidence(evidence, tmp_path, "sample")
    assert secret not in json_path.read_text(encoding="utf-8")
    assert "never-print-this" not in markdown_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="overwrite"):
        collector.write_evidence(evidence, tmp_path, "sample")


def test_cli_fails_closed_without_source_or_with_unsafe_label(monkeypatch, capsys):
    monkeypatch.delenv("INV_AUDIT_DSN", raising=False)
    assert collector.main([]) == 2
    assert "required" in capsys.readouterr().err

    monkeypatch.setenv("INV_AUDIT_DSN", "postgresql://user:secret@example.invalid/db")
    assert collector.main(["--label", "../escape"]) == 2
    captured = capsys.readouterr()
    assert "safe filename" in captured.err
    assert "secret" not in captured.err


def test_cli_does_not_echo_database_exception_details(monkeypatch, capsys):
    monkeypatch.setenv("INV_AUDIT_DSN", "postgresql://user:secret@example.invalid/db")
    monkeypatch.setattr(collector, "_collect_provenance_at_root", lambda _executor: _provenance())

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("secret endpoint and password")

    monkeypatch.setattr(collector, "collect_database", unavailable)
    assert collector.main([]) == 2
    captured = capsys.readouterr()
    assert captured.err.strip() == "collector unavailable: RuntimeError"
    assert "secret" not in captured.err
