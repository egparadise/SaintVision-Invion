"""Real PostgreSQL for the model version registration route (G-04 W2).

These are the things a stand-in session cannot establish, because what they test
is the database:

* the unique constraints actually firing, in the two shapes the design names as
  the second defence, and answering 409 rather than 500;
* RLS keeping another tenant's model invisible, and the parent join answering the
  same 404 for a sibling project;
* the IDEM-6 contract -- two concurrent *first* requests with one idempotency
  key, serialised by a real ``pg_advisory_xact_lock``, producing one row, one
  ledger record and no unique error. A stand-in cannot show this at all: the
  whole point is what two transactions do to each other.

The transport contract (order of checks, canonical bodies, request shape) is
``tests/core/test_model_version_register_route.py`` and runs everywhere.
"""

from __future__ import annotations

import datetime as dt
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.api.deps import get_principal
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.api.v1 import model_versions
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id

pytestmark = pytest.mark.postgres


def _digest() -> str:
    """64 lowercase hex, unique: the shape the checksum columns require."""
    return uuid.uuid4().hex + uuid.uuid4().hex


def _insert(connection, table_name, **values):
    """Insert through the model metadata, so a wrong column cannot reach hosted CI.

    Raw SQL in a fixture is checked by PostgreSQL and nowhere else. Building the
    statement from ``Base.metadata`` validates the column names as it is written,
    and the required-column check covers the omissions PostgreSQL would otherwise
    be the first to notice -- an hour of hosted CI to learn a name.
    """
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


def _seed(connection, *, tenant_id, now, label, role="approver"):
    """One project, one member of the given role, one model with no versions."""
    user_id = new_id("user")
    project_id = new_id("project")
    model_id = new_id("model")

    _insert(
        connection,
        "users",
        user_id=user_id,
        tenant_id=tenant_id,
        external_subject=f"register-{label}",
        display_name=f"register-{label}",
        status="active",
        created_at=now,
        updated_at=now,
        version=1,
    )
    _insert(
        connection,
        "projects",
        project_id=project_id,
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
        project_id=project_id,
        user_id=user_id,
        role_code=role,
    )
    _insert(
        connection,
        "models",
        model_id=model_id,
        tenant_id=tenant_id,
        project_id=project_id,
        name=f"model-{label}",
        created_at=now,
    )
    return {"user_id": user_id, "project_id": project_id, "model_id": model_id}


def _client(app_engine, *, tenant_id, user_id, now, authenticate=True):
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only", idempotency_ttl_seconds=600),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    if authenticate:
        app.dependency_overrides[get_principal] = lambda: Principal(
            user_id=user_id, tenant_id=tenant_id, external_subject="synthetic-register"
        )
    return TestClient(app, raise_server_exceptions=False)


def _path(seeded, project_id=None, model_id=None):
    return (
        f"/v1/projects/{project_id or seeded['project_id']}"
        f"/models/{model_id or seeded['model_id']}/versions"
    )


def _body(version="1.0.0", digest=None):
    """The request, which no longer carries a URI: the server derives it."""
    return {
        "version": version,
        "contentSha256": digest or _digest(),
        "byteSize": 4096,
    }


def _headers(key):
    return {"Idempotency-Key": key, "Content-Type": "application/json"}


def _rows(owner_engine, tenant_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT model_version_id, model_id, version, stage, content_sha256, uri "
                "FROM model_versions WHERE tenant_id = :t ORDER BY model_version_id"
            ),
            {"t": tenant_id},
        ).mappings().all()


def _ledger(owner_engine, tenant_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT endpoint, idempotency_key, project_id, response_status "
                "FROM idempotency_records WHERE tenant_id = :t"
            ),
            {"t": tenant_id},
        ).mappings().all()


def _canonical(response, *, code, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["type"] == "about:blank"
    assert body["code"] == code
    return body


# --------------------------------------------------------------------------
# The write itself
# --------------------------------------------------------------------------


def test_an_approver_registers_one_draft_and_one_ledger_row(
    owner_engine, app_engine, two_tenants, frozen_now
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-ok")

    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
    body = _body()
    response = client.post(_path(seeded), json=body, headers=_headers("k-ok"))

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["stage"] == "draft"
    assert payload["contentSha256"] == body["contentSha256"]
    assert payload["version"] == "1.0.0"

    # The stored address is derived from the model's name and this version, so
    # the kernel manifest's join key holds by construction (Codex #191 F2).
    assert payload["uri"] == "inv://models/model-w2-ok@1.0.0"

    rows = _rows(owner_engine, tenant)
    assert len(rows) == 1
    assert rows[0]["stage"] == "draft"
    assert rows[0]["model_version_id"] == payload["modelVersionId"]
    assert rows[0]["uri"] == payload["uri"]

    ledger = _ledger(owner_engine, tenant)
    assert len(ledger) == 1
    assert ledger[0]["endpoint"] == model_versions.ENDPOINT
    assert ledger[0]["idempotency_key"] == "k-ok"
    assert ledger[0]["project_id"] == seeded["project_id"]
    # The stored status is the status the route returns, so a replay is exact.
    assert ledger[0]["response_status"] == 201


def test_a_member_without_the_approval_grade_cannot_register(
    owner_engine, app_engine, two_tenants, frozen_now
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(
            connection, tenant_id=tenant, now=frozen_now, label="w2-req", role="requester"
        )

    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
    response = client.post(_path(seeded), json=_body(), headers=_headers("k-req"))

    _canonical(response, code="AUTH-0030", status=403)
    assert _rows(owner_engine, tenant) == []
    assert _ledger(owner_engine, tenant) == []


def test_a_non_member_of_the_project_cannot_register(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """The caller is a real user of the tenant, with no membership of this project."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-own")
        outsider = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-out")

    client = _client(app_engine, tenant_id=tenant, user_id=outsider["user_id"], now=frozen_now)
    response = client.post(_path(seeded), json=_body(), headers=_headers("k-out"))

    _canonical(response, code="AUTH-0030", status=403)
    assert _rows(owner_engine, tenant) == []


# --------------------------------------------------------------------------
# path -> row through the parent, and RLS
# --------------------------------------------------------------------------


def test_a_model_in_a_sibling_project_of_my_tenant_is_a_404(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """The caller approves in their own project and names the other project's model."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-mine")
        theirs = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-sib")

    client = _client(app_engine, tenant_id=tenant, user_id=mine["user_id"], now=frozen_now)
    response = client.post(
        _path(mine, model_id=theirs["model_id"]), json=_body(), headers=_headers("k-sib")
    )

    body = _canonical(response, code="RES-0004", status=404)
    assert body["detail"] == model_versions.NO_SUCH_MODEL
    assert _rows(owner_engine, tenant) == []


def test_another_tenants_model_is_the_same_404_under_rls(
    owner_engine, app_engine, two_tenants, frozen_now
):
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        mine = _seed(connection, tenant_id=tenant_a, now=frozen_now, label="w2-a")
        theirs = _seed(connection, tenant_id=tenant_b, now=frozen_now, label="w2-b")

    client = _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"], now=frozen_now)
    response = client.post(
        _path(mine, model_id=theirs["model_id"]), json=_body(), headers=_headers("k-rls")
    )

    body = _canonical(response, code="RES-0004", status=404)
    assert body["detail"] == model_versions.NO_SUCH_MODEL
    assert _rows(owner_engine, tenant_a) == []
    assert _rows(owner_engine, tenant_b) == []


# --------------------------------------------------------------------------
# The unique constraints, which is what the design calls the second defence
# --------------------------------------------------------------------------


def test_the_same_version_name_under_one_model_is_a_409_and_writes_nothing(
    owner_engine, app_engine, two_tenants, frozen_now
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-dupv")

    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
    assert client.post(
        _path(seeded), json=_body("1.0.0"), headers=_headers("k-v1")
    ).status_code == 201
    response = client.post(_path(seeded), json=_body("1.0.0"), headers=_headers("k-v2"))

    body = _canonical(response, code="GRAPH-0002", status=409)
    assert body["detail"] == "This model already has a version with that name."
    assert len(_rows(owner_engine, tenant)) == 1
    # IDEM-4: a refused request leaves no ledger row, so it can be retried.
    assert len(_ledger(owner_engine, tenant)) == 1


def test_the_same_digest_again_is_a_409_and_writes_nothing(
    owner_engine, app_engine, two_tenants, frozen_now
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-dupd")

    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
    digest = _digest()
    assert client.post(
        _path(seeded), json=_body("1.0.0", digest=digest), headers=_headers("k-d1")
    ).status_code == 201
    response = client.post(
        _path(seeded), json=_body("2.0.0", digest=digest), headers=_headers("k-d2")
    )

    body = _canonical(response, code="GRAPH-0002", status=409)
    assert body["detail"] == "That content digest is already registered."
    assert len(_rows(owner_engine, tenant)) == 1
    # This is the invariant that survives the F1 narrowing: the same bytes under
    # two names *within one model* stays a conflict.


def test_f1_today_that_same_digest_is_refused_and_says_nothing_about_where(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """The sibling-project existence oracle, recorded as a gap, not as correct.

    ``uq_model_versions_tenant_id_content_sha256`` is tenant scoped, so a digest
    held in a project the caller cannot see refuses this registration -- and a
    409/201 difference carries that existence bit whatever the wording says.
    Codex #191 F1 decided the invariant moves to ``(model_id, content_sha256)``.

    The target test ("two projects of one tenant may each register the same
    digest") is **not** here: it would have to be an expected failure until the
    migration lands, and an xfail is a JUnit ``skipped`` entry that the Backend
    lane's exact-skip gate would reject. It belongs to the migration PR, which is
    where it turns green. This test asserts what happens today, and that the
    refusal at least discloses no identifier while it still happens.
    """
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        hidden = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-hid2")
        mine = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-vis2")
        digest = _digest()
        _insert(
            connection,
            "model_versions",
            model_version_id=new_id("model_version"),
            tenant_id=tenant,
            model_id=hidden["model_id"],
            version="1.0.0",
            stage="draft",
            content_sha256=digest,
            byte_size=1,
            uri="inv://models/model-w2-hid2@1.0.0",
            created_at=frozen_now,
        )

    client = _client(app_engine, tenant_id=tenant, user_id=mine["user_id"], now=frozen_now)
    response = client.post(
        _path(mine), json=_body("1.0.0", digest=digest), headers=_headers("k-hid2")
    )

    _canonical(response, code="GRAPH-0002", status=409)
    assert hidden["project_id"] not in response.text
    assert hidden["model_id"] not in response.text


# --------------------------------------------------------------------------
# Idempotency against a real ledger
# --------------------------------------------------------------------------


def test_the_same_key_and_the_same_body_replays_exactly_once_written(
    owner_engine, app_engine, two_tenants, frozen_now
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-rep")

    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
    body = _body()
    first = client.post(_path(seeded), json=body, headers=_headers("k-rep"))
    second = client.post(_path(seeded), json=body, headers=_headers("k-rep"))

    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert len(_rows(owner_engine, tenant)) == 1
    assert len(_ledger(owner_engine, tenant)) == 1


def test_the_same_key_with_a_different_body_is_a_409(
    owner_engine, app_engine, two_tenants, frozen_now
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-conf")

    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
    assert client.post(
        _path(seeded), json=_body("1.0.0"), headers=_headers("k-conf")
    ).status_code == 201
    response = client.post(_path(seeded), json=_body("2.0.0"), headers=_headers("k-conf"))

    _canonical(response, code="GRAPH-0002", status=409)
    assert len(_rows(owner_engine, tenant)) == 1


def test_the_same_key_for_a_different_model_is_not_that_models_answer(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """The ledger payload carries the path's model, so one key cannot replay
    another model's registration."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-two")
        second_model = new_id("model")
        _insert(
            connection,
            "models",
            model_id=second_model,
            tenant_id=tenant,
            project_id=seeded["project_id"],
            name="model-w2-two-b",
            created_at=frozen_now,
        )

    client = _client(app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now)
    body = _body("1.0.0")
    assert client.post(_path(seeded), json=body, headers=_headers("k-same")).status_code == 201
    response = client.post(
        _path(seeded, model_id=second_model), json=body, headers=_headers("k-same")
    )

    # Same key, same request body, different model: a conflict, not a replay.
    _canonical(response, code="GRAPH-0002", status=409)
    assert len(_rows(owner_engine, tenant)) == 1


def test_two_concurrent_first_requests_with_one_key_produce_one_row(
    owner_engine, app_engine, two_tenants, frozen_now, monkeypatch
):
    """IDEM-6, the reason the advisory lock exists.

    ``replay_or_reserve`` reserves nothing, so without the lock both
    transactions read "absent", both register, and one loses on the ledger's
    unique index after its write already happened. The barrier puts both
    transactions at the lock at the same moment, so this is the race and not a
    sequence that happens to pass.
    """
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-race")

    barrier = threading.Barrier(2, timeout=60)
    real = model_versions.serialise_idempotent_write

    def at_the_same_moment(session, **kwargs):
        barrier.wait()
        return real(session, **kwargs)

    monkeypatch.setattr(model_versions, "serialise_idempotent_write", at_the_same_moment)

    body = _body()

    def send():
        client = _client(
            app_engine, tenant_id=tenant, user_id=seeded["user_id"], now=frozen_now
        )
        return client.post(_path(seeded), json=body, headers=_headers("k-race"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [future.result(timeout=90) for future in [pool.submit(send), pool.submit(send)]]

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [201, 201], [response.text for response in responses]
    assert responses[0].json() == responses[1].json()
    # One registration, one ledger row, and no unique violation reached anyone.
    assert len(_rows(owner_engine, tenant)) == 1
    assert len(_ledger(owner_engine, tenant)) == 1


# --------------------------------------------------------------------------
# No credential, observed on the real application role
# --------------------------------------------------------------------------


def test_a_request_without_a_credential_is_refused(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """No ``get_principal`` override: the real verifier refuses.

    Recorded as observed rather than asserted narrowly, because the denial audit
    for an anonymous request is a shared boundary under the application role
    (#184 reports a 500 there on the app-role engine). Whatever this does, it
    must not register anything.
    """
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="w2-anon")

    client = _client(
        app_engine,
        tenant_id=tenant,
        user_id=seeded["user_id"],
        now=frozen_now,
        authenticate=False,
    )
    response = client.post(_path(seeded), json=_body(), headers=_headers("k-anon"))

    assert response.status_code != 201, response.text
    assert _rows(owner_engine, tenant) == []
    assert _ledger(owner_engine, tenant) == []
