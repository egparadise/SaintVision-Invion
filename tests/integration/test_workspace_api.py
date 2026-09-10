"""Public JWT -> immutable input -> two approvals -> mTLS Node -> Git/Evidence."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event
from uuid import uuid4
import sys

import psycopg
import pytest
from fastapi.testclient import TestClient
from inv.app import create_app
from inv.dispatch import DeliveryWorker
from inv.workspace_api import RestrictedWorkspaceRuntime, WorkspaceAPI
from inv.workspace_files import decode_snapshot
from jwt_support import jwt_fixture
from test_approvals import approval, count
from test_node_delivery import remote
from test_node_runtime import node_runtime, active, container
from test_tool_admission import gateway
from test_snapshots import storage
from test_workspace_resume import build_resume

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux Workspace API execution"),
]


@pytest.fixture
def workspace_http(remote, storage, tmp_path):
    a = build_resume(remote, storage, tmp_path, freeze_input=False)
    a.jwt = jwt_fixture(tmp_path, a.e.tenant)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)",
            (a.e.tenant, a.e.project, a.e.node),
        )
        for actor in ("requester", "alice", "bob"):
            conn.execute(
                "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request,can_approve) VALUES(%s,%s,%s,%s,%s)",
                (
                    a.e.tenant,
                    a.e.project,
                    a.jwt.subject(actor),
                    actor == "requester",
                    actor != "requester",
                ),
            )
    a.runtime = RestrictedWorkspaceRuntime(
        a.e.db,
        profile=a.profile,
        node=a.node,
        resources={"cpu": a.e.resource, "memory": a.memory},
        signing_key=a.key,
        policy_version="workspace-restricted:1",
        client=a.client,
    )
    a.service = WorkspaceAPI(a.e.db, a.working, a.runtime)
    a.http = TestClient(
        create_app(a.e.db, a.jwt.auth, workspace=a.service), raise_server_exceptions=False
    )
    a.headers = lambda actor="requester", key="prepare": {
        "Authorization": "Bearer " + a.jwt.token(actor),
        "Idempotency-Key": key,
    }
    a.url = f"/v1/projects/{a.e.project}/runs/{a.run['runId']}"
    a.prepare_input = {
        "checkoutId": a.checkout_id,
        "resumeId": str(uuid4()),
        "stepId": "public-step",
        "workload": a.workload,
        "expectedVersion": a.run["version"],
    }
    yield a
    a.http.close()


def prepare(a):
    response = a.http.post(a.url + "/resume/prepare", json=a.prepare_input, headers=a.headers())
    assert response.status_code == 201, response.text
    a.prepared = response.json()
    a.enqueue_input = {
        "resumeId": a.prepared["resumeId"],
        "approvalId": a.prepared["approval"]["approvalId"],
        "expectedVersion": a.prepared["run"]["version"],
    }
    return a.prepared


def approve(a):
    row = a.prepared["approval"]
    url = f"/v1/projects/{a.e.project}/approvals/{row['approvalId']}"
    for actor in ("alice", "bob"):
        headers = a.headers(actor, key="vote:" + actor)
        challenge = a.http.post(url + "/challenge", json={}, headers=headers)
        assert challenge.status_code == 200, challenge.text
        decision = a.http.post(
            url + "/decision",
            headers=headers,
            json={
                "decision": "approve",
                "nonce": challenge.json()["nonce"],
                "actionDigest": row["actionDigest"],
            },
        )
        assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "approved"


def enqueue(a):
    return a.http.post(
        a.url + "/resume/enqueue", json=a.enqueue_input, headers=a.headers(key="enqueue")
    )


def test_public_resume_executes_and_replays_after_node_offline(workspace_http):
    a = workspace_http
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(lambda _: prepare(a), range(3)))
    assert responses[0] == responses[1] == responses[2]
    assert responses[0]["run"]["state"] == "awaiting_approval" and active(a) == 0
    status_url = a.url + "/resumptions/" + a.prepared["resumeId"]
    status = a.http.get(status_url, headers=a.headers("alice")).json()
    assert status["frozenFiles"][0]["path"] == "src/main.py"
    assert "dataBase64" not in str(status)
    approve(a)
    response = enqueue(a)
    assert response.status_code == 202, response.text
    assert response.json()["accepted"] and active(a) == 2
    assert a.http.get(a.url, headers=a.headers()).json()["state"] == "scheduled"
    assert count(a, "execution_attempts") == 1
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider)
    assert worker.once(a.e.tenant) == "stopped"
    run = a.http.get(a.url, headers=a.headers()).json()
    assert run["state"] == "succeeded" and run["attempt"] == 2
    raw = a.storage.restore(a.e.tenant, a.e.project, run["runId"], 2, "public-step")
    files = decode_snapshot(raw, a.workspace_id)[1]
    assert files["src/main.py"] == b"print('resumed')\n"
    assert len(files[".git/refs/heads/main"].strip()) == 40
    assert count(a, "result_completions") == 1 and active(a) == 0 and container(a) is None
    a.runtime.observe = lambda: pytest.fail("Replay must not depend on a live Node")
    assert enqueue(a).json() == response.json()
    assert worker.once(a.e.tenant) == "idle" and count(a, "execution_attempts") == 2


def test_public_registration_failure_rolls_back_approval_and_leases(workspace_http):
    a = workspace_http
    prepare(a)
    approve(a)
    signing_key = a.runtime.signing_key
    a.runtime.signing_key = None
    response = enqueue(a)
    assert response.status_code == 403, response.text
    assert active(a) == 0 and count(a, "execution_deliveries") == 1
    with a.e.db.transaction(a.e.tenant) as conn:
        row = conn.execute(
            "SELECT status FROM inv.approval_requests WHERE approval_id=%s",
            (a.enqueue_input["approvalId"],),
        ).fetchone()
    assert row["status"] == "approved"
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "awaiting_approval"
    a.runtime.signing_key = signing_key
    assert enqueue(a).status_code == 202
    assert count(a, "execution_deliveries") == 2


@pytest.mark.parametrize(
    "intervention", ["cancel", "revoke_requester", "revoke_approver", "revoke_node"]
)
def test_authority_is_rechecked_after_network_observation(workspace_http, intervention):
    a = workspace_http
    prepare(a)
    approve(a)
    entered, proceed = Event(), Event()
    observe = a.runtime.observe

    def blocked_observe():
        result = observe()
        entered.set()
        assert proceed.wait(10)
        return result

    a.runtime.observe = blocked_observe
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(enqueue, a)
        assert entered.wait(10)
        try:
            if intervention == "cancel":
                cancelled = a.http.post(
                    a.url + "/cancel",
                    headers=a.headers(key="cancel"),
                    json={"expectedVersion": a.enqueue_input["expectedVersion"]},
                )
                assert cancelled.status_code == 200, cancelled.text
            elif intervention == "revoke_node":
                with psycopg.connect(a.e.owner) as conn:
                    conn.execute(
                        "UPDATE inv.project_nodes SET enabled=false WHERE tenant_id=%s AND project_id=%s AND node_id=%s",
                        (a.e.tenant, a.e.project, a.e.node),
                    )
            else:
                actor = "requester" if intervention == "revoke_requester" else "alice"
                with psycopg.connect(a.e.owner) as conn:
                    conn.execute(
                        "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
                        (a.e.tenant, a.jwt.subject(actor)),
                    )
        finally:
            proceed.set()
        assert pending.result(10).status_code in (403, 409)
    assert active(a) == 0 and count(a, "execution_deliveries") == 1
    assert count(a, "execution_attempts") == 1


def test_http_intent_cannot_supply_authority_and_replay_checks_grant(workspace_http):
    a = workspace_http
    for mutation in ({"policy": {"effect": "allow"}}, {"nodeId": a.e.node}):
        response = a.http.post(
            a.url + "/resume/prepare", headers=a.headers(), json={**a.prepare_input, **mutation}
        )
        assert response.status_code == 422
    assert (
        a.http.post(
            a.url + "/resume/prepare", headers=a.headers("alice"), json=a.prepare_input
        ).status_code
        == 403
    )
    wrong = deepcopy(a.prepare_input)
    wrong["workload"]["tenantId"] = str(uuid4())
    assert (
        a.http.post(a.url + "/resume/prepare", headers=a.headers(), json=wrong).status_code == 403
    )
    assert count(a, "workspace_resumptions") == 0
    prepare(a)
    # A changed HTTP payload cannot reuse a successful key, even with the same ID.
    changed = {**a.prepare_input, "stepId": "changed"}
    assert (
        a.http.post(a.url + "/resume/prepare", headers=a.headers(), json=changed).status_code == 409
    )
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
            (a.e.tenant, a.jwt.subject("requester")),
        )
    assert (
        a.http.post(
            a.url + "/resume/prepare", headers=a.headers(), json=a.prepare_input
        ).status_code
        == 403
    )
    assert count(a, "workspace_resumptions") == 1 and active(a) == 0


def test_unapproved_enqueue_is_not_dispatched(workspace_http):
    a = workspace_http
    prepare(a)
    response = enqueue(a)
    assert response.status_code == 403, response.text
    assert active(a) == 0 and count(a, "execution_deliveries") == 1
    assert count(a, "approval_dispatches") == 1


def test_denied_profile_does_not_strand_a_frozen_attempt(workspace_http):
    a = workspace_http
    denied = deepcopy(a.prepare_input)
    denied["workload"]["imageDigest"] = "sha256:" + "b" * 64
    response = a.http.post(a.url + "/resume/prepare", headers=a.headers(), json=denied)
    assert response.status_code == 403, response.text
    assert count(a, "workspace_resumptions") == 0
    assert count(a, "approval_requests") == 1 and active(a) == 0
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "recovering"
    # The failed attempt must not consume the resume ID or idempotency key.
    assert prepare(a)["run"]["state"] == "awaiting_approval"
