"""VF-CL-02: ``inv://models/<name>@<version>`` resolution into ModelManifest shards (real PG).

The business role cannot read the kernel's ``inv.model_manifests``; the manifest reaches the
resolver through an injected ``manifest_reader``. These tests use a fake reader that returns a
contract-shaped ``ModelManifest`` so the expansion logic (shard -> replica -> catalogued
DataLocation -> ready node) is exercised against real ``public`` tables under RLS. Without a
reader the resolver must say so honestly (``manifest_source == "unavailable"``), never an empty
shard list.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError, RES_ARTIFACT_NOT_FOUND
from saintvision.ids import new_id
from saintvision.services import lineage as lineage_service
from saintvision.services.resolver import resolve_model
from saintvision.storage.pathsafe import build_uri

pytestmark = pytest.mark.postgres

SHA = "a" * 64
SHA_B = "b" * 64
NOW = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.timezone.utc)


@pytest.fixture
def model_world(owner_engine, two_tenants):
    """Tenant A: project + model 'classifier' + two nodes + active contribution + two
    kind='model' locations (shard 0 ready on node 0; shard 1 catalogued at version 1 only).
    Tenant B: one location the manifest may wrongly point at (must stay invisible)."""
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a, "tenant_b": tenant_b,
        "project_id": new_id("project"), "model_id": new_id("model"),
        "user_id": new_id("user"), "nodes": [new_id("node"), new_id("node")],
        "contribution_id": new_id("storage_contribution"),
        "loc0": new_id("data_location"), "loc1": new_id("data_location"), "loc_b": new_id("data_location"),
        "user_b": new_id("user"), "node_b": new_id("node"), "contribution_b": new_id("storage_contribution"),
    }
    ids["uri"] = build_uri("model", name="classifier", version="3", relative_path="w.safetensors")
    ids["uri0"] = build_uri("model", name="classifier", version="3", relative_path="shard-0.bin")
    ids["uri1"] = build_uri("model", name="classifier", version="3", relative_path="shard-1.bin")
    with owner_engine.begin() as c:
        c.execute(text("INSERT INTO projects (project_id, tenant_id, code, display_name, status, created_at, version) VALUES (:p, :t, 'a', 'A', 'active', now(), 1)"), {"p": ids["project_id"], "t": tenant_a})
        c.execute(text("INSERT INTO models (model_id, tenant_id, project_id, name, created_at) VALUES (:m, :t, :p, 'classifier', now())"), {"m": ids["model_id"], "t": tenant_a, "p": ids["project_id"]})
        for t, u in ((tenant_a, ids["user_id"]), (tenant_b, ids["user_b"])):
            c.execute(text("INSERT INTO users (user_id, tenant_id, external_subject, display_name, status, created_at, updated_at, version) VALUES (:u, :t, :s, 'U', 'active', now(), now(), 1)"), {"u": u, "t": t, "s": "sub-" + u})
        for t, n in ((tenant_a, ids["nodes"][0]), (tenant_a, ids["nodes"][1]), (tenant_b, ids["node_b"])):
            c.execute(text("INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, agent_version, status, enrolled_at, heartbeat_sequence, version) VALUES (:n, :t, :h, 'linux', '22.04', '0.1', 'active', now(), 0, 1)"), {"n": n, "t": t, "h": "h-" + n[-4:]})
        for t, cid, n, u in ((tenant_a, ids["contribution_id"], ids["nodes"][0], ids["user_id"]), (tenant_b, ids["contribution_b"], ids["node_b"], ids["user_b"])):
            c.execute(text("INSERT INTO storage_contributions (contribution_id, tenant_id, node_id, declared_path, normalized_path, mode, status, registered_by_user_id, registered_at, version) VALUES (:c, :t, :n, '/srv/inv/0', '/srv/inv/0', 'read_write', 'active', :u, now(), 1)"), {"c": cid, "t": t, "n": n, "u": u})
        for t, cid, lid, uri, ver in ((tenant_a, ids["contribution_id"], ids["loc0"], ids["uri0"], 1), (tenant_a, ids["contribution_id"], ids["loc1"], ids["uri1"], 1), (tenant_b, ids["contribution_b"], ids["loc_b"], ids["uri0"], 1)):
            c.execute(text("INSERT INTO data_locations (location_id, tenant_id, contribution_id, uri, kind, relative_path, byte_size, checksum_sha256, verified_at, ready, catalogued_at, version) VALUES (:l, :t, :c, :uri, 'model', 'x', 10, :s, now(), true, now(), :v)"), {"l": lid, "t": t, "c": cid, "uri": uri, "s": SHA, "v": ver})
        for lid, n, state in ((ids["loc0"], ids["nodes"][0], "ready"), (ids["loc1"], ids["nodes"][1], "stale")):
            c.execute(text("INSERT INTO data_replicas (replica_id, tenant_id, location_id, node_id, contribution_id, state, local_bytes, checksum_sha256, verified_at, last_used_at, created_at) VALUES (:r, :t, :l, :n, :c, :s, 10, :sha, now(), now(), now())"), {"r": new_id("replica"), "t": tenant_a, "l": lid, "n": n, "c": ids["contribution_id"], "s": state, "sha": SHA})
    return ids


def _register(session, ids, version="3"):
    return lineage_service.register_model_version(
        session, tenant_id=ids["tenant_a"], model_id=ids["model_id"], version=version,
        content_sha256=SHA_B, uri=ids["uri"], now=NOW,
    )


def _manifest(ids, *, replicas):
    return {
        "modelId": ids["model_id"], "version": "3", "format": "safetensors", "totalBytes": 20,
        "contentHash": SHA_B,
        "shards": [
            {"index": 0, "offset": 0, "byteLength": 10, "sha256": SHA},
            {"index": 1, "offset": 10, "byteLength": 10, "sha256": SHA},
        ],
        "replicas": replicas,
        "runtimeCompatibility": [], "licensePolicy": "internal", "classification": "internal",
        "encryption": "none", "keyRef": None,
    }


def test_a_dataset_uri_is_refused_before_any_lookup(app_sessionmaker, model_world):
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, model_world["tenant_a"]):
        with pytest.raises(ValueError):
            resolve_model(session, tenant_id=model_world["tenant_a"], uri="inv://datasets/corpus@1/data.bin")


def test_an_unregistered_model_version_is_not_found(app_sessionmaker, model_world):
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, model_world["tenant_a"]):
        with pytest.raises(InvError) as err:
            resolve_model(session, tenant_id=model_world["tenant_a"], uri=model_world["uri"])
        assert err.value.code == RES_ARTIFACT_NOT_FOUND


def test_without_a_manifest_reader_shards_are_unavailable_not_empty(app_sessionmaker, model_world):
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, model_world["tenant_a"]):
        _register(session, model_world)
        r = resolve_model(session, tenant_id=model_world["tenant_a"], uri=model_world["uri"])
        assert r.model_version.version == "3" and r.parsed.name == "classifier"
        assert r.shards is None and r.manifest_source == "unavailable"
        assert "not readable" in r.reason and r.fully_materialisable is False


def test_shards_expand_through_catalogued_locations_and_ready_replicas(app_sessionmaker, model_world):
    ids = model_world
    replicas = [
        {"shardIndex": 0, "locationId": ids["loc0"], "locationVersion": 1, "nodeId": ids["nodes"][0], "state": "verified"},
        {"shardIndex": 1, "locationId": ids["loc1"], "locationVersion": 2, "nodeId": ids["nodes"][1], "state": "verified"},
    ]
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, ids["tenant_a"]):
        _register(session, ids)
        r = resolve_model(session, tenant_id=ids["tenant_a"], uri=ids["uri"], manifest_reader=lambda *_: _manifest(ids, replicas=replicas))
        assert r.manifest_source == "reader" and len(r.shards) == 2
        s0, s1 = r.shards
        assert s0.materialisable is True and s0.replicas[0].reason == "ok"
        assert s0.replicas[0].location.location_id == ids["loc0"]
        assert s1.materialisable is False and s1.replicas[0].reason == "location-version-drift"
        assert r.fully_materialisable is False


def test_manifest_states_and_replica_readiness_are_reported_not_masked(app_sessionmaker, model_world):
    ids = model_world
    replicas = [
        {"shardIndex": 0, "locationId": ids["loc0"], "locationVersion": 1, "nodeId": ids["nodes"][0], "state": "unavailable"},
        {"shardIndex": 1, "locationId": ids["loc1"], "locationVersion": 1, "nodeId": ids["nodes"][1], "state": "verified"},
    ]
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, ids["tenant_a"]):
        _register(session, ids)
        r = resolve_model(session, tenant_id=ids["tenant_a"], uri=ids["uri"], manifest_reader=lambda *_: _manifest(ids, replicas=replicas))
        assert r.shards[0].replicas[0].reason == "manifest-unavailable" and r.shards[0].materialisable is False
        assert r.shards[1].replicas[0].reason == "replica-not-ready" and r.shards[1].materialisable is False


def test_a_shard_with_no_replica_is_unrecorded_and_a_foreign_location_is_missing(app_sessionmaker, model_world):
    ids = model_world
    replicas = [{"shardIndex": 0, "locationId": ids["loc_b"], "locationVersion": 1, "nodeId": ids["node_b"], "state": "verified"}]
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, ids["tenant_a"]):
        _register(session, ids)
        r = resolve_model(session, tenant_id=ids["tenant_a"], uri=ids["uri"], manifest_reader=lambda *_: _manifest(ids, replicas=replicas))
        assert r.shards[0].replicas[0].reason == "location-missing" and r.shards[0].replicas[0].location is None
        assert r.shards[1].replicas == [] and r.shards[1].reason == "unrecorded"
        assert r.fully_materialisable is False


def test_a_reader_result_outside_the_contract_shape_is_refused(app_sessionmaker, model_world):
    ids = model_world
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, ids["tenant_a"]):
        _register(session, ids)
        with pytest.raises(ValueError):
            resolve_model(session, tenant_id=ids["tenant_a"], uri=ids["uri"], manifest_reader=lambda *_: {"shards": []})
