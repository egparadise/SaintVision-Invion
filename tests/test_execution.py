"""S03 execution against a real PostgreSQL.

The claims worth testing here are the ones the database itself enforces or that
only a transaction can demonstrate: a Run cannot be stored as succeeded without
Evidence, the success write is atomic, redelivery is deduplicated, and an
approval does not survive an edit to what it approved.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.runs.state import RunState, TerminationReason
from saintvision.services import evidence as evidence_service
from saintvision.services import runs as run_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 9, 7, 0, 0, tzinfo=UTC)


@pytest.fixture
def project(owner_engine, two_tenants):
    """A tenant with a user, a project, a workspace and a workload."""
    tenant_a, tenant_b = two_tenants
    user_id = new_id("user")
    project_id = new_id("project")
    workspace_id = new_id("workspace")
    workload_id = new_id("workload")
    spec = {"objective": "run the tests", "image": "python:3.12"}
    digest = run_service.workload_digest(spec)

    with owner_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
                "status, created_at, updated_at, version) "
                "VALUES (:u, :t, 'sub', 'User', 'active', now(), now(), 1)"
            ),
            {"u": user_id, "t": tenant_a},
        )
        connection.execute(
            text(
                "INSERT INTO projects (project_id, tenant_id, code, display_name, status, "
                "created_at, version) VALUES (:p, :t, 'alpha', 'Alpha', 'active', now(), 1)"
            ),
            {"p": project_id, "t": tenant_a},
        )
        connection.execute(
            text(
                "INSERT INTO workspaces (workspace_id, tenant_id, project_id, name, status, "
                "created_by_user_id, created_at, version) "
                "VALUES (:w, :t, :p, 'ws1', 'ready', :u, now(), 1)"
            ),
            {"w": workspace_id, "t": tenant_a, "p": project_id, "u": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO workloads (workload_id, tenant_id, project_id, kind, objective, "
                "spec, spec_sha256, contract_version, created_by_user_id, created_at, version) "
                "VALUES (:wl, :t, :p, 'batch', 'run the tests', :spec, :d, '1.0.0', :u, now(), 1)"
            ),
            {
                "wl": workload_id,
                "t": tenant_a,
                "p": project_id,
                "spec": '{"objective": "run the tests", "image": "python:3.12"}',
                "d": digest,
                "u": user_id,
            },
        )
    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_id": user_id,
        "project_id": project_id,
        "workspace_id": workspace_id,
        "workload_id": workload_id,
        "spec": spec,
        "digest": digest,
    }


def _scoped(app_sessionmaker, tenant_id):
    session = app_sessionmaker()
    session.begin()
    ctx = tenant_scope(session, tenant_id)
    ctx.__enter__()
    return session


def _new_run(session, project, **kwargs):
    return run_service.create_run(
        session,
        tenant_id=project["tenant_a"],
        workload_id=project["workload_id"],
        workspace_id=project["workspace_id"],
        requested_by_user_id=project["user_id"],
        now=NOW,
        **kwargs,
    )


def _to_verifying(session, project, run):
    for target in ("validated", "planned", "scheduled"):
        run_service.advance(
            session, tenant_id=project["tenant_a"], run_id=run.run_id, target=target, now=NOW
        )
    run_service.start_attempt(
        session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
    )
    run_service.advance(
        session, tenant_id=project["tenant_a"], run_id=run.run_id, target="verifying", now=NOW
    )


# --------------------------------------------------------------------------
# The Evidence invariant (ADR-008)
# --------------------------------------------------------------------------


def test_the_database_refuses_a_success_without_evidence(app_sessionmaker, project):
    """The constraint behind the service, tested by going around the service.

    If this ever passes, the invariant rests on application code alone.
    """
    with app_sessionmaker() as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, project["tenant_a"]):
                    run = _new_run(session, project)
                    session.execute(
                        text(
                            "UPDATE runs SET state = 'succeeded', "
                            "termination_reason = 'completed', ended_at = now() "
                            "WHERE run_id = :r"
                        ),
                        {"r": run.run_id},
                    )


def test_complete_run_writes_state_evidence_and_event_together(
    app_sessionmaker, project
):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project)
                _to_verifying(session, project, run)
                completed, evidence_id, event_id = run_service.complete_run(
                    session,
                    tenant_id=project["tenant_a"],
                    run_id=run.run_id,
                    now=NOW,
                    actor_type="system",
                    actor_id="control-plane",
                    action="run.complete",
                    input_schema="RunInput@1",
                    input_payload=project["spec"],
                    output_ref=f"inv://artifacts/{run.run_id}/art_x",
                )
                run_id = run.run_id

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                state, stored_evidence = session.execute(
                    text("SELECT state, evidence_id FROM runs WHERE run_id = :r"),
                    {"r": run_id},
                ).one()
                evidence_rows = session.execute(
                    text("SELECT count(*) FROM evidence_envelopes WHERE run_id = :r"),
                    {"r": run_id},
                ).scalar_one()
                events = session.execute(
                    text(
                        "SELECT event_type, status FROM outbox_events WHERE aggregate_id = :r"
                    ),
                    {"r": run_id},
                ).mappings().all()

    assert state == "succeeded"
    assert stored_evidence == evidence_id
    assert evidence_rows == 1
    assert [(e["event_type"], e["status"]) for e in events] == [
        ("inv.run.succeeded", "pending")
    ]
    assert event_id


def test_a_failure_after_evidence_rolls_the_evidence_back_too(
    app_sessionmaker, project
):
    """Atomicity in the direction that matters.

    Evidence for a run that did not finish is worse than no evidence: it
    asserts something happened that did not.
    """
    with app_sessionmaker() as session:
        with pytest.raises(RuntimeError):
            with session.begin():
                with tenant_scope(session, project["tenant_a"]):
                    run = _new_run(session, project)
                    _to_verifying(session, project, run)
                    run_service.complete_run(
                        session,
                        tenant_id=project["tenant_a"],
                        run_id=run.run_id,
                        now=NOW,
                        actor_type="system",
                        actor_id="control-plane",
                        action="run.complete",
                        input_schema="RunInput@1",
                        input_payload=project["spec"],
                    )
                    raise RuntimeError("publisher exploded after the writes")

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                assert (
                    session.execute(
                        text("SELECT count(*) FROM evidence_envelopes")
                    ).scalar_one()
                    == 0
                )
                assert (
                    session.execute(text("SELECT count(*) FROM outbox_events")).scalar_one()
                    == 0
                )
                assert session.execute(text("SELECT count(*) FROM runs")).scalar_one() == 0


def test_success_is_refused_from_any_state_but_verifying(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project)
                with pytest.raises(InvError) as caught:
                    run_service.complete_run(
                        session,
                        tenant_id=project["tenant_a"],
                        run_id=run.run_id,
                        now=NOW,
                        actor_type="system",
                        actor_id="cp",
                        action="run.complete",
                        input_schema="RunInput@1",
                        input_payload={},
                    )
                assert caught.value.code == "VAL-SCHEMA"


def test_evidence_is_append_only_for_the_application_role(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project)
                _to_verifying(session, project, run)
                run_service.complete_run(
                    session,
                    tenant_id=project["tenant_a"],
                    run_id=run.run_id,
                    now=NOW,
                    actor_type="system",
                    actor_id="cp",
                    action="run.complete",
                    input_schema="RunInput@1",
                    input_payload={},
                )
    for statement in (
        "UPDATE evidence_envelopes SET result = 'failed'",
        "DELETE FROM evidence_envelopes",
    ):
        with app_sessionmaker() as session:
            with pytest.raises((ProgrammingError, DBAPIError)):
                with session.begin():
                    with tenant_scope(session, project["tenant_a"]):
                        session.execute(text(statement))


def test_output_ref_must_be_an_inv_uri(app_sessionmaker, project):
    """A presigned URL stored in Evidence leaks on every later read."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project)
                with pytest.raises(InvError):
                    evidence_service.record_evidence(
                        session,
                        tenant_id=project["tenant_a"],
                        run_id=run.run_id,
                        action="x",
                        actor_type="system",
                        actor_id="cp",
                        input_schema="X@1",
                        input_payload={},
                        result="succeeded",
                        now=NOW,
                        output_ref="https://store.example/presigned?sig=abc",
                    )


# --------------------------------------------------------------------------
# State machine against the database
# --------------------------------------------------------------------------


def test_the_check_constraint_rejects_an_invented_state(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, project["tenant_a"]):
                    run = _new_run(session, project)
                    session.execute(
                        text("UPDATE runs SET state = 'paused' WHERE run_id = :r"),
                        {"r": run.run_id},
                    )


def test_a_terminal_state_without_a_reason_is_rejected(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, project["tenant_a"]):
                    run = _new_run(session, project)
                    session.execute(
                        text(
                            "UPDATE runs SET state = 'failed', ended_at = now() "
                            "WHERE run_id = :r"
                        ),
                        {"r": run.run_id},
                    )


def test_cancel_is_idempotent(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project)
                once = run_service.cancel_run(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
                )
                twice = run_service.cancel_run(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
                )
    assert once.state == twice.state == "cancelled"
    assert once.termination_reason == "cancelled_by_user"


def test_cancelling_a_finished_run_is_refused(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project)
                run_service.fail_run(
                    session,
                    tenant_id=project["tenant_a"],
                    run_id=run.run_id,
                    reason=TerminationReason.UNRECOVERABLE_ERROR,
                    now=NOW,
                )
                with pytest.raises(InvError):
                    run_service.cancel_run(
                        session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
                    )


def test_attempts_accumulate_rather_than_overwrite(app_sessionmaker, project):
    """A retry is a new RunAttempt (ADR-001); the earlier try stays readable."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project, retry_budget=2)
                for target in ("validated", "planned", "scheduled"):
                    run_service.advance(
                        session, tenant_id=project["tenant_a"], run_id=run.run_id,
                        target=target, now=NOW,
                    )
                first = run_service.start_attempt(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id,
                    now=NOW, node_id=None, scheduler_version="0.1.0",
                )
                run_service.finish_attempt(
                    session, tenant_id=project["tenant_a"], attempt_id=first.attempt_id,
                    outcome="failed", now=NOW, error_code="TOOL-EXIT",
                )
                run_service.advance(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id,
                    target="recovering", now=NOW,
                )
                run_service.advance(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id,
                    target="scheduled", now=NOW,
                )
                second = run_service.start_attempt(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
                )
                run_id = run.run_id

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                rows = session.execute(
                    text(
                        "SELECT attempt_number, outcome, error_code FROM run_attempts "
                        "WHERE run_id = :r ORDER BY attempt_number"
                    ),
                    {"r": run_id},
                ).mappings().all()
    assert [r["attempt_number"] for r in rows] == [1, 2]
    assert rows[0]["outcome"] == "failed"
    assert rows[0]["error_code"] == "TOOL-EXIT"
    assert rows[1]["outcome"] is None
    assert first.attempt_id != second.attempt_id


def test_retry_budget_is_enforced(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project, retry_budget=0)
                for target in ("validated", "planned", "scheduled"):
                    run_service.advance(
                        session, tenant_id=project["tenant_a"], run_id=run.run_id,
                        target=target, now=NOW,
                    )
                run_service.start_attempt(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
                )
                run_service.advance(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id,
                    target="recovering", now=NOW,
                )
                run_service.advance(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id,
                    target="scheduled", now=NOW,
                )
                with pytest.raises(InvError) as caught:
                    run_service.start_attempt(
                        session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
                    )
                assert caught.value.code == "BUDGET-RETRY-EXHAUSTED"


# --------------------------------------------------------------------------
# Approvals
# --------------------------------------------------------------------------


def test_an_approval_does_not_survive_an_edit_to_what_it_approved(
    app_sessionmaker, project
):
    """The rule an approval exists for: a changed request is not approved."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project)
                run_service.record_approval(
                    session,
                    tenant_id=project["tenant_a"],
                    run_id=run.run_id,
                    decision="approved",
                    risk_level=2,
                    decided_by_user_id=project["user_id"],
                    now=NOW,
                    expires_at=NOW + dt.timedelta(hours=1),
                )
                run_service.assert_approval_valid(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
                )

                # The spec is edited after approval.
                session.execute(
                    text("UPDATE workloads SET spec_sha256 = :d WHERE workload_id = :w"),
                    {"d": "f" * 64, "w": project["workload_id"]},
                )
                with pytest.raises(InvError) as caught:
                    run_service.assert_approval_valid(
                        session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
                    )
                assert caught.value.code == "AUTH-APPROVAL-DIGEST-MISMATCH"


def test_an_expired_approval_is_refused(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project)
                run_service.record_approval(
                    session,
                    tenant_id=project["tenant_a"],
                    run_id=run.run_id,
                    decision="approved",
                    risk_level=1,
                    decided_by_user_id=project["user_id"],
                    now=NOW,
                    expires_at=NOW + dt.timedelta(minutes=5),
                )
                with pytest.raises(InvError) as caught:
                    run_service.assert_approval_valid(
                        session,
                        tenant_id=project["tenant_a"],
                        run_id=run.run_id,
                        now=NOW + dt.timedelta(hours=1),
                    )
                assert caught.value.code == "AUTH-APPROVAL-EXPIRED"


# --------------------------------------------------------------------------
# Outbox and inbox (ADR-007)
# --------------------------------------------------------------------------


def test_a_redelivered_event_is_rejected_by_the_inbox(app_sessionmaker, project):
    event_id = new_id("outbox")
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                evidence_service.mark_processed(
                    session,
                    tenant_id=project["tenant_a"],
                    consumer="projector",
                    event_id=event_id,
                    event_type="inv.run.succeeded",
                    now=NOW,
                )
    with app_sessionmaker() as session:
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, project["tenant_a"]):
                    evidence_service.mark_processed(
                        session,
                        tenant_id=project["tenant_a"],
                        consumer="projector",
                        event_id=event_id,
                        event_type="inv.run.succeeded",
                        now=NOW,
                    )


def test_two_consumers_each_process_the_same_event(app_sessionmaker, project):
    """Deduplication is per consumer, not global."""
    event_id = new_id("outbox")
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                for consumer in ("projector", "notifier"):
                    evidence_service.mark_processed(
                        session,
                        tenant_id=project["tenant_a"],
                        consumer=consumer,
                        event_id=event_id,
                        event_type="inv.run.succeeded",
                        now=NOW,
                    )
                count = session.execute(
                    text("SELECT count(*) FROM inbox_events WHERE event_id = :e"),
                    {"e": event_id},
                ).scalar_one()
    assert count == 2


def test_event_type_must_be_namespaced(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project)
                with pytest.raises(InvError):
                    evidence_service.enqueue_event(
                        session,
                        tenant_id=project["tenant_a"],
                        event_type="run.succeeded",
                        aggregate_type="run",
                        aggregate_id=run.run_id,
                        payload={},
                        now=NOW,
                    )


def test_publish_failures_retry_before_parking(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project)
                evidence_service.enqueue_event(
                    session,
                    tenant_id=project["tenant_a"],
                    event_type="inv.run.created",
                    aggregate_type="run",
                    aggregate_id=run.run_id,
                    payload={"runId": run.run_id},
                    now=NOW,
                )
                claimed = evidence_service.claim_pending_events(session)
                assert len(claimed) == 1
                outbox_id = claimed[0].outbox_id

                evidence_service.mark_publish_failed(
                    session, outbox_id, error="broker refused", max_attempts=3
                )
                assert claimed[0].status == "pending"
                evidence_service.mark_publish_failed(
                    session, outbox_id, error="broker refused", max_attempts=3
                )
                evidence_service.mark_publish_failed(
                    session, outbox_id, error="broker refused", max_attempts=3
                )
                assert claimed[0].status == "failed"


# --------------------------------------------------------------------------
# Isolation carries into the new tables
# --------------------------------------------------------------------------


def test_another_tenant_cannot_see_runs_or_evidence(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project)
                _to_verifying(session, project, run)
                run_service.complete_run(
                    session,
                    tenant_id=project["tenant_a"],
                    run_id=run.run_id,
                    now=NOW,
                    actor_type="system",
                    actor_id="cp",
                    action="run.complete",
                    input_schema="RunInput@1",
                    input_payload={},
                )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_b"]):
                assert session.execute(text("SELECT count(*) FROM runs")).scalar_one() == 0
                assert (
                    session.execute(
                        text("SELECT count(*) FROM evidence_envelopes")
                    ).scalar_one()
                    == 0
                )
                assert (
                    session.execute(text("SELECT count(*) FROM outbox_events")).scalar_one()
                    == 0
                )


def test_a_dataset_mount_cannot_be_writable(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, project["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO workspace_volumes (volume_id, tenant_id, workspace_id, "
                            "kind, mount_path, writable, size_bytes, created_at, version) "
                            "VALUES (:v, :t, :w, 'dataset_mount', '/data', true, 0, now(), 1)"
                        ),
                        {"v": new_id("volume"), "t": project["tenant_a"], "w": project["workspace_id"]},
                    )


def test_an_artifact_cannot_be_active_without_verification(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _new_run(session, project)
                run_id = run.run_id
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, project["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO artifacts (artifact_id, tenant_id, run_id, name, "
                            "media_type, status, byte_size, created_at, version) "
                            "VALUES (:a, :t, :r, 'report', 'text/plain', 'active', 10, now(), 1)"
                        ),
                        {"a": new_id("artifact"), "t": project["tenant_a"], "r": run_id},
                    )


# --------------------------------------------------------------------------
# Scoping found by comparing the two implementations (public is authoritative)
# --------------------------------------------------------------------------


def test_the_same_idempotency_key_in_two_projects_is_two_operations(
    app_sessionmaker, project
):
    """The defect the merge comparison exposed.

    Keys are chosen by clients — "retry", "deploy-1". Two projects using the
    same one for the same endpoint were colliding, and the second project
    received the first project's stored response instead of performing its own
    operation.
    """
    from saintvision.db.models import IdempotencyRecord

    tenant = project["tenant_a"]
    other_project = new_id("project")
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                for project_id in (project["project_id"], other_project):
                    session.add(
                        IdempotencyRecord(
                            record_id=new_id("idempotency"),
                            tenant_id=tenant,
                            project_id=project_id,
                            endpoint="POST /v1/runs",
                            idempotency_key="retry",
                            request_sha256="a" * 64,
                            response_status=201,
                            response_body={},
                            created_at=NOW,
                            expires_at=NOW + dt.timedelta(days=1),
                        )
                    )
                session.flush()
                count = session.execute(
                    text(
                        "SELECT count(*) FROM idempotency_records "
                        "WHERE idempotency_key = 'retry'"
                    )
                ).scalar_one()
    assert count == 2


def test_the_same_key_in_one_project_still_collides(app_sessionmaker, project):
    from saintvision.db.models import IdempotencyRecord

    tenant = project["tenant_a"]

    def record():
        return IdempotencyRecord(
            record_id=new_id("idempotency"),
            tenant_id=tenant,
            project_id=project["project_id"],
            endpoint="POST /v1/runs",
            idempotency_key="retry",
            request_sha256="a" * 64,
            response_status=201,
            response_body={},
            created_at=NOW,
            expires_at=NOW + dt.timedelta(days=1),
        )

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                session.add(record())
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, tenant):
                    session.add(record())


def test_two_tenant_wide_operations_with_one_key_still_collide(
    app_sessionmaker, project
):
    """NULLS NOT DISTINCT: no project is still one scope, not unlimited ones."""
    from saintvision.db.models import IdempotencyRecord

    tenant = project["tenant_a"]

    def record():
        return IdempotencyRecord(
            record_id=new_id("idempotency"),
            tenant_id=tenant,
            project_id=None,
            endpoint="POST /v1/storage/contributions",
            idempotency_key="k",
            request_sha256="b" * 64,
            response_status=201,
            response_body={},
            created_at=NOW,
            expires_at=NOW + dt.timedelta(days=1),
        )

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                session.add(record())
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, tenant):
                    session.add(record())


def test_one_tenants_processed_event_does_not_suppress_anothers(
    app_sessionmaker, project
):
    """Inbox dedup is per tenant as well as per consumer."""
    event_id = new_id("outbox")
    for tenant in (project["tenant_a"], project["tenant_b"]):
        with app_sessionmaker() as session:
            with session.begin():
                with tenant_scope(session, tenant):
                    evidence_service.mark_processed(
                        session,
                        tenant_id=tenant,
                        consumer="projector",
                        event_id=event_id,
                        event_type="inv.run.succeeded",
                        now=NOW,
                    )
    # Both recorded; neither hid the other.
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_b"]):
                mine = session.execute(
                    text("SELECT count(*) FROM inbox_events WHERE event_id = :e"),
                    {"e": event_id},
                ).scalar_one()
    assert mine == 1
