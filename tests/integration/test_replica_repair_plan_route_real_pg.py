"""Card 266: the repair plan read, against a real PostgreSQL.

The service has decided "short of ready copies" since VF-CL-04 and no product
path read it, so the catalogue routes reported five per-state counts and never
said a location was **under-replicated**. This file holds the claims that reading
has to make good on, and they are all about a boundary: the plan is this
project's, and a pre-``0062`` row whose ``project_id`` is NULL belongs to nobody's.
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id
from test_storage_project_scope_real_pg import _insert, _seed

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 3, 16, 0, tzinfo=UTC)
SHA = "e" * 64
PATH = "/v1/projects/{project}/storage/replica-repair-plan"


def _client(app_engine, *, tenant_id, user_id):
    token = f"c266-{user_id}"
    principal = Principal(
        user_id=user_id, tenant_id=tenant_id, external_subject=f"oidc:{user_id}"
    )
    app = create_app(
        engine=app_engine,
        settings=Settings(
            database_url="test-only",
            kernel_base_url="http://kernel.invalid",
            business_lock_timeout_ms=5_000,
        ),
        verifier=StaticPrincipalVerifier({token: principal}, allow_outside_dev=True),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _location(connection, *, tenant_id, ids, project_id, suffix):
    location_id = new_id("data_location")
    _insert(
        connection, "data_locations",
        location_id=location_id, tenant_id=tenant_id, project_id=project_id,
        contribution_id=ids["contribution"], uri=f"inv://datasets/c266@1/{suffix}.bin",
        kind="dataset", relative_path=f"{suffix}.bin", byte_size=4096,
        checksum_sha256=SHA, verified_at=NOW, ready=True, catalogued_at=NOW, version=1,
    )
    return location_id


def _replica(connection, *, tenant_id, ids, location_id, state):
    extra = {}
    if state == "ready":
        extra = {"checksum_sha256": SHA, "verified_at": NOW}
    _insert(
        connection, "data_replicas",
        replica_id=new_id("replica"), tenant_id=tenant_id, location_id=location_id,
        node_id=ids["node"], contribution_id=ids["contribution"], state=state,
        local_bytes=4096, last_used_at=NOW, created_at=NOW, **extra,
    )


@pytest.fixture
def catalogue(owner_engine, two_tenants):
    """Three locations in one tenant: project A's, project B's, and a NULL legacy.

    A's has one ready copy against a factor of two, so it is under-replicated and
    has a source node. The other two are unreplicated -- which is the more urgent
    state, so if scope leaked they would be impossible to miss in the answer.
    """
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        ids = _seed(connection, tenant_id=tenant, now=NOW, label="c266")
        mine = _location(connection, tenant_id=tenant, ids=ids, project_id=ids["a"], suffix="mine")
        theirs = _location(
            connection, tenant_id=tenant, ids=ids, project_id=ids["b"], suffix="theirs"
        )
        legacy = _location(connection, tenant_id=tenant, ids=ids, project_id=None, suffix="legacy")
        _replica(connection, tenant_id=tenant, ids=ids, location_id=mine, state="ready")
    return {"tenant": tenant, "mine": mine, "theirs": theirs, "legacy": legacy, **ids}


def _rows(owner_engine, table, tenant_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(f"SELECT count(*) FROM {table} WHERE tenant_id = :t"), {"t": tenant_id}
        ).scalar_one()


def test_the_plan_names_this_projects_under_replicated_location_and_its_source(
    owner_engine, app_engine, catalogue, clean_tables
):
    client = _client(app_engine, tenant_id=catalogue["tenant"], user_id=catalogue["owner"])
    response = client.get(PATH.format(project=catalogue["a"]), params={"replicaFactor": 2})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["projectId"] == catalogue["a"]
    assert body["replicaFactor"] == 2
    # One location in this project, not the tenant's three.
    assert body["locations"] == 1
    assert (body["healthy"], body["underReplicated"], body["atRisk"], body["unreplicated"]) == (
        0, 1, 0, 0
    )
    assert body["truncated"] is False
    # The thing the catalogue routes could not say.
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["locationId"] == catalogue["mine"]
    assert (item["ready"], item["desired"], item["deficit"]) == (1, 2, 1)
    assert item["classification"] == "under_replicated"
    # A copy exists to read from, and the plan says where.
    assert item["sourceNodes"] == [catalogue["node"]]
    # It plans; it does not repair, and says so in the contract rather than in prose.
    assert body["repairPerformed"] is False


def test_another_projects_and_the_null_legacy_location_are_not_in_the_answer(
    owner_engine, app_engine, catalogue, clean_tables
):
    """Both are unreplicated, so a tenant-only query would surface them first."""
    client = _client(app_engine, tenant_id=catalogue["tenant"], user_id=catalogue["owner"])
    body = client.get(
        PATH.format(project=catalogue["a"]), params={"replicaFactor": 2}
    ).json()
    listed = {item["locationId"] for item in body["items"]}
    assert catalogue["theirs"] not in listed
    assert catalogue["legacy"] not in listed
    assert body["unreplicated"] == 0


def test_the_other_project_sees_its_own_one_and_not_this_ones(
    owner_engine, app_engine, catalogue, clean_tables
):
    client = _client(app_engine, tenant_id=catalogue["tenant"], user_id=catalogue["outsider"])
    response = client.get(PATH.format(project=catalogue["b"]), params={"replicaFactor": 2})
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["locationId"] for item in body["items"]] == [catalogue["theirs"]]
    assert body["items"][0]["classification"] == "unreplicated"
    # Nothing to copy from, so no source is offered rather than a guessed one.
    assert body["items"][0]["sourceNodes"] == []


def test_a_project_the_caller_is_not_in_and_one_that_does_not_exist_answer_alike(
    owner_engine, app_engine, catalogue, clean_tables
):
    """A project id must not become an existence oracle: the refusal for "not a
    member of B" and for a project that was never created is the same."""
    client = _client(app_engine, tenant_id=catalogue["tenant"], user_id=catalogue["owner"])
    refused = client.get(PATH.format(project=catalogue["b"]))
    absent = client.get(PATH.format(project=new_id("project")))
    assert refused.status_code == absent.status_code
    assert refused.json()["code"] == absent.json()["code"]
    assert refused.json()["status"] == absent.json()["status"]


def test_the_read_writes_nothing(owner_engine, app_engine, catalogue, clean_tables):
    before = {
        table: _rows(owner_engine, table, catalogue["tenant"])
        for table in ("data_replicas", "data_locations", "audit_events")
    }
    client = _client(app_engine, tenant_id=catalogue["tenant"], user_id=catalogue["owner"])
    assert client.get(PATH.format(project=catalogue["a"])).status_code == 200
    after = {
        table: _rows(owner_engine, table, catalogue["tenant"])
        for table in ("data_replicas", "data_locations", "audit_events")
    }
    assert before == after


def test_the_page_is_bounded_and_truncation_is_measured(
    owner_engine, app_engine, catalogue, clean_tables
):
    """``truncated`` comes from reading one more than the page, not from guessing."""
    with owner_engine.begin() as connection:
        for index in range(3):
            _location(
                connection, tenant_id=catalogue["tenant"], ids=catalogue,
                project_id=catalogue["a"], suffix=f"extra-{index}",
            )
    client = _client(app_engine, tenant_id=catalogue["tenant"], user_id=catalogue["owner"])
    body = client.get(PATH.format(project=catalogue["a"]), params={"limit": 2}).json()
    assert len(body["items"]) == 2
    assert body["truncated"] is True
    # The summary counts the whole project even when the page is cut.
    assert body["locations"] == 4
    full = client.get(PATH.format(project=catalogue["a"]), params={"limit": 50}).json()
    assert len(full["items"]) == 4
    assert full["truncated"] is False
