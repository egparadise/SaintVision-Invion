"""Real PostgreSQL for the eval run route (G-05 W5).

What only a database can show:

* a suite in a sibling project, in another tenant, and one whose ``project_id`` is
  NULL because it predates ``0053`` -- all the same 404, through real RLS;
* the run and its closing state actually landing in ``eval_runs``;
* a refusal reaching ``audit_events`` as **exactly one** denial row (#195), and a
  success leaving an ``allow`` and no denial;
* a repeated idempotency key replaying instead of running the suite twice.

**No provider is ever called.** The suites here have **zero cases**, so
``run_suite`` runs the real service end to end -- the model-pinning check, the run
row, the gate -- without executing a single case. The adapter is a stub that answers
only what the service asks of it before the loop. That is deliberate: a test must
not buy provider calls, and the route's job is to choose the adapter and record the
run, not to evaluate anything itself.

An empty suite is **not** a pass (``gate_passed``: "zero of zero cases passing is a
fact about arithmetic"), so ``passedGate`` is false here and that is asserted rather
than worked around.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.adapters.contract import Capability
from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.api.v1 import eval_runs
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id

pytestmark = pytest.mark.postgres

TOKEN = "eval-real-token"


class StubAdapter:
    """Everything ``run_suite`` asks for before the case loop, and nothing else.

    With zero cases the loop never runs, so no provider method is ever reached.
    """

    name = "claude-code"
    contract_version = "1.0.0"
    capabilities = frozenset({Capability.MODEL_PINNING})


def _digest() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


def _insert(connection, table_name, **values):
    """Insert through the model metadata, so a wrong column cannot reach hosted CI."""
    from saintvision.db import models  # noqa: F401  (registers the tables)
    from saintvision.db.base import Base

    table = Base.metadata.tables[table_name]
    unknown = set(values) - set(table.columns.keys())
    assert not unknown, f"{table_name} has no column(s) {sorted(unknown)}"
    required = {
        column.name
        for column in table.columns
        if not column.nullable and column.default is None and column.server_default is None
    }
    assert required <= set(values), f"{table_name} needs {sorted(required - set(values))}"
    connection.execute(table.insert().values(**values))


def _seed(connection, *, tenant_id, now, label, role="approver", project_id=None):
    """One project, one member of the given role, and one zero-case suite.

    ``project_id=None`` on the suite is the pre-0053 shape this route must refuse.
    """
    user_id = new_id("user")
    own_project = new_id("project")
    suite_id = new_id("eval_suite")
    _insert(
        connection,
        "users",
        user_id=user_id,
        tenant_id=tenant_id,
        external_subject=f"eval-{label}",
        display_name=f"eval-{label}",
        status="active",
        created_at=now,
        updated_at=now,
        version=1,
    )
    _insert(
        connection,
        "projects",
        project_id=own_project,
        tenant_id=tenant_id,
        code=label,
        display_name=label,
        status="active",
        created_at=now,
        version=1,
    )
    _insert(
        connection,
        "project_members",
        tenant_id=tenant_id,
        project_id=own_project,
        user_id=user_id,
        role_code=role,
    )
    _insert(
        connection,
        "eval_suites",
        suite_id=suite_id,
        tenant_id=tenant_id,
        project_id=own_project if project_id == "own" else project_id,
        name=f"suite-{label}",
        version="1.0.0",
        case_count=0,
        definition_sha256=_digest(),
        created_at=now,
    )
    return {"user_id": user_id, "project_id": own_project, "suite_id": suite_id}


def _client(app_engine, *, tenant_id, user_id, now, monkeypatch):
    """The real verifier, so get_principal pins the actor the denial row needs."""
    monkeypatch.setattr(eval_runs.agents, "adapter_for", lambda _name: StubAdapter())
    principal = Principal(
        user_id=user_id, tenant_id=tenant_id, external_subject="eval-real"
    )
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only", idempotency_ttl_seconds=600),
        verifier=StaticPrincipalVerifier({TOKEN: principal}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    return TestClient(app, raise_server_exceptions=False)


def _path(project_id, suite_id):
    return f"/v1/projects/{project_id}/eval/suites/{suite_id}/runs"


def _headers(key, *, token=TOKEN):
    headers = {"Idempotency-Key": key, "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _runs(owner_engine, tenant_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT eval_run_id, suite_id, status, total_cases, passed_cases, "
                "violations, passed_gate FROM eval_runs WHERE tenant_id = :t"
            ),
            {"t": tenant_id},
        ).mappings().all()


def _events(owner_engine, outcome):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT tenant_id, actor_type, actor_id, action, reason_code, "
                "target_type, target_id FROM audit_events WHERE outcome = :o "
                "ORDER BY occurred_at"
            ),
            {"o": outcome},
        ).mappings().all()


def _canonical(response, *, code, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["code"] == code
    return body


# --------------------------------------------------------------------------
# The run itself
# --------------------------------------------------------------------------


def test_an_approver_runs_a_suite_and_the_run_is_recorded(
    owner_engine, app_engine, two_tenants, frozen_now, monkeypatch
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(
            connection, tenant_id=tenant, now=frozen_now, label="w5-ok", project_id="own"
        )

    client = _client(
        app_engine,
        tenant_id=tenant,
        user_id=seeded["user_id"],
        now=frozen_now,
        monkeypatch=monkeypatch,
    )
    response = client.post(
        _path(seeded["project_id"], seeded["suite_id"]),
        json={"adapter": "claude-code"},
        headers=_headers("k-w5-ok"),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["suiteId"] == seeded["suite_id"]
    assert body["status"] == "completed"
    assert body["totalCases"] == 0
    # An empty suite is not a pass: zero of zero is a fact about arithmetic.
    assert body["passedGate"] is False
    # The service records the identity, not the caller.
    assert body["componentVersions"]["adapter"] == "claude-code"
    assert body["componentVersions"]["contractVersion"] == "1.0.0"

    rows = _runs(owner_engine, tenant)
    assert len(rows) == 1
    assert rows[0]["eval_run_id"] == body["evalRunId"]
    assert rows[0]["status"] == "completed"
    assert rows[0]["passed_gate"] is False

    allows = _events(owner_engine, "allow")
    assert [row["action"] for row in allows] == ["eval_run.execute"]
    assert allows[0]["target_type"] == "eval_run"
    assert allows[0]["target_id"] == body["evalRunId"]
    assert _events(owner_engine, "deny") == []


def test_the_same_key_replays_and_does_not_run_the_suite_again(
    owner_engine, app_engine, two_tenants, frozen_now, monkeypatch
):
    """The difference between a retry and a second bill."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(
            connection, tenant_id=tenant, now=frozen_now, label="w5-rep", project_id="own"
        )

    client = _client(
        app_engine,
        tenant_id=tenant,
        user_id=seeded["user_id"],
        now=frozen_now,
        monkeypatch=monkeypatch,
    )
    path = _path(seeded["project_id"], seeded["suite_id"])
    first = client.post(path, json={"adapter": "claude-code"}, headers=_headers("k-w5-r"))
    second = client.post(path, json={"adapter": "claude-code"}, headers=_headers("k-w5-r"))

    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert len(_runs(owner_engine, tenant)) == 1, "a retry must not buy a second run"
    assert len(_events(owner_engine, "allow")) == 1


def test_the_same_key_with_a_different_adapter_is_a_conflict(
    owner_engine, app_engine, two_tenants, frozen_now, monkeypatch
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(
            connection, tenant_id=tenant, now=frozen_now, label="w5-conf", project_id="own"
        )

    client = _client(
        app_engine,
        tenant_id=tenant,
        user_id=seeded["user_id"],
        now=frozen_now,
        monkeypatch=monkeypatch,
    )
    path = _path(seeded["project_id"], seeded["suite_id"])
    assert client.post(
        path, json={"adapter": "claude-code"}, headers=_headers("k-w5-c")
    ).status_code == 201
    response = client.post(
        path, json={"adapter": "codex-cli"}, headers=_headers("k-w5-c")
    )

    _canonical(response, code="GRAPH-0002", status=409)
    assert len(_runs(owner_engine, tenant)) == 1


# --------------------------------------------------------------------------
# path -> suite, including the NULL project 0053 leaves behind
# --------------------------------------------------------------------------


def test_a_suite_of_a_sibling_project_is_a_404(
    owner_engine, app_engine, two_tenants, frozen_now, monkeypatch
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(
            connection, tenant_id=tenant, now=frozen_now, label="w5-mine", project_id="own"
        )
        theirs = _seed(
            connection, tenant_id=tenant, now=frozen_now, label="w5-sib", project_id="own"
        )

    client = _client(
        app_engine,
        tenant_id=tenant,
        user_id=mine["user_id"],
        now=frozen_now,
        monkeypatch=monkeypatch,
    )
    response = client.post(
        _path(mine["project_id"], theirs["suite_id"]),
        json={"adapter": "claude-code"},
        headers=_headers("k-w5-sib"),
    )

    body = _canonical(response, code="RES-0004", status=404)
    assert body["detail"] == eval_runs.NO_SUCH_SUITE
    assert _runs(owner_engine, tenant) == []


def test_a_suite_with_no_project_is_a_404_not_every_projects(
    owner_engine, app_engine, two_tenants, frozen_now, monkeypatch
):
    """The pre-0053 shape. NULL means no project, not any project."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(
            connection, tenant_id=tenant, now=frozen_now, label="w5-null", project_id=None
        )

    with owner_engine.begin() as connection:
        stored = connection.execute(
            text("SELECT project_id FROM eval_suites WHERE suite_id = :s"),
            {"s": seeded["suite_id"]},
        ).scalar_one()
    assert stored is None, "the fixture has to actually produce the NULL case"

    client = _client(
        app_engine,
        tenant_id=tenant,
        user_id=seeded["user_id"],
        now=frozen_now,
        monkeypatch=monkeypatch,
    )
    response = client.post(
        _path(seeded["project_id"], seeded["suite_id"]),
        json={"adapter": "claude-code"},
        headers=_headers("k-w5-null"),
    )

    _canonical(response, code="RES-0004", status=404)
    assert _runs(owner_engine, tenant) == []


def test_another_tenants_suite_is_the_same_404_under_rls(
    owner_engine, app_engine, two_tenants, frozen_now, monkeypatch
):
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(
            connection, tenant_id=tenant_a, now=frozen_now, label="w5-a", project_id="own"
        )
        theirs = _seed(
            connection, tenant_id=tenant_b, now=frozen_now, label="w5-b", project_id="own"
        )

    client = _client(
        app_engine,
        tenant_id=tenant_a,
        user_id=mine["user_id"],
        now=frozen_now,
        monkeypatch=monkeypatch,
    )
    response = client.post(
        _path(mine["project_id"], theirs["suite_id"]),
        json={"adapter": "claude-code"},
        headers=_headers("k-w5-rls"),
    )

    _canonical(response, code="RES-0004", status=404)
    assert _runs(owner_engine, tenant_a) == []
    assert _runs(owner_engine, tenant_b) == []


# --------------------------------------------------------------------------
# Authorisation, and the denial row
# --------------------------------------------------------------------------


def test_a_member_without_the_approval_grade_cannot_run_and_leaves_one_denial(
    owner_engine, app_engine, two_tenants, frozen_now, monkeypatch
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(
            connection,
            tenant_id=tenant,
            now=frozen_now,
            label="w5-req",
            role="requester",
            project_id="own",
        )

    client = _client(
        app_engine,
        tenant_id=tenant,
        user_id=seeded["user_id"],
        now=frozen_now,
        monkeypatch=monkeypatch,
    )
    body = _canonical(
        client.post(
            _path(seeded["project_id"], seeded["suite_id"]),
            json={"adapter": "claude-code"},
            headers=_headers("k-w5-req"),
        ),
        code="AUTH-0030",
        status=403,
    )

    rows = _events(owner_engine, "deny")
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["tenant_id"] == tenant
    assert row["actor_type"] == "user"
    assert row["actor_id"] == seeded["user_id"]
    assert row["reason_code"] == "AUTH-0030"
    assert (row["target_type"], row["target_id"]) == ("project", seeded["project_id"])
    assert row["action"] == "POST /v1/projects/{project_id}/eval/suites/{suite_id}/runs"
    assert seeded["suite_id"] not in row["action"]
    assert _runs(owner_engine, tenant) == []
    assert body["detail"]


def test_a_non_member_cannot_run(
    owner_engine, app_engine, two_tenants, frozen_now, monkeypatch
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        owner = _seed(
            connection, tenant_id=tenant, now=frozen_now, label="w5-own", project_id="own"
        )
        outsider = _seed(
            connection, tenant_id=tenant, now=frozen_now, label="w5-out", project_id="own"
        )

    client = _client(
        app_engine,
        tenant_id=tenant,
        user_id=outsider["user_id"],
        now=frozen_now,
        monkeypatch=monkeypatch,
    )
    _canonical(
        client.post(
            _path(owner["project_id"], owner["suite_id"]),
            json={"adapter": "claude-code"},
            headers=_headers("k-w5-out"),
        ),
        code="AUTH-0030",
        status=403,
    )
    assert len(_events(owner_engine, "deny")) == 1
    assert _runs(owner_engine, tenant) == []


def test_no_credential_is_refused_and_recorded_as_anonymous(
    owner_engine, app_engine, two_tenants, frozen_now, monkeypatch
):
    """#195's boundary. Nothing is run and nothing is charged."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(
            connection, tenant_id=tenant, now=frozen_now, label="w5-anon", project_id="own"
        )

    client = _client(
        app_engine,
        tenant_id=tenant,
        user_id=seeded["user_id"],
        now=frozen_now,
        monkeypatch=monkeypatch,
    )
    response = client.post(
        _path(seeded["project_id"], seeded["suite_id"]),
        json={"adapter": "claude-code"},
        headers=_headers("k-w5-anon", token=None),
    )

    assert response.status_code == 401, response.text
    rows = _events(owner_engine, "deny")
    assert len(rows) == 1, rows
    assert rows[0]["actor_type"] == "anonymous"
    assert rows[0]["tenant_id"] is None
    assert rows[0]["action"] == (
        "POST /v1/projects/{project_id}/eval/suites/{suite_id}/runs"
    )
    assert _runs(owner_engine, tenant) == []


def test_an_archive_committed_before_the_cost_check_buys_nothing(
    owner_engine, app_engine, two_tenants, frozen_now, monkeypatch
):
    """The third permission check has to read the project, not remember it.

    Codex found that it did not. ``effective_permission`` refreshed the
    membership and the user row but took the project out of the identity map, so
    the second and third checks in one transaction saw whatever ``status`` the
    first check had loaded. An archive committed by another transaction in
    between was therefore invisible at the one check whose whole purpose is to
    stand immediately before a call that spends money.

    This test is the barrier the mock cannot be: ``adapter_for`` is resolved
    between the second check and the third, so archiving the project *there*, on
    a different connection, with a real commit, puts a real concurrent change in
    the real window. Nothing here flips a mock's return value.

    **What this test does not prove.** It passes with or without the
    ``populate_existing=True`` fix, and saying otherwise would be the kind of
    claim this suite exists to prevent. SQLAlchemy's identity map holds *weak*
    references, so the moment ``effective_permission`` returns, nothing in this
    route still refers to the ``Project`` and it is evicted -- the next
    ``session.get`` re-reads it whether or not the fix is there. Measured both
    ways. The test that does discriminate is the one below, which supplies the
    missing condition (a strong reference) instead of assuming it.

    So this test pins the behaviour a caller depends on -- an archive committed
    before the cost check buys nothing -- and the next one pins the reason it
    holds no matter who else is holding the row.
    """
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(
            connection,
            tenant_id=tenant,
            now=frozen_now,
            label="w5-barrier",
            project_id="own",
        )

    client = _client(
        app_engine,
        tenant_id=tenant,
        user_id=seeded["user_id"],
        now=frozen_now,
        monkeypatch=monkeypatch,
    )

    archived: list[str] = []
    ran: list[str] = []

    def archive_then_answer(_name):
        """Commit the archive on another connection, then hand back the adapter."""
        with owner_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE projects SET status = 'archived', version = version + 1 "
                    "WHERE tenant_id = :t AND project_id = :p"
                ),
                {"t": tenant, "p": seeded["project_id"]},
            )
        archived.append(seeded["project_id"])
        return StubAdapter()

    real_run_suite = eval_runs.run_suite

    def recording_run_suite(*args, **kwargs):
        ran.append(kwargs.get("suite_id"))
        return real_run_suite(*args, **kwargs)

    monkeypatch.setattr(eval_runs.agents, "adapter_for", archive_then_answer)
    monkeypatch.setattr(eval_runs, "run_suite", recording_run_suite)

    response = client.post(
        _path(seeded["project_id"], seeded["suite_id"]),
        json={"adapter": "claude-code"},
        headers=_headers("k-w5-barrier"),
    )

    # The barrier has to have fired, or this test proves nothing.
    assert archived == [seeded["project_id"]]
    with owner_engine.begin() as connection:
        status = connection.execute(
            text("SELECT status FROM projects WHERE project_id = :p"),
            {"p": seeded["project_id"]},
        ).scalar_one()
    assert status == "archived"

    body = _canonical(response, code="AUTH-0030", status=403)
    assert body["detail"]
    # Nothing was bought and nothing was written.
    assert ran == []
    assert _runs(owner_engine, tenant) == []
    assert _events(owner_engine, "allow") == []
    denials = _events(owner_engine, "deny")
    assert len(denials) == 1, denials
    assert denials[0]["reason_code"] == "AUTH-0030"
    assert denials[0]["actor_id"] == seeded["user_id"]
    assert denials[0]["action"] == (
        "POST /v1/projects/{project_id}/eval/suites/{suite_id}/runs"
    )


def test_the_cost_check_rereads_the_project_even_when_something_holds_it(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """``effective_permission`` asked twice in one transaction must answer twice.

    This is the mutation-sensitive half of the finding above, at the service
    boundary where the defect actually lived.

    The identity map is weak, so the route above re-read the project by accident:
    nothing held it. Hold it -- which any relationship load, any helper that
    returns the row, any future ``lock_project`` in the same request would do --
    and without ``populate_existing=True`` the second answer is the *first*
    answer: ``active``/``canApprove`` for a project that is archived and
    committed in the database. That is the answer the check immediately before a
    paid provider call would have acted on.

    Removing ``populate_existing=True`` from ``effective_permission`` fails this
    test. Verified by removing it and re-running: ``second`` comes back
    ``active``/``True``.
    """
    from saintvision.db.models.identity import Project
    from saintvision.db.session import tenant_scope
    from saintvision.services import settings as settings_service
    from sqlalchemy.orm import Session

    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(
            connection,
            tenant_id=tenant,
            now=frozen_now,
            label="w5-reread",
            project_id="own",
        )

    with Session(app_engine) as session, session.begin(), tenant_scope(session, tenant):
        first = settings_service.effective_permission(
            session,
            tenant_id=tenant,
            project_id=seeded["project_id"],
            user_id=seeded["user_id"],
        )
        assert (first["projectStatus"], first["canApprove"]) == ("active", True)

        # The strong reference the route happens not to keep. Anything that
        # returns or stores the row creates it.
        held = session.get(Project, seeded["project_id"])
        assert held is not None

        with owner_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE projects SET status = 'archived', version = version + 1 "
                    "WHERE tenant_id = :t AND project_id = :p"
                ),
                {"t": tenant, "p": seeded["project_id"]},
            )

        second = settings_service.effective_permission(
            session,
            tenant_id=tenant,
            project_id=seeded["project_id"],
            user_id=seeded["user_id"],
        )

        assert second["projectStatus"] == "archived"
        assert second["canApprove"] is False
        # The held instance is refreshed too, so a caller that kept the row does
        # not go on acting on the old one. Read inside the session: outside it
        # the instance is detached and this would be a lazy load, not a check.
        assert held.status == "archived"
