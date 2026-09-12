"""The guard that used to yield to a weaker predecessor.

``create_app_role`` guarded with ``IF NOT EXISTS`` and nothing more, so it
deferred to whatever already held the name. That is exactly how a deployed
database ended up with an ``inv_app`` that has LOGIN and a password committed
to the repository: the bootstrap script created the weaker role first, and the
migration saw the name and moved on.

Every test here uses a throwaway role name. Roles are cluster-wide, the test
cluster on this machine carries a real deployment's roles, and a test that
mutated ``inv_app`` itself would be doing to the cluster what these tests exist
to prevent.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from saintvision.db.rls import (
    DESIGNED_ROLE_SHAPE,
    WeakerRoleExists,
    create_app_role,
    shape_deviations,
)

pytestmark = pytest.mark.postgres


@pytest.fixture
def scratch_role(owner_engine):
    """A cluster-unique role name, dropped afterwards whatever happened."""
    name = "inv_shape_test_" + uuid.uuid4().hex[:16]
    yield name
    with owner_engine.begin() as connection:
        connection.execute(text(f"DROP ROLE IF EXISTS {name}"))


def _properties(engine, role: str) -> dict:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT rolcanlogin, rolbypassrls, rolsuper, rolcreatedb, "
                "rolcreaterole FROM pg_roles WHERE rolname = :r"
            ),
            {"r": role},
        ).mappings().one()
    return dict(row)


def test_a_fresh_role_is_created_to_the_designed_shape(owner_engine, scratch_role):
    with owner_engine.begin() as connection:
        create_app_role(connection, role=scratch_role)
    assert _properties(owner_engine, scratch_role) == DESIGNED_ROLE_SHAPE


def test_creating_twice_is_still_idempotent(owner_engine, scratch_role):
    """Verification must not cost the idempotency the guard existed for."""
    with owner_engine.begin() as connection:
        create_app_role(connection, role=scratch_role)
    with owner_engine.begin() as connection:
        create_app_role(connection, role=scratch_role)
    assert _properties(owner_engine, scratch_role) == DESIGNED_ROLE_SHAPE


def test_an_existing_weaker_role_is_refused_not_accepted(owner_engine, scratch_role):
    """The B-9 shape: a bootstrap made the role WITH LOGIN before migrations."""
    with owner_engine.begin() as connection:
        connection.execute(
            text(f"CREATE ROLE {scratch_role} LOGIN PASSWORD 'bootstrapped'")
        )
    with pytest.raises(WeakerRoleExists) as refused:
        with owner_engine.begin() as connection:
            create_app_role(connection, role=scratch_role)
    message = str(refused.value)
    assert "NOLOGIN group role" in message
    assert "bootstrap" in message
    # And it chose loudly, not quietly: the role was not altered, because the
    # weaker role may be what a running deployment currently connects as.
    assert _properties(owner_engine, scratch_role)["rolcanlogin"] is True


def test_bypassrls_is_refused_by_name(owner_engine, scratch_role):
    """BYPASSRLS makes every tenant policy decorative; it must be named."""
    with owner_engine.begin() as connection:
        connection.execute(text(f"CREATE ROLE {scratch_role} NOLOGIN BYPASSRLS"))
    with pytest.raises(WeakerRoleExists, match="BYPASSRLS"):
        with owner_engine.begin() as connection:
            create_app_role(connection, role=scratch_role)


def test_an_existing_role_of_the_designed_shape_passes(owner_engine, scratch_role):
    with owner_engine.begin() as connection:
        connection.execute(
            text(
                f"CREATE ROLE {scratch_role} NOLOGIN NOBYPASSRLS NOSUPERUSER "
                f"NOCREATEDB NOCREATEROLE"
            )
        )
    with owner_engine.begin() as connection:
        create_app_role(connection, role=scratch_role)  # must not raise


def test_shape_deviations_is_empty_for_the_designed_shape():
    assert shape_deviations(dict(DESIGNED_ROLE_SHAPE)) == []


@pytest.mark.parametrize(
    "prop,expected",
    [
        ("rolcanlogin", "NOLOGIN group role"),
        ("rolbypassrls", "BYPASSRLS"),
        ("rolsuper", "SUPERUSER"),
        ("rolcreatedb", "CREATE DATABASE"),
        ("rolcreaterole", "CREATE ROLE"),
    ],
)
def test_each_deviation_is_named_in_words(prop: str, expected: str):
    """A refusal has to say which property, or the operator greps the source."""
    weakened = dict(DESIGNED_ROLE_SHAPE, **{prop: True})
    (deviation,) = shape_deviations(weakened)
    assert expected in deviation


def test_unknown_properties_are_ignored_not_judged():
    """The rule judges only what it defines; extra pg_roles columns pass through."""
    assert shape_deviations(dict(DESIGNED_ROLE_SHAPE, rolreplication=True)) == []


def test_the_inline_copy_in_0001_matches_the_designed_shape():
    """Migration 0001 carries its own CREATE ROLE, and copies drift.

    0001 is published and already applied everywhere real, so it cannot import
    the hardened helper retroactively — but its literal is what every fresh
    deployment actually runs, and this repository has already had five
    hardcoded lists drift away from the thing they copied. The keywords are
    derived from DESIGNED_ROLE_SHAPE rather than typed again, so weakening
    either side names the property that moved.
    """
    from pathlib import Path

    keyword_of = {
        "rolcanlogin": "NOLOGIN",
        "rolbypassrls": "NOBYPASSRLS",
        "rolsuper": "NOSUPERUSER",
        "rolcreatedb": "NOCREATEDB",
        "rolcreaterole": "NOCREATEROLE",
    }
    assert set(keyword_of) == set(DESIGNED_ROLE_SHAPE), (
        "a property was added to the designed shape without deciding its "
        "CREATE ROLE keyword; extend both together"
    )
    source = (
        Path(__file__).resolve().parents[1]
        / "migrations/versions/0001_s02_baseline.py"
    ).read_text(encoding="utf-8")
    (create_line,) = [
        line for line in source.splitlines() if "CREATE ROLE" in line
    ]
    missing = [
        keyword_of[prop]
        for prop, designed in DESIGNED_ROLE_SHAPE.items()
        if not designed and keyword_of[prop] not in create_line
    ]
    assert not missing, (
        f"0001's inline CREATE ROLE no longer states {missing}; it has drifted "
        f"from the designed shape in saintvision.db.rls"
    )
