"""Project authorization and duplicate-write boundaries for pool mutations."""

from __future__ import annotations

from contextlib import nullcontext
import datetime as dt
from types import SimpleNamespace
import uuid

import pytest
from fastapi import Response
from sqlalchemy.exc import IntegrityError

from saintvision.api import schemas
from saintvision.api.v1 import pools
from saintvision.errors import AUTH_PROJECT_SCOPE, GRAPH_INVALID_TRANSITION, InvError
from saintvision.identity.principal import Principal


TENANT = uuid.UUID("cf179c2a-1f1e-489e-8a92-a6aca19077dd")
PRINCIPAL = Principal(user_id="usr_pool_actor", tenant_id=TENANT, external_subject="pool-actor")
NOW = dt.datetime(2026, 9, 29, 2, 20, tzinfo=dt.timezone.utc)


class _Session:
    def __init__(self, scalars=(), *, workload=None, member=None, project_member=None, user=None):
        self._scalars = list(scalars)
        self.workload = workload
        self.member = member
        self.project_member = project_member
        self.user = user
        self.statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        return self._scalars.pop(0)

    def get(self, model, _identity, **_kwargs):
        if model is pools.Workload:
            return self.workload
        if model is pools.ResourcePoolMember:
            return self.member
        if model is pools.project_service.ProjectMember:
            return self.project_member
        if model is pools.project_service.User:
            return self.user
        raise AssertionError(f"unexpected model lookup: {model}")

    def begin_nested(self):
        return nullcontext()


class _Original(Exception):
    def __init__(self, constraint):
        super().__init__(constraint or "database integrity error")
        self.diag = SimpleNamespace(constraint_name=constraint)


def _integrity(constraint):
    return IntegrityError("statement", {}, _Original(constraint))


def test_pool_writer_locks_project_then_rechecks_permission_and_pool(monkeypatch):
    pool = SimpleNamespace(project_id="prj_owned")
    session = _Session(["prj_owned", pool])
    calls = []
    monkeypatch.setattr(
        pools.settings_service,
        "lock_project",
        lambda *_args: calls.append("project-lock"),
    )
    monkeypatch.setattr(
        pools.project_service,
        "require_project_access",
        lambda *_args, **_kwargs: calls.append("permission") or {"canRequest": True},
    )

    assert (
        pools._require_pool_write_access(
            session,
            tenant_id=TENANT,
            pool_id="pol_owned",
            user_id=PRINCIPAL.user_id,
        )
        is pool
    )
    assert calls == ["project-lock", "permission"]
    assert session.statements[0]._for_update_arg is None
    assert session.statements[1]._for_update_arg is not None


def test_viewer_non_member_or_unknown_pool_have_identical_problem_bodies(monkeypatch):
    monkeypatch.setattr(pools.settings_service, "lock_project", lambda *_args: None)
    monkeypatch.setattr(
        pools.settings_service,
        "effective_permission",
        lambda *_args, **_kwargs: {"canRequest": False},
    )
    active_user = SimpleNamespace(tenant_id=TENANT, status="active")
    with pytest.raises(InvError) as viewer:
        pools._require_pool_write_access(
            _Session(
                ["prj_hidden"],
                project_member=SimpleNamespace(role_code="viewer"),
                user=active_user,
            ),
            tenant_id=TENANT,
            pool_id="pol_hidden",
            user_id=PRINCIPAL.user_id,
        )
    with pytest.raises(InvError) as non_member:
        pools._require_pool_write_access(
            _Session(["prj_hidden"], project_member=None, user=active_user),
            tenant_id=TENANT,
            pool_id="pol_hidden",
            user_id=PRINCIPAL.user_id,
        )
    with pytest.raises(InvError) as missing:
        pools._require_pool_write_access(
            _Session([None]),
            tenant_id=TENANT,
            pool_id="pol_absent",
            user_id=PRINCIPAL.user_id,
        )
    bodies = [
        error.value.to_problem(trace_id="trc_pool", instance="/v1/pools/pol_hidden")
        for error in (viewer, non_member, missing)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    assert bodies[0]["code"] == AUTH_PROJECT_SCOPE
    assert "projectId" not in bodies[0]


def test_plan_requires_run_workload_to_belong_to_the_locked_pool_project(monkeypatch):
    pool = SimpleNamespace(project_id="prj_pool")
    run = SimpleNamespace(workload_id="wkl_foreign")
    session = _Session(
        [run],
        workload=SimpleNamespace(tenant_id=TENANT, project_id="prj_other"),
    )
    monkeypatch.setattr(pools, "_require_pool_write_access", lambda *_args, **_kwargs: pool)

    with pytest.raises(InvError) as caught:
        pools._require_plan_write_access(
            session,
            tenant_id=TENANT,
            pool_id="pol_owned",
            run_id="run_foreign",
            user_id=PRINCIPAL.user_id,
        )
    assert caught.value.code == AUTH_PROJECT_SCOPE
    assert session.statements[0]._for_update_arg is not None


def test_permission_denial_happens_before_member_side_effect(monkeypatch):
    called = []

    def denied(*_args, **_kwargs):
        raise InvError(AUTH_PROJECT_SCOPE, "project is not accessible to this principal")

    monkeypatch.setattr(pools, "_require_pool_write_access", denied)
    monkeypatch.setattr(
        pools.pool_service,
        "add_member",
        lambda *_args, **_kwargs: called.append("mutated"),
    )
    with pytest.raises(InvError, match="not accessible"):
        pools.add_member(
            pool_id="pol_hidden",
            node_id="nod_target",
            principal=PRINCIPAL,
            session=_Session(),
            now=NOW,
        )
    assert called == []


def test_concurrent_member_primary_key_is_idempotent_only_when_exact_row_exists(monkeypatch):
    monkeypatch.setattr(
        pools,
        "_require_pool_write_access",
        lambda *_args, **_kwargs: SimpleNamespace(project_id="prj_owned"),
    )
    monkeypatch.setattr(
        pools.pool_service,
        "add_member",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(_integrity(pools._POOL_MEMBER_PRIMARY_KEY)),
    )
    result = pools.add_member(
        pool_id="pol_owned",
        node_id="nod_target",
        principal=PRINCIPAL,
        session=_Session(member=SimpleNamespace()),
        now=NOW,
    )
    assert result == {"poolId": "pol_owned", "nodeId": "nod_target", "member": True}

    with pytest.raises(IntegrityError):
        pools.add_member(
            pool_id="pol_owned",
            node_id="nod_target",
            principal=PRINCIPAL,
            session=_Session(member=None),
            now=NOW,
        )


@pytest.mark.parametrize(
    ("constraint", "message"),
    [
        ("uq_resource_pools_tenant_id_name", "name already exists"),
        ("uq_distributed_plans_run_id", "already has a distributed plan"),
    ],
)
def test_only_registered_unique_constraints_become_public_409(constraint, message):
    conflict = pools._translate_pool_conflict(_integrity(constraint))
    assert conflict is not None
    assert conflict.code == GRAPH_INVALID_TRANSITION
    assert conflict.status == 409
    assert message in conflict.message
    assert pools._translate_pool_conflict(_integrity("unexpected_new_constraint")) is None


def test_create_pool_translates_only_its_registered_name_conflict(monkeypatch):
    monkeypatch.setattr(
        pools.project_service,
        "require_project_access",
        lambda *_args, **_kwargs: {"canRequest": True},
    )
    monkeypatch.setattr(
        pools.pool_service,
        "create_pool",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            _integrity("uq_resource_pools_tenant_id_name")
        ),
    )
    with pytest.raises(InvError) as caught:
        pools.create_pool(
            payload=schemas.PoolRequest(projectId="prj_owned", name="duplicate"),
            response=Response(),
            principal=PRINCIPAL,
            session=_Session(),
            now=NOW,
        )
    assert caught.value.code == GRAPH_INVALID_TRANSITION
    assert caught.value.status == 409
