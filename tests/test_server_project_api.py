"""
Tests for saintvision.server canonical project-scoped control API endpoints:
1. GET /v1/projects/{project}/runs and GET /v1/projects/{project}/runs/{run_id}
2. POST /v1/projects/{project}/runs/{run_id}/cancel
3. GET /v1/projects/{project}/nodes
4. POST /v1/projects/{project}/approvals/{approval_id}/challenge
5. POST /v1/projects/{project}/approvals/{approval_id}/decision
6. Two-Person Rule: Requester self-approval is rejected with 403 SEC-TWO-PERSON-RULE-VIOLATION
7. Nonce validation: Mismatching nonce is rejected with 400 SEC-NONCE-INVALID
"""

from fastapi.testclient import TestClient
import pytest

from saintvision.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_list_and_get_project_runs(client):
    res = client.get("/v1/projects/prj_01JABCDE/runs")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] >= 1
    assert all(r["projectId"] == "prj_01JABCDE" for r in data["items"])

    first_run_id = data["items"][0]["id"]
    get_res = client.get(f"/v1/projects/prj_01JABCDE/runs/{first_run_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == first_run_id

    missing_res = client.get("/v1/projects/prj_01JABCDE/runs/run_nonexistent_9999")
    assert missing_res.status_code == 404
    assert missing_res.json()["code"] == "RES-RUN-404"


def test_cancel_project_run(client):
    create_res = client.post(
        "/v1/projects/prj_01JABCDE/runs",
        json={"objective": "Test Cancel Run", "workspaceId": "wsp_01JABCDE001"},
    )
    assert create_res.status_code == 201
    run_id = create_res.json()["id"]

    cancel_res = client.post(f"/v1/projects/prj_01JABCDE/runs/{run_id}/cancel")
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["runId"] == run_id
    assert cancel_data["state"] == "cancelled"
    assert cancel_data["projectId"] == "prj_01JABCDE"


def test_list_project_nodes(client):
    res = client.get("/v1/projects/prj_01JABCDE/nodes")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) >= 5


def test_project_approval_challenge_and_decision_flow(client):
    create_run_res = client.post(
        "/v1/projects/prj_01JABCDE/runs",
        json={
            "objective": "High-Risk Deployment",
            "workspaceId": "wsp_01JABCDE001",
            "riskLevel": "L2",
            "requiresApproval": True,
            "requestedBy": "usr_requester_alice",
        },
    )
    assert create_run_res.status_code == 201
    run_data = create_run_res.json()
    assert run_data["state"] == "awaiting_approval"
    approval_id = run_data["approvalId"]

    # 1. Requester cannot challenge or approve their own request (Two-Person Rule)
    self_challenge_res = client.post(
        f"/v1/projects/prj_01JABCDE/approvals/{approval_id}/challenge",
        headers={"X-Subject": "usr_requester_alice"},
    )
    assert self_challenge_res.status_code == 403
    assert self_challenge_res.json()["code"] == "SEC-TWO-PERSON-RULE-VIOLATION"

    # 2. Independent approver requests challenge nonce
    challenge_res = client.post(
        f"/v1/projects/prj_01JABCDE/approvals/{approval_id}/challenge",
        headers={"X-Subject": "usr_reviewer_01"},
    )
    assert challenge_res.status_code == 200
    challenge_data = challenge_res.json()
    assert "nonce" in challenge_data
    nonce = challenge_data["nonce"]

    # 3. Decision with invalid nonce fails
    invalid_nonce_res = client.post(
        f"/v1/projects/prj_01JABCDE/approvals/{approval_id}/decision",
        json={"decision": "approve", "nonce": "invalid_nonce_abc"},
        headers={"X-Subject": "usr_reviewer_01"},
    )
    assert invalid_nonce_res.status_code == 400
    assert invalid_nonce_res.json()["code"] == "SEC-NONCE-INVALID"

    # 4. Requester cannot decide approval
    self_decide_res = client.post(
        f"/v1/projects/prj_01JABCDE/approvals/{approval_id}/decision",
        json={"decision": "approve", "nonce": nonce},
        headers={"X-Subject": "usr_requester_alice"},
    )
    assert self_decide_res.status_code == 403
    assert self_decide_res.json()["code"] == "SEC-TWO-PERSON-RULE-VIOLATION"

    # 5. Independent reviewer approves with valid nonce
    decide_res = client.post(
        f"/v1/projects/prj_01JABCDE/approvals/{approval_id}/decision",
        json={"decision": "approve", "nonce": nonce},
        headers={"X-Subject": "usr_reviewer_01"},
    )
    assert decide_res.status_code == 200
    view = decide_res.json()
    assert view["approvalId"] == approval_id
    assert view["status"] == "approved"
    assert view["projectId"] == "prj_01JABCDE"

    # Verify run transitioned to scheduled
    run_res = client.get(f"/v1/projects/prj_01JABCDE/runs/{run_data['id']}")
    assert run_res.status_code == 200
    assert run_res.json()["state"] in ("scheduled", "succeeded")


def test_project_scoped_resume_lifecycle(client):
    # Reset recovering run
    client.post("/v1/runs/run_01JRECOVERING/reset")

    # 1. Prepare resume via project-scoped route
    prep_res = client.post("/v1/projects/prj_01JABCDE/runs/run_01JRECOVERING/resume/prepare")
    assert prep_res.status_code == 200
    prep_data = prep_res.json()
    assert "inputHash" in prep_data
    approval_id = prep_data["approvalId"]

    # 2. Approve via project-scoped route
    chall_res = client.post(
        f"/v1/projects/prj_01JABCDE/approvals/{approval_id}/challenge",
        headers={"X-Subject": "usr_reviewer_01"},
    )
    assert chall_res.status_code == 200
    nonce = chall_res.json()["nonce"]

    decide_res = client.post(
        f"/v1/projects/prj_01JABCDE/approvals/{approval_id}/decision",
        json={"decision": "approve", "nonce": nonce},
        headers={"X-Subject": "usr_reviewer_01"},
    )
    assert decide_res.status_code == 200
    assert decide_res.json()["status"] == "approved"

    # 3. Enqueue resume via project-scoped route
    enq_res = client.post("/v1/projects/prj_01JABCDE/runs/run_01JRECOVERING/resume/enqueue")
    assert enq_res.status_code == 200
    enq_data = enq_res.json()
    assert enq_data["state"] == "running"
    assert enq_data["attempt"] == 2


def test_workspace_terminal_tickets_canonical(client):
    # 1. Canonical workspace terminal tickets route
    ws_ticket_res = client.post(
        "/v1/workspaces/wsp_01JABCDE/terminal-tickets",
        json={"sessionId": "sess_test_01"},
    )
    assert ws_ticket_res.status_code == 201
    ticket_data = ws_ticket_res.json()
    assert "ticketId" in ticket_data
    assert ticket_data["ticketId"].startswith("tkt_")
    assert ticket_data["workspaceId"] == "wsp_01JABCDE"
    assert ticket_data["expiresInSeconds"] == 30
    assert ticket_data["used"] is False

    # 2. Flat terminal tickets route compatibility
    flat_ticket_res = client.post(
        "/v1/terminal/tickets",
        json={"workspaceId": "wsp_01JABCDE", "sessionId": "sess_test_02"},
    )
    assert flat_ticket_res.status_code == 201
    flat_data = flat_ticket_res.json()
    assert "ticketId" in flat_data
    assert flat_data["ticketId"].startswith("tkt_")
    assert flat_data["workspaceId"] == "wsp_01JABCDE"
