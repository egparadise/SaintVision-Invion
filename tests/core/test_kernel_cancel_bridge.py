"""PG-free guards for the kernel-owned cancellation bridge."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from inv.business_cancel import record_user_cancel
from inv.errors import DomainError


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/versions/0056_kernel_cancel_audit_bridge.py"


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((" ".join(query.split()), params))
        return Result(next(self.rows))


def _migration():
    spec = importlib.util.spec_from_file_location("cancel_bridge_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_unmapped_kernel_run_never_calls_the_definer():
    conn = Connection([None])
    assert not record_user_cancel(
        conn,
        SimpleNamespace(subject_id="oidc:" + "1" * 64),
        "prj_01KERNELCANCELBRIDGE000000",
        "run_01KERNELCANCELBRIDGE000000",
        "a" * 32,
    )
    assert len(conn.calls) == 1
    assert "inv.business_runs" in conn.calls[0][0]


def test_mapped_run_uses_the_closed_named_argument_surface(monkeypatch):
    monkeypatch.setattr("inv.business_cancel.new_id", lambda prefix: "aud_" + "A" * 26)
    conn = Connection([{"mapped": 1}, {"recorded": True}])
    subject = "oidc:" + "1" * 64
    assert record_user_cancel(
        conn,
        SimpleNamespace(subject_id=subject),
        "prj_01KERNELCANCELBRIDGE000000",
        "run_01KERNELCANCELBRIDGE000000",
        "b" * 32,
    )
    sql, params = conn.calls[1]
    assert "public.record_kernel_run_cancel" in sql
    assert [name in sql for name in (
        "p_subject_id", "p_project_id", "p_run_id", "p_event_id", "p_trace_id"
    )] == [True] * 5
    assert "actor" not in sql and "reason" not in sql and "user_id" not in sql
    assert params == (
        subject,
        "prj_01KERNELCANCELBRIDGE000000",
        "run_01KERNELCANCELBRIDGE000000",
        "aud_" + "A" * 26,
        "b" * 32,
    )


@pytest.mark.parametrize("trace_id", [None, "", "A" * 32, "a" * 31, "a" * 33])
def test_invalid_trace_is_rejected_before_any_database_read(trace_id):
    conn = Connection([])
    with pytest.raises(DomainError) as raised:
        record_user_cancel(
            conn,
            SimpleNamespace(subject_id="oidc:" + "1" * 64),
            "prj_01KERNELCANCELBRIDGE000000",
            "run_01KERNELCANCELBRIDGE000000",
            trace_id,
        )
    assert raised.value.code == "SYS-0001"
    assert conn.calls == []


def test_route_passes_boundary_trace_and_only_real_transitions_call_bridge():
    app = (ROOT / "services/control-plane/src/inv/app.py").read_text(encoding="utf-8")
    control = (ROOT / "services/control-plane/src/inv/control.py").read_text(encoding="utf-8")
    shards = (ROOT / "services/control-plane/src/inv/shards.py").read_text(encoding="utf-8")
    assert "trace_id=request.state.trace_id" in app
    transition_branch = control[control.index('if row["state"] != "cancelled":'):]
    assert transition_branch.index("record_user_cancel") < transition_branch.index("event(")
    assert control[:control.index('if row["state"] != "cancelled":')].count(
        "record_user_cancel("
    ) == 0
    assert shards.count("record_user_cancel(") == 2
    assert shards.index("if run[\"state\"] not in TERMINAL:") < shards.index(
        "record_user_cancel("
    )
    parent_branch = shards.split("if parent:", 1)[1].split("pending =", 1)[0]
    assert parent_branch.index('if parent["state"] not in TERMINAL:') < parent_branch.index(
        "record_user_cancel("
    ) < parent_branch.index("else:")


def test_migration_closes_owner_function_policy_and_downgrade_boundaries():
    source = MIGRATION.read_text(encoding="utf-8")
    module = _migration()
    assert module.revision == "0056_kernel_cancel_audit_bridge"
    assert module.down_revision == "0055_adapter_conformance_records"
    assert "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE" in source
    assert "NOINHERIT NOBYPASSRLS" in source
    assert "already has members" in source
    assert "REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC, inv_app" in source
    assert "GRANT EXECUTE ON FUNCTION {SIGNATURE} TO inv_kernel" in source
    assert source.index("GRANT CREATE ON SCHEMA public") < source.index(
        "ALTER FUNCTION {SIGNATURE} OWNER"
    ) < source.index("REVOKE CREATE ON SCHEMA public")
    assert "CREATE POLICY cancel_bridge_audit_append" in source
    assert "CREATE POLICY cancel_bridge_audit_read" in source
    assert "action = 'run.cancel.requested'" in source
    assert "outcome = 'allow'" in source
    assert "target_type = 'run'" in source
    assert "GRANT UPDATE (state,termination_reason,ended_at,version)" in source
    assert "GRANT UPDATE (lock_sentinel)" not in source
    assert "GRANT UPDATE (kernel_lock_sentinel)" not in source
    assert "GRANT UPDATE (state)" not in source
    assert "GRANT UPDATE (workspace_id)" not in source
    assert "GRANT SELECT (tenant_id,event_id) ON public.audit_events" in source
    assert "DROP ROLE" not in source


def test_definer_rechecks_kernel_authority_and_contains_no_dynamic_sql():
    source = MIGRATION.read_text(encoding="utf-8")
    body = source.split("AS $fn$", 1)[1].split("$fn$;", 1)[0]
    assert "FROM inv.runs" in body
    assert "v_kernel_state IS DISTINCT FROM 'cancelled'" in body
    assert "v_kernel_project IS DISTINCT FROM p_project_id" in body
    assert "inv.business_subjects" in body
    assert "public.project_members" in body
    assert "pm.role_code IN ('owner','maintainer','operator')" in body
    assert "p_trace_id !~ '^[0-9a-f]{{32}}$'" in body
    assert "EXECUTE " not in body.upper()
    for forbidden in (
        "p_user_id", "p_actor_type", "p_action", "p_outcome", "p_target_type", "p_reason"
    ):
        assert forbidden not in body


def test_definer_does_not_relock_caller_locked_or_immutable_kernel_rows():
    source = MIGRATION.read_text(encoding="utf-8")
    body = source.split("AS $fn$", 1)[1].split("$fn$;", 1)[0]
    kernel_check = body.split("SELECT r.state, r.project_id", 1)[1].split(
        "IF v_kernel_state", 1
    )[0]
    mapping_check = body.split("SELECT br.workspace_id", 1)[1].split(
        "IF v_workspace_id", 1
    )[0]
    assert "FOR SHARE" not in kernel_check
    assert "FOR SHARE" not in mapping_check


def test_definer_reuses_control_grant_authority_locks_without_extra_row_locks():
    source = MIGRATION.read_text(encoding="utf-8")
    body = source.split("AS $fn$", 1)[1].split("$fn$;", 1)[0]
    authority_check = body.split("SELECT s.user_id", 1)[1].split(
        "IF v_user_id", 1
    )[0]
    assert "FOR SHARE" not in authority_check
    assert "FOR SHARE OF bp, s, p, u, pm" not in body


def test_definer_rejects_reused_audit_event_identifiers():
    source = MIGRATION.read_text(encoding="utf-8")
    body = source.split("AS $fn$", 1)[1].split("$fn$;", 1)[0]
    assert "a.event_id = p_event_id" in body
    assert "ERRCODE = '23505'" in body


def test_definer_and_rls_inputs_are_pinned_to_the_changed_repository_blobs():
    policy_path = ROOT / "tools/definer-policy.json"
    migration_digest = hashlib.sha256(MIGRATION.read_bytes()).hexdigest()
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    entry = policy["functions"][
        "public.record_kernel_run_cancel(text, text, text, text, text)"
    ]
    assert entry["sourceMigrationSHA256"] == migration_digest

    def blob(path):
        result = subprocess.run(
            ["git", "hash-object", path],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    aggregate = (ROOT / "tools/aggregate_ac11_evidence.py").read_text(encoding="utf-8")
    assert blob("tools/definer-policy.json") in aggregate
    assert blob("tools/collect_rls_evidence.py") in aggregate
