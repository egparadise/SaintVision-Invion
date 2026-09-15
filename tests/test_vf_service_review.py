"""Independent regression probes for Claude 7ef9a3c on kernel 0042."""
import datetime as dt

import pytest
from sqlalchemy import text

from saintvision.db.session import tenant_scope
from saintvision.services import replica_repair, locality, resolver
from saintvision.storage.pathsafe import build_uri, parse_uri
from test_replica_repair import location, _add_replica, NOW


@pytest.mark.postgres
def test_departure_preserves_retention_and_marks_pinned_replica_stale(
    owner_engine, app_sessionmaker, location
):
    _add_replica(owner_engine, location, 0, "ready")
    until = NOW + dt.timedelta(hours=1)
    with owner_engine.begin() as conn:
        conn.execute(text("UPDATE data_replicas SET pinned_until=:until WHERE location_id=:id"),
                     {"until": until, "id": location["location_id"]})
    with app_sessionmaker() as session, session.begin():
        with tenant_scope(session, location["tenant_a"]):
            assert replica_repair.mark_node_replicas_unavailable(
                session, tenant_id=location["tenant_a"], node_id=location["nodes"][0], now=NOW
            ) == 1
            row = session.execute(text("SELECT state,pinned_until FROM data_replicas WHERE location_id=:id"),
                                  {"id": location["location_id"]}).one()
            assert row.state == "stale"
            assert row.pinned_until == until
            assert locality.cache_usage(
                session, tenant_id=location["tenant_a"],
                contribution_id=location["contribution_id"]
            )["cacheUsedBytes"] == location["bytes"]
            assert replica_repair.mark_node_replicas_unavailable(
                session, tenant_id=location["tenant_a"], node_id=location["nodes"][0], now=NOW
            ) == 0
            health = replica_repair.replica_health(
                session, tenant_id=location["tenant_a"], location_id=location["location_id"]
            )
            assert health.classification == "at_risk"
            assert health.source_nodes == []
            assert not resolver.is_materialisable(
                session, tenant_id=location["tenant_a"], uri="inv://datasets/corpus@1/data.bin"
            )
            assert locality.eviction_candidates(
                session, tenant_id=location["tenant_a"],
                contribution_id=location["contribution_id"], now=NOW, bytes_needed=4096
            ) == []


@pytest.mark.parametrize("uri", ["inv://models/model@v1/", "inv://datasets/data@v1/"])
def test_parser_never_accepts_a_non_roundtripping_uri(uri):
    try:
        parsed = parse_uri(uri)
    except ValueError:
        return
    assert build_uri(**vars(parsed)) == uri


def test_builder_rejects_ambiguous_version_path():
    with pytest.raises(ValueError):
        build_uri("model", name="model", version="v1/shard")


@pytest.mark.parametrize("kind,fields", [
    ("artifact", {"run_id": "run/extra", "artifact_id": "art"}),
    ("artifact", {"run_id": "run", "artifact_id": "art/extra"}),
    ("workspace", {"workspace_id": "ws/extra", "relative_path": "file"}),
])
def test_builder_rejects_ambiguous_identifier(kind, fields):
    with pytest.raises(ValueError):
        build_uri(kind, **fields)
