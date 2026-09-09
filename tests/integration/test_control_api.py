from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
import json
import time
import psycopg
import pytest
from fastapi.testclient import TestClient
from inv.app import create_app
from inv.approvals import Principal
from inv.control import Control
from inv.ids import new_id
from inv.runs import event
from inv.errors import DomainError
from jwt_support import jwt_fixture
from test_approvals import approval, request

pytestmark = pytest.mark.postgres


@pytest.fixture
def api(approval, tmp_path):
    a = approval
    a.jwt = jwt_fixture(tmp_path, a.e.tenant)
    a.control = Control(a.e.db)
    with psycopg.connect(a.e.owner) as conn:
        for name in ["requester", "alice", "bob"]:
            conn.execute(
                "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request,can_approve) VALUES(%s,%s,%s,%s,true)",
                (a.e.tenant, a.e.project, a.jwt.subject(name), name == "requester"),
            )
            a.people[name] = Principal(a.e.tenant, a.jwt.subject(name))
    a.policy["subjectId"] = a.jwt.subject("requester")
    a.client = TestClient(
        create_app(a.e.db, a.jwt.auth, allowed_origins=["https://web.invalid"]),
        raise_server_exceptions=False,
    )
    a.headers = lambda actor="requester", key="test-key": {
        "Authorization": "Bearer " + a.jwt.token(actor),
        "Idempotency-Key": key,
    }
    a.url = "/v1/projects/" + a.e.project
    yield a
    a.client.close()


def test_public_create_cancel_and_replay_are_durable(api):
    a = api
    responses = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(
            pool.map(
                lambda _: a.client.post(a.url + "/runs", json={}, headers=a.headers()),
                range(8),
            )
        )
    assert all(r.status_code == 201 for r in responses)
    assert len({r.json()["runId"] for r in responses}) == 1
    run = responses[0].json()
    url = a.url + "/runs/" + run["runId"]
    r = a.client.post(
        url + "/cancel", json={"expectedVersion": 1}, headers=a.headers(key="cancel")
    )
    assert r.status_code == 200 and r.json()["state"] == "cancelled"
    assert (
        a.client.post(
            url + "/cancel",
            json={"expectedVersion": 1},
            headers=a.headers(key="cancel"),
        ).json()
        == r.json()
    )
    assert (
        a.client.post(
            url + "/cancel",
            json={"expectedVersion": 2},
            headers=a.headers(key="cancel"),
        ).status_code
        == 409
    )
    with a.e.db.transaction(a.e.tenant) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM inv.outbox WHERE run_id=%s AND event_type='inv.run.cancel_requested'",
                (run["runId"],),
            ).fetchone()["n"]
            == 1
        )


def test_public_identity_scope_and_body_cannot_supply_authority(api):
    a = api
    url = a.url + "/runs/" + a.run["runId"]
    assert (
        a.client.get(
            url, headers={"X-Tenant-ID": a.e.tenant, "X-Subject": "requester"}
        ).status_code
        == 401
    )
    assert a.client.get(url, headers=a.headers("outsider")).status_code == 403
    assert (
        a.client.post(
            url + "/cancel",
            json={"expectedVersion": 3, "subjectId": "requester"},
            headers=a.headers(),
        ).status_code
        == 422
    )
    assert (
        a.client.post(
            url + "/cancel", json={"expectedVersion": 3}, headers=a.headers("alice")
        ).status_code
        == 403
    )
    with psycopg.connect(a.e.owner) as conn:
        other_project = new_id("prj")
        conn.execute(
            "INSERT INTO inv.projects VALUES(%s,%s)", (a.e.tenant, other_project)
        )
        conn.execute(
            "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request) VALUES(%s,%s,%s,true)",
            (a.e.tenant, other_project, a.jwt.subject("requester")),
        )
    assert (
        a.client.get(
            "/v1/projects/" + other_project + "/runs/" + a.run["runId"],
            headers=a.headers(),
        ).status_code
        == 404
    )


def test_grant_revocation_applies_to_replays_and_inventory_is_explicit(api):
    a = api
    assert a.client.get(a.url + "/nodes", headers=a.headers()).json() == {"items": []}
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)",
            (a.e.tenant, a.e.project, a.e.node),
        )
    assert (
        a.client.get(a.url + "/nodes", headers=a.headers()).json()["items"][0]["nodeId"]
        == a.e.node
    )
    assert (
        a.client.post(a.url + "/runs", json={}, headers=a.headers()).status_code == 201
    )
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
            (a.e.tenant, a.jwt.subject("requester")),
        )
    assert (
        a.client.post(a.url + "/runs", json={}, headers=a.headers()).status_code == 403
    )


def test_authenticated_approval_votes_require_two_distinct_people(api):
    a = api
    row = request(a)
    url = a.url + "/approvals/" + row["approvalId"]
    assert (
        a.client.post(url + "/challenge", json={}, headers=a.headers()).status_code
        == 403
    )
    for actor, expected in [("alice", "pending"), ("bob", "approved")]:
        challenge = a.client.post(url + "/challenge", json={}, headers=a.headers(actor))
        assert challenge.status_code == 200
        body = {
            "decision": "approve",
            "nonce": challenge.json()["nonce"],
            "actionDigest": row["actionDigest"],
        }
        vote = a.client.post(
            url + "/decision", json=body, headers=a.headers(actor, key="vote-" + actor)
        )
        assert vote.status_code == 200 and vote.json()["status"] == expected
    assert (
        a.client.post(
            url + "/challenge", json={}, headers=a.headers("alice")
        ).status_code
        == 403
    )


def test_per_run_event_order_blocks_late_commit_and_never_exposes_payload(api):
    a = api
    p = a.people["requester"]
    first_ready = Event()
    finish = Event()

    def first():
        with a.e.db.transaction(a.e.tenant) as conn:
            event(
                conn,
                a.e.tenant,
                a.run["runId"],
                "inv.synthetic.first",
                {"secret": "never-public"},
            )
            first_ready.set()
            assert finish.wait(2)

    def second():
        with a.e.db.transaction(a.e.tenant) as conn:
            event(
                conn,
                a.e.tenant,
                a.run["runId"],
                "inv.synthetic.second",
                {"secret": "never-public"},
            )

    initial = a.control.events(p, a.e.project, a.run["runId"])
    cursor = initial[-1]["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        x = pool.submit(first)
        assert first_ready.wait(2)
        y = pool.submit(second)
        assert a.control.events(p, a.e.project, a.run["runId"], cursor) == []
        finish.set()
        x.result()
        y.result()
    page = a.control.events(p, a.e.project, a.run["runId"], cursor)
    assert [e["eventType"] for e in page] == [
        "inv.synthetic.first",
        "inv.synthetic.second",
    ]
    assert "secret" not in json.dumps(page)
    assert a.control.events(p, a.e.project, a.run["runId"], page[-1]["id"]) == []
    with pytest.raises(DomainError):
        a.control.events(
            p, a.e.project, a.run["runId"], a.e.epoch + ":" + new_id("run") + ":1"
        )
    with a.e.db.transaction(a.e.tenant) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("DELETE FROM inv.outbox WHERE run_id=%s", (a.run["runId"],))


def test_event_stream_closes_on_token_expiry_and_can_reconnect(api):
    a = api
    url = a.url + "/runs/" + a.run["runId"] + "/events"
    token = a.jwt.token(claims={"exp": int(time.time()) + 2})
    r = a.client.get(url, headers={"Authorization": "Bearer " + token})
    assert (
        r.status_code == 200
        and "event: inv.event" in r.text
        and "inv.stream.closed" in r.text
    )
    ids = [line[4:] for line in r.text.splitlines() if line.startswith("id: ")]
    assert len(ids) == 3
    # Reconnect with same exact cursor emits no duplicate; short token closes stream.
    r = a.client.get(
        url,
        headers={
            "Authorization": "Bearer "
            + a.jwt.token(claims={"exp": int(time.time()) + 2}),
            "Last-Event-ID": ids[-1],
        },
    )
    assert r.status_code == 200 and "event: inv.event" not in r.text


def test_error_response_never_contains_database_diagnostics(api, monkeypatch):
    a = api

    def broken(*args, **kwargs):
        raise RuntimeError("postgres://secret-user:secret-token@private-host")

    monkeypatch.setattr(a.e.db, "transaction", broken)
    r = a.client.get(a.url + "/nodes", headers=a.headers())
    assert (
        r.status_code == 503
        and "secret" not in r.text
        and r.headers["content-type"].startswith("application/problem+json")
    )
    assert r.json()["traceId"] == r.headers["traceparent"].split("-")[1]
