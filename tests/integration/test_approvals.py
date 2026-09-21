from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4
import hashlib
import json
import time

import psycopg
import pytest
from inv.approvals import ApprovalStore, Principal
from inv.contracts import validate_contract
from inv.db import Database
from inv.errors import DomainError
from inv.ids import new_id
from inv.policy import action_digest

pytestmark = pytest.mark.postgres


@pytest.fixture
def approval(env):
    e = env
    store = ApprovalStore(e.db)
    people = {
        name: Principal(e.tenant, name)
        for name in ["requester", "alice", "bob", "outsider"]
    }
    with psycopg.connect(e.owner) as conn:
        for name in ["requester", "alice", "bob"]:
            conn.execute(
                "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request,can_approve) VALUES(%s,%s,%s,%s,true)",
                (e.tenant, e.project, name, name == "requester"),
            )
    run = e.runs.create(e.tenant, e.project)
    for state in ["validated", "planned"]:
        run = e.runs.transition(
            e.tenant, run["runId"], state, expected_version=run["version"]
        )
    workload = {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "Workload",
        "workloadId": new_id("wld"),
        "tenantId": e.tenant,
        "projectId": e.project,
        "workspaceId": new_id("wsp"),
        "resources": {
            "cpuMillis": 1,
            "memoryBytes": 1,
            "gpuCount": 0,
            "minVramBytes": 0,
        },
        "imageDigest": "sha256:" + "a" * 64,
        "command": ["synthetic-private-command"],
        "timeoutSeconds": 30,
    }
    policy = {
        "decisionId": str(uuid4()),
        "tenantId": e.tenant,
        "projectId": e.project,
        "subjectId": "requester",
        "effect": "require_approval",
        "riskLevel": "L2",
        "actionDigest": action_digest(workload),
        "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "requiredApprovals": 2,
        "approvedBy": [],
    }
    return SimpleNamespace(
        e=e, store=store, people=people, run=run, workload=workload, policy=policy
    )


def request(a, *, key="request"):
    return a.store.request(
        a.people["requester"],
        a.run["runId"],
        a.workload,
        a.policy,
        policy_version="roof:test:1",
        expected_version=a.run["version"],
        key=key,
    )


def challenge(a, row, actor="alice"):
    result = a.store.challenge(a.people[actor], a.e.project, row["approvalId"])
    validate_contract("ApprovalChallenge", result)
    return result["nonce"]


def decide(a, row, actor, nonce, *, decision="approve", key=None, digest=None):
    result = a.store.decide(
        a.people[actor],
        a.e.project,
        row["approvalId"],
        decision,
        nonce,
        action_digest=digest or row["actionDigest"],
        key=key or "decision:" + actor,
    )
    validate_contract("ApprovalView", result)
    return result


def approved(a):
    row = request(a)
    for actor in ["alice", "bob"]:
        row = decide(a, row, actor, challenge(a, row, actor))
    assert row["status"] == "approved"
    return row


def dispatch(a, row, *, key="dispatch", workload=None):
    result = a.store.dispatch(
        a.people["requester"],
        a.e.project,
        row["approvalId"],
        workload or a.workload,
        key=key,
    )
    validate_contract("AuthorizedCommand", result)
    return result


def count(a, table):
    # Table names are test constants, never application input.
    from psycopg import sql

    with a.e.db.transaction(a.e.tenant) as conn:
        return conn.execute(
            sql.SQL("SELECT count(*) AS n FROM inv.{}").format(sql.Identifier(table))
        ).fetchone()["n"]


def test_request_replay_and_scope_are_immutable(approval):
    a = approval
    row = request(a)
    validate_contract("ApprovalView", row)
    assert request(a) == row and count(a, "approval_requests") == 1
    with a.e.db.transaction(a.e.tenant) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "UPDATE inv.approval_requests SET action_digest=%s WHERE approval_id=%s",
                ("b" * 64, row["approvalId"]),
            )
    a.policy["decisionId"] = str(uuid4())
    with pytest.raises(DomainError, match="IDEM-0001"):
        request(a)


@pytest.mark.parametrize(
    "change",
    [
        {"riskLevel": "L3"},
        {"riskLevel": "L2", "requiredApprovals": 1},
        {"effect": "allow"},
        {"effect": "deny"},
        {"approvedBy": ["alice", "bob"]},
        {"subjectId": "outsider"},
        {"actionDigest": "b" * 64},
        {"expiresAt": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()},
        {"expiresAt": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()},
    ],
)
def test_untrusted_or_weakened_policy_cannot_create_approval(approval, change):
    a = approval
    a.policy.update(change)
    with pytest.raises(DomainError):
        request(a)
    assert count(a, "approval_requests") == 0
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "planned"


def test_quorum_and_direct_state_bypass_are_blocked(approval):
    a = approval
    row = request(a)
    with pytest.raises(DomainError, match="AUTH-0033"):
        challenge(a, row, "requester")
    with pytest.raises(DomainError, match="AUTH-0030"):
        challenge(a, row, "outsider")
    with pytest.raises(DomainError):
        dispatch(a, row)
    row = decide(a, row, "alice", challenge(a, row))
    assert row["status"] == "pending"
    with pytest.raises(DomainError):
        dispatch(a, row)
    with pytest.raises(psycopg.errors.CheckViolation):
        a.e.runs.transition(
            a.e.tenant, a.run["runId"], "scheduled", expected_version=row["runVersion"]
        )
    with a.e.db.transaction(a.e.tenant) as conn:
        assert not conn.execute(
            "SELECT 1 FROM inv.outbox WHERE event_type='inv.command.authorized'"
        ).fetchone()
    assert count(a, "approval_dispatches") == 0


def test_challenge_is_actor_bound_rotating_and_digest_bound(approval):
    a = approval
    row = request(a)
    old = challenge(a, row)
    fresh = challenge(a, row)
    assert fresh != old
    with pytest.raises(DomainError, match="AUTH-0034"):
        decide(a, row, "alice", old)
    with pytest.raises(DomainError, match="AUTH-0034"):
        decide(a, row, "bob", fresh)
    with pytest.raises(DomainError, match="AUTH-0033"):
        decide(a, row, "alice", fresh, digest="c" * 64)
    assert count(a, "approval_votes") == 0
    assert decide(a, row, "alice", fresh)["status"] == "pending"
    with pytest.raises(DomainError, match="AUTH-0033"):
        decide(a, row, "alice", fresh, key="new-key")
    with pytest.raises(DomainError, match="AUTH-0033"):
        challenge(a, row)
    # No raw nonce or action in the persisted ledger, audit, or events.
    with a.e.db.transaction(a.e.tenant) as conn:
        stored = {
            t: conn.execute("SELECT to_jsonb(t) AS row FROM inv." + t + " t").fetchall()
            for t in [
                "approval_nonces",
                "approval_votes",
                "approval_audit",
                "outbox",
                "idempotency",
            ]
        }
    serial = json.dumps(stored, default=str)
    assert (
        fresh not in serial
        and old not in serial
        and "synthetic-private-command" not in serial
    )
    assert hashlib.sha256(fresh.encode()).hexdigest() in serial


def test_expired_nonce_does_not_consume_vote(approval):
    a = approval
    row = request(a)
    nonce = challenge(a, row)
    # Simulate an elapsed challenge using only this fixture's isolated database.
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.approval_nonces SET expires_at=clock_timestamp()-interval '1 second' WHERE approval_id=%s",
            (row["approvalId"],),
        )
    with pytest.raises(DomainError, match="AUTH-0034"):
        decide(a, row, "alice", nonce)
    assert count(a, "approval_votes") == 0
    assert decide(a, row, "alice", challenge(a, row))["status"] == "pending"


def test_same_decision_race_is_exactly_once_and_survives_store_restart(approval):
    a = approval
    row = request(a)
    nonce = challenge(a, row)
    barrier = Barrier(8)

    def call(_):
        barrier.wait(timeout=10)
        return decide(a, row, "alice", nonce)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(call, range(8)))
    assert all(r == results[0] for r in results)
    assert count(a, "approval_votes") == 1 and count(a, "approval_audit") == 2
    a.store = ApprovalStore(Database(a.e.runtime, recovery_epoch=a.e.epoch))
    assert decide(a, row, "alice", nonce) == results[0]
    with pytest.raises(DomainError, match="IDEM-0001"):
        decide(a, row, "alice", nonce, decision="reject")


def test_distinct_voters_race_and_dispatch_race_emit_one_command(approval):
    a = approval
    row = request(a)
    nonces = {p: challenge(a, row, p) for p in ["alice", "bob"]}
    barrier = Barrier(2)

    def vote(actor):
        barrier.wait(timeout=10)
        return decide(a, row, actor, nonces[actor])

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(vote, nonces))
    assert {r["status"] for r in results} == {"pending", "approved"}
    barrier = Barrier(8)

    def send(_):
        barrier.wait(timeout=10)
        return dispatch(a, row)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(send, range(8)))
    assert all(r == results[0] for r in results)
    assert count(a, "approval_dispatches") == 1
    with a.e.db.transaction(a.e.tenant) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM inv.outbox WHERE event_type='inv.command.authorized'"
            ).fetchone()["n"]
            == 1
        )
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "scheduled"
    a.store = ApprovalStore(Database(a.e.runtime, recovery_epoch=a.e.epoch))
    assert dispatch(a, row) == results[0]
    with pytest.raises(DomainError, match="AUTH-0031"):
        dispatch(a, row, key="second-command")


@pytest.mark.parametrize("actor", ["requester", "alice"])
def test_revoked_grants_stop_dispatch_and_cannot_be_self_restored(approval, actor):
    a = approval
    row = approved(a)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
            (a.e.tenant, actor),
        )
    with pytest.raises(DomainError, match="AUTH-0030"):
        dispatch(a, row)
    assert count(a, "approval_dispatches") == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with a.e.db.transaction(a.e.tenant) as conn:
            conn.execute(
                "UPDATE inv.project_grants SET enabled=true WHERE subject_id=%s",
                (actor,),
            )
    with pytest.raises(psycopg.errors.CheckViolation):
        with a.e.db.transaction(a.e.tenant) as conn:
            conn.execute(
                "UPDATE inv.project_grants SET lock_sentinel=false WHERE subject_id=%s",
                (actor,),
            )


def test_content_change_wrong_tenant_and_wrong_project_are_denied(approval):
    a = approval
    row = approved(a)
    changed = deepcopy(a.workload)
    changed["command"] = ["different"]
    with pytest.raises(DomainError, match="AUTH-0011"):
        dispatch(a, row, workload=changed)
    with pytest.raises(DomainError, match="RES-0004"):
        a.store.challenge(Principal(a.e.other, "alice"), a.e.project, row["approvalId"])
    with pytest.raises(DomainError, match="RES-0004"):
        a.store.challenge(a.people["alice"], new_id("prj"), row["approvalId"])
    with a.e.db.transaction(a.e.other) as conn:
        for table in [
            "project_grants",
            "approval_requests",
            "approval_nonces",
            "approval_votes",
            "approval_audit",
            "approval_dispatches",
        ]:
            assert not conn.execute("SELECT 1 FROM inv." + table).fetchone()
    assert count(a, "approval_dispatches") == 0


@pytest.mark.parametrize("phase", ["decision", "dispatch"])
def test_audit_failure_rolls_back_nonce_vote_dispatch_and_outbox(
    approval, monkeypatch, phase
):
    a = approval
    row = approved(a) if phase == "dispatch" else request(a)
    nonce = challenge(a, row) if phase == "decision" else None
    tables = [
        "approval_votes",
        "approval_dispatches",
        "approval_audit",
        "outbox",
        "idempotency",
    ]
    before = {t: count(a, t) for t in tables}
    original = a.store._audit

    def broken(*args):
        raise RuntimeError("injected audit failure")

    monkeypatch.setattr(a.store, "_audit", broken)
    with pytest.raises(RuntimeError, match="injected"):
        if phase == "decision":
            decide(a, row, "alice", nonce)
        else:
            dispatch(a, row)
    assert {t: count(a, t) for t in tables} == before
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "awaiting_approval"
    monkeypatch.setattr(a.store, "_audit", original)
    if phase == "decision":
        assert decide(a, row, "alice", nonce)["status"] == "pending"
    else:
        assert dispatch(a, row)["runId"] == a.run["runId"]


def test_rejection_is_terminal_and_audited(approval):
    a = approval
    row = request(a)
    nonce = challenge(a, row)
    result = decide(a, row, "alice", nonce, decision="reject")
    assert result["status"] == "rejected"
    assert decide(a, row, "alice", nonce, decision="reject") == result
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "failed"
    with pytest.raises(DomainError):
        dispatch(a, row)
    assert count(a, "approval_audit") == 2
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with a.e.db.transaction(a.e.tenant) as conn:
            conn.execute("DELETE FROM inv.approval_votes")


@pytest.mark.parametrize("has_quorum", [False, True])
def test_expiry_closes_pending_or_approved_run_once(approval, has_quorum):
    a = approval
    a.policy["expiresAt"] = (
        datetime.now(timezone.utc) + timedelta(seconds=2)
    ).isoformat()
    row = approved(a) if has_quorum else request(a)
    assert not a.store.expire(a.e.tenant, a.e.project, row["approvalId"])
    wait = (
        datetime.fromisoformat(row["expiresAt"]) - datetime.now(timezone.utc)
    ).total_seconds()
    time.sleep(max(0, wait) + 0.05)
    with pytest.raises(DomainError, match="AUTH-0031"):
        dispatch(a, row)
    assert a.store.expire(a.e.tenant, a.e.project, row["approvalId"])
    assert not a.store.expire(a.e.tenant, a.e.project, row["approvalId"])
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "failed"


@pytest.mark.parametrize("change", ["cancel", "epoch"])
def test_cancelled_run_or_restored_epoch_invalidates_approval(approval, change):
    a = approval
    row = approved(a)
    if change == "cancel":
        a.e.runs.transition(
            a.e.tenant, a.run["runId"], "cancelled", expected_version=row["runVersion"]
        )
    else:
        with psycopg.connect(a.e.owner) as conn:
            conn.execute("UPDATE inv.control_epoch SET epoch=%s", (uuid4(),))
    with pytest.raises(DomainError):
        dispatch(a, row)
    with psycopg.connect(a.e.owner) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM inv.approval_dispatches WHERE tenant_id=%s",
                (a.e.tenant,),
            ).fetchone()[0]
            == 0
        )
    if change == "epoch":
        with psycopg.connect(a.e.owner) as conn:
            new_epoch = str(
                conn.execute("SELECT epoch FROM inv.control_epoch").fetchone()[0]
            )
        a.store = ApprovalStore(Database(a.e.runtime, recovery_epoch=new_epoch))
        with pytest.raises(DomainError, match="AUTH-0031"):
            dispatch(a, row)
