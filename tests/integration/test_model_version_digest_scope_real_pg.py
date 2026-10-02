"""0052 against a real database: what the narrowed digest constraint allows.

The migration has run by the time these start (the ``migrated`` fixture upgrades
to head), so this is not a test of the DDL text -- it is a test of the rule the
catalogue now enforces, which is the only place that can be observed.

The cases Codex named in #191 F1:

* two projects of one tenant may each register the same bytes -- the
  cross-project existence oracle is gone;
* the same bytes under two version names **in one model** is still refused --
  the original S10-ST invariant survives where it means something;
* and the old tenant-wide constraint is actually gone from the catalogue, not
  merely unused.

Plus the retry boundary from the review of this migration (#197): a run
interrupted between the promotion and the drop must resume, and it must leave the
new constraint *the same object* rather than rebuilding it. The reason the first
version could not is asserted here too, from PostgreSQL's own refusal to drop an
index a constraint owns -- so the resume logic is not defending against an
imagined error.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from saintvision.ids import new_id

pytestmark = pytest.mark.postgres

CURRENT_HEAD = "0060_build_execution_admissions"

OLD = "uq_model_versions_tenant_id_content_sha256"
NEW = "uq_model_versions_model_id_content_sha256"


def _digest() -> str:
    """64 lowercase hex, unique: the shape the checksum column requires."""
    return uuid.uuid4().hex + uuid.uuid4().hex


def _insert(connection, table_name, **values):
    """Insert through the model metadata, so a wrong column cannot reach hosted CI."""
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


def _project_with_model(connection, *, tenant_id, now, label):
    project_id = new_id("project")
    model_id = new_id("model")
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
        "models",
        model_id=model_id,
        tenant_id=tenant_id,
        project_id=project_id,
        name=f"model-{label}",
        created_at=now,
    )
    return {"project_id": project_id, "model_id": model_id, "name": f"model-{label}"}


def _version(connection, *, tenant_id, model, version, digest, now):
    _insert(
        connection,
        "model_versions",
        model_version_id=new_id("model_version"),
        tenant_id=tenant_id,
        model_id=model["model_id"],
        version=version,
        stage="draft",
        content_sha256=digest,
        byte_size=1,
        uri=f"inv://models/{model['name']}@{version}",
        created_at=now,
    )


def _constraints(owner_engine):
    with owner_engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'model_versions'::regclass AND contype = 'u'"
            )
        ).scalars().all()
    return set(rows)


def test_the_catalogue_carries_the_narrow_constraint_and_not_the_wide_one(
    owner_engine, migrated
):
    names = _constraints(owner_engine)
    assert NEW in names, names
    assert OLD not in names, "the tenant-wide rule has to be gone, not merely unused"


def test_the_new_constraint_covers_model_id_and_the_digest(owner_engine, migrated):
    with owner_engine.begin() as connection:
        columns = connection.execute(
            text(
                "SELECT a.attname FROM pg_constraint c "
                "JOIN unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord) ON true "
                "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum "
                "WHERE c.conname = :name ORDER BY k.ord"
            ),
            {"name": NEW},
        ).scalars().all()
    assert columns == ["model_id", "content_sha256"]


def test_two_projects_of_one_tenant_may_each_register_the_same_digest(
    owner_engine, two_tenants, frozen_now
):
    """The oracle #191 F1 closed.

    Before 0052 the second insert failed, and that failure was observable from a
    project with no access to the first -- a 409 instead of a 201 is the existence
    bit, whatever the message says.
    """
    tenant, _ = two_tenants
    digest = _digest()
    with owner_engine.begin() as connection:
        first = _project_with_model(
            connection, tenant_id=tenant, now=frozen_now, label="scope-a"
        )
        second = _project_with_model(
            connection, tenant_id=tenant, now=frozen_now, label="scope-b"
        )
        _version(
            connection,
            tenant_id=tenant,
            model=first,
            version="1.0.0",
            digest=digest,
            now=frozen_now,
        )
        _version(
            connection,
            tenant_id=tenant,
            model=second,
            version="1.0.0",
            digest=digest,
            now=frozen_now,
        )

    with owner_engine.begin() as connection:
        count = connection.execute(
            text(
                "SELECT count(*) FROM model_versions "
                "WHERE tenant_id = :t AND content_sha256 = :d"
            ),
            {"t": tenant, "d": digest},
        ).scalar_one()
    assert count == 2


def test_the_same_digest_under_two_versions_of_one_model_is_still_refused(
    owner_engine, two_tenants, frozen_now
):
    """The S10-ST invariant, kept where it is meaningful."""
    tenant, _ = two_tenants
    digest = _digest()
    with owner_engine.begin() as connection:
        model = _project_with_model(
            connection, tenant_id=tenant, now=frozen_now, label="scope-same"
        )
        _version(
            connection,
            tenant_id=tenant,
            model=model,
            version="1.0.0",
            digest=digest,
            now=frozen_now,
        )

    with pytest.raises(IntegrityError) as raised:
        with owner_engine.begin() as connection:
            _version(
                connection,
                tenant_id=tenant,
                model=model,
                version="2.0.0",
                digest=digest,
                now=frozen_now,
            )
    assert NEW in str(raised.value)


def test_two_models_in_one_project_may_hold_the_same_digest(
    owner_engine, two_tenants, frozen_now
):
    """A consequence worth stating rather than discovering.

    The constraint is per model, so two models of the *same* project may hold the
    same bytes. That is the same relaxation as across projects and carries no
    disclosure: the caller can see both models, because they are in a project they
    hold.
    """
    tenant, _ = two_tenants
    digest = _digest()
    with owner_engine.begin() as connection:
        model = _project_with_model(
            connection, tenant_id=tenant, now=frozen_now, label="scope-two"
        )
        sibling_id = new_id("model")
        _insert(
            connection,
            "models",
            model_id=sibling_id,
            tenant_id=tenant,
            project_id=model["project_id"],
            name="model-scope-two-b",
            created_at=frozen_now,
        )
        sibling = {"model_id": sibling_id, "name": "model-scope-two-b"}
        _version(
            connection,
            tenant_id=tenant,
            model=model,
            version="1.0.0",
            digest=digest,
            now=frozen_now,
        )
        _version(
            connection,
            tenant_id=tenant,
            model=sibling,
            version="1.0.0",
            digest=digest,
            now=frozen_now,
        )

    with owner_engine.begin() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM model_versions WHERE content_sha256 = :d"),
            {"d": digest},
        ).scalar_one()
    assert count == 2


def test_another_tenant_is_unaffected_by_the_narrowing(
    owner_engine, two_tenants, frozen_now
):
    """Narrowing removed a tenant-wide rule; it did not widen anything.

    The same digest in two tenants was already allowed by the old constraint
    (``tenant_id`` led it), and still is. Asserted so a future widening of the
    scope in the other direction is noticed here.
    """
    tenant_a, tenant_b = two_tenants
    digest = _digest()
    with owner_engine.begin() as connection:
        for tenant, label in ((tenant_a, "scope-ta"), (tenant_b, "scope-tb")):
            model = _project_with_model(
                connection, tenant_id=tenant, now=frozen_now, label=label
            )
            _version(
                connection,
                tenant_id=tenant,
                model=model,
                version="1.0.0",
                digest=digest,
                now=frozen_now,
            )

    with owner_engine.begin() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM model_versions WHERE content_sha256 = :d"),
            {"d": digest},
        ).scalar_one()
    assert count == 2

def _constraint_oid(owner_engine, name):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT oid FROM pg_constraint "
                "WHERE conname = :n AND conrelid = 'model_versions'::regclass"
            ),
            {"n": name},
        ).scalar_one_or_none()


def test_a_run_interrupted_after_the_promotion_resumes_and_converges(
    owner_engine, database_url, migrated, clean_tables, monkeypatch
):
    """The crash point the first version of this migration wedged on.

    The catalogue is put back into the interrupted state -- both constraints
    present, the revision still 0051 -- and the migration is re-run through the
    real Alembic machinery. It must finish by removing only the old constraint,
    leaving the new one *the same object*: its oid is unchanged, which a drop and
    rebuild would not be.

    Before the fix this raised ``cannot drop index
    uq_model_versions_model_id_content_sha256 because constraint ... requires
    it``, because the re-run began by dropping the index the constraint owns.
    """
    from alembic import command
    from alembic.config import Config

    before = _constraint_oid(owner_engine, NEW)
    assert before is not None, "the migration has run, so the new constraint is there"

    # Recreate the pre-crash catalogue: the wide constraint back, revision 0051.
    # model_versions is empty here (clean_tables), so the wide rule is satisfiable.
    with owner_engine.begin() as connection:
        connection.execute(
            text(
                f"ALTER TABLE model_versions ADD CONSTRAINT {OLD} "
                "UNIQUE (tenant_id, content_sha256)"
            )
        )
        connection.execute(
            text("UPDATE alembic_version SET version_num = '0051_service_credentials'")
        )

    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    try:
        with monkeypatch.context() as patch:
            patch.setenv("INV_DATABASE_URL", database_url)
            patch.setenv("INV_MIGRATION_DSN", database_url)
            command.upgrade(config, "0052_model_version_digest_scope")
            with owner_engine.begin() as connection:
                assert connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one() == "0052_model_version_digest_scope"
    finally:
        # Whatever happened, leave the shared session database at the real head.
        # This test replays only 0052; replaying every later migration over its
        # already-present objects is not the crash state under test.
        with owner_engine.begin() as connection:
            connection.execute(
                text(f"ALTER TABLE model_versions DROP CONSTRAINT IF EXISTS {OLD}")
            )
            connection.execute(
                text("UPDATE alembic_version SET version_num = :head"),
                {"head": CURRENT_HEAD},
            )

    names = _constraints(owner_engine)
    assert NEW in names
    assert OLD not in names, "the resume has to finish the job"
    # The same constraint object, not a rebuilt one.
    assert _constraint_oid(owner_engine, NEW) == before

    with owner_engine.begin() as connection:
        recorded = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert recorded == CURRENT_HEAD


def test_the_index_the_new_constraint_owns_cannot_be_dropped_on_its_own(owner_engine, migrated):
    """Why the resume path must not touch the index -- stated by PostgreSQL itself.

    This is the refusal that wedged the first version. Asserting it here means the
    resume logic is not defending against an imagined error.
    """
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError) as raised:
        with owner_engine.begin() as connection:
            connection.execute(text(f"DROP INDEX {NEW}"))
    message = str(raised.value).lower()
    assert "constraint" in message and "requires it" in message
