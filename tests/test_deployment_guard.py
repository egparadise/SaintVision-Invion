"""Real PostgreSQL approval time and concurrent registry record boundaries."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import datetime as dt
import time

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from saintvision.db.session import tenant_scope
from saintvision.db.models.execution import Approval
from saintvision.db.models.lineage import ModelVersion
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services.lineage import record_deployment
from test_model_registry import (
    registry, NOW, SHA, _seed_traceable_subjects, _release_with_subjects,
    _deployment_approval,
)

pytestmark = pytest.mark.postgres


@pytest.fixture
def released(owner_engine, app_sessionmaker, registry):
    user = new_id('user')
    with owner_engine.begin() as c:
        c.execute(text("INSERT INTO users(user_id,tenant_id,external_subject,display_name) VALUES(:u,:t,:subject,'guard')"),
                  {'u': user, 'subject': user, 't': registry['tenant_a']})
    subjects = _seed_traceable_subjects(owner_engine, registry, user)
    approvals = [new_id('approval'), new_id('approval')]
    for approval in approvals:
        _deployment_approval(owner_engine, registry, subjects, user, digest=SHA, approval_id=approval)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, registry['tenant_a']):
        version = _release_with_subjects(session, owner_engine, registry, user, subjects)
        version_id = version.model_version_id
    return {'tenant_id': registry['tenant_a'], 'model_version_id': version_id,
            'environment': 'pilot', 'deployed_by_user_id': user, 'now': NOW}, approvals


@pytest.mark.parametrize('boundary', ['expired', 'future', 'cached-revoked'])
def test_approval_time_and_cached_revocation_are_checked(owner_engine, app_sessionmaker, released, boundary):
    args, approvals = released
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, args['tenant_id']):
        cached = session.get(Approval, approvals[0])
        assert cached.decision == 'approved'
        with owner_engine.begin() as c:
            if boundary == 'cached-revoked':
                c.execute(text("UPDATE approvals SET decision='rejected' WHERE approval_id=:id"), {'id': approvals[0]})
            else:
                decided = NOW - dt.timedelta(days=1) if boundary == 'expired' else NOW + dt.timedelta(seconds=1)
                expiry = NOW if boundary == 'expired' else NOW + dt.timedelta(days=1)
                c.execute(text('UPDATE approvals SET decided_at=:d,expires_at=:e WHERE approval_id=:id'),
                          {'id': approvals[0], 'd': decided, 'e': expiry})
        with pytest.raises(InvError):
            record_deployment(session, **args, approval_id=approvals[0])
        assert session.scalar(text('SELECT count(*) FROM deployments WHERE model_version_id=:id'),
                              {'id': args['model_version_id']}) == 0


def test_concurrent_first_deployments_leave_one_active_record(owner_engine, app_sessionmaker, released):
    args, approvals = released
    first_inserted, release_first, second_started = Event(), Event(), Event()
    marker = 'deployment-' + new_id('deployment')

    def first():
        with app_sessionmaker() as session, session.begin(), tenant_scope(session, args['tenant_id']):
            record_deployment(session, **args, approval_id=approvals[0])
            first_inserted.set()
            assert release_first.wait(10)

    def second():
        with app_sessionmaker() as session, session.begin(), tenant_scope(session, args['tenant_id']):
            session.execute(text("SELECT set_config('application_name',:name,true)"), {'name': marker})
            second_started.set()
            record_deployment(session, **args, approval_id=approvals[1])

    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(first)
        try:
            if not first_inserted.wait(5):
                one.result(timeout=1)  # Surface the actual worker failure.
                pytest.fail('First registration did not reach its hold point')
            two = pool.submit(second)
            assert second_started.wait(5)
            deadline = time.monotonic() + 5
            blocked = False
            while not two.done() and time.monotonic() < deadline:
                with owner_engine.connect() as c:
                    blocked = bool(c.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE application_name=:name AND wait_event_type='Lock'"), {'name': marker}))
                if blocked:
                    break
                time.sleep(.02)
        finally:
            release_first.set()
        one.result(timeout=10)
        two.result(timeout=10)
    with owner_engine.connect() as c:
        states = dict(c.execute(text('SELECT status,count(*) FROM deployments WHERE model_version_id=:id GROUP BY status'),
                                {'id': args['model_version_id']}).all())
    assert states == {'active': 1, 'superseded': 1}
    assert blocked, 'The second registration must serialize against the first'


def test_cached_released_stage_cannot_override_current_draft(owner_engine, app_sessionmaker, released):
    args, approvals = released
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, args['tenant_id']):
        cached = session.get(ModelVersion, args['model_version_id'])
        assert cached.stage == 'released'
        with owner_engine.begin() as c:
            c.execute(text("UPDATE model_versions SET stage='draft' WHERE model_version_id=:id"),
                      {'id': args['model_version_id']})
        with pytest.raises(InvError, match='only a released'):
            record_deployment(session, **args, approval_id=approvals[0])


def test_database_rejects_duplicate_active_and_service_supersedes(owner_engine, app_sessionmaker, released):
    args, approvals = released
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, args['tenant_id']):
        first = record_deployment(session, **args, approval_id=approvals[0])
        first_id = first.deployment_id
    # The existing migration's unique index remains the last line of defense.
    with pytest.raises(IntegrityError):
        with owner_engine.begin() as c:
            c.execute(text("""INSERT INTO deployments(deployment_id,tenant_id,model_version_id,
                environment,status,deployed_digest,approval_id,deployed_by_user_id,deployed_at)
                SELECT :id,tenant_id,model_version_id,environment,status,deployed_digest,
                approval_id,deployed_by_user_id,deployed_at FROM deployments WHERE deployment_id=:first"""),
                      {'id': new_id('deployment'), 'first': first_id})
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, args['tenant_id']):
        record_deployment(session, **args, approval_id=approvals[1])
    with owner_engine.connect() as c:
        states = dict(c.execute(text('SELECT status,count(*) FROM deployments WHERE model_version_id=:id GROUP BY status'),
                                {'id': args['model_version_id']}).all())
    assert states == {'active': 1, 'superseded': 1}
