"""inv:// parsing and resolution (VF-CL-02, contract-independent part).

Two layers, tested where they live:

* ``parse_uri`` is the strict inverse of ``build_uri`` and needs no database.
  The round-trip property is the contract -- anything ``build_uri`` emits,
  ``parse_uri`` reads back to the same fields -- and malformed input is rejected
  rather than guessed.
* the resolver is a tenant-scoped database lookup. A URI that parses is not one
  that resolves; a catalogued location is not a readable one; and choosing which
  node serves it is the Scheduler's job, not the resolver's, so this only
  reports the set of nodes holding a ready copy.

The model-manifest expansion of a ``kind='model'`` URI is deferred to VF-CX-02
and is not exercised here.
"""

from __future__ import annotations

import datetime as dt

import pytest

from saintvision.storage.pathsafe import build_uri, parse_uri

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 15, 7, 0, 0, tzinfo=UTC)
SHA = "c" * 64


# --------------------------------------------------------------------------
# parse_uri: pure, no database
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "kind,kwargs",
    [
        ("dataset", dict(name="corpus", version="1")),
        ("dataset", dict(name="corpus", version="3", relative_path="a/b.bin")),
        ("model", dict(name="llama", version="2", relative_path="w.safetensors")),
        ("model", dict(name="mixtral", version="0.1")),
        ("artifact", dict(run_id="run_1", artifact_id="art_9")),
        ("workspace", dict(workspace_id="ws_1", relative_path="src/main.py")),
    ],
)
def test_parse_uri_is_the_inverse_of_build_uri(kind, kwargs):
    uri = build_uri(kind, **kwargs)
    parsed = parse_uri(uri)
    assert parsed.kind == kind
    # Rebuilding from the parsed fields reproduces the exact URI.
    rebuilt = build_uri(
        parsed.kind,
        name=parsed.name,
        version=parsed.version,
        relative_path=parsed.relative_path,
        run_id=parsed.run_id,
        artifact_id=parsed.artifact_id,
        workspace_id=parsed.workspace_id,
    )
    assert rebuilt == uri


@pytest.mark.parametrize(
    "bad",
    [
        "https://example/x",              # wrong scheme
        "inv://",                         # no namespace/path
        "inv://datasets",                 # namespace only
        "inv://datasets/corpus",          # missing @version
        "inv://datasets/corpus@",         # empty version
        "inv://datasets/@1",              # empty name
        "inv://widgets/thing@1",          # unknown namespace
        "inv://artifacts/run_1",          # artifact needs two segments
        "inv://artifacts/run_1/a/extra",  # too many segments
        "inv://workspaces/ws_1",          # workspace needs a relative path
        "",                               # empty
    ],
)
def test_parse_uri_rejects_malformed(bad):
    with pytest.raises(ValueError):
        parse_uri(bad)


def test_parse_uri_reads_dataset_fields():
    parsed = parse_uri("inv://datasets/corpus@7/train/data.bin")
    assert (parsed.kind, parsed.name, parsed.version, parsed.relative_path) == (
        "dataset", "corpus", "7", "train/data.bin",
    )


# --------------------------------------------------------------------------
# resolver: tenant-scoped database lookup
# --------------------------------------------------------------------------

pytest_postgres = pytest.mark.postgres


@pytest.fixture
def catalogued(owner_engine, two_tenants):
    """Tenant A: two nodes, an active contribution, one verified dataset location."""
    from saintvision.ids import new_id

    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_id": new_id("user"),
        "nodes": [new_id("node"), new_id("node")],
        "contribution_id": new_id("storage_contribution"),
        "location_id": new_id("data_location"),
        "uri": "inv://datasets/corpus@1/data.bin",
        "bytes": 4096,
    }
    from sqlalchemy import text

    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
                "status, created_at, updated_at, version) "
                "VALUES (:u, :t, 'sub', 'U', 'active', now(), now(), 1)"
            ),
            {"u": ids["user_id"], "t": tenant_a},
        )
        for index, node_id in enumerate(ids["nodes"]):
            c.execute(
                text(
                    "INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, "
                    "agent_version, status, enrolled_at, heartbeat_sequence, version) "
                    "VALUES (:n, :t, :h, 'linux', '22.04', '0.1', 'active', now(), 0, 1)"
                ),
                {"n": node_id, "t": tenant_a, "h": f"res-{index:02d}"},
            )
        c.execute(
            text(
                "INSERT INTO storage_contributions (contribution_id, tenant_id, node_id, "
                "declared_path, normalized_path, mode, status, registered_by_user_id, "
                "registered_at, version) VALUES (:c, :t, :n, '/srv/inv/0', '/srv/inv/0', "
                "'read_write', 'active', :u, now(), 1)"
            ),
            {"c": ids["contribution_id"], "t": tenant_a, "n": ids["nodes"][0], "u": ids["user_id"]},
        )
        c.execute(
            text(
                "INSERT INTO data_locations (location_id, tenant_id, contribution_id, uri, kind, "
                "relative_path, byte_size, checksum_sha256, verified_at, ready, catalogued_at, version) "
                "VALUES (:l, :t, :c, :uri, 'dataset', 'data.bin', :b, :s, now(), true, now(), 1)"
            ),
            {"l": ids["location_id"], "t": tenant_a, "c": ids["contribution_id"],
             "uri": ids["uri"], "b": ids["bytes"], "s": SHA},
        )
    return ids


@pytest_postgres
def test_resolve_location_finds_a_catalogued_uri(app_sessionmaker, catalogued):
    from saintvision.db.session import tenant_scope
    from saintvision.services import resolver

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogued["tenant_a"]):
                location = resolver.resolve_location(
                    session, tenant_id=catalogued["tenant_a"], uri=catalogued["uri"]
                )
                assert location.location_id == catalogued["location_id"]
                assert location.kind == "dataset"


@pytest_postgres
def test_resolve_location_raises_for_an_uncatalogued_uri(app_sessionmaker, catalogued):
    from saintvision.db.session import tenant_scope
    from saintvision.errors import InvError
    from saintvision.services import resolver

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogued["tenant_a"]):
                with pytest.raises(InvError, match="no catalogued location"):
                    resolver.resolve_location(
                        session, tenant_id=catalogued["tenant_a"],
                        uri="inv://datasets/absent@1/x",
                    )


@pytest_postgres
def test_resolve_location_rejects_a_malformed_uri_before_lookup(app_sessionmaker, catalogued):
    from saintvision.db.session import tenant_scope
    from saintvision.services import resolver

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogued["tenant_a"]):
                with pytest.raises(ValueError):
                    resolver.resolve_location(
                        session, tenant_id=catalogued["tenant_a"], uri="inv://datasets/x"
                    )


@pytest_postgres
def test_ready_replica_nodes_lists_only_ready_copies(app_sessionmaker, catalogued):
    from saintvision.db.session import tenant_scope
    from saintvision.services import locality as locality_service
    from saintvision.services import resolver

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogued["tenant_a"]):
                # node 0: a ready replica; node 1: still transferring.
                ready = locality_service.register_replica(
                    session, tenant_id=catalogued["tenant_a"],
                    location_id=catalogued["location_id"], node_id=catalogued["nodes"][0],
                    contribution_id=catalogued["contribution_id"], now=NOW,
                    local_bytes=catalogued["bytes"],
                )
                locality_service.mark_replica_ready(
                    session, tenant_id=catalogued["tenant_a"],
                    replica_id=ready.replica_id, checksum_sha256=SHA, now=NOW,
                )
                locality_service.register_replica(
                    session, tenant_id=catalogued["tenant_a"],
                    location_id=catalogued["location_id"], node_id=catalogued["nodes"][1],
                    contribution_id=catalogued["contribution_id"], now=NOW,
                    local_bytes=catalogued["bytes"] // 2,
                )
                nodes = resolver.ready_replica_nodes(
                    session, tenant_id=catalogued["tenant_a"], uri=catalogued["uri"]
                )
                assert nodes == [catalogued["nodes"][0]]
                assert resolver.is_materialisable(
                    session, tenant_id=catalogued["tenant_a"], uri=catalogued["uri"]
                )


@pytest_postgres
def test_a_catalogued_uri_with_no_ready_replica_is_not_materialisable(app_sessionmaker, catalogued):
    from saintvision.db.session import tenant_scope
    from saintvision.services import resolver

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogued["tenant_a"]):
                assert resolver.ready_replica_nodes(
                    session, tenant_id=catalogued["tenant_a"], uri=catalogued["uri"]
                ) == []
                assert not resolver.is_materialisable(
                    session, tenant_id=catalogued["tenant_a"], uri=catalogued["uri"]
                )


@pytest_postgres
def test_a_public_reader_sees_only_locations_in_their_own_active_contribution(
    app_sessionmaker, catalogued
):
    """Codex's owner-scoping (reviewed): a reader_user_id filters to that user's
    active contributions, so a non-owner cannot resolve someone else's URI even
    within the same tenant. Omitting reader_user_id is the internal path."""
    from saintvision.db.session import tenant_scope
    from saintvision.errors import InvError
    from saintvision.services import resolver

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogued["tenant_a"]):
                # The owner resolves their own contribution's location.
                owned = resolver.resolve_location(
                    session, tenant_id=catalogued["tenant_a"], uri=catalogued["uri"],
                    reader_user_id=catalogued["user_id"],
                )
                assert owned.location_id == catalogued["location_id"]
                # A different reader in the same tenant cannot.
                with pytest.raises(InvError, match="no catalogued location"):
                    resolver.resolve_location(
                        session, tenant_id=catalogued["tenant_a"], uri=catalogued["uri"],
                        reader_user_id="usr_someone_else",
                    )


@pytest_postgres
def test_rls_hides_the_location_even_when_the_where_would_match(app_sessionmaker, catalogued):
    """A genuine RLS test, not a WHERE test.

    The query filters on tenant A's id -- which *does* match the catalogued row --
    but runs under tenant B's scope. If resolution depended only on the WHERE it
    would succeed; RLS must make the row invisible, so it raises not-found.
    """
    from saintvision.db.session import tenant_scope
    from saintvision.errors import InvError
    from saintvision.services import resolver

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogued["tenant_b"]):
                with pytest.raises(InvError, match="no catalogued location"):
                    resolver.resolve_location(
                        session, tenant_id=catalogued["tenant_a"], uri=catalogued["uri"]
                    )
