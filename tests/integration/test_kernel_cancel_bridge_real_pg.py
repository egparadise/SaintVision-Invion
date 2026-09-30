"""Real PostgreSQL/HTTP proof for the kernel-to-business cancel bridge."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from inv.ids import new_id
from test_approvals import approval
from test_business_handoff import business
from test_node_delivery import remote
from test_node_runtime import node_runtime
from test_snapshots import storage
from test_workspace_api import workspace_http


pytestmark = pytest.mark.postgres

ROOT = Path(__file__).resolve().parents[2]
SIGNATURE = "public.record_kernel_run_cancel(text,text,text,text,text)"


def _url(a):
    return f"/v1/projects/{a.e.project}/runs/{a.run['runId']}/cancel"


def _body(a):
    with psycopg.connect(a.e.owner) as conn:
        version = conn.execute(
            "SELECT version FROM inv.runs WHERE tenant_id=%s AND run_id=%s",
            (a.e.tenant, a.run["runId"]),
        ).fetchone()[0]
    return {"expectedVersion": version}


def _facts(a):
    with psycopg.connect(a.e.owner) as conn:
        kernel = conn.execute(
            "SELECT state,version FROM inv.runs WHERE tenant_id=%s AND run_id=%s",
            (a.e.tenant, a.run["runId"]),
        ).fetchone()
        public = conn.execute(
            """SELECT state,termination_reason,version FROM public.runs
               WHERE tenant_id=%s AND run_id=%s""",
            (a.e.tenant, a.run["runId"]),
        ).fetchone()
        audit = conn.execute(
            """SELECT actor_type,actor_id,action,outcome,reason_code,trace_id,
                      target_type,target_id,detail
               FROM public.audit_events
               WHERE tenant_id=%s AND target_id=%s
                 AND action='run.cancel.requested'
               ORDER BY occurred_at""",
            (a.e.tenant, a.run["runId"]),
        ).fetchall()
        ledger = conn.execute(
            """SELECT key,response FROM inv.idempotency
               WHERE tenant_id=%s AND project_id=%s AND operation='api.run.cancel'
               ORDER BY key""",
            (a.e.tenant, a.e.project),
        ).fetchall()
    return kernel, public, audit, ledger


def _direct_call(a, *, subject="requester", project=None, run_id=None, event_id=None, trace_id=None):
    with psycopg.connect(a.e.runtime) as conn:
        conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (a.e.tenant,))
        return conn.execute(
            "SELECT public.record_kernel_run_cancel(%s,%s,%s,%s,%s)",
            (
                a.jwt.subject(subject),
                project or a.e.project,
                run_id or a.run["runId"],
                event_id or new_id("aud"),
                trace_id or "c" * 32,
            ),
        ).fetchone()[0]


def test_http_cancel_commits_kernel_public_and_exact_audit_once(business):
    a = business
    response = a.http.post(
        _url(a), json=_body(a), headers=a.headers(key="cancel-bridge-first")
    )
    assert response.status_code == 200, response.text
    trace_id = response.headers["traceparent"].split("-")[1]
    kernel, public, audit, ledger = _facts(a)
    assert kernel[0] == public[0] == "cancelled"
    assert public[1] == "cancelled_by_user"
    assert len(audit) == 1
    assert audit[0] == (
        "user",
        a.users["requester"],
        "run.cancel.requested",
        "allow",
        None,
        trace_id,
        "run",
        a.run["runId"],
        {"reason": "cancelled_by_user"},
    )
    assert [row[0] for row in ledger] == ["cancel-bridge-first"]

    replay = a.http.post(
        _url(a), json={"expectedVersion": response.json()["version"]},
        headers=a.headers(key="cancel-bridge-replay"),
    )
    assert replay.status_code == 200, replay.text
    assert len(_facts(a)[2]) == 1


def test_kernel_pre_cancel_is_not_relabelled_as_a_user_business_cancel(business):
    a = business
    current = _body(a)["expectedVersion"]
    a.e.runs.transition(a.e.tenant, a.run["runId"], "cancelled", expected_version=current)
    response = a.http.post(
        _url(a), json=_body(a), headers=a.headers(key="cancel-after-containment")
    )
    assert response.status_code == 200, response.text
    kernel, public, audit, _ledger = _facts(a)
    assert kernel[0] == "cancelled"
    assert public[0] == "draft"
    assert audit == []


def test_public_run_lock_timeout_rolls_back_every_kernel_write_and_same_key_retries(business):
    a = business
    body = _body(a)
    with psycopg.connect(a.e.owner) as holder:
        holder.execute(
            "SELECT run_id FROM public.runs WHERE tenant_id=%s AND run_id=%s FOR UPDATE",
            (a.e.tenant, a.run["runId"]),
        )
        blocked = a.http.post(
            _url(a), json=body, headers=a.headers(key="cancel-bridge-locked")
        )
        assert blocked.status_code == 503, blocked.text
        assert blocked.json()["code"] == "RES-0007"
    kernel, public, audit, ledger = _facts(a)
    assert kernel[0] != "cancelled" and public[0] != "cancelled"
    assert audit == [] and ledger == []

    retry = a.http.post(
        _url(a), json=body, headers=a.headers(key="cancel-bridge-locked")
    )
    assert retry.status_code == 200, retry.text
    assert len(_facts(a)[2]) == 1


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_cancel_has_one_audit_and_the_declared_idempotency_surface(
    business, same_key
):
    a = business
    body = _body(a)

    def cancel(index):
        key = "cancel-concurrent" if same_key else f"cancel-concurrent-{index}"
        return a.http.post(_url(a), json=body, headers=a.headers(key=key))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [future.result(timeout=10) for future in (pool.submit(cancel, 1), pool.submit(cancel, 2))]
    statuses = sorted(response.status_code for response in responses)
    assert statuses == ([200, 200] if same_key else [200, 409])
    if not same_key:
        denied = next(response for response in responses if response.status_code == 409)
        assert denied.json()["code"] == "GRAPH-0003"
    assert len(_facts(a)[2]) == 1


def test_function_authority_and_runtime_table_privileges_fail_closed(business):
    a = business
    with psycopg.connect(a.e.owner) as conn:
        assert not conn.execute(
            "SELECT has_function_privilege('inv_app',%s,'EXECUTE')", (SIGNATURE,)
        ).fetchone()[0]
        assert not conn.execute(
            "SELECT has_column_privilege('inv_kernel','public.runs','state','UPDATE')"
        ).fetchone()[0]
        assert not conn.execute(
            "SELECT has_table_privilege('inv_kernel','public.audit_events','INSERT')"
        ).fetchone()[0]
        assert not conn.execute(
            """SELECT EXISTS(
                 SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid
                 WHERE r.rolname='inv_cancel_bridge_owner')"""
        ).fetchone()[0]
        grants = conn.execute(
            """SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END
               FROM pg_proc p, LATERAL aclexplode(coalesce(
                 p.proacl,acldefault('f',p.proowner))) a
               WHERE p.oid=%s::regprocedure AND a.privilege_type='EXECUTE'
                 AND a.grantee<>p.proowner ORDER BY 1""",
            (SIGNATURE,),
        ).fetchall()
        assert grants == [("inv_kernel",)]

    with psycopg.connect(a.e.runtime) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SET ROLE inv_cancel_bridge_owner")

    with psycopg.connect(a.e.runtime) as conn:
        conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (a.e.tenant,))
        with pytest.raises(psycopg.Error):
            conn.execute(
                "UPDATE public.runs SET state='cancelled' WHERE run_id=%s",
                (a.run["runId"],),
            )
    with psycopg.connect(a.e.runtime) as conn:
        conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (a.e.tenant,))
        with pytest.raises(psycopg.Error):
            conn.execute(
                "SELECT public.record_kernel_run_cancel(%s,%s,%s,%s,%s)",
                (
                    a.jwt.subject("requester"),
                    a.e.project,
                    a.run["runId"],
                    new_id("aud"),
                    "c" * 32,
                ),
            )
    assert _facts(a)[2] == []


def test_direct_function_rejects_missing_scope_wrong_scope_nonterminal_and_bad_ids(business):
    a = business
    with psycopg.connect(a.e.runtime) as conn:
        with pytest.raises(psycopg.Error) as missing_scope:
            conn.execute(
                "SELECT public.record_kernel_run_cancel(%s,%s,%s,%s,%s)",
                (
                    a.jwt.subject("requester"),
                    a.e.project,
                    a.run["runId"],
                    new_id("aud"),
                    "c" * 32,
                ),
            )
    assert missing_scope.value.sqlstate == "42501"

    with pytest.raises(psycopg.Error) as nonterminal:
        _direct_call(a)
    assert nonterminal.value.sqlstate == "23514"

    with pytest.raises(psycopg.Error) as wrong_project:
        _direct_call(a, project="prj_" + "Z" * 26)
    assert wrong_project.value.sqlstate == "23514"

    with psycopg.connect(a.e.runtime) as conn:
        conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (str(uuid4()),))
        with pytest.raises(psycopg.Error) as wrong_tenant:
            conn.execute(
                "SELECT public.record_kernel_run_cancel(%s,%s,%s,%s,%s)",
                (
                    a.jwt.subject("requester"),
                    a.e.project,
                    a.run["runId"],
                    new_id("aud"),
                    "c" * 32,
                ),
            )
    assert wrong_tenant.value.sqlstate == "23514"

    for event_id, trace_id in (("aud_bad", "c" * 32), (new_id("aud"), "C" * 32)):
        with pytest.raises(psycopg.Error) as invalid_id:
            _direct_call(a, event_id=event_id, trace_id=trace_id)
        assert invalid_id.value.sqlstate == "22023"


def test_business_authority_is_rederived_and_failure_rolls_back_kernel_state(business):
    a = business
    response = a.http.post(
        _url(a),
        json=_body(a),
        headers=a.headers("stranger", key="cancel-bridge-no-business-role"),
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "AUTH-0030"
    kernel, public, audit, ledger = _facts(a)
    assert kernel[0] != "cancelled" and public[0] != "cancelled"
    assert audit == [] and ledger == []

    a.e.runs.transition(
        a.e.tenant, a.run["runId"], "cancelled", expected_version=kernel[1]
    )
    with pytest.raises(psycopg.Error) as denied:
        _direct_call(a, subject="stranger")
    assert denied.value.sqlstate == "42501"
    assert _facts(a)[1][0] == "draft" and _facts(a)[2] == []


@pytest.mark.parametrize("authority_change", ["subject-disabled", "user-suspended", "approver"])
def test_direct_function_rejects_stale_or_non_requesting_business_authority(
    business, authority_change
):
    a = business
    current = _body(a)["expectedVersion"]
    a.e.runs.transition(a.e.tenant, a.run["runId"], "cancelled", expected_version=current)
    with psycopg.connect(a.e.owner) as conn:
        if authority_change == "subject-disabled":
            conn.execute(
                "UPDATE inv.business_subjects SET enabled=false WHERE tenant_id=%s AND user_id=%s",
                (a.e.tenant, a.users["requester"]),
            )
        elif authority_change == "user-suspended":
            conn.execute(
                "UPDATE public.users SET status='suspended' WHERE tenant_id=%s AND user_id=%s",
                (a.e.tenant, a.users["requester"]),
            )
        else:
            conn.execute(
                "UPDATE public.project_members SET role_code='approver' "
                "WHERE tenant_id=%s AND project_id=%s AND user_id=%s",
                (a.e.tenant, a.e.project, a.users["requester"]),
            )
    with pytest.raises(psycopg.Error) as denied:
        _direct_call(a)
    assert denied.value.sqlstate == "42501"
    assert _facts(a)[1][0] == "draft" and _facts(a)[2] == []


def test_direct_function_rejects_cancelled_kernel_run_without_business_mapping(business):
    a = business
    run = a.e.runs.create(a.e.tenant, a.e.project)
    for state in ("validated", "planned", "cancelled"):
        run = a.e.runs.transition(
            a.e.tenant, run["runId"], state, expected_version=run["version"]
        )
    with pytest.raises(psycopg.Error) as missing:
        _direct_call(a, run_id=run["runId"])
    assert missing.value.sqlstate == "23514"


def test_duplicate_audit_event_id_is_rejected(business):
    a = business
    current = _body(a)["expectedVersion"]
    a.e.runs.transition(a.e.tenant, a.run["runId"], "cancelled", expected_version=current)
    event_id = new_id("aud")
    assert _direct_call(a, event_id=event_id)
    with pytest.raises(psycopg.Error) as duplicate:
        _direct_call(a, event_id=event_id)
    assert duplicate.value.sqlstate == "23505"
    assert len(_facts(a)[2]) == 1


def test_public_terminal_mismatch_rolls_back_kernel_and_ledger(business):
    a = business
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE public.runs SET state='succeeded' WHERE tenant_id=%s AND run_id=%s",
            (a.e.tenant, a.run["runId"]),
        )
    response = a.http.post(
        _url(a), json=_body(a), headers=a.headers(key="cancel-public-terminal")
    )
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "SYS-0001"
    kernel, public, audit, ledger = _facts(a)
    assert kernel[0] != "cancelled" and public[0] == "succeeded"
    assert audit == [] and ledger == []


def test_execute_revoke_fails_closed_and_same_key_retries_after_restore(business):
    a = business
    body = _body(a)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(f"REVOKE EXECUTE ON FUNCTION {SIGNATURE} FROM inv_kernel")
    try:
        denied = a.http.post(
            _url(a), json=body, headers=a.headers(key="cancel-execute-revoked")
        )
        assert denied.status_code == 503, denied.text
        assert denied.json()["code"] == "SYS-0001"
        kernel, public, audit, ledger = _facts(a)
        assert kernel[0] != "cancelled" and public[0] != "cancelled"
        assert audit == [] and ledger == []
    finally:
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO inv_kernel")
    retry = a.http.post(
        _url(a), json=body, headers=a.headers(key="cancel-execute-revoked")
    )
    assert retry.status_code == 200, retry.text
    assert len(_facts(a)[2]) == 1


def test_missing_current_audit_partition_rolls_back_and_same_key_retries(business):
    a = business
    body = _body(a)
    partition = "audit_events_p" + datetime.now(timezone.utc).strftime("%Y%m")
    with psycopg.connect(a.e.owner) as conn:
        bound = conn.execute(
            "SELECT pg_get_expr(c.relpartbound,c.oid) FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname=%s",
            (partition,),
        ).fetchone()
        assert bound and bound[0].startswith("FOR VALUES FROM")
        conn.execute(
            sql.SQL("ALTER TABLE public.audit_events DETACH PARTITION {}").format(
                sql.Identifier("public", partition)
            )
        )
    try:
        denied = a.http.post(
            _url(a), json=body, headers=a.headers(key="cancel-partition-missing")
        )
        assert denied.status_code == 503, denied.text
        assert denied.json()["code"] == "SYS-0001"
        kernel, public, audit, ledger = _facts(a)
        assert kernel[0] != "cancelled" and public[0] != "cancelled"
        assert audit == [] and ledger == []
    finally:
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(
                sql.SQL("ALTER TABLE public.audit_events ATTACH PARTITION {} ").format(
                    sql.Identifier("public", partition)
                )
                + sql.SQL(bound[0])
            )
    retry = a.http.post(
        _url(a), json=body, headers=a.headers(key="cancel-partition-missing")
    )
    assert retry.status_code == 200, retry.text
    assert len(_facts(a)[2]) == 1


def test_definer_policy_matches_the_live_catalogue_definition(business):
    a = business
    policy = json.loads((ROOT / "tools/definer-policy.json").read_text(encoding="utf-8"))
    expected = policy["functions"]["public.record_kernel_run_cancel(text, text, text, text, text)"]
    with psycopg.connect(a.e.owner) as conn:
        definition = conn.execute(
            "SELECT pg_get_functiondef(%s::regprocedure)", (SIGNATURE,)
        ).fetchone()[0]
    observed = hashlib.sha256(definition.encode("utf-8")).hexdigest()
    assert observed == expected["definitionSHA256"], (
        f"live record_kernel_run_cancel definitionSHA256={observed}"
    )
