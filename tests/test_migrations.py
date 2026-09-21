"""Migration ordering, checked without a database.

Alembic can render the whole upgrade as SQL offline, which is enough to catch
the ordering mistakes that otherwise only show up against a live server — and
one of them already did: revision 0001 read
``saintvision.db.models.PARTITIONED_TABLES``, and when 0002 added a table to
that constant, 0001 began trying to partition a table that would not exist for
another revision.

A migration must be pinned to the schema of its own moment. These tests hold
that.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations" / "versions"


@pytest.fixture(scope="module")
def rendered_sql() -> str:
    """The full upgrade rendered offline. No server is contacted."""
    env = dict(os.environ)
    # Offline rendering never connects, but Alembic still requires a URL.
    env["INV_DATABASE_URL"] = "postgresql+psycopg://offline:offline@localhost:1/offline"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"offline render failed:\n{result.stderr[-4000:]}")
    return result.stdout


def _position(sql: str, pattern: str) -> int:
    match = re.search(pattern, sql, re.IGNORECASE)
    assert match is not None, f"not found in rendered SQL: {pattern}"
    return match.start()


@pytest.mark.parametrize(
    "table",
    ["resource_snapshots", "audit_events", "evidence_envelopes"],
)
def test_a_partition_is_never_created_before_its_parent(rendered_sql, table):
    parent = _position(rendered_sql, rf"CREATE TABLE {table} \(")
    first_partition = _position(rendered_sql, rf"CREATE TABLE {table}_p\d{{6}} PARTITION OF")
    assert parent < first_partition, f"{table}: partition precedes the parent table"


@pytest.mark.parametrize(
    "table",
    ["resource_snapshots", "audit_events", "evidence_envelopes"],
)
def test_each_partitioned_table_gets_a_four_month_lead(rendered_sql, table):
    """This month plus three (CR-06)."""
    partitions = re.findall(rf"CREATE TABLE {table}_p(\d{{6}}) PARTITION OF", rendered_sql)
    assert len(partitions) == 4, f"{table}: expected 4 partitions, got {partitions}"
    assert partitions == sorted(partitions)


def test_no_default_partition_is_ever_created(rendered_sql):
    assert "PARTITION OF" in rendered_sql
    assert re.search(r"PARTITION OF \w+ DEFAULT", rendered_sql) is None


def test_a_child_table_is_never_created_before_its_parent(rendered_sql):
    """Foreign keys are declared inline, so creation order has to be right."""
    pairs = [
        ("tenants", "users"),
        ("projects", "workspaces"),
        ("workspaces", "workspace_volumes"),
        ("workloads", "runs"),
        ("runs", "run_attempts"),
        ("run_attempts", "steps"),
        ("runs", "artifacts"),
        ("artifacts", "upload_sessions"),
        ("nodes", "node_capabilities"),
        ("storage_contributions", "data_locations"),
    ]
    for parent, child in pairs:
        assert _position(rendered_sql, rf"CREATE TABLE {parent} \(") < _position(
            rendered_sql, rf"CREATE TABLE {child} \("
        ), f"{child} is created before {parent}"


def test_rls_is_applied_after_the_table_it_protects(rendered_sql):
    for table in ("users", "nodes", "runs", "evidence_envelopes", "artifacts"):
        created = _position(rendered_sql, rf"CREATE TABLE {table} \(")
        enabled = _position(rendered_sql, rf"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        forced = _position(rendered_sql, rf"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        policy = _position(rendered_sql, rf"CREATE POLICY {table}_tenant_isolation")
        assert created < enabled < forced < policy, table


def test_evidence_is_granted_insert_but_not_update_or_delete(rendered_sql):
    """Append-only for the application role (PLAN-DB-001)."""
    for table in ("audit_events", "evidence_envelopes"):
        grants = re.findall(rf"GRANT ([^;]+) ON {table} TO inv_app", rendered_sql)
        assert grants, f"{table}: no grant rendered"
        for grant in grants:
            assert "UPDATE" not in grant.upper(), f"{table}: UPDATE granted"
            assert "DELETE" not in grant.upper(), f"{table}: DELETE granted"
            assert "INSERT" in grant.upper()


def test_no_migration_reads_the_mutable_partition_constant():
    """The bug this file exists for.

    Importing the live constant into a migration means a later revision can
    change what an older one does. Each revision states its own list.
    """
    offenders = []
    for path in sorted(MIGRATIONS.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if re.search(r"^\s*from .*models import .*PARTITIONED_TABLES", source, re.M):
            offenders.append(path.name)
    assert offenders == [], f"migrations importing PARTITIONED_TABLES: {offenders}"


def test_every_revision_declares_its_predecessor():
    import ast

    revisions = {}
    for path in sorted(MIGRATIONS.glob("*.py")):
        declarations = {}
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                        declarations[target.id] = ast.literal_eval(node.value)
        assert set(declarations) == {"revision", "down_revision"}, path.name
        assert declarations["revision"] not in revisions, path.name
        revisions[declarations["revision"]] = declarations["down_revision"]
    assert sum(d is None for d in revisions.values()) == 1
    for revision, down in revisions.items():
        parents = () if down is None else (down,) if isinstance(down, str) else down
        assert isinstance(parents, tuple) and len(set(parents)) == len(parents)
        assert all(parent in revisions and parent != revision for parent in parents)


def test_the_migrations_create_exactly_the_modelled_tables(rendered_sql):
    """The invariant that would have caught three separate staleness bugs.

    A model with no migration is a table that exists only in tests; a migration
    with no model is a table nothing reads. Both are silent until something far
    away breaks.
    """
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from saintvision.db import models  # noqa: F401  (registers the tables)
    from saintvision.db.base import Base

    created = set(re.findall(r"CREATE TABLE (\w+) \(", rendered_sql))
    # Partition children are named <parent>_pYYYYMM and are not modelled
    # separately; alembic owns its own bookkeeping table.
    created = {
        name for name in created if not re.search(r"_p\d{6}$", name) and name != "alembic_version"
    }
    modelled = set(Base.metadata.tables)

    assert created - modelled == set(), f"migrated but not modelled: {created - modelled}"
    assert modelled - created == set(), f"modelled but not migrated: {modelled - created}"


def test_every_tenant_scoped_table_is_policed(rendered_sql):
    """RLS is declared per table in each revision; a table added to the model
    list without a policy would isolate nothing."""
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from saintvision.db.models import TENANT_SCOPED_TABLES

    for table in TENANT_SCOPED_TABLES:
        assert re.search(
            rf"ALTER TABLE {table} FORCE ROW LEVEL SECURITY", rendered_sql
        ), f"{table}: RLS not forced by any migration"
        assert re.search(
            rf"CREATE POLICY {table}_tenant_isolation", rendered_sql
        ), f"{table}: no isolation policy"


def test_append_only_tables_are_never_granted_update_or_delete(rendered_sql):
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from saintvision.db.models import APPEND_ONLY_TABLES

    for table in APPEND_ONLY_TABLES:
        grants = re.findall(rf"GRANT ([^;]+) ON {table} TO inv_app", rendered_sql)
        assert grants, f"{table}: no grant rendered"
        for grant in grants:
            assert "UPDATE" not in grant.upper(), f"{table}: UPDATE granted"
            assert "DELETE" not in grant.upper(), f"{table}: DELETE granted"


def test_lifecycle_tables_get_column_scoped_update_and_no_delete(rendered_sql):
    """Identity immutable, lifecycle advancing.

    Blanket append-only on model_versions was the first attempt; a version has
    to become verified, pinned and released after insertion, so CI failed with
    "permission denied". Column-level UPDATE says the intended thing instead —
    content_sha256 and version cannot be rewritten, stage and the pin can move.
    """
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from saintvision.db.models import LIFECYCLE_UPDATE_COLUMNS

    for table, columns in LIFECYCLE_UPDATE_COLUMNS.items():
        grants = re.findall(rf"GRANT ([^;]+) ON {table} TO inv_app", rendered_sql)
        assert grants, f"{table}: no grant rendered"
        assert not any("DELETE" in g.upper() for g in grants), f"{table}: DELETE granted"

        scoped = [g for g in grants if g.upper().startswith("UPDATE (")]
        assert len(scoped) == 1, f"{table}: expected exactly one column-scoped UPDATE"
        granted = {c.strip() for c in scoped[0][len("UPDATE (") : -1].split(",")}
        assert granted == set(columns), f"{table}: granted {granted}, expected {set(columns)}"

        # An unqualified UPDATE would defeat the point entirely.
        assert not any(
            re.match(r"^UPDATE\b(?!\s*\()", g.strip(), re.IGNORECASE) for g in grants
        ), f"{table}: an unqualified UPDATE is granted"


def test_identity_columns_are_never_grantable(rendered_sql):
    """The columns a lineage claim rests on must not appear in any grant."""
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from saintvision.db.models import LIFECYCLE_UPDATE_COLUMNS

    forbidden = {"content_sha256", "version", "uri", "model_id", "dataset_id", "tenant_id"}
    for table, columns in LIFECYCLE_UPDATE_COLUMNS.items():
        assert not (set(columns) & forbidden), f"{table}: grants an identity column"


def test_discovery_issuer_is_a_separate_nonlogin_role_with_scoped_table_privileges(rendered_sql):
    role = re.search(
        r"CREATE ROLE inv_discovery_issuer([^;]+);", rendered_sql, re.IGNORECASE
    )
    assert role, "discovery issuer role is not created"
    flags = role.group(1).upper()
    for flag in ("NOLOGIN", "NOSUPERUSER", "NOBYPASSRLS", "NOCREATEDB", "NOCREATEROLE", "NOINHERIT"):
        assert flag in flags, f"issuer role lacks {flag}"
    assert re.search(
        r"ALTER ROLE inv_discovery_issuer([^;]+);", rendered_sql, re.IGNORECASE
    )
    assert re.search(
        r"GRANT SELECT \(credential_id, tenant_id, installation_id, scope, issued_by,\s*"
        r"issued_at, expires_at, revoked_at, announcement_id, last_announcement_at\)\s*"
        r"ON discovery_machine_credentials TO inv_discovery_issuer",
        rendered_sql,
        re.IGNORECASE,
    )
    assert not re.search(
        r"GRANT SELECT[^;]*token_sha256[^;]*TO inv_discovery_issuer",
        rendered_sql,
        re.IGNORECASE,
    ), "issuer does not need to read credential digests"
    assert re.search(
        r"GRANT UPDATE \(revoked_at\) ON discovery_machine_credentials TO inv_discovery_issuer",
        rendered_sql,
        re.IGNORECASE,
    )
    assert not re.search(
        r"GRANT (?:[^;]*,\s*)?DELETE[^;]*ON discovery_machine_credentials TO inv_discovery_issuer",
        rendered_sql,
        re.IGNORECASE,
    )
    assert re.search(
        r"GRANT INSERT ON discovery_credential_events TO inv_discovery_issuer",
        rendered_sql,
        re.IGNORECASE,
    )
    assert not re.search(
        r"GRANT (?:SELECT|UPDATE|DELETE)[^;]*ON discovery_credential_events TO inv_discovery_issuer",
        rendered_sql,
        re.IGNORECASE,
    ), "issuer only appends audit events; it must not read or alter them"
    assert "inv_discovery_issuer already has members; review membership before migration" in rendered_sql
    assert "token_sha256 = nullif(current_setting('inv.discovery_token_sha256',true),'')" in rendered_sql


# --------------------------------------------------------------------------
# The chain itself, read from source
# --------------------------------------------------------------------------


def test_the_migration_graph_has_a_single_integrated_head():
    """Two heads mean nobody knows what `head` refers to, and an upgrade picks
    one of them."""
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import migration_graph

    ordered = migration_graph.chain()
    assert len(ordered) == len(migration_graph.load())
    assert ordered[0].down_revision is None
    seen = set()
    for revision in ordered:
        down = revision.down_revision
        parents = () if down is None else (down,) if isinstance(down, str) else down
        assert set(parents) <= seen, "Every parent must precede its child"
        seen.add(revision.revision)
    referenced = {
        p
        for r in ordered
        for p in (
            ()
            if r.down_revision is None
            else (r.down_revision,) if isinstance(r.down_revision, str) else r.down_revision
        )
    }
    assert seen - referenced == {ordered[-1].revision}


def test_every_irreversible_revision_says_what_to_do_instead():
    """PLAN-DB-001: an irreversible migration states a verified restore and
    forward-fix plan rather than forcing a downgrade.

    A revision that simply refuses, with no reason recorded, leaves an operator
    holding a broken rollback and no instruction.
    """
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import migration_graph

    silent = [r.name for r in migration_graph.load() if r.irreversible and not r.recovery_note]
    assert silent == [], f"irreversible with no recovery note: {silent}"


def test_the_downgrade_target_never_crosses_an_irreversible_revision():
    """The rollback test must stop where the plan says to stop."""
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import migration_graph

    ordered = migration_graph.chain()
    target = migration_graph.downgrade_target(ordered)
    if target == "base":
        assert not any(r.irreversible for r in ordered)
        return

    index = [r.revision for r in ordered].index(target)
    # Everything above the target reverses; the target itself does not.
    assert ordered[index].irreversible
    assert not any(r.irreversible for r in ordered[index + 1 :])
