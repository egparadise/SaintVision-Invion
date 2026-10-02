# -*- coding: utf-8 -*-
"""Negative tests for clearing a **node quarantine**, with real PostgreSQL (card 227).

``#318`` landed the durable node quarantine channel, and its r4 left a follow-up: the negative
coverage around clearing containment was generic (written for ``kill``/``drain``), so nothing
pinned the quarantine-specific path -- the one where ``resume`` is also the only reconciliation
for a Node the control plane fenced after a proven violation.  This file adds only tests; the
product is unchanged, and anything these measurements show to be wrong is reported to Codex
rather than patched here.

The quarantine is created by the product's own fence (``BuildExecutionService
._mark_node_quarantined``), not by an UPDATE this file writes, so the state under test is the
state a lost build race actually leaves: ``inv.nodes.status = 'quarantined'`` plus the
``inv.build.node_quarantined`` outbox record that names the cause.

What is fabricated and why: the readiness query behind ``resume`` requires a fresh authenticated
channel and resource observation, which a real Node agent writes over mTLS.  ``fresh_observation``
writes those rows directly, because this file is about the approval/audit gates in front of the
status change, not about the probe -- the Docker-backed
``test_drain_preserves_inflight_execution_and_resume_needs_fresh_probe`` already measures the real
observation path, including a stale snapshot being refused.
"""

from uuid import uuid4

import psycopg
import pytest

from inv.approvals import Principal, digest
from inv.build_execution import BuildExecutionService
from inv.errors import DomainError
from inv.ids import new_id

from test_approvals import approval, count  # noqa: F401  (fixture chain)
from test_control_api import api  # noqa: F401
from test_containment import ops, operators  # noqa: F401

pytestmark = pytest.mark.postgres

QUARANTINE_REASON = "VERIFY-0022"


def quarantine_identity() -> dict:
    return {
        "build_session_id": new_id("bld"),
        "lease_id": new_id("lse"),
        "resource_id": new_id("res"),
        "decision_id": new_id("dec"),
        "binding_digest": "a" * 64,
        "daemon_identity": "b" * 64,
    }


def quarantine_the_node(a, reason_code: str = QUARANTINE_REASON) -> dict:
    """Fence the Node the way the product fences it after a lost build race."""

    run = a.e.runs.create(a.e.tenant, a.e.project)
    identity = quarantine_identity()
    BuildExecutionService(a.e.db, None, None)._mark_node_quarantined(
        tenant_id=a.e.tenant,
        project_id=a.e.project,
        run_id=run["runId"],
        leased_node_id=a.e.node,
        recovery_epoch=a.e.db.recovery_epoch,
        reason_code=reason_code,
        identity=identity,
    )
    with a.e.db.transaction(a.e.tenant) as conn:
        status = conn.execute(
            "SELECT status FROM inv.nodes WHERE node_id=%s", (a.e.node,)
        ).fetchone()["status"]
    assert status == "quarantined", "the product fence did not take"
    return {"run": run, "identity": identity}


def fresh_observation(a, *, node_id: str | None = None) -> None:
    """The authenticated channel and resource observation ``resume`` requires (see module doc)."""

    node_id = node_id or a.e.node
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            """INSERT INTO inv.node_channels
            (tenant_id,node_id,recovery_epoch,version,endpoint,certificate_sha256,
             certificate_not_after,enabled)
            VALUES (%s,%s,%s,1,'https://node.invalid:8443',%s,clock_timestamp()+interval '1 day',true)
            ON CONFLICT (tenant_id,node_id) DO NOTHING""",
            (a.e.tenant, node_id, a.e.db.recovery_epoch, "c" * 64),
        )
        conn.execute(
            """INSERT INTO inv.node_resource_snapshots
            (tenant_id,node_id,recovery_epoch,channel_version,received_at,snapshot)
            VALUES (%s,%s,%s,1,clock_timestamp(),'{}'::jsonb)
            ON CONFLICT (tenant_id,node_id) DO UPDATE SET received_at=clock_timestamp()""",
            (a.e.tenant, node_id, a.e.db.recovery_epoch),
        )
        conn.execute(
            "UPDATE inv.nodes SET heartbeat_at=clock_timestamp(),clock_skew_seconds=0"
            " WHERE tenant_id=%s AND node_id=%s",
            (a.e.tenant, node_id),
        )


def propose(a, *, operation: str = "resume", node_id: str | None = "self", version: int = 0,
            actor: str = "bob", reason: str = "maintenance", key: str | None = None) -> dict:
    target = a.e.node if node_id == "self" else node_id
    return a.control_approvals.propose(
        a.people[actor],
        {"operation": operation, "nodeId": target, "expectedVersion": version,
         "reasonCode": reason},
        key or digest((operation, target, version, actor, reason)),
    )


def vote(a, approval_id: str, voter: str, *, decision: str = "approve",
         key: str | None = None) -> dict:
    challenge = a.control_approvals.challenge(a.people[voter], approval_id)
    return a.control_approvals.decide(
        a.people[voter], approval_id, {**challenge, "decision": decision}, key or voter
    )


def clear(a, approval_id: str, *, version: int = 0, actor: str = "bob", key: str = "clear",
          reason: str = "maintenance", node_id: str | None = "self") -> dict:
    return a.ops.change(
        a.people[actor],
        "resume",
        {"approvalId": approval_id, "expectedVersion": version, "reasonCode": reason},
        key,
        a.e.node if node_id == "self" else node_id,
    )


def node_status(a, node_id: str | None = None) -> str:
    with a.e.db.transaction(a.e.tenant) as conn:
        return conn.execute(
            "SELECT status FROM inv.nodes WHERE node_id=%s", (node_id or a.e.node,)
        ).fetchone()["status"]


def quarantine_events(a) -> list[dict]:
    with a.e.db.transaction(a.e.tenant) as conn:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT event_type,payload FROM inv.outbox WHERE event_type LIKE 'inv.build.%'"
                " ORDER BY event_type"
            ).fetchall()
        ]


def test_clearing_a_quarantine_needs_two_votes_and_one_is_not_enough(ops):
    """One approval is not two, and the refusal leaves no audit row and no status change.

    ``resume`` is the only reconciliation path for a fenced Node, so a single operator must not
    be able to walk it.  The request row is inserted before the approval is consumed, so this
    also measures that the refusal rolls the row back with the status.
    """

    a = ops
    quarantine_the_node(a)
    fresh_observation(a)
    row = propose(a)
    assert vote(a, row["approvalId"], "alice")["status"] == "pending"

    with pytest.raises(DomainError) as caught:
        clear(a, row["approvalId"])
    assert caught.value.code == "AUTH-0063"
    assert node_status(a) == "quarantined"
    assert count(a, "containment_requests") == 0

    # The second distinct person makes the same request succeed -- so the refusal above was
    # about the count of people, not about anything else in this state.
    assert vote(a, row["approvalId"], "carol")["status"] == "approved"
    assert clear(a, row["approvalId"])["control"]["nodeStatus"] == "online"


def test_one_person_cannot_be_both_approvals_of_a_quarantine_clear(ops):
    """The same human twice is one human: self-approval and a repeated vote are both refused.

    ``containment_votes`` is keyed by actor, so a second vote from the same subject replays the
    first rather than adding one, and a requester who grants themselves ``can_approve`` is
    refused at the challenge.  Either way the vote count stays 1 and the Node stays fenced.
    """

    a = ops
    quarantine_the_node(a)
    fresh_observation(a)
    row = propose(a)
    first = vote(a, row["approvalId"], "alice")
    assert first["status"] == "pending"

    # The same approver again, with a new idempotency key: a different key for the same actor is
    # a conflict, not a second person.
    with pytest.raises(DomainError) as repeated:
        vote(a, row["approvalId"], "alice", key="alice-again")
    assert repeated.value.code == "IDEM-0001"

    # The requester tries to be the second person.
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.operator_grants SET can_approve=true WHERE tenant_id=%s AND subject_id=%s",
            (a.e.tenant, a.people["bob"].subject_id),
        )
    with pytest.raises(DomainError) as itself:
        vote(a, row["approvalId"], "bob")
    assert itself.value.code == "AUTH-0063"

    with a.e.db.transaction(a.e.tenant) as conn:
        votes = conn.execute(
            "SELECT count(*) AS n FROM inv.containment_votes WHERE approval_id=%s",
            (row["approvalId"],),
        ).fetchone()["n"]
    assert votes == 1
    with pytest.raises(DomainError, match="AUTH-0063"):
        clear(a, row["approvalId"])
    assert node_status(a) == "quarantined"
    assert count(a, "containment_requests") == 0


@pytest.mark.parametrize("actor", ["requester", "alice", "outsider"])
def test_an_actor_without_can_resume_cannot_clear_a_quarantine(ops, actor):
    """Clearing is a ``can_resume`` act, and the other grants are not it.

    ``requester`` may contain (``can_contain``), ``alice`` may approve (``can_approve``), and
    ``outsider`` holds no operator grant at all.  All three are refused before any state moves --
    and the approval cannot even be proposed by them, which is where the refusal lands.
    """

    a = ops
    quarantine_the_node(a)
    fresh_observation(a)
    row = propose(a)
    for voter in ("alice", "carol"):
        vote(a, row["approvalId"], voter)

    with pytest.raises(DomainError) as caught:
        clear(a, row["approvalId"], actor=actor)
    assert caught.value.code == "AUTH-0062"
    assert node_status(a) == "quarantined"
    assert count(a, "containment_requests") == 0


def test_an_expired_or_forged_approval_cannot_clear_a_quarantine(ops):
    """Four ways to arrive without two current people, each refused on its own.

    (1) an approval whose window has passed, (2) an id nobody issued, (3) a row whose status was
    written as ``approved`` with no votes behind it, and (4) a vote whose recorded person is not
    the person the grant says.  The fourth is the one a forger would reach for: the row shape is
    right and only the identity behind it is wrong.
    """

    a = ops
    quarantine_the_node(a)
    fresh_observation(a)
    row = propose(a)
    for voter in ("alice", "carol"):
        vote(a, row["approvalId"], voter)

    expired = str(uuid4())
    forged = str(uuid4())
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            """INSERT INTO inv.containment_approvals
            SELECT tenant_id,%s,%s,requester_id,requester_person_id,operation,node_id,
                   expected_version,gate_version,recovery_epoch,reason_code,content_digest,
                   request_hash,status,statement_timestamp()-interval '5 minutes',
                   statement_timestamp()-interval '1 second',NULL
            FROM inv.containment_approvals WHERE tenant_id=%s AND approval_id=%s""",
            (expired, str(expired), a.e.tenant, row["approvalId"]),
        )
        conn.execute(
            """INSERT INTO inv.containment_votes
            SELECT tenant_id,%s,actor_id,person_id,key,decision,request_hash,response,created_at
            FROM inv.containment_votes WHERE tenant_id=%s AND approval_id=%s""",
            (expired, a.e.tenant, row["approvalId"]),
        )
        # An "approved" row with no votes at all.
        conn.execute(
            """INSERT INTO inv.containment_approvals
            SELECT tenant_id,%s,%s,requester_id,requester_person_id,operation,node_id,
                   expected_version,gate_version,recovery_epoch,reason_code,content_digest,
                   request_hash,'approved',created_at,expires_at,NULL
            FROM inv.containment_approvals WHERE tenant_id=%s AND approval_id=%s""",
            (forged, str(forged), a.e.tenant, row["approvalId"]),
        )

    with pytest.raises(DomainError) as lapsed:
        clear(a, expired, key="expired")
    assert lapsed.value.code == "AUTH-0063" and "expired" in lapsed.value.detail

    with pytest.raises(DomainError) as unknown:
        clear(a, str(uuid4()), key="unknown")
    assert unknown.value.code == "RES-0004"

    with pytest.raises(DomainError) as voteless:
        clear(a, forged, key="voteless")
    assert voteless.value.code == "AUTH-0063"

    # A vote whose recorded person is not the person that actor's grant carries.  Measured while
    # writing this: the database refuses to *repoint* a recorded vote at all -- the votes table
    # carries the same immutability trigger as the request history -- so the forgery has to be
    # written as a new row, and the application still refuses it.
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(
                "UPDATE inv.containment_votes SET person_id=%s WHERE tenant_id=%s"
                " AND approval_id=%s",
                (uuid4(), a.e.tenant, row["approvalId"]),
            )
    impostor = str(uuid4())
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            """INSERT INTO inv.containment_approvals
            SELECT tenant_id,%s,%s,requester_id,requester_person_id,operation,node_id,
                   expected_version,gate_version,recovery_epoch,reason_code,content_digest,
                   request_hash,'approved',created_at,expires_at,NULL
            FROM inv.containment_approvals WHERE tenant_id=%s AND approval_id=%s""",
            (impostor, str(impostor), a.e.tenant, row["approvalId"]),
        )
        conn.execute(
            """INSERT INTO inv.containment_votes
            SELECT tenant_id,%s,actor_id,
                   CASE WHEN actor_id=%s THEN %s::uuid ELSE person_id END,
                   key,decision,request_hash,response,created_at
            FROM inv.containment_votes WHERE tenant_id=%s AND approval_id=%s""",
            (impostor, a.people["carol"].subject_id, str(uuid4()), a.e.tenant,
             row["approvalId"]),
        )
    with pytest.raises(DomainError) as forged_person:
        clear(a, impostor, key="impostor")
    assert forged_person.value.code == "AUTH-0063"

    assert node_status(a) == "quarantined"
    assert count(a, "containment_requests") == 0


def copy_approval(a, source: str, approval_id: str, status: str, voters: tuple[str, ...]) -> None:
    """A hand-written approval row with exactly the votes named, for the forgery cases.

    Written with the owner connection because the application never produces these states: an
    ``approved`` row with one vote, or a ``pending`` row with two.  Each one isolates a product
    check that the ordinary paths mask -- measured by mutating the product and watching which
    test noticed (card 227).
    """

    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            """INSERT INTO inv.containment_approvals
            SELECT tenant_id,%s,%s,requester_id,requester_person_id,operation,node_id,
                   expected_version,gate_version,recovery_epoch,reason_code,content_digest,
                   request_hash,%s,created_at,expires_at,NULL
            FROM inv.containment_approvals WHERE tenant_id=%s AND approval_id=%s""",
            (approval_id, str(approval_id), status, a.e.tenant, source),
        )
        for voter in voters:
            conn.execute(
                """INSERT INTO inv.containment_votes
                SELECT tenant_id,%s,actor_id,person_id,key,decision,request_hash,response,created_at
                FROM inv.containment_votes
                WHERE tenant_id=%s AND approval_id=%s AND actor_id=%s""",
                (approval_id, a.e.tenant, source, a.people[voter].subject_id),
            )


def test_an_approved_row_with_one_vote_behind_it_cannot_clear_a_quarantine(ops):
    """Two distinct people is counted, not inferred from the status word.

    Measured by mutation: with the ordinary flow, a single vote leaves the approval ``pending``,
    so the status check refuses first and the vote count is never reached.  This row says
    ``approved`` with one vote behind it, which is the state a forger would write, and it is the
    only case where the count itself is the refusal.
    """

    a = ops
    quarantine_the_node(a)
    fresh_observation(a)
    row = propose(a)
    for voter in ("alice", "carol"):
        vote(a, row["approvalId"], voter)

    one_vote = str(uuid4())
    copy_approval(a, row["approvalId"], one_vote, "approved", ("alice",))
    with pytest.raises(DomainError) as caught:
        clear(a, one_vote, key="one-vote")
    assert caught.value.code == "AUTH-0063"
    assert node_status(a) == "quarantined"
    assert count(a, "containment_requests") == 0


def test_two_votes_under_a_status_that_was_never_approved_cannot_clear_a_quarantine(ops):
    """The status is a fact the votes produced, so a row that skips it is refused.

    With two real votes copied under a ``pending`` row, every other check passes -- the people are
    distinct and current, the scope matches -- and the refusal has to come from the status.  The
    database's own trigger refuses to *change* a status this way, so the forgery is an insert.
    """

    a = ops
    quarantine_the_node(a)
    fresh_observation(a)
    row = propose(a)
    for voter in ("alice", "carol"):
        vote(a, row["approvalId"], voter)

    pending = str(uuid4())
    copy_approval(a, row["approvalId"], pending, "pending", ("alice", "carol"))
    with pytest.raises(DomainError) as caught:
        clear(a, pending, key="pending")
    assert caught.value.code == "AUTH-0063"
    assert node_status(a) == "quarantined"
    assert count(a, "containment_requests") == 0


def test_the_requester_cannot_be_counted_as_one_of_the_two_people(ops):
    """The requester's own person is already in the set, so their vote is not a second person.

    ``inv.containment_votes`` is unique per person, so the only way to reach this check is the
    requester voting on their own request -- which is exactly what an operator with both grants
    would do.  The row is inserted because ``challenge`` refuses it earlier in the live flow, and
    this test exists to keep the *consume*-side check load-bearing too.
    """

    a = ops
    quarantine_the_node(a)
    fresh_observation(a)
    row = propose(a)
    for voter in ("alice", "carol"):
        vote(a, row["approvalId"], voter)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.operator_grants SET can_approve=true WHERE tenant_id=%s AND subject_id=%s",
            (a.e.tenant, a.people["bob"].subject_id),
        )
        person = conn.execute(
            "SELECT person_id FROM inv.operator_grants WHERE tenant_id=%s AND subject_id=%s",
            (a.e.tenant, a.people["bob"].subject_id),
        ).fetchone()[0]

    self_approved = str(uuid4())
    copy_approval(a, row["approvalId"], self_approved, "approved", ("alice",))
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            """INSERT INTO inv.containment_votes
            (tenant_id,approval_id,actor_id,person_id,key,decision,request_hash)
            VALUES (%s,%s,%s,%s,%s,'approve',%s)""",
            (a.e.tenant, self_approved, a.people["bob"].subject_id, person, "self-vote",
             "0" * 64),
        )
    with pytest.raises(DomainError) as caught:
        clear(a, self_approved, key="self-approved")
    assert caught.value.code == "AUTH-0063"
    assert node_status(a) == "quarantined"
    assert count(a, "containment_requests") == 0


def test_an_approval_for_another_node_or_for_the_tenant_gate_cannot_clear_this_node(ops):
    """An approval is bound to its target: another Node, and the tenant-wide gate, are refused.

    The fence is per Node, so a correctly approved ``resume`` of a different Node -- or a
    tenant-wide ``clear`` approved by two people -- must not open this one.  The second case is
    the one a tired operator would try, because the tenant gate is the louder ceremony.
    """

    a = ops
    quarantine_the_node(a)
    fresh_observation(a)
    other_node = new_id("nod")
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch,clock_skew_seconds)"
            " VALUES (%s,%s,'quarantined',%s,0)",
            (a.e.tenant, other_node, a.e.db.recovery_epoch),
        )
    fresh_observation(a, node_id=other_node)

    for_other = propose(a, node_id=other_node)
    for voter in ("alice", "carol"):
        vote(a, for_other["approvalId"], voter, key=f"other-{voter}")
    with pytest.raises(DomainError) as wrong_node:
        clear(a, for_other["approvalId"], key="wrong-node")
    assert wrong_node.value.code == "AUTH-0063"

    gate = propose(a, operation="clear", node_id=None)
    for voter in ("alice", "carol"):
        vote(a, gate["approvalId"], voter, key=f"gate-{voter}")
    with pytest.raises(DomainError) as wrong_scope:
        clear(a, gate["approvalId"], key="wrong-scope")
    assert wrong_scope.value.code == "AUTH-0063"

    assert node_status(a) == "quarantined" and node_status(a, other_node) == "quarantined"
    assert count(a, "containment_requests") == 0


def rows_in(a, tenant: str, statement: str, params=()) -> list[dict]:
    """Read inside ``tenant``'s own transaction, so RLS answers as that tenant."""

    with a.e.db.transaction(tenant) as conn:
        return [dict(row) for row in conn.execute(statement, params).fetchall()]


def second_tenant(a) -> dict:
    """A second tenant with its own node, its own operator people and its own approved resume.

    The other tenant is not a bystander here: it has a complete, valid containment ceremony of its
    own, so the only thing wrong with using its approval on this tenant's Node is the tenant
    boundary itself.
    """

    other = a.e.other
    node = new_id("nod")
    people = {}
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch,clock_skew_seconds)"
            " VALUES (%s,%s,'quarantined',%s,0)",
            (other, node, a.e.db.recovery_epoch),
        )
        for name, resume, approve in (("owner", True, False), ("one", False, True),
                                      ("two", False, True)):
            subject = f"other-{name}"
            people[name] = Principal(other, subject)
            conn.execute(
                "INSERT INTO inv.operator_grants"
                "(tenant_id,subject_id,person_id,can_contain,can_resume,can_approve)"
                " VALUES(%s,%s,%s,false,%s,%s)",
                (other, subject, uuid4(), resume, approve),
            )
    approvals = a.control_approvals
    proposed = approvals.propose(
        people["owner"],
        {"operation": "resume", "nodeId": node, "expectedVersion": 0,
         "reasonCode": "maintenance"},
        "other-tenant-proposal",
    )
    for name in ("one", "two"):
        challenge = approvals.challenge(people[name], proposed["approvalId"])
        decided = approvals.decide(
            people[name], proposed["approvalId"], {**challenge, "decision": "approve"}, name
        )
    assert decided["status"] == "approved"
    return {"tenant": other, "node": node, "people": people,
            "approvalId": proposed["approvalId"]}


def test_an_approval_from_another_tenant_cannot_clear_a_quarantine_in_either_direction(ops):
    """A quarantine clear is bound to its tenant, and the refusal does not disclose the other one.

    Both directions, because a boundary that holds one way and not the other is not a boundary:
    this tenant's operator presenting the other tenant's (correctly approved) approval id, and the
    other tenant's operator presenting this one's.  Row-level security makes each approval
    invisible outside its tenant, so the canonical answer is ``RES-0004`` -- "unavailable" rather
    than "exists but not for you", which is the non-disclosure the boundary is for.

    Nothing may move in either tenant: both Node statuses, both audit tables and both approvals'
    consumption state are read before and after.
    """

    a = ops
    quarantine_the_node(a)
    fresh_observation(a)
    mine = propose(a)
    for voter in ("alice", "carol"):
        vote(a, mine["approvalId"], voter)
    other = second_tenant(a)

    def state() -> dict:
        return {
            "mine_status": node_status(a),
            "other_status": rows_in(a, other["tenant"],
                                   "SELECT status FROM inv.nodes WHERE node_id=%s",
                                   (other["node"],))[0]["status"],
            "mine_requests": rows_in(a, a.e.tenant,
                                     "SELECT count(*) AS n FROM inv.containment_requests")[0]["n"],
            "other_requests": rows_in(a, other["tenant"],
                                      "SELECT count(*) AS n FROM inv.containment_requests")[0]["n"],
            "mine_approval": rows_in(
                a, a.e.tenant,
                "SELECT status,consumed_request_id FROM inv.containment_approvals"
                " WHERE approval_id=%s", (mine["approvalId"],))[0],
            "other_approval": rows_in(
                a, other["tenant"],
                "SELECT status,consumed_request_id FROM inv.containment_approvals"
                " WHERE approval_id=%s", (other["approvalId"],))[0],
        }

    before = state()
    assert before["mine_status"] == "quarantined" and before["other_status"] == "quarantined"
    assert before["mine_approval"]["status"] == before["other_approval"]["status"] == "approved"
    assert before["mine_requests"] == before["other_requests"] == 0

    # This tenant's operator, the other tenant's approval.
    with pytest.raises(DomainError) as forward:
        clear(a, other["approvalId"], key="other-tenant-approval")
    assert forward.value.code == "RES-0004"
    assert "unavailable" in forward.value.detail

    # The other tenant's operator, this tenant's approval -- on the other tenant's own Node.
    with pytest.raises(DomainError) as backward:
        a.ops.change(
            other["people"]["owner"],
            "resume",
            {"approvalId": mine["approvalId"], "expectedVersion": 0,
             "reasonCode": "maintenance"},
            "this-tenant-approval",
            other["node"],
        )
    assert backward.value.code == "RES-0004"

    assert state() == before

    # And each tenant's own approval still works, so the refusals above were about the boundary.
    assert clear(a, mine["approvalId"], key="own-tenant")["control"]["nodeStatus"] == "online"
    assert node_status(a) == "online"
    assert rows_in(a, other["tenant"], "SELECT status FROM inv.nodes WHERE node_id=%s",
                   (other["node"],))[0]["status"] == "quarantined"
    assert rows_in(a, other["tenant"],
                   "SELECT count(*) AS n FROM inv.containment_requests")[0]["n"] == 0


def test_a_clear_without_an_addressable_audit_row_is_refused(ops):
    """No idempotency key, no audit row, no clear -- and the row cannot be rewritten afterwards.

    ``inv.containment_requests`` is where the actor, reason, approval and exact response are
    recorded, and the key is what makes that row addressable.  The product refuses a missing or
    oversized key before anything else, and the table is append-only to the application role, so
    a clear cannot be performed and then unwritten.
    """

    a = ops
    quarantine_the_node(a)
    fresh_observation(a)
    row = propose(a)
    for voter in ("alice", "carol"):
        vote(a, row["approvalId"], voter)

    for key in ("", "k" * 201):
        with pytest.raises(DomainError) as caught:
            clear(a, row["approvalId"], key=key)
        assert caught.value.code == "VAL-0003"
    assert node_status(a) == "quarantined"
    assert count(a, "containment_requests") == 0

    assert clear(a, row["approvalId"], key="recorded")["control"]["nodeStatus"] == "online"
    assert count(a, "containment_requests") == 1
    for statement in (
        "UPDATE inv.containment_requests SET reason_code='other'",
        "DELETE FROM inv.containment_requests",
    ):
        with pytest.raises(psycopg.Error):
            with a.e.db.transaction(a.e.tenant) as conn:
                conn.execute(statement)


def test_clearing_a_quarantine_records_one_audit_row_and_keeps_the_original_cause(ops):
    """The successful clear is recorded exactly once, and it does not erase why the fence existed.

    The audit row names the person who cleared it, the reason they gave and the approval they
    consumed; the ``inv.build.node_quarantined`` record that explains the fence stays as it was.
    A reconciliation that hid its own cause would make the next investigation impossible.
    """

    a = ops
    fenced = quarantine_the_node(a)
    fresh_observation(a)
    before = quarantine_events(a)
    assert [event["event_type"] for event in before] == ["inv.build.node_quarantined"]
    assert before[0]["payload"]["reasonCode"] == QUARANTINE_REASON
    assert before[0]["payload"]["buildSessionId"] == fenced["identity"]["build_session_id"]

    row = propose(a)
    for voter in ("alice", "carol"):
        vote(a, row["approvalId"], voter)
    result = clear(a, row["approvalId"], key="reconcile")
    assert result["control"]["nodeStatus"] == "online"

    assert count(a, "containment_requests") == 1
    with a.e.db.transaction(a.e.tenant) as conn:
        audit = conn.execute(
            "SELECT subject_id,reason_code,node_id,operation,response"
            " FROM inv.containment_requests WHERE key='reconcile'"
        ).fetchone()
        consumed = conn.execute(
            "SELECT status,consumed_request_id FROM inv.containment_approvals WHERE approval_id=%s",
            (row["approvalId"],),
        ).fetchone()
    assert audit["subject_id"] == a.people["bob"].subject_id
    assert (audit["operation"], audit["node_id"], audit["reason_code"]) == (
        "resume", a.e.node, "maintenance",
    )
    assert audit["response"]["approvalId"] == row["approvalId"]
    assert consumed["status"] == "consumed"
    assert str(consumed["consumed_request_id"]) == result["requestId"]
    # The cause is still the cause.
    assert quarantine_events(a) == before


def test_retrying_the_same_clear_is_idempotent_and_the_approval_is_spent(ops):
    """The same key returns the same receipt; a different key cannot spend the approval twice.

    An operator who loses the response and retries must not perform a second reconciliation, and
    the consumed approval must not open the next quarantine.
    """

    a = ops
    quarantine_the_node(a)
    fresh_observation(a)
    row = propose(a)
    for voter in ("alice", "carol"):
        vote(a, row["approvalId"], voter)
    first = clear(a, row["approvalId"], key="retry")
    again = clear(a, row["approvalId"], key="retry")
    assert again == first
    assert count(a, "containment_requests") == 1

    with a.e.db.transaction(a.e.tenant) as conn:
        version = conn.execute(
            "SELECT version FROM inv.node_controls WHERE node_id=%s", (a.e.node,)
        ).fetchone()["version"]
    assert version == first["control"]["version"]

    # Fence it again: the spent approval is not a second permission.
    quarantine_the_node(a)
    fresh_observation(a)
    with pytest.raises(DomainError) as spent:
        clear(a, row["approvalId"], version=version, key="second-use")
    assert spent.value.code == "AUTH-0063"
    assert node_status(a) == "quarantined"


def test_a_transient_channel_refusal_is_not_a_quarantine_to_clear(ops):
    """The two states stay different: a probe failure fences nothing, so there is nothing to clear.

    ``#312`` N2 split them on purpose -- a proven violation after dispatch fences the Node for
    operator reconciliation, while a transient channel failure before dispatch is a retryable
    refusal (``RES-0006``) that must not become an operator-only state.  If a later change made
    the transient path fence the Node, this test fails: the Node would be ``quarantined`` and the
    two-person ceremony would be owed for an error that fixed itself.
    """

    a = ops
    run = a.e.runs.create(a.e.tenant, a.e.project)
    BuildExecutionService(a.e.db, None, None)._record_preflight_unavailable(
        tenant_id=a.e.tenant,
        project_id=a.e.project,
        run_id=run["runId"],
        leased_node_id=a.e.node,
        identity=quarantine_identity(),
    )
    assert node_status(a) == "online"
    events = quarantine_events(a)
    assert [event["event_type"] for event in events] == [
        "inv.build.quarantine_preflight_unavailable"
    ]
    assert events[0]["payload"]["reasonCode"] == "RES-0006"

    # And the clear path has nothing to do here: an online Node is not drained or quarantined.
    fresh_observation(a)
    row = propose(a)
    for voter in ("alice", "carol"):
        vote(a, row["approvalId"], voter)
    with pytest.raises(DomainError) as nothing:
        clear(a, row["approvalId"], key="nothing-to-clear")
    assert nothing.value.code == "LEASE-0003"
    assert count(a, "containment_requests") == 0

    # The proven-violation path, by contrast, does fence it and then owes the full ceremony.
    quarantine_the_node(a)
    assert node_status(a) == "quarantined"
    assert clear(a, row["approvalId"], key="after-fence")["control"]["nodeStatus"] == "online"
