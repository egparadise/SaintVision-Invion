"""Card 253 against a real PostgreSQL: what only the database can establish.

The project-scoped catalogue surface is here because its promises are database
promises -- a row lock read at ``READ COMMITTED``, an advisory lock a second
request waits on, an authorisation that can be revoked *during* those waits, and
a ``project_id`` column that means "invisible" when it is NULL. A stand-in
session can say none of that.

Covers the design's (card 250 §3-4) T3, T4, T5, T6, T7, T8, T9, T12, T13, T14,
T15, T16, T18-a/b/c, T20, T21 and T22. The contract, enum, ``oneOf`` and
translation-table nodes are PG-free and live in
``tests/core/test_storage_project_contract.py``.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import threading
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.api.v1 import storage_project
from saintvision.config import Settings
from saintvision.db.session import project_scope as real_project_scope
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id
from test_model_retention_pin_real_pg import _wait_until_blocked
from test_model_version_register_real_pg import _insert

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 3, 9, 0, tzinfo=UTC)
PATH = "/v1/projects/{project}/storage/locations"
#: Long enough that a poll-then-commit handover never spends the budget, short
#: enough that a test which genuinely deadlocks fails instead of hanging.
RACE_BUDGET_MS = 30_000
JOIN_SECONDS = 60
MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations/versions/0062_data_location_project_scope.py"
)


# --------------------------------------------------------------------------
# The world each test starts from
# --------------------------------------------------------------------------


def _seed(connection, *, tenant_id, now, label, role="operator", peer_role="operator"):
    """Two projects, three users and one active folder the first user owns.

    ``owner`` is a member of project A and registered the contribution; ``peer``
    is a member of the same project and owns nothing; ``outsider`` is a member of
    project B only. Three users is the fewest that can tell a project boundary
    and an ownership boundary apart, and the design keeps those two apart.
    """
    ids = {
        "owner": new_id("user"),
        "peer": new_id("user"),
        "outsider": new_id("user"),
        "a": new_id("project"),
        "b": new_id("project"),
        "node": new_id("node"),
        "contribution": new_id("storage_contribution"),
    }
    for key in ("owner", "peer", "outsider"):
        _insert(
            connection, "users",
            user_id=ids[key], tenant_id=tenant_id, external_subject=f"c253-{label}-{key}",
            display_name=f"c253-{label}-{key}", status="active",
            created_at=now, updated_at=now, version=1,
        )
    for key in ("a", "b"):
        _insert(
            connection, "projects",
            project_id=ids[key], tenant_id=tenant_id, code=f"c253-{label}-{key}",
            display_name=f"c253-{label}-{key}", status="active", created_at=now, version=1,
        )
    for user_key, project_key, role_code in (
        ("owner", "a", role), ("peer", "a", peer_role), ("outsider", "b", role)
    ):
        _insert(
            connection, "project_members",
            tenant_id=tenant_id, project_id=ids[project_key],
            user_id=ids[user_key], role_code=role_code,
        )
    _insert(
        connection, "nodes",
        node_id=ids["node"], tenant_id=tenant_id, hostname=f"node-{label}", os_type="linux",
        os_version="6.1", agent_version="1.0.0", status="active", enrolled_at=now,
        heartbeat_sequence=0, version=1,
    )
    _insert(
        connection, "storage_contributions",
        contribution_id=ids["contribution"], tenant_id=tenant_id, node_id=ids["node"],
        declared_path=f"/srv/inv/{label}", normalized_path=f"/srv/inv/{label}",
        mode="read_write", status="active", registered_by_user_id=ids["owner"],
        registered_at=now, version=1,
    )
    return ids


def _client(app_engine, *, tenant_id, user_id, lock_timeout_ms=5_000):
    """The real verifier and the real ``get_principal``: the actor is a verified
    credential's, not an override of the dependency."""
    token = f"c253-{user_id}"
    principal = Principal(
        user_id=user_id, tenant_id=tenant_id, external_subject=f"oidc:{user_id}"
    )
    app = create_app(
        engine=app_engine,
        settings=Settings(
            database_url="test-only",
            kernel_base_url="http://kernel.invalid",
            business_lock_timeout_ms=lock_timeout_ms,
        ),
        verifier=StaticPrincipalVerifier({token: principal}, allow_outside_dev=True),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _body(ids, *, name="sales", version="1", path="train/part-0.bin", size=1024):
    return {
        "contributionId": ids["contribution"],
        "kind": "dataset",
        "relativePath": path,
        "byteSize": size,
        "name": name,
        "version": version,
    }


def _post(client, project_id, body, *, key="k-1"):
    return client.post(
        PATH.format(project=project_id), json=body, headers={"Idempotency-Key": key}
    )


def _canonical(response, *, code, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["code"] == code
    return body


# --------------------------------------------------------------------------
# Read as the owner: the application role has no SELECT on audit_events
# --------------------------------------------------------------------------


def _locations(owner_engine, tenant_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT location_id, project_id, contribution_id, uri, kind, byte_size, ready "
                "FROM data_locations WHERE tenant_id = :t ORDER BY location_id"
            ),
            {"t": tenant_id},
        ).mappings().all()


def _ledger(owner_engine, tenant_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT endpoint, idempotency_key, project_id, response_status "
                "FROM idempotency_records WHERE tenant_id = :t ORDER BY created_at"
            ),
            {"t": tenant_id},
        ).mappings().all()


def _audits(owner_engine, *, outcome):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT action, outcome, reason_code, target_type, target_id, actor_id, "
                "trace_id, detail FROM audit_events WHERE outcome = :o ORDER BY occurred_at"
            ),
            {"o": outcome},
        ).mappings().all()


def _status(owner_engine, contribution_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text("SELECT status FROM storage_contributions WHERE contribution_id = :c"),
            {"c": contribution_id},
        ).scalar_one()


# ==========================================================================
# T4, T9 -- the project boundary on the write, and the denial it records
# ==========================================================================


def test_t4_a_member_of_another_project_cannot_catalogue_into_this_one(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """The axis is ``canRequest`` on *this* project. Membership elsewhere is not
    membership here, and the refusal leaves one denial row and no location."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t4")
    client = _client(app_engine, tenant_id=tenant, user_id=ids["outsider"])

    body = _canonical(_post(client, ids["a"], _body(ids)), code="AUTH-0030", status=403)

    assert _locations(owner_engine, tenant) == []
    assert _ledger(owner_engine, tenant) == []
    denials = _audits(owner_engine, outcome="deny")
    assert len(denials) == 1, denials
    row = denials[0]
    assert row["actor_id"] == ids["outsider"]
    assert (row["target_type"], row["target_id"]) == ("project", ids["a"])
    assert row["reason_code"] == "AUTH-0030" and row["trace_id"] == body["traceId"]
    assert row["action"] == storage_project.AUDIT_ACTION and len(row["action"]) <= 64


def test_t4_a_viewer_of_this_project_cannot_catalogue_either(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """``viewer`` is in none of the three grade sets, so a visible project is not
    a writable one. The grade is read, never inferred from "no exception"."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t4v", peer_role="viewer")
    client = _client(app_engine, tenant_id=tenant, user_id=ids["peer"])

    _canonical(_post(client, ids["a"], _body(ids)), code="AUTH-0030", status=403)
    assert _locations(owner_engine, tenant) == []


# ==========================================================================
# T3 -- the project boundary on every read, with no existence oracle
# ==========================================================================


def test_t3_another_projects_member_reads_no_rows_and_learns_nothing(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """Three reads, two boundaries: asking about project A as a non-member is the
    same refusal as asking about a project that does not exist, and asking about
    A's row *from inside* project B is the same 404 as a URI never catalogued."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t3")
    owner = _client(app_engine, tenant_id=tenant, user_id=ids["owner"])
    created = _post(owner, ids["a"], _body(ids))
    assert created.status_code == 201, created.text
    uri = created.json()["uri"]

    outsider = _client(app_engine, tenant_id=tenant, user_id=ids["outsider"])
    absent_project = new_id("project")
    for suffix in ("", "/resolve", "/replica-status"):
        for project in (ids["a"], absent_project):
            query = {"uri": uri} if suffix else None
            response = outsider.get(PATH.format(project=project) + suffix, params=query)
            _canonical(response, code="AUTH-0030", status=403)

    # Inside the project the outsider *can* see, the row simply is not there, and
    # neither is any hint that it exists somewhere else.
    page = outsider.get(PATH.format(project=ids["b"]))
    assert page.status_code == 200 and page.json() == {"items": [], "nextCursor": None}
    foreign = outsider.get(PATH.format(project=ids["b"]) + "/resolve", params={"uri": uri})
    never = outsider.get(
        PATH.format(project=ids["b"]) + "/resolve",
        params={"uri": "inv://datasets/never@1/nothing.bin"},
    )
    for response in (foreign, never):
        _canonical(response, code="RES-0004", status=404)
    assert {k: v for k, v in foreign.json().items() if k != "traceId"} == {
        k: v for k, v in never.json().items() if k != "traceId"
    }
    assert len(_locations(owner_engine, tenant)) == 1


def test_t3_a_viewer_member_cannot_read_this_projects_catalogue(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """The read authority is a grade, not mere membership. ``viewer`` is in
    neither ``canRequest`` nor ``canApprove``, so it reads nothing here -- and
    widening that is a product decision with its own boolean, not something this
    route may infer (card 250 §3-4-2)."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t3v", peer_role="viewer")
    owner = _client(app_engine, tenant_id=tenant, user_id=ids["owner"])
    created = _post(owner, ids["a"], _body(ids))
    assert created.status_code == 201, created.text
    uri = created.json()["uri"]

    viewer = _client(app_engine, tenant_id=tenant, user_id=ids["peer"])
    for suffix, query in (("", None), ("/resolve", {"uri": uri}), ("/replica-status", {"uri": uri})):
        response = viewer.get(PATH.format(project=ids["a"]) + suffix, params=query)
        _canonical(response, code="AUTH-0030", status=403)

    # An approver may read without being able to write: the two grades are
    # separate, and both take part in the project's work.
    with owner_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE project_members SET role_code = 'approver' "
                "WHERE tenant_id = :t AND project_id = :p AND user_id = :u"
            ),
            {"t": tenant, "p": ids["a"], "u": ids["peer"]},
        )
    approver = _client(app_engine, tenant_id=tenant, user_id=ids["peer"])
    page = approver.get(PATH.format(project=ids["a"]))
    assert page.status_code == 200
    assert [item["locationId"] for item in page.json()["items"]] == [created.json()["locationId"]]
    _canonical(_post(approver, ids["a"], _body(ids), key="k-9"), code="AUTH-0030", status=403)


# ==========================================================================
# T5 -- the project scope is opened only after the check has passed
# ==========================================================================


def test_t5_the_project_scope_is_only_opened_after_the_access_check_passes(
    owner_engine, app_engine, two_tenants, clean_tables, monkeypatch
):
    """A refused request must not reach a scoped read at all. If it did, the
    answer would be a quiet empty page instead of a refusal -- the failure §3-2
    of the design names."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t5")
    opened: list[str] = []

    def recording_scope(session, project_id):
        opened.append(project_id)
        return real_project_scope(session, project_id)

    monkeypatch.setattr(storage_project, "project_scope", recording_scope)

    refused = _client(app_engine, tenant_id=tenant, user_id=ids["outsider"])
    _canonical(_post(refused, ids["a"], _body(ids)), code="AUTH-0030", status=403)
    _canonical(refused.get(PATH.format(project=ids["a"])), code="AUTH-0030", status=403)
    assert opened == []

    allowed = _client(app_engine, tenant_id=tenant, user_id=ids["owner"])
    assert _post(allowed, ids["a"], _body(ids)).status_code == 201
    assert opened == [ids["a"]]


def test_t5_the_scope_is_transaction_local_and_absent_outside_it(app_sessionmaker, two_tenants):
    """``SET LOCAL`` means the scope cannot leak into the next transaction."""
    project_id = new_id("project")
    with app_sessionmaker() as session:
        with session.begin():
            empty = session.execute(
                text("SELECT current_setting('inv.project_id', true)")
            ).scalar_one()
            assert empty in (None, "")
            with real_project_scope(session, project_id):
                assert session.execute(
                    text("SELECT current_setting('inv.project_id', true)")
                ).scalar_one() == project_id
        with session.begin():
            assert session.execute(
                text("SELECT current_setting('inv.project_id', true)")
            ).scalar_one() in (None, "")


# ==========================================================================
# T7 -- a row bound to no project is in no project
# ==========================================================================


def test_t7_a_null_project_row_is_invisible_to_project_reads_and_still_visible_to_its_owner(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """Every row catalogued before 0062 is this row. "No binding" has to mean
    invisible to every project, not visible to all of them."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t7")
        legacy_id = new_id("data_location")
        _insert(
            connection, "data_locations",
            location_id=legacy_id, tenant_id=tenant, contribution_id=ids["contribution"],
            uri="inv://datasets/legacy@1/part-0.bin", kind="dataset",
            relative_path="part-0.bin", byte_size=7, ready=False,
            catalogued_at=NOW, version=1,
        )
    with owner_engine.begin() as connection:
        assert connection.execute(
            text("SELECT project_id FROM data_locations WHERE location_id = :l"),
            {"l": legacy_id},
        ).scalar_one() is None

    owner = _client(app_engine, tenant_id=tenant, user_id=ids["owner"])
    scoped = owner.get(PATH.format(project=ids["a"]))
    assert scoped.status_code == 200 and scoped.json() == {"items": [], "nextCursor": None}
    resolved = owner.get(
        PATH.format(project=ids["a"]) + "/resolve",
        params={"uri": "inv://datasets/legacy@1/part-0.bin"},
    )
    _canonical(resolved, code="RES-0004", status=404)

    # The owner-scoped tenant-wide surface is unchanged: Phase 1 touched no policy.
    wide = owner.get("/v1/storage/locations")
    assert wide.status_code == 200
    assert [item["locationId"] for item in wide.json()["items"]] == [legacy_id]


# ==========================================================================
# T12, T13 -- ownership of the folder, on the locked row, with no oracle
# ==========================================================================


def test_t12_a_non_owner_and_an_unknown_contribution_get_the_same_audited_404(
    owner_engine, app_engine, two_tenants, clean_tables
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t12")

    peer = _client(app_engine, tenant_id=tenant, user_id=ids["peer"])
    not_owned = _canonical(_post(peer, ids["a"], _body(ids)), code="RES-0004", status=404)

    owner = _client(app_engine, tenant_id=tenant, user_id=ids["owner"])
    unknown = dict(_body(ids), contributionId=new_id("storage_contribution"))
    never_existed = _canonical(
        _post(owner, ids["a"], unknown, key="k-2"), code="RES-0004", status=404
    )

    assert {k: v for k, v in not_owned.items() if k != "traceId"} == {
        k: v for k, v in never_existed.items() if k != "traceId"
    }
    assert not_owned["detail"] == "No such resource."
    assert _locations(owner_engine, tenant) == []

    denials = _audits(owner_engine, outcome="deny")
    assert len(denials) == 2, denials
    for row, trace in zip(denials, (not_owned["traceId"], never_existed["traceId"])):
        assert row["action"] == storage_project.AUDIT_ACTION
        assert (row["target_type"], row["target_id"]) == ("project", ids["a"])
        assert row["reason_code"] == "RES-0004" and row["trace_id"] == trace


@pytest.mark.parametrize("role", ["owner", "maintainer"])
def test_t13_no_project_role_stands_in_for_the_folders_owner(
    owner_engine, app_engine, two_tenants, clean_tables, role
):
    """``canRequest`` and ``canAdminister`` are about the project. The folder is
    not the project's, so raising the role changes nothing."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label=f"t13-{role}", peer_role=role)
    peer = _client(app_engine, tenant_id=tenant, user_id=ids["peer"])

    _canonical(_post(peer, ids["a"], _body(ids)), code="RES-0004", status=404)
    assert _locations(owner_engine, tenant) == []


# ==========================================================================
# T6 -- the same authority on activation and revocation
# ==========================================================================


def test_t6_only_the_registering_user_may_activate_or_revoke_a_contribution(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """A project role is not ownership here either, and the refusal is the same
    404 as a contribution that does not exist. The row does not move."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t6", peer_role="owner")
        connection.execute(
            text("UPDATE storage_contributions SET status = 'pending' WHERE contribution_id = :c"),
            {"c": ids["contribution"]},
        )
    peer = _client(app_engine, tenant_id=tenant, user_id=ids["peer"])

    activation = peer.post(f"/v1/storage/contributions/{ids['contribution']}/activation")
    _canonical(activation, code="RES-0004", status=404)
    assert _status(owner_engine, ids["contribution"]) == "pending"

    revocation = peer.delete(f"/v1/storage/contributions/{ids['contribution']}")
    _canonical(revocation, code="RES-0004", status=404)
    assert _status(owner_engine, ids["contribution"]) == "pending"

    owner = _client(app_engine, tenant_id=tenant, user_id=ids["owner"])
    allowed = owner.post(f"/v1/storage/contributions/{ids['contribution']}/activation")
    assert allowed.status_code == 200, allowed.text
    assert _status(owner_engine, ids["contribution"]) == "active"


# ==========================================================================
# T14, T15, T16, T20 -- the key, the ledger and exactly-once
# ==========================================================================


def test_t14_the_same_key_and_body_replays_the_stored_answer_and_writes_nothing_new(
    owner_engine, app_engine, two_tenants, clean_tables
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t14")
    owner = _client(app_engine, tenant_id=tenant, user_id=ids["owner"])

    first = _post(owner, ids["a"], _body(ids))
    assert first.status_code == 201, first.text
    replay = _post(owner, ids["a"], _body(ids))

    assert replay.status_code == 201 and replay.json() == first.json()
    assert len(_locations(owner_engine, tenant)) == 1
    assert len(_ledger(owner_engine, tenant)) == 1
    allows = _audits(owner_engine, outcome="allow")
    assert len(allows) == 1, allows
    assert allows[0]["action"] == "storage.location.catalogue"
    assert (allows[0]["target_type"], allows[0]["target_id"]) == (
        "data_location", first.json()["locationId"]
    )
    assert dict(allows[0]["detail"]) == {
        "projectId": ids["a"],
        "contributionId": ids["contribution"],
        "kind": "dataset",
    }


def test_t15_the_same_key_with_a_different_body_is_a_409_that_adds_nothing(
    owner_engine, app_engine, two_tenants, clean_tables
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t15")
    owner = _client(app_engine, tenant_id=tenant, user_id=ids["owner"])

    first = _post(owner, ids["a"], _body(ids))
    assert first.status_code == 201, first.text
    before = _locations(owner_engine, tenant)

    _canonical(_post(owner, ids["a"], _body(ids, size=2048)), code="GRAPH-0002", status=409)

    assert _locations(owner_engine, tenant) == before
    assert len(_ledger(owner_engine, tenant)) == 1
    assert len(_audits(owner_engine, outcome="allow")) == 1


def test_t16_the_ledger_records_the_path_project_and_the_bounded_endpoint(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """The body cannot carry a project (T1), so the ledger's project can only be
    the path's -- the value ``require_project_access`` judged."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t16")
    owner = _client(app_engine, tenant_id=tenant, user_id=ids["owner"])
    assert _post(owner, ids["a"], _body(ids), key="ledger-1").status_code == 201

    rows = _ledger(owner_engine, tenant)
    assert len(rows) == 1
    assert rows[0]["endpoint"] == storage_project.ENDPOINT
    assert rows[0]["idempotency_key"] == "ledger-1"
    assert rows[0]["project_id"] == ids["a"]
    assert rows[0]["response_status"] == 201
    assert ids["a"] not in rows[0]["endpoint"]


@pytest.mark.parametrize(
    "key",
    [None, "", "x" * 129, "bad key", "key/with/slash"],
    ids=["missing", "empty", "too-long", "space", "slash"],
)
def test_t20_a_missing_or_malformed_idempotency_key_is_422_and_writes_nothing(
    owner_engine, app_engine, two_tenants, clean_tables, key
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t20")
    owner = _client(app_engine, tenant_id=tenant, user_id=ids["owner"])
    headers = {} if key is None else {"Idempotency-Key": key}

    response = owner.post(PATH.format(project=ids["a"]), json=_body(ids), headers=headers)

    _canonical(response, code="VAL-0003", status=422)
    assert _locations(owner_engine, tenant) == []
    assert _ledger(owner_engine, tenant) == []


def test_the_tenant_wide_uri_uniqueness_is_a_409_and_not_a_500(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """0001 made ``(tenant_id, uri)`` unique and 0062 did not narrow it, so a
    second project cannot catalogue the same URI. This route is the first product
    caller that can reach the collision, and it answers rather than crashes."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="uri")
        _insert(
            connection, "project_members",
            tenant_id=tenant, project_id=ids["b"], user_id=ids["owner"], role_code="operator",
        )
    owner = _client(app_engine, tenant_id=tenant, user_id=ids["owner"])
    assert _post(owner, ids["a"], _body(ids), key="u-1").status_code == 201

    clash = _canonical(_post(owner, ids["b"], _body(ids), key="u-2"), code="GRAPH-0002", status=409)

    assert clash["detail"] == storage_project.URI_TAKEN_DETAIL
    assert ids["a"] not in clash["detail"]            # no project is named
    assert len(_locations(owner_engine, tenant)) == 1


# ==========================================================================
# T18-a/b/c -- the revoke race, both schedules
# ==========================================================================


def _hold_contribution(owner_engine, contribution_id):
    """A raw transaction holding the contribution row ``FOR UPDATE``."""
    connection = owner_engine.connect()
    tx = connection.begin()
    connection.execute(
        text(
            "SELECT contribution_id FROM storage_contributions "
            "WHERE contribution_id = :c FOR UPDATE"
        ),
        {"c": contribution_id},
    )
    return connection, tx


def _revoke_sql():
    return text(
        "UPDATE storage_contributions SET status = 'revoked', revoked_at = :n "
        "WHERE contribution_id = :c"
    )


def test_t18a_a_revoke_that_locks_first_makes_the_waiting_post_refuse(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """The POST blocks on the row, the revoke commits, and the POST then reads the
    status *from the locked row* -- so it refuses and catalogues nothing. Drop the
    ``FOR UPDATE`` and this is a location inside a withdrawn folder."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t18a")
    holder, tx = _hold_contribution(owner_engine, ids["contribution"])
    owner = _client(
        app_engine, tenant_id=tenant, user_id=ids["owner"], lock_timeout_ms=RACE_BUDGET_MS
    )
    result: dict = {}

    thread = threading.Thread(
        target=lambda: result.update(response=_post(owner, ids["a"], _body(ids)))
    )
    thread.start()
    try:
        _wait_until_blocked(owner_engine)
        holder.execute(_revoke_sql(), {"c": ids["contribution"], "n": NOW})
        tx.commit()
    finally:
        holder.close()
        thread.join(timeout=JOIN_SECONDS)

    _canonical(result["response"], code="RES-0004", status=404)
    assert _locations(owner_engine, tenant) == []                      # T18-c
    assert _status(owner_engine, ids["contribution"]) == "revoked"
    assert len(_audits(owner_engine, outcome="deny")) == 1


def test_t18b_a_post_that_locks_first_wins_and_the_revoke_lands_after_it(
    owner_engine, app_engine, two_tenants, clean_tables, monkeypatch
):
    """The other schedule. The catalogue row stays after the revoke commits --
    that is what revocation has always meant here (the platform stops using the
    folder; it does not erase the record)."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t18b")
    locked = threading.Event()
    release = threading.Event()

    def pausing_scope(session, project_id):
        # Strictly after the row lock and strictly before the insert: a delay,
        # never a different decision.
        locked.set()
        release.wait(timeout=JOIN_SECONDS)
        return real_project_scope(session, project_id)

    monkeypatch.setattr(storage_project, "project_scope", pausing_scope)
    owner = _client(
        app_engine, tenant_id=tenant, user_id=ids["owner"], lock_timeout_ms=RACE_BUDGET_MS
    )
    result: dict = {}
    revoked: dict = {}

    def revoke():
        with owner_engine.begin() as connection:
            connection.execute(_revoke_sql(), {"c": ids["contribution"], "n": NOW})
        revoked["done"] = True

    poster = threading.Thread(
        target=lambda: result.update(response=_post(owner, ids["a"], _body(ids)))
    )
    revoker = threading.Thread(target=revoke)
    poster.start()
    try:
        assert locked.wait(timeout=JOIN_SECONDS), "the request never reached the write"
        revoker.start()
        _wait_until_blocked(owner_engine)
        assert "done" not in revoked
    finally:
        release.set()
        poster.join(timeout=JOIN_SECONDS)
        revoker.join(timeout=JOIN_SECONDS)

    assert result["response"].status_code == 201, result["response"].text
    rows = _locations(owner_engine, tenant)
    assert len(rows) == 1 and rows[0]["project_id"] == ids["a"]
    assert _status(owner_engine, ids["contribution"]) == "revoked"
    assert revoked.get("done") is True


def test_t18c_no_location_is_inserted_after_a_revoke_has_committed(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """The claim both schedules share, measured on its own: once the revoke is
    committed, a fresh request cannot catalogue into that folder."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t18c")
        connection.execute(_revoke_sql(), {"c": ids["contribution"], "n": NOW})
    owner = _client(app_engine, tenant_id=tenant, user_id=ids["owner"])

    _canonical(_post(owner, ids["a"], _body(ids)), code="RES-0004", status=404)
    assert _locations(owner_engine, tenant) == []


# ==========================================================================
# T21, T22 -- authorisation lost during a wait
# ==========================================================================


def test_t21_a_membership_revoked_while_the_key_lock_is_held_refuses_instead_of_replaying(
    owner_engine, app_engine, two_tenants, clean_tables, monkeypatch
):
    """Two requests with the same key. The second waits on the first's advisory
    lock; the membership disappears during that wait. The re-check after the lock
    and before the replay decision is what turns the stored 201 into a refusal --
    remove it and the second request is handed a success it no longer has."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t21")
    locked = threading.Event()
    release = threading.Event()
    paused: list[str] = []

    def pausing_scope(session, project_id):
        if not paused:                       # only the first request waits
            paused.append(project_id)
            locked.set()
            release.wait(timeout=JOIN_SECONDS)
        return real_project_scope(session, project_id)

    monkeypatch.setattr(storage_project, "project_scope", pausing_scope)
    first_client = _client(
        app_engine, tenant_id=tenant, user_id=ids["owner"], lock_timeout_ms=RACE_BUDGET_MS
    )
    second_client = _client(
        app_engine, tenant_id=tenant, user_id=ids["owner"], lock_timeout_ms=RACE_BUDGET_MS
    )
    first: dict = {}
    second: dict = {}

    one = threading.Thread(
        target=lambda: first.update(r=_post(first_client, ids["a"], _body(ids), key="same"))
    )
    two = threading.Thread(
        target=lambda: second.update(r=_post(second_client, ids["a"], _body(ids), key="same"))
    )
    one.start()
    try:
        assert locked.wait(timeout=JOIN_SECONDS), "the first request never reached the write"
        two.start()
        _wait_until_blocked(owner_engine)
        with owner_engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM project_members "
                    "WHERE tenant_id = :t AND project_id = :p AND user_id = :u"
                ),
                {"t": tenant, "p": ids["a"], "u": ids["owner"]},
            )
    finally:
        release.set()
        one.join(timeout=JOIN_SECONDS)
        two.join(timeout=JOIN_SECONDS)

    assert first["r"].status_code == 201, first["r"].text
    body = _canonical(second["r"], code="AUTH-0030", status=403)
    assert len(_locations(owner_engine, tenant)) == 1
    denials = _audits(owner_engine, outcome="deny")
    assert len(denials) == 1 and denials[0]["trace_id"] == body["traceId"]
    assert (denials[0]["target_type"], denials[0]["target_id"]) == ("project", ids["a"])


def test_t22_a_project_archived_while_the_row_lock_is_awaited_refuses_before_the_insert(
    owner_engine, app_engine, two_tenants, clean_tables
):
    """``effective_permission`` raises nothing for an archived project -- it
    returns three false booleans. So the third re-check only catches this if the
    route *reads* the grade, which is what this measures."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="t22")
    holder, tx = _hold_contribution(owner_engine, ids["contribution"])
    owner = _client(
        app_engine, tenant_id=tenant, user_id=ids["owner"], lock_timeout_ms=RACE_BUDGET_MS
    )
    result: dict = {}

    thread = threading.Thread(
        target=lambda: result.update(response=_post(owner, ids["a"], _body(ids)))
    )
    thread.start()
    try:
        _wait_until_blocked(owner_engine)
        with owner_engine.begin() as connection:
            connection.execute(
                text("UPDATE projects SET status = 'archived' WHERE project_id = :p"),
                {"p": ids["a"]},
            )
        tx.rollback()
    finally:
        holder.close()
        thread.join(timeout=JOIN_SECONDS)

    _canonical(result["response"], code="AUTH-0030", status=403)
    assert _locations(owner_engine, tenant) == []
    assert len(_audits(owner_engine, outcome="deny")) == 1


# ==========================================================================
# T8 -- 0062's downgrade, as SQL-level invariants
# ==========================================================================


def _schema_state(connection):
    """What the design promised 0062 would not change, plus the shape of what it
    does add."""
    columns = connection.execute(
        text(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'data_locations' ORDER BY column_name"
        )
    ).fetchall()
    policies = connection.execute(
        text(
            "SELECT policyname, cmd, qual, with_check FROM pg_policies "
            "WHERE tablename = 'data_locations' ORDER BY policyname"
        )
    ).fetchall()
    forced = connection.execute(
        text(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = 'data_locations'"
        )
    ).one()
    grants = connection.execute(
        text(
            "SELECT grantee, privilege_type FROM information_schema.role_table_grants "
            "WHERE table_name = 'data_locations' ORDER BY grantee, privilege_type"
        )
    ).fetchall()
    return columns, policies, forced, grants


def test_t8_the_0062_downgrade_restores_the_schema_and_never_touched_a_policy(
    owner_engine, clean_tables
):
    spec = importlib.util.spec_from_file_location("migration_0062", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with owner_engine.begin() as connection:
        before = _schema_state(connection)
        assert any(row[0] == "project_id" for row in before[0])
        try:
            with Operations.context(MigrationContext.configure(connection)):
                module.downgrade()
            columns, policies, forced, grants = _schema_state(connection)
            # The column and its index are gone...
            assert not any(row[0] == "project_id" for row in columns)
            assert columns == [row for row in before[0] if row[0] != "project_id"]
            # ...and nothing else moved: same policies, same RLS, same grants.
            assert (policies, forced, grants) == (before[1], before[2], before[3])
            assert forced == (True, True)
        finally:
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
        assert _schema_state(connection) == before
