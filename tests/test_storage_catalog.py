"""Storage catalogue service and DataLocation reuse (VF-CL-01).

The catalogue (StorageContribution, DataLocation) and its service and API already
exist as the S02-ST substrate; this suite is the API/DB integration evidence that
VF-CL-01 requires, and it exists so the reinforcement track builds *on* that
substrate instead of re-implementing it. Every assertion is a place where an
optimistic default would let an unusable or mis-addressed item look catalogued:

* a location is not ``ready`` until a checksum over the real bytes is recorded
  (ADR-011), and the database refuses ``ready`` without it -- proven here by
  forcing the row and catching the constraint, so the check is shown able to fail;
* a re-verification whose bytes now hash differently is a substitution and is
  refused, not overwritten;
* a retention pin only ever extends;
* the ``inv://`` grammar is per-kind (ADR-010), not one shape for all;
* a non-owner login scoped to one tenant cannot see another tenant's locations.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import storage as storage_service
from saintvision.services.storage import ContributionInput

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 15, 7, 0, 0, tzinfo=UTC)
SHA_A = "a" * 64
SHA_B = "b" * 64


@pytest.fixture
def seeded(owner_engine, two_tenants):
    """One node and one user under tenant A, seeded as the owner (outside RLS)."""
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_id": new_id("user"),
        "node_id": new_id("node"),
    }
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
                "status, created_at, updated_at, version) "
                "VALUES (:u, :t, 'sub', 'U', 'active', now(), now(), 1)"
            ),
            {"u": ids["user_id"], "t": tenant_a},
        )
        c.execute(
            text(
                "INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, "
                "agent_version, status, enrolled_at, heartbeat_sequence, version) "
                "VALUES (:n, :t, 'store-00', 'linux', '22.04', '0.1', 'active', now(), 0, 1)"
            ),
            {"n": ids["node_id"], "t": tenant_a},
        )
    return ids


def _active_contribution(session, seeded):
    contribution = storage_service.register_contribution(
        session,
        tenant_id=seeded["tenant_a"],
        registered_by_user_id=seeded["user_id"],
        payload=ContributionInput(
            node_id=seeded["node_id"], declared_path="/srv/inv/0", mode="read_write"
        ),
        now=NOW,
    )
    storage_service.activate_contribution(
        session, tenant_id=seeded["tenant_a"], contribution_id=contribution.contribution_id
    )
    return contribution


def test_contribution_lifecycle_is_pending_then_active_then_revoked(app_sessionmaker, seeded):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seeded["tenant_a"]):
                contribution = storage_service.register_contribution(
                    session,
                    tenant_id=seeded["tenant_a"],
                    registered_by_user_id=seeded["user_id"],
                    payload=ContributionInput(
                        node_id=seeded["node_id"], declared_path="/srv/inv/0"
                    ),
                    now=NOW,
                )
                assert contribution.status == "pending"
                cid = contribution.contribution_id
                storage_service.activate_contribution(
                    session, tenant_id=seeded["tenant_a"], contribution_id=cid
                )
                assert contribution.status == "active"
                storage_service.revoke_contribution(
                    session, tenant_id=seeded["tenant_a"], contribution_id=cid, now=NOW
                )
                assert contribution.status == "revoked"
                assert contribution.revoked_at is not None


def test_cataloguing_requires_an_active_contribution(app_sessionmaker, seeded):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seeded["tenant_a"]):
                pending = storage_service.register_contribution(
                    session,
                    tenant_id=seeded["tenant_a"],
                    registered_by_user_id=seeded["user_id"],
                    payload=ContributionInput(
                        node_id=seeded["node_id"], declared_path="/srv/inv/0"
                    ),
                    now=NOW,
                )
                with pytest.raises(InvError, match="not active"):
                    storage_service.catalogue_location(
                        session,
                        tenant_id=seeded["tenant_a"],
                        contribution_id=pending.contribution_id,
                        kind="dataset",
                        relative_path="data.bin",
                        byte_size=10,
                        name="corpus",
                        version="1",
                        now=NOW,
                    )


def test_a_catalogued_location_is_not_ready_until_verified(app_sessionmaker, seeded):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seeded["tenant_a"]):
                contribution = _active_contribution(session, seeded)
                location = storage_service.catalogue_location(
                    session,
                    tenant_id=seeded["tenant_a"],
                    contribution_id=contribution.contribution_id,
                    kind="dataset",
                    relative_path="data.bin",
                    byte_size=10,
                    name="corpus",
                    version="1",
                    now=NOW,
                )
                assert location.ready is False
                assert location.checksum_sha256 is None
                assert location.uri == "inv://datasets/corpus@1/data.bin"


@pytest.mark.parametrize(
    "kind,kwargs,expected",
    [
        ("dataset", dict(name="corpus", version="3", relative_path="a.bin"),
         "inv://datasets/corpus@3/a.bin"),
        ("model", dict(name="llama", version="2", relative_path="w.safetensors"),
         "inv://models/llama@2/w.safetensors"),
        ("workspace", dict(workspace_id="ws_1", relative_path="src/main.py"),
         "inv://workspaces/ws_1/src/main.py"),
    ],
)
def test_inv_uri_grammar_is_per_kind(app_sessionmaker, seeded, kind, kwargs, expected):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seeded["tenant_a"]):
                contribution = _active_contribution(session, seeded)
                location = storage_service.catalogue_location(
                    session,
                    tenant_id=seeded["tenant_a"],
                    contribution_id=contribution.contribution_id,
                    kind=kind,
                    byte_size=1,
                    now=NOW,
                    **kwargs,
                )
                assert location.uri == expected
                assert location.kind == kind


def test_a_model_uri_without_a_version_is_rejected(app_sessionmaker, seeded):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seeded["tenant_a"]):
                contribution = _active_contribution(session, seeded)
                with pytest.raises(InvError, match="version"):
                    storage_service.catalogue_location(
                        session,
                        tenant_id=seeded["tenant_a"],
                        contribution_id=contribution.contribution_id,
                        kind="model",
                        relative_path="w.bin",
                        byte_size=1,
                        name="llama",
                        version="",
                        now=NOW,
                    )


def test_mark_verified_sets_ready_with_a_valid_sha256(app_sessionmaker, seeded):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seeded["tenant_a"]):
                contribution = _active_contribution(session, seeded)
                location = storage_service.catalogue_location(
                    session,
                    tenant_id=seeded["tenant_a"],
                    contribution_id=contribution.contribution_id,
                    kind="dataset",
                    relative_path="data.bin",
                    byte_size=10,
                    name="corpus",
                    version="1",
                    now=NOW,
                )
                verified = storage_service.mark_verified(
                    session,
                    tenant_id=seeded["tenant_a"],
                    location_id=location.location_id,
                    checksum_sha256=SHA_A,
                    byte_size=10,
                    now=NOW,
                )
                assert verified.ready is True
                assert verified.checksum_sha256 == SHA_A
                assert verified.verified_at is not None


def test_mark_verified_rejects_a_non_hex_checksum(app_sessionmaker, seeded):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seeded["tenant_a"]):
                contribution = _active_contribution(session, seeded)
                location = storage_service.catalogue_location(
                    session,
                    tenant_id=seeded["tenant_a"],
                    contribution_id=contribution.contribution_id,
                    kind="dataset",
                    relative_path="data.bin",
                    byte_size=10,
                    name="corpus",
                    version="1",
                    now=NOW,
                )
                with pytest.raises(InvError, match="SHA-256"):
                    storage_service.mark_verified(
                        session,
                        tenant_id=seeded["tenant_a"],
                        location_id=location.location_id,
                        checksum_sha256="NOTAHEX",
                        byte_size=10,
                        now=NOW,
                    )


def test_reverification_with_a_conflicting_checksum_is_refused(app_sessionmaker, seeded):
    """A verified item whose bytes now hash differently is a substitution."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seeded["tenant_a"]):
                contribution = _active_contribution(session, seeded)
                location = storage_service.catalogue_location(
                    session,
                    tenant_id=seeded["tenant_a"],
                    contribution_id=contribution.contribution_id,
                    kind="dataset",
                    relative_path="data.bin",
                    byte_size=10,
                    name="corpus",
                    version="1",
                    now=NOW,
                )
                storage_service.mark_verified(
                    session,
                    tenant_id=seeded["tenant_a"],
                    location_id=location.location_id,
                    checksum_sha256=SHA_A,
                    byte_size=10,
                    now=NOW,
                )
                with pytest.raises(InvError, match="conflicts"):
                    storage_service.mark_verified(
                        session,
                        tenant_id=seeded["tenant_a"],
                        location_id=location.location_id,
                        checksum_sha256=SHA_B,
                        byte_size=10,
                        now=NOW,
                    )


def test_the_database_refuses_ready_without_a_verified_checksum(owner_engine, seeded):
    """The ADR-011 rule is a CHECK constraint, not only service logic.

    Forcing the row as the owner (outside the service) must still fail, or a
    direct writer could mark an unverified item usable.
    """
    with pytest.raises(IntegrityError):
        with owner_engine.begin() as c:
            # A contribution to hang the location off.
            cid = new_id("storage_contribution")
            c.execute(
                text(
                    "INSERT INTO storage_contributions (contribution_id, tenant_id, node_id, "
                    "declared_path, normalized_path, mode, status, registered_by_user_id, "
                    "registered_at, version) VALUES (:c, :t, :n, '/srv/inv/0', '/srv/inv/0', "
                    "'read_write', 'active', :u, now(), 1)"
                ),
                {"c": cid, "t": seeded["tenant_a"], "n": seeded["node_id"], "u": seeded["user_id"]},
            )
            c.execute(
                text(
                    "INSERT INTO data_locations (location_id, tenant_id, contribution_id, uri, "
                    "kind, relative_path, byte_size, ready, catalogued_at, version) "
                    "VALUES (:l, :t, :c, 'inv://datasets/x@1/a', 'dataset', 'a', 1, true, now(), 1)"
                ),
                {"l": new_id("data_location"), "t": seeded["tenant_a"], "c": cid},
            )


def test_a_retention_pin_only_extends(app_sessionmaker, seeded):
    later = dt.datetime(2027, 1, 1, tzinfo=UTC)
    earlier = dt.datetime(2026, 6, 1, tzinfo=UTC)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seeded["tenant_a"]):
                contribution = _active_contribution(session, seeded)
                location = storage_service.catalogue_location(
                    session,
                    tenant_id=seeded["tenant_a"],
                    contribution_id=contribution.contribution_id,
                    kind="artifact",
                    relative_path="out.bin",
                    byte_size=1,
                    run_id="run_1",
                    artifact_id="art_1",
                    now=NOW,
                )
                storage_service.pin_retention(
                    session, tenant_id=seeded["tenant_a"],
                    location_id=location.location_id, until=later,
                )
                assert location.retention_pinned_until == later
                # A weaker (earlier) claim must not shorten it.
                storage_service.pin_retention(
                    session, tenant_id=seeded["tenant_a"],
                    location_id=location.location_id, until=earlier,
                )
                assert location.retention_pinned_until == later


def test_a_non_owner_scoped_to_one_tenant_cannot_see_another_tenants_location(
    owner_engine, app_sessionmaker, seeded
):
    """RLS on data_locations: tenant B's rows are invisible under tenant A's scope."""
    # Seed a location under tenant B directly, as the owner.
    other_node = new_id("node")
    other_contribution = new_id("storage_contribution")
    other_location = new_id("data_location")
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, "
                "agent_version, status, enrolled_at, heartbeat_sequence, version) "
                "VALUES (:n, :t, 'b-00', 'linux', '22.04', '0.1', 'active', now(), 0, 1)"
            ),
            {"n": other_node, "t": seeded["tenant_b"]},
        )
        c.execute(
            text(
                "INSERT INTO storage_contributions (contribution_id, tenant_id, node_id, "
                "declared_path, normalized_path, mode, status, registered_by_user_id, "
                "registered_at, version) VALUES (:c, :t, :n, '/srv/b', '/srv/b', 'read_write', "
                "'active', :u, now(), 1)"
            ),
            {"c": other_contribution, "t": seeded["tenant_b"], "n": other_node, "u": new_id("user")},
        )
        c.execute(
            text(
                "INSERT INTO data_locations (location_id, tenant_id, contribution_id, uri, kind, "
                "relative_path, byte_size, ready, catalogued_at, version) "
                "VALUES (:l, :t, :c, 'inv://datasets/secret@1/b', 'dataset', 'b', 1, false, now(), 1)"
            ),
            {"l": other_location, "t": seeded["tenant_b"], "c": other_contribution},
        )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, seeded["tenant_a"]):
                found = session.execute(
                    text("SELECT count(*) FROM data_locations WHERE location_id = :l"),
                    {"l": other_location},
                ).scalar_one()
                assert found == 0
