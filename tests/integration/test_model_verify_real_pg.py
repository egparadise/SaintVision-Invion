"""W3 against a real PostgreSQL: the seam end to end, with the kernel observation injected.

The kernel measurement is recorded as the owner (``measurement_support``, the
kernel's accept path stood in for) and the observation the route fetches is
injected, as the release route's tests inject the commitment: the subject
here is the database boundary and the route's decisions against it, not a
second HTTP server. What only the database can say is here: both columns
land in one transaction with one audit row and one ledger row; a replay is
exact and a second key is a visible no-op; a forged, foreign, other-version,
other-digest, stale or second measurement binds nothing; the storage
snapshot drift the catalogue shows is refused; the member without the
approval grade and the anonymous caller are refused with one denial row
each; the version row's lock is the shared one (a pin holder is waited for,
a held row past the budget is ``SYS-0001/503`` with nothing written).
"""

from __future__ import annotations

import datetime as dt
import threading
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from lock_wait_harness import within_deadline
from measurement_support import insert_measurement
from saintvision.api.app import create_app
from saintvision.api.deps import get_principal
from saintvision.api.v1 import model_verify
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id
from test_model_retention_pin_real_pg import _hold_row, _wait_until_blocked
from test_model_version_register_real_pg import _canonical, _digest, _insert, _ledger, _seed

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 28, 9, 0, tzinfo=UTC)
TOKEN = "verify-real-token"
BUDGET_MS = 300
DEADLINE_SECONDS = 20


def _storage(connection, *, tenant_id, user_id, uri, digest, now, byte_size):
    """One active node, one active contribution, one ready model location, one ready replica."""
    node_id, contribution_id, location_id, replica_id = new_id("node"), new_id("storage_contribution"), new_id("data_location"), new_id("replica")
    _insert(
        connection, "nodes",
        node_id=node_id, tenant_id=tenant_id, hostname=f"node-{node_id[-6:]}", os_type="linux", os_version="6.1",
        agent_version="1.0.0", status="active", enrolled_at=now, heartbeat_sequence=0, version=1,
    )
    _insert(
        connection, "storage_contributions",
        contribution_id=contribution_id, tenant_id=tenant_id, node_id=node_id, declared_path="/srv/models",
        normalized_path="/srv/models", mode="read_only", status="active", registered_by_user_id=user_id,
        registered_at=now, version=1,
    )
    _insert(
        connection, "data_locations",
        location_id=location_id, tenant_id=tenant_id, contribution_id=contribution_id, uri=uri, kind="model",
        relative_path="weights.safetensors", byte_size=byte_size, checksum_sha256=digest, verified_at=now, ready=True,
        catalogued_at=now, version=1,
    )
    _insert(
        connection, "data_replicas",
        replica_id=replica_id, tenant_id=tenant_id, location_id=location_id, node_id=node_id,
        contribution_id=contribution_id, state="ready", local_bytes=byte_size, checksum_sha256=digest, verified_at=now,
        last_used_at=now, created_at=now,
    )
    return {"node_id": node_id, "contribution_id": contribution_id, "location_id": location_id}


def _prepare(connection, *, tenant_id, now, label, role="approver", byte_size=4096, measured_sha256=None, measured_size=None):
    """A project with a member of ``role``, a draft version of a model, the
    storage it names, and one kernel-recorded measurement of it (the kernel's
    accept path stood in for as the owner). Returns everything the route and
    the observation need."""
    seeded = _seed(connection, tenant_id=tenant_id, now=now, label=label, role=role)
    digest = _digest()
    uri = f"inv://models/model-{label}@1.0.0"
    version_id = new_id("model_version")
    _insert(
        connection, "model_versions",
        model_version_id=version_id, tenant_id=tenant_id, model_id=seeded["model_id"], version="1.0.0", stage="draft",
        content_sha256=digest, byte_size=byte_size, uri=uri, created_at=now,
    )
    storage = _storage(connection, tenant_id=tenant_id, user_id=seeded["user_id"], uri=uri, digest=digest, now=now, byte_size=byte_size)
    observed_at = now - dt.timedelta(minutes=5)
    measurement_id = insert_measurement(
        connection, tenant_id=tenant_id, model_version_id=version_id, sha256=measured_sha256 or digest,
        byte_size=byte_size if measured_size is None else measured_size, project_id=seeded["project_id"], uri=uri,
        observed_at=observed_at, location_id=storage["location_id"], contribution_id=storage["contribution_id"],
        node_id=storage["node_id"],
    )
    return {
        **seeded, **storage, "tenant_id": tenant_id, "version_id": version_id, "digest": digest, "uri": uri,
        "measurement_id": measurement_id, "observed_at": observed_at, "byte_size": byte_size,
    }


def _observation(p, **overrides):
    body = {
        "measurementId": p["measurement_id"],
        "tenantId": str(p["tenant_id"]),
        "projectId": p["project_id"],
        "modelId": p["model_id"],
        "modelVersionId": p["version_id"],
        "uri": p["uri"],
        "contributionId": p["contribution_id"],
        "contributionVersion": 1,
        "locationId": p["location_id"],
        "locationVersion": 1,
        "relativePath": "weights.safetensors",
        "nodeId": p["node_id"],
        "recoveryEpoch": str(uuid.uuid4()),
        "channelVersion": 1,
        "certificateSha256": "c" * 64,
        "sha256": p.get("observed_sha256", p["digest"]),
        "byteSize": p["byte_size"],
        "observedAt": p["observed_at"].isoformat(),
        "recordedAt": (p["observed_at"] + dt.timedelta(seconds=1)).isoformat(),
    }
    body.update(overrides)
    return {k: v for k, v in body.items() if v is not ...}


def _client(app_engine, *, tenant_id, user_id, observation, now=NOW, lock_timeout_ms=5_000, authenticate=True):
    principal = Principal(user_id=user_id, tenant_id=tenant_id, external_subject="oidc:verify-real")
    app = create_app(
        engine=app_engine,
        settings=Settings(
            database_url="test-only", idempotency_ttl_seconds=600, business_lock_timeout_ms=lock_timeout_ms,
            kernel_base_url="http://kernel.invalid",
        ),
        verifier=StaticPrincipalVerifier({TOKEN: principal} if authenticate else {}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    app.state.model_measurement_fetcher = lambda **_kwargs: observation
    return TestClient(app, raise_server_exceptions=False)


def _path(p):
    return f"/v1/projects/{p['project_id']}/models/{p['model_id']}/versions/1.0.0/verify"


def _headers(key, *, token=TOKEN):
    headers = {"Idempotency-Key": key, "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _post(client, p, key="k-verify", body=None, **kw):
    return client.post(_path(p), json=body or {"measurementId": p["measurement_id"]}, headers=_headers(key, **kw))


def _row(owner_engine, version_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text("SELECT verified_at, verified_measurement_id FROM model_versions WHERE model_version_id = :v"),
            {"v": version_id},
        ).one()


def _audits(owner_engine, *, action, outcome="allow"):
    with owner_engine.begin() as connection:
        return connection.execute(
            text("SELECT detail FROM audit_events WHERE action = :a AND outcome = :o"), {"a": action, "o": outcome}
        ).mappings().all()


def _denials(owner_engine):
    with owner_engine.begin() as connection:
        return connection.execute(
            text("SELECT action, tenant_id FROM audit_events WHERE outcome = 'deny' AND action LIKE '%verify%'")
        ).fetchall()


# ---------------------------------------------------------------- the write


def test_an_approver_verifies_once_with_one_audit_row_and_one_ledger_row(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-ok")
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(p))
    response = _post(client, p)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["modelVersionId"] == p["version_id"] and body["verifiedMeasurementId"] == p["measurement_id"]
    assert body["newlyVerified"] is True and body["contentSha256"] == p["digest"] and body["stage"] == "draft"
    assert _row(owner_engine, p["version_id"]) == (NOW, p["measurement_id"])
    audits = _audits(owner_engine, action="model_version.verify")
    assert len(audits) == 1 and audits[0]["detail"]["measurementId"] == p["measurement_id"]
    assert set(audits[0]["detail"]) == {"projectId", "modelId", "version", "measurementId", "newlyVerified"}
    ledger = _ledger(owner_engine, tenant)
    assert [(r["endpoint"], r["idempotency_key"], r["response_status"]) for r in ledger] == [(model_verify.ENDPOINT, "k-verify", 200)]


def test_a_replay_is_exact_and_a_second_key_is_a_visible_no_op(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-replay")
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(p))
    first = _post(client, p).json()
    assert _post(client, p).json() == first                                    # exact replay
    again = _post(client, p, key="k-verify-2")
    assert again.status_code == 200 and again.json()["newlyVerified"] is False
    assert len(_ledger(owner_engine, tenant)) == 2 and len(_audits(owner_engine, action="model_version.verify")) == 2
    assert _row(owner_engine, p["version_id"]) == (NOW, p["measurement_id"])


def test_the_same_key_with_another_measurement_is_409(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-key")
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(p))
    assert _post(client, p).status_code == 200
    body = _canonical(_post(client, p, body={"measurementId": new_id("model_measurement")}), code="GRAPH-0002", status=409)
    assert p["measurement_id"] not in body["detail"]


# ---------------------------------------------------------------- what binds nothing


def test_a_forged_measurement_the_kernel_never_recorded_is_404_and_binds_nothing(owner_engine, app_engine, two_tenants, clean_tables):
    """The observation says a measurement exists; the kernel table has no such
    row. The service's read through the reader finds nothing."""
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-forged")
    forged = {**p, "measurement_id": new_id("model_measurement")}
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(forged))
    body = _canonical(_post(client, forged), code="RES-0004", status=404)
    assert forged["measurement_id"] not in body["detail"]
    assert _row(owner_engine, p["version_id"]) == (None, None)
    assert _ledger(owner_engine, tenant) == [] and _audits(owner_engine, action="model_version.verify") == []


def test_another_tenants_measurement_is_404_through_both_the_identity_and_the_reader(owner_engine, app_engine, two_tenants, clean_tables):
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        mine = _prepare(connection, tenant_id=tenant_a, now=NOW, label="w3-mine")
        theirs = _prepare(connection, tenant_id=tenant_b, now=NOW, label="w3-theirs")
    # The kernel would not serve it; even an observation that names my path with their measurement id is refused.
    observation = _observation(mine, measurementId=theirs["measurement_id"])
    client = _client(app_engine, tenant_id=tenant_a, user_id=mine["user_id"], observation=observation)
    _canonical(_post(client, mine, body={"measurementId": theirs["measurement_id"]}), code="RES-0004", status=404)
    assert _row(owner_engine, mine["version_id"]) == (None, None)


def test_a_measurement_of_another_version_is_404_and_binds_nothing(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-other")
        other_id = new_id("model_version")
        _insert(
            connection, "model_versions",
            model_version_id=other_id, tenant_id=tenant, model_id=p["model_id"], version="2.0.0", stage="draft",
            content_sha256=_digest(), byte_size=1, uri=f"inv://models/model-w3-other@2.0.0", created_at=NOW,
        )
    observation = _observation(p, modelVersionId=other_id)
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=observation)
    _canonical(_post(client, p), code="RES-0004", status=404)
    assert _row(owner_engine, p["version_id"]) == (None, None) and _row(owner_engine, other_id) == (None, None)


def test_a_measurement_whose_digest_differs_from_the_registration_is_409_with_no_value(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    other = _digest()
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-digest", measured_sha256=other)
    observation = _observation({**p, "observed_sha256": other})
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=observation)
    body = _canonical(_post(client, p), code="GRAPH-0002", status=409)
    assert other not in body["detail"] and p["digest"] not in body["detail"]
    assert _row(owner_engine, p["version_id"]) == (None, None)


def test_a_measurement_whose_size_differs_is_409(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-size", measured_size=4095)
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(p, byteSize=4095))
    _canonical(_post(client, p), code="GRAPH-0002", status=409)
    assert _row(owner_engine, p["version_id"]) == (None, None)


def test_a_stale_measurement_is_409(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-stale")
    old = NOW - dt.timedelta(days=2)
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(p, observedAt=old.isoformat(), recordedAt=(old + dt.timedelta(seconds=1)).isoformat()))
    body = _canonical(_post(client, p), code="GRAPH-0002", status=409)
    assert body["detail"] == model_verify.STALE_DETAIL
    assert _row(owner_engine, p["version_id"]) == (None, None)


def test_a_second_measurement_after_the_first_is_409_and_the_first_stays(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-second")
        second = insert_measurement(
            connection, tenant_id=tenant, model_version_id=p["version_id"], sha256=p["digest"], byte_size=p["byte_size"],
            project_id=p["project_id"], uri=p["uri"], observed_at=p["observed_at"], location_id=p["location_id"],
            contribution_id=p["contribution_id"], node_id=p["node_id"],
        )
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(p))
    assert _post(client, p).status_code == 200
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation({**p, "measurement_id": second}))
    _canonical(_post(client, {**p, "measurement_id": second}, key="k-second"), code="GRAPH-0002", status=409)
    assert _row(owner_engine, p["version_id"]) == (NOW, p["measurement_id"])


@pytest.mark.parametrize(
    "drift",
    ["location-version", "contribution-revoked", "replica-stale", "location-not-ready"],
)
def test_a_storage_snapshot_that_drifted_since_the_measurement_is_409(owner_engine, app_engine, two_tenants, clean_tables, drift):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label=f"w3-{drift}")
        if drift == "location-version":
            connection.execute(text("UPDATE data_locations SET version = 2 WHERE location_id = :l"), {"l": p["location_id"]})
        elif drift == "contribution-revoked":
            connection.execute(text("UPDATE storage_contributions SET status = 'revoked', revoked_at = :n WHERE contribution_id = :c"), {"c": p["contribution_id"], "n": NOW})
        elif drift == "replica-stale":
            connection.execute(text("UPDATE data_replicas SET state = 'stale' WHERE location_id = :l"), {"l": p["location_id"]})
        else:
            connection.execute(text("UPDATE data_locations SET ready = false WHERE location_id = :l"), {"l": p["location_id"]})
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(p))
    body = _canonical(_post(client, p), code="GRAPH-0002", status=409)
    assert body["detail"] == model_verify.SNAPSHOT_DETAIL
    assert _row(owner_engine, p["version_id"]) == (None, None)


def test_an_observation_without_a_worker_identity_is_503_and_binds_nothing(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-noworker")
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(p, nodeId=..., certificateSha256=...))
    body = _canonical(_post(client, p), code="SYS-0001", status=503)
    assert body["retryable"] is True
    assert _row(owner_engine, p["version_id"]) == (None, None) and _ledger(owner_engine, tenant) == []


def test_a_digest_in_the_body_is_422_and_nothing_is_read_or_written(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-body")
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(p))
    _canonical(_post(client, p, body={"measurementId": p["measurement_id"], "sha256": p["digest"]}), code="VAL-0003", status=422)
    assert _row(owner_engine, p["version_id"]) == (None, None) and _ledger(owner_engine, tenant) == []


# ---------------------------------------------------------------- permission and denials


def test_a_member_without_the_approval_grade_is_403_with_one_denial_row(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-operator", role="operator")
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(p))
    _canonical(_post(client, p), code="AUTH-0030", status=403)
    denials = _denials(owner_engine)
    assert len(denials) == 1 and denials[0][1] == tenant
    assert _row(owner_engine, p["version_id"]) == (None, None) and _ledger(owner_engine, tenant) == []


def test_a_request_without_a_credential_is_401_with_one_denial_row(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-anon")
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(p))
    response = _post(client, p, token=None)
    assert response.status_code == 401, response.text
    denials = _denials(owner_engine)
    assert len(denials) == 1 and denials[0][1] is None
    assert _row(owner_engine, p["version_id"]) == (None, None)


# ---------------------------------------------------------------- the shared lock


def test_a_verification_waits_for_a_pin_holder_and_then_binds_the_committed_row(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-wait")
    holder, tx = _hold_row(owner_engine, p["version_id"])
    client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(p))
    result: dict = {}

    def request():
        result["response"] = _post(client, p)

    thread = threading.Thread(target=request)
    thread.start()
    try:
        _wait_until_blocked(owner_engine)
        holder.execute(
            text("UPDATE model_versions SET retention_pinned_until = :u WHERE model_version_id = :v"),
            {"u": NOW + dt.timedelta(days=30), "v": p["version_id"]},
        )
        tx.commit()
    finally:
        holder.close()
        thread.join(timeout=DEADLINE_SECONDS)
    assert result["response"].status_code == 200, result["response"].text
    assert _row(owner_engine, p["version_id"]) == (NOW, p["measurement_id"])
    with owner_engine.begin() as connection:
        pinned = connection.execute(text("SELECT retention_pinned_until FROM model_versions WHERE model_version_id = :v"), {"v": p["version_id"]}).scalar_one()
    assert pinned == NOW + dt.timedelta(days=30)                              # the holder's write survived the verify


def test_a_wait_past_the_budget_is_a_retryable_503_with_nothing_written(owner_engine, app_engine, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        p = _prepare(connection, tenant_id=tenant, now=NOW, label="w3-budget")
    holder, tx = _hold_row(owner_engine, p["version_id"])
    try:
        client = _client(app_engine, tenant_id=tenant, user_id=p["user_id"], observation=_observation(p), lock_timeout_ms=BUDGET_MS)
        response, elapsed = within_deadline(lambda: _post(client, p), seconds=DEADLINE_SECONDS)
    finally:
        tx.rollback()
        holder.close()
    body = _canonical(response, code="SYS-0001", status=503)
    assert body["retryable"] is True and elapsed < DEADLINE_SECONDS
    for forbidden in ("55P03", "FOR UPDATE", p["version_id"]):
        assert forbidden not in body["detail"]
    assert _row(owner_engine, p["version_id"]) == (None, None)
    assert _ledger(owner_engine, tenant) == [] and _audits(owner_engine, action="model_version.verify") == []
