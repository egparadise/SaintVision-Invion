"""Real public business rows + JWT + restricted Node + immutable kernel evidence."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event
from uuid import uuid4
import sys

import psycopg
from psycopg.types.json import Jsonb
import pytest
from inv.approvals import digest
from inv.dispatch import DeliveryWorker
from inv.ids import new_id
from test_workspace_api import workspace_http, approve
from test_workspace_resume import build_resume
from test_node_delivery import remote
from test_node_runtime import node_runtime, active
from test_tool_admission import gateway
from test_snapshots import storage
from test_approvals import approval, count

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux business Workspace execution"),
]


@pytest.fixture
def business(workspace_http):
    a = workspace_http
    a.users = {actor: new_id("usr") for actor in ("requester", "alice", "bob", "stranger")}
    a.workload_id = new_id("wkl")
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,%s)",
            (a.e.tenant, a.e.tenant, "Synthetic"),
        )
        conn.execute(
            "INSERT INTO public.projects(tenant_id,project_id,code,display_name) VALUES(%s,%s,%s,%s)",
            (a.e.tenant, a.e.project, a.e.project, "Synthetic"),
        )
        for actor, user in a.users.items():
            conn.execute(
                "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,%s)",
                (a.e.tenant, user, actor, actor),
            )
            conn.execute(
                "INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id) VALUES(%s,%s,%s)",
                (a.e.tenant, a.jwt.subject(actor), user),
            )
            if actor != "stranger":
                conn.execute(
                    "INSERT INTO public.project_members(tenant_id,project_id,user_id,role_code) VALUES(%s,%s,%s,%s)",
                    (
                        a.e.tenant,
                        a.e.project,
                        user,
                        "operator" if actor == "requester" else "approver",
                    ),
                )
        conn.execute(
            "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request,can_approve) VALUES(%s,%s,%s,true,true)",
            (a.e.tenant, a.e.project, a.jwt.subject("stranger")),
        )
        conn.execute(
            "INSERT INTO public.workspaces(tenant_id,project_id,workspace_id,name,status,created_by_user_id) VALUES(%s,%s,%s,%s,%s,%s)",
            (a.e.tenant, a.e.project, a.workspace_id, "Synthetic", "ready", a.users["requester"]),
        )
        conn.execute(
            """INSERT INTO public.workloads(tenant_id,project_id,workload_id,kind,objective,spec,spec_sha256,contract_version,created_by_user_id)
                        VALUES(%s,%s,%s,'batch','Synthetic',%s,%s,'1.0.0',%s)""",
            (
                a.e.tenant,
                a.e.project,
                a.workload_id,
                Jsonb(a.workload),
                digest(a.workload),
                a.users["requester"],
            ),
        )
        conn.execute(
            "INSERT INTO public.runs(tenant_id,run_id,workspace_id,workload_id,requested_by_user_id) VALUES(%s,%s,%s,%s,%s)",
            (a.e.tenant, a.run["runId"], a.workspace_id, a.workload_id, a.users["requester"]),
        )
        conn.execute(
            "INSERT INTO inv.business_projects(tenant_id,project_id) VALUES(%s,%s)",
            (a.e.tenant, a.e.project),
        )
        conn.execute(
            "INSERT INTO inv.business_runs(tenant_id,project_id,run_id,workspace_id) VALUES(%s,%s,%s,%s)",
            (a.e.tenant, a.e.project, a.run["runId"], a.workspace_id),
        )
    a.stop_input = {
        "projectId": a.e.project,
        "runId": a.run["runId"],
        "checkoutId": a.checkout_id,
        "expectedVersion": a.run["version"],
    }
    return a


def stop(a):
    response = a.http.post(
        f"/v1/workspaces/{a.workspace_id}/edit-lock",
        json=a.stop_input,
        headers=a.headers(key="business-lock"),
    )
    assert response.status_code == 201, response.text
    a.lock = response.json()
    return a.lock


def prepare(a):
    response = a.http.post(
        f"/v1/runs/{a.run['runId']}/bindings",
        json={
            "projectId": a.e.project,
            "lockId": a.lock["lockId"],
            "prepare": a.prepare_input,
        },
        headers=a.headers(key="business-prepare"),
    )
    assert response.status_code == 201, response.text
    a.prepared = response.json()
    a.binding_url = "/v1/bindings/" + a.prepared["bindingId"]
    return a.prepared


def enqueue(a):
    return a.http.post(
        a.binding_url + "/enqueue", json={}, headers=a.headers(key="business-enqueue")
    )


def release(a, actor="requester"):
    return a.http.delete(
        "/v1/edit-locks/" + a.lock["lockId"], headers=a.headers(actor, key="business-release")
    )


def test_binding_tracks_real_quorum_queue_receipt_evidence_and_safe_unlock(business):
    a = business
    assert a.http.get(f"/v1/projects/{a.e.project}/permission", headers=a.headers()).json()[
        "canRequest"
    ]
    stop(a)
    with ThreadPoolExecutor(max_workers=3) as pool:
        prepared = list(pool.map(lambda _: prepare(a), range(3)))
    assert prepared[0] == prepared[1] == prepared[2]
    assert prepared[0]["state"] == "frozen" and active(a) == 0
    assert release(a).status_code == 409
    assert enqueue(a).status_code == 403
    approve(a)
    attached = a.http.post(
        a.binding_url + "/approval",
        json={"approvalId": a.prepared["approval"]["approvalId"]},
        headers=a.headers("alice"),
    )
    assert attached.status_code == 200 and attached.json()["state"] == "approved", attached.text
    accepted = enqueue(a)
    assert accepted.status_code == 202, accepted.text
    queued = a.http.get(a.binding_url, headers=a.headers()).json()
    assert queued["state"] == "queued" and not queued["releaseAllowed"] and active(a) == 2
    assert release(a).status_code == 409
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider)
    assert worker.once(a.e.tenant) == "stopped"
    result = a.http.get(a.binding_url, headers=a.headers()).json()
    assert result["state"] == "settled" and result["run"]["state"] == "succeeded"
    assert result["attempt"] == 2 and result["stopReceiptId"] and result["evidenceId"]
    assert result["releaseAllowed"] and result["releasedAt"] and active(a) == 0
    with a.e.db.transaction(a.e.tenant) as conn:
        assert (
            conn.execute(
                "SELECT envelope FROM inv.evidence WHERE evidence_id=%s", (result["evidenceId"],)
            ).fetchone()["envelope"]["result"]
            == "succeeded"
        )
        # Business metadata is never passed off as the actual kernel Run state.
        assert (
            conn.execute(
                "SELECT state FROM public.runs WHERE run_id=%s", (a.run["runId"],)
            ).fetchone()["state"]
            == "draft"
        )
    reconciled = a.http.post(
        a.binding_url + "/reconcile", json={}, headers=a.headers(key="reconcile")
    )
    assert reconciled.status_code == 200 and reconciled.json()["releasedAt"], reconciled.text
    assert release(a).status_code == 200
    a.runtime.observe = lambda: pytest.fail("Replay cannot require a live Node")
    assert enqueue(a).json() == accepted.json()


def test_state_and_forged_approval_cannot_release_editing(business):
    a = business
    stop(a)
    prepare(a)
    for state in ("approved", "queued", "executing", "settled", "abandoned"):
        response = a.http.post(a.binding_url + "/state", json={"state": state}, headers=a.headers())
        assert response.status_code == 403, response.text
    response = a.http.post(
        a.binding_url + "/approval", json={"approvalId": new_id("apr")}, headers=a.headers("alice")
    )
    assert response.status_code == 403
    assert release(a).status_code == 409
    assert a.http.get(a.binding_url, headers=a.headers()).json()["state"] == "frozen"


def test_same_tenant_other_project_and_other_lock_owner_are_denied(business):
    a = business
    stop(a)
    prepare(a)
    assert a.http.get(a.binding_url, headers=a.headers("stranger")).status_code == 403
    assert (
        a.http.post(a.binding_url + "/enqueue", json={}, headers=a.headers("stranger")).status_code
        == 403
    )
    assert release(a, "stranger").status_code == 403
    # A second requester in this project still cannot release another owner's lock.
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO public.project_members(tenant_id,project_id,user_id,role_code) VALUES(%s,%s,%s,'operator')",
            (a.e.tenant, a.e.project, a.users["stranger"]),
        )
    assert a.http.get(a.binding_url, headers=a.headers("stranger")).status_code == 200
    assert release(a, "stranger").status_code == 403
    current = a.http.get(
        f"/v1/projects/{a.e.project}/permission", headers=a.headers("stranger")
    ).json()
    assert current["canRequest"] and not current["canApprove"]
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE public.project_members SET role_code='approver' WHERE user_id=%s",
            (a.users["requester"],),
        )
    # Having a different permission on each side gives no effective permission.
    assert a.http.get("/v1/projects", headers=a.headers()).json()["items"] == []
    assert (
        a.http.get(f"/v1/projects/{a.e.project}/permission", headers=a.headers()).status_code == 403
    )


def test_current_public_scope_is_required_even_with_matching_tenant(business):
    a = business
    other = new_id("prj")
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO public.projects(tenant_id,project_id,code,display_name) VALUES(%s,%s,%s,'Other')",
            (a.e.tenant, other, other),
        )
        conn.execute(
            "UPDATE public.workspaces SET project_id=%s WHERE workspace_id=%s",
            (other, a.workspace_id),
        )
    response = a.http.post(
        f"/v1/workspaces/{a.workspace_id}/edit-lock", json=a.stop_input, headers=a.headers()
    )
    assert response.status_code == 403, response.text


def test_changed_files_roll_back_freeze_approval_and_binding(business):
    a = business
    stop(a)
    path = a.working.root / a.checkout["generation"] / "files" / "src" / "main.py"
    path.write_bytes(b"print('changed after stop')\n")
    response = a.http.post(
        f"/v1/runs/{a.run['runId']}/bindings",
        json={
            "projectId": a.e.project,
            "lockId": a.lock["lockId"],
            "prepare": a.prepare_input,
        },
        headers=a.headers(key="changed-input"),
    )
    assert response.status_code == 409, response.text
    with a.e.db.transaction(a.e.tenant) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM public.execution_bindings").fetchone()["n"] == 0
        )
        assert (
            conn.execute("SELECT count(*) AS n FROM inv.workspace_resumptions").fetchone()["n"] == 0
        )
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "recovering"
    assert release(a).status_code == 200


def test_registration_failure_rolls_back_real_approval_consumption_and_leases(business):
    a = business
    stop(a)
    prepare(a)
    approve(a)
    signing_key = a.runtime.signing_key
    a.runtime.signing_key = None
    response = enqueue(a)
    assert response.status_code == 403, response.text
    assert active(a) == 0 and count(a, "execution_deliveries") == 1
    assert a.http.get(a.binding_url, headers=a.headers()).json()["state"] == "approved"
    a.runtime.signing_key = signing_key
    assert enqueue(a).status_code == 202


@pytest.mark.parametrize("change", ["requester", "approver", "archived", "mapping", "workload"])
def test_business_authority_is_rechecked_after_node_observation(business, change):
    a = business
    stop(a)
    prepare(a)
    approve(a)
    entered, proceed = Event(), Event()
    observe = a.runtime.observe

    def blocked():
        value = observe()
        entered.set()
        assert proceed.wait(10)
        return value

    a.runtime.observe = blocked
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(enqueue, a)
        assert entered.wait(10)
        try:
            with psycopg.connect(a.e.owner) as conn:
                if change in {"requester", "approver"}:
                    conn.execute(
                        "DELETE FROM public.project_members WHERE user_id=%s",
                        (a.users["requester" if change == "requester" else "alice"],),
                    )
                elif change == "archived":
                    conn.execute(
                        "UPDATE public.projects SET status='archived' WHERE project_id=%s",
                        (a.e.project,),
                    )
                elif change == "mapping":
                    conn.execute(
                        "UPDATE inv.business_subjects SET enabled=false WHERE user_id=%s",
                        (a.users["requester"],),
                    )
                else:
                    conn.execute(
                        "UPDATE public.workloads SET spec_sha256=%s WHERE workload_id=%s",
                        ("a" * 64, a.workload_id),
                    )
        finally:
            proceed.set()
        response = pending.result(timeout=15)
    assert response.status_code == 403, response.text
    assert active(a) == 0 and count(a, "execution_deliveries") == 1


def test_direct_workspace_admission_cannot_bypass_binding(business):
    a = business
    denied = a.http.post(a.url + "/resume/prepare", json=a.prepare_input, headers=a.headers())
    assert denied.status_code == 403, denied.text
    stop(a)
    prepare(a)
    approve(a)
    data = {
        "resumeId": a.prepared["resumeId"],
        "approvalId": a.prepared["approval"]["approvalId"],
        "expectedVersion": a.prepared["boundRunVersion"],
    }
    denied = a.http.post(a.url + "/resume/enqueue", json=data, headers=a.headers(key="bypass"))
    assert denied.status_code == 403, denied.text
    assert active(a) == 0


def test_cancel_before_dispatch_unlocks_without_fabricating_a_receipt(business):
    a = business
    stop(a)
    prepare(a)
    response = a.http.post(
        a.url + "/cancel",
        json={"expectedVersion": a.prepared["boundRunVersion"]},
        headers=a.headers(key="cancel"),
    )
    assert response.status_code == 200, response.text
    view = a.http.get(a.binding_url, headers=a.headers()).json()
    assert view["state"] == "abandoned" and view["releaseAllowed"] and view["stopReceiptId"] is None
    assert release(a).status_code == 200
    assert enqueue(a).status_code in {403, 409}
    assert count(a, "execution_deliveries") == 1 and active(a) == 0


def test_database_roles_cannot_forge_authority_binding_or_unlock(business):
    a = business
    stop(a)
    prepare(a)
    with a.e.db.transaction(a.e.tenant) as conn:
        for table, column in [
            ("public.project_members", "role_code"),
            ("public.runs", "state"),
            ("inv.business_subjects", "enabled"),
            ("inv.control_epoch", "epoch"),
        ]:
            assert not conn.execute(
                "SELECT has_column_privilege(current_user,%s,%s,'UPDATE') AS allowed",
                (table, column),
            ).fetchone()["allowed"]
        assert not conn.execute(
            "SELECT has_table_privilege('inv_app','public.execution_bindings','INSERT') AS allowed"
        ).fetchone()["allowed"]
        assert not conn.execute(
            "SELECT has_schema_privilege('inv_app','inv','USAGE') AS allowed"
        ).fetchone()["allowed"]
    with pytest.raises(psycopg.errors.CheckViolation):
        with a.e.db.transaction(a.e.tenant) as conn:
            conn.execute(
                "UPDATE public.workspace_edit_locks SET released_at=clock_timestamp() WHERE lock_id=%s",
                (a.lock["lockId"],),
            )
    with a.e.db.transaction(a.e.other) as conn:
        assert conn.execute("SELECT * FROM public.execution_bindings").fetchall() == []
    with pytest.raises(psycopg.errors.UniqueViolation):
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(
                "INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id) VALUES(%s,%s,%s)",
                (a.e.tenant, a.jwt.subject("duplicate"), a.users["alice"]),
            )


def test_worker_releases_completed_lock_after_requester_revocation(business):
    a = business
    stop(a)
    prepare(a)
    approve(a)
    assert enqueue(a).status_code == 202
    with psycopg.connect(a.e.owner) as conn:
        conn.execute("DELETE FROM public.project_members WHERE user_id=%s", (a.users["requester"],))
    assert release(a).status_code == 403
    assert a.http.get("/v1/projects", headers=a.headers()).json()["items"] == []
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider)
    assert worker.once(a.e.tenant) == "stopped"
    with a.e.db.transaction(a.e.tenant) as conn:
        assert (
            conn.execute(
                "SELECT released_at FROM public.workspace_edit_locks WHERE lock_id=%s",
                (a.lock["lockId"],),
            ).fetchone()["released_at"]
            is not None
        )
    assert active(a) == 0


def test_queued_cancellation_keeps_lock_until_node_stop_receipt(business):
    a = business
    stop(a)
    prepare(a)
    approve(a)
    assert enqueue(a).status_code == 202
    current = a.http.get(a.url, headers=a.headers()).json()
    cancelled = a.http.post(
        a.url + "/cancel",
        json={"expectedVersion": current["version"]},
        headers=a.headers(key="queued-cancel"),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert release(a).status_code == 409
    assert active(a) == 2
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider)
    assert worker.once(a.e.tenant) == "stopped"
    view = a.http.get(a.binding_url, headers=a.headers()).json()
    assert view["run"]["state"] == "cancelled" and view["stopReceiptId"]
    assert view["releasedAt"] and active(a) == 0
