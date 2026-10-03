"""Card 266 over HTTP: the route, its refusals, and what each one audits.

The service-level file proves the three phases and the authority order. This one
proves the parts only the HTTP boundary has: the status codes a caller actually
sees, the ProblemDetails shape, and -- the half that was silently broken before
Codex's r1 -- that an authenticated refusal is recorded **once**, with the real
actor, tenant and project rather than as ``anonymous``.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import psycopg
import psycopg.rows
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy import create_engine, text as sql_text

from inv.app import create_app
from inv.business_surface import configured_business
from inv.errors import DomainError
from inv.storage_check_collect import CatalogueProjectReader, StorageCheckCollector
from test_storage_check_collect import Transport, _bind_locations
from test_storage_commit import sample, storage_subject  # noqa: F401  (fixtures)

pytestmark = pytest.mark.postgres


def _tokens(principal):
    class Tokens:
        tenant_id = principal.tenant_id

        @staticmethod
        def verify(_value):
            return SimpleNamespace(
                principal=principal, expires_at="2026-10-04T00:00:00Z"
            )

        @staticmethod
        def _keys():
            return None

    return Tokens()


def _auth():
    return {"Authorization": "Bearer synthetic"}


@pytest.fixture
def app_role(sample):  # noqa: F811
    """A login granted ``inv_app``: the role production gives the business surface."""
    role = "c266_http_" + uuid.uuid4().hex[:18]
    password = uuid.uuid4().hex
    with psycopg.connect(sample.e.owner) as connection:
        connection.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        connection.execute(sql.SQL("GRANT inv_app TO {}").format(sql.Identifier(role)))
        connection.commit()
    dsn = make_conninfo(sample.e.owner, user=role, password=password)
    try:
        yield dsn
    finally:
        with psycopg.connect(sample.e.owner) as connection:
            connection.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
            connection.commit()


@pytest.fixture
def served(sample, app_role, monkeypatch):  # noqa: F811
    """The kernel app with the collector and the denial recorder actually wired.

    Built the way production builds it -- ``configured_business`` makes the
    app-role engine, the kernel app takes it for both the catalogue read and the
    denial recorder -- because the thing under test is precisely that wiring.
    """
    _bind_locations(sample, sample.e.project)
    monkeypatch.setenv("INV_BUSINESS_DSN", "postgresql+psycopg://" + "")
    url = make_conninfo(app_role)
    values = conninfo_to_dict(url)
    monkeypatch.setenv(
        "INV_BUSINESS_DSN",
        "postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}".format(
            user=values["user"], password=values["password"],
            host=values["host"], port=values.get("port", "5432"), dbname=values["dbname"],
        ),
    )
    tokens = _tokens(sample.principal)
    business = configured_business(sample.e.db, tokens)
    engine = business.state.denial_engine
    transport = Transport(sample.sampler, sample.certificate.der)
    collector = StorageCheckCollector(
        sample.e.db, transport, CatalogueProjectReader(engine)
    )
    app = create_app(
        sample.e.db,
        tokens,
        business=business,
        storage_sample_collector=collector,
        denial_engine=engine,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(
            client=client, transport=transport, collector=collector,
            engine=engine, sample=sample,
            path=f"/v1/projects/{sample.e.project}/runs/{sample.run}/storage-samples",
        )


def _post(served, *, key, body=None, path=None):
    return served.client.post(
        path or served.path,
        json=body if body is not None else {"contributionId": served.sample.contribution},
        headers={**_auth(), "Idempotency-Key": key},
    )


def _denials(served):
    """Read the audit as the owner.

    The app role can **append** to ``audit_events`` and deliberately cannot read it
    -- reading is ``inv_audit_reader``'s, which is the whole point of that split --
    so a test that wants to see the rows asks the owner.
    """
    with psycopg.connect(served.sample.e.owner, row_factory=psycopg.rows.dict_row) as connection:
        # Scoped to this test's tenant: the database is session-scoped, so another
        # test's refusal is somebody else's row rather than a leak into this count.
        return connection.execute(
            "SELECT actor_type, actor_id, tenant_id, action, reason_code, "
            "target_type, target_id, trace_id FROM public.audit_events "
            "WHERE outcome='deny' AND tenant_id=%s ORDER BY occurred_at",
            (served.sample.e.tenant,),
        ).fetchall()


def _checks(served):
    with served.sample.e.db.transaction(served.sample.e.tenant) as c:
        return c.execute("SELECT count(*) AS n FROM public.storage_checks").fetchone()["n"]


PROBLEM_KEYS = {
    "type", "title", "status", "code", "category", "detail",
    "retryable", "traceId", "causeRef", "evidenceId",
}


# ============================================================== the happy path
def test_the_route_records_a_check_and_replays_the_same_answer(served):
    first = _post(served, key="http-a")
    assert first.status_code == 201, first.text
    body = first.json()
    assert set(body) == {"checkId", "evidenceId", "requestId", "contributionId"}
    assert _checks(served) == 1

    again = _post(served, key="http-a")
    # A replay is the same answer and says so with 200 rather than a second 201.
    assert again.status_code == 200, again.text
    assert again.json() == body
    assert _checks(served) == 1
    assert served.transport.calls == 1
    # Nothing was refused, so nothing was audited as a denial.
    assert _denials(served) == []


# ============================================= the authenticated refusal is audited once
def test_an_authenticated_refusal_is_recorded_once_with_the_real_actor(served):
    """What F4 found: the kernel pinned no identity, so this row used to say
    ``anonymous`` with no tenant and no project."""
    with psycopg.connect(served.sample.e.owner) as connection:
        connection.execute(
            "UPDATE inv.project_grants SET can_request=false WHERE project_id=%s",
            (served.sample.e.project,),
        )
        connection.commit()

    response = _post(served, key="http-denied")
    assert response.status_code == 403, response.text
    problem = response.json()
    assert set(problem) == PROBLEM_KEYS
    assert problem["code"] == "AUTH-0030"
    assert problem["retryable"] is False

    rows = _denials(served)
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["reason_code"] == "AUTH-0030"
    assert row["actor_type"] == "user"
    assert row["actor_id"] == served.sample.principal.subject_id
    assert str(row["tenant_id"]) == str(served.sample.e.tenant)
    # The audited target is the path's project, which the recorder reads from
    # ``path_params["project_id"]`` -- the reason the route spells it that way.
    assert (row["target_type"], row["target_id"]) == ("project", served.sample.e.project)
    assert row["trace_id"] == problem["traceId"]
    # The action is bounded and carries no identifier.
    assert row["action"] and len(row["action"]) <= 64
    assert served.sample.e.project not in row["action"]
    assert _checks(served) == 0


def test_an_absence_is_not_a_denial_and_records_nothing(served):
    response = _post(
        served, key="http-absent",
        body={"contributionId": "stc_" + "2" * 26},
    )
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "RES-0004"
    assert _denials(served) == []
    assert _checks(served) == 0


# ======================================================================= the 503s
def test_an_unconfigured_deployment_answers_503_and_records_nothing(sample, monkeypatch):  # noqa: F811
    """No collector: the surface must refuse rather than look healthy."""
    tokens = _tokens(sample.principal)
    app = create_app(sample.e.db, tokens)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            f"/v1/projects/{sample.e.project}/runs/{sample.run}/storage-samples",
            json={"contributionId": sample.contribution},
            headers={**_auth(), "Idempotency-Key": "http-unconfigured"},
        )
    assert response.status_code == 503, response.text
    problem = response.json()
    assert set(problem) == PROBLEM_KEYS
    assert problem["code"] == "SYS-0001"
    with sample.e.db.transaction(sample.e.tenant) as c:
        assert c.execute("SELECT count(*) AS n FROM public.storage_checks").fetchone()["n"] == 0


@pytest.mark.parametrize(
    "error, code, retryable",
    [
        (DomainError("NODE-0030", "Node delivery unconfirmed; observe the same command", 503),
         "NODE-0030", False),
        (DomainError("NODE-0050", "Node observation capacity reached", 503, retryable=True),
         "NODE-0050", True),
        (DomainError("RES-0007", "Transaction contention; retry with the same key", 503,
                     retryable=True), "RES-0007", True),
    ],
)
def test_each_unavailable_cause_is_its_own_code_and_writes_nothing(
    served, error, code, retryable
):
    """The agent's 503 or non-200, its 429, and lock contention. Each is a
    different wire code, each is 503, and none of them records a check -- turning
    "not observed" into a stored observation is the defect this card exists to
    stop."""
    def refuse(channel, challenge):
        served.transport.calls += 1
        raise error

    served.transport.storage_sample = refuse
    response = _post(served, key=f"http-503-{code}")
    assert response.status_code == 503, response.text
    problem = response.json()
    assert set(problem) == PROBLEM_KEYS
    assert problem["code"] == code
    assert problem["retryable"] is retryable
    assert problem["category"] == code.split("-", 1)[0]
    assert _checks(served) == 0
    # Unavailable is not a denial: nothing in the AUTH/SEC set, nothing recorded.
    assert _denials(served) == []


# ================================================= strict body and required key
def test_the_body_is_strict_and_the_key_is_required(served):
    unknown = served.client.post(
        served.path,
        json={"contributionId": served.sample.contribution, "requestId": str(uuid.uuid4())},
        headers={**_auth(), "Idempotency-Key": "http-strict"},
    )
    assert unknown.status_code == 422, unknown.text
    assert unknown.json()["code"] == "VAL-0003"

    keyless = served.client.post(
        served.path,
        json={"contributionId": served.sample.contribution},
        headers=_auth(),
    )
    assert keyless.status_code == 422, keyless.text
    assert keyless.json()["code"] == "VAL-0003"
    assert _checks(served) == 0


# ========================================== an audit failure is not a quiet success
def test_a_failing_audit_write_is_not_served_as_a_tidy_refusal(served, monkeypatch):
    """Fail-closed: the recorder's contract says an audit failure propagates.

    What the caller then sees is each app's **sanitized** internal answer, and the
    two apps differ: the core app ends as a generic 500, the kernel's middleware
    turns an unhandled error into ``SYS-0001`` 503. Measured rather than assumed --
    my first version of this test asserted 500 and the kernel gave 503. Either way
    the property that matters holds: it is **not** a tidy 403, and nothing
    privileged was done.
    """
    from saintvision.api import denial_recorder

    def broken(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(denial_recorder, "record_denial", broken)
    with psycopg.connect(served.sample.e.owner) as connection:
        connection.execute(
            "UPDATE inv.project_grants SET can_request=false WHERE project_id=%s",
            (served.sample.e.project,),
        )
        connection.commit()
    response = _post(served, key="http-audit-broken")
    assert response.status_code in (500, 503), response.text
    assert response.status_code != 403
    body = response.json()
    # Sanitized: the internal failure is not described to the caller.
    assert body["code"] == "SYS-0001"
    assert "audit" not in body["detail"].lower()
    assert _checks(served) == 0


# =================================================== the startup refusal (F1/F4)
def test_a_configured_collector_without_the_business_surface_refuses_to_start(sample):  # noqa: F811
    """The collector needs the app-role engine for the project boundary and for
    the denial recorder. Without it the process must not start, because both
    would fail silently: no boundary and no audit row."""
    from inv.storage_check_collect import configured_storage_sample_collector

    with pytest.raises(ValueError, match="catalogue"):
        configured_storage_sample_collector(
            sample.e.db,
            {"caFile": "a", "certificateFile": "b", "keyFile": "c"},
            None,
        )


def test_the_storage_sample_configuration_block_is_strict(sample):  # noqa: F811
    from inv.storage_check_collect import configured_storage_sample_collector

    for configuration in (
        "not-an-object",
        {"caFile": "a", "certificateFile": "b"},
        {"caFile": "a", "certificateFile": "b", "keyFile": "c", "extra": "x"},
        {"caFile": "", "certificateFile": "b", "keyFile": "c"},
    ):
        with pytest.raises(ValueError):
            configured_storage_sample_collector(sample.e.db, configuration, object())
