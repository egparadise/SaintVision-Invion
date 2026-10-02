# -*- coding: utf-8 -*-
"""The reviewed RLS table census may not go stale unnoticed (card 234).

What happened: ``#322`` bound the AC-11 RLS report's table population to a reviewed census, and
``#323`` added ``inv.build_execution_intents`` with migration ``0059``.  Both landed in the same
train sequence, the census was not regenerated, and every RLS report in that tree was refused with
``unreviewed ['inv.build_execution_intents']`` -- correct fail-closed behaviour discovered three
trains later by reading one hosted artifact.

So this file reads the migrations themselves, offline, and fails when a migration creates a table
the census does not list.  It is a ratchet, not a second definition of the population: the census
is still a measurement of a live catalogue, and the direction checked here is the one that catches
staleness -- *created and not dropped* must be *listed*.  The census may legitimately list tables
this parser does not find (one is not a parser of PostgreSQL), which is why the other direction is
left to the live measurement.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import aggregate_ac11_evidence as aggregator  # noqa: E402

SQL_DIR = ROOT / "services/control-plane/src/inv/migrations"
PY_DIR = ROOT / "migrations/versions"
#: ``CREATE TABLE <schema>.<name>`` up to the statement end, so the body can be inspected for
#: ``PARTITION OF`` (a partition is not a measured table: the collector excludes inherited
#: relations, and the census is built from that same query).
SQL_CREATE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_]\w*)\.([A-Za-z_]\w*)(.*?)(?=;)",
    re.S | re.I,
)
SQL_CREATE_UNQUALIFIED = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_]\w*)\s*\((.*?)(?=;)", re.S | re.I
)
SQL_DROP = re.compile(
    r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?([A-Za-z_]\w*)\.([A-Za-z_]\w*)", re.I
)
PY_CREATE = re.compile(r'op\.create_table\(\s*["\'](\w+)["\'](.*?)\n    \)', re.S)
PY_SCHEMA = re.compile(r'schema\s*=\s*["\'](\w+)["\']')
PY_DROP = re.compile(r'op\.drop_table\(\s*["\'](\w+)["\'](?:[^)]*schema\s*=\s*["\'](\w+)["\'])?')
MEASURED_SCHEMAS = ("inv", "public")


def migration_tables() -> tuple[set[str], set[str]]:
    """(created, dropped) qualified table names the migrations in this tree name."""

    created: set[str] = set()
    partitions: set[str] = set()
    dropped: set[str] = set()
    for path in sorted(SQL_DIR.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        for schema, name, body in SQL_CREATE.findall(text):
            target = partitions if re.search(r"PARTITION\s+OF", body, re.I) else created
            target.add(f"{schema}.{name}")
        for name, body in SQL_CREATE_UNQUALIFIED.findall(text):
            if "." in name:  # already handled above
                continue
            if not re.search(r"PARTITION\s+OF", body, re.I):
                created.add(f"public.{name}")
        for schema, name in SQL_DROP.findall(text):
            dropped.add(f"{schema}.{name}")
    for path in sorted(PY_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        # Only the upgrade half.  Every alembic migration drops its own table in ``downgrade``,
        # so counting those cancelled each table it had just created -- measured while writing
        # this: with the drops counted, removing migration 0059's table from the census still
        # passed, which is exactly the hole this file exists to close.
        upgrade = text.split("def downgrade(", 1)[0]
        for name, body in PY_CREATE.findall(upgrade):
            schema = PY_SCHEMA.search(body)
            created.add(f"{schema.group(1) if schema else 'public'}.{name}")
        for name, schema in PY_DROP.findall(upgrade):
            dropped.add(f"{schema or 'public'}.{name}")
    created = {
        name for name in created - partitions if name.split(".", 1)[0] in MEASURED_SCHEMAS
    }
    return created, dropped


def test_the_parser_finds_the_schema_and_not_nothing():
    """A ratchet that silently stops parsing is not a ratchet.

    The same vacuity trap as a comparison over zero rows: if a refactor broke these patterns the
    set would be empty and every census would pass.  So the floor is asserted, and it is well
    below the real count on purpose -- this guards the parser, not the schema's size.
    """

    created, dropped = migration_tables()
    assert len(created) > 100, f"the migration parser found only {len(created)} tables"
    assert "inv.build_execution_intents" in created, "migration 0059's table must be found"
    assert "inv.build_execution_intents" not in dropped, (
        "a table dropped in its own migration's downgrade() is not a removal"
    )


def test_every_table_a_migration_creates_is_in_the_reviewed_census():
    """The staleness this file exists for, in one direction.

    A migration that adds a table without regenerating the census makes the AC-11 evaluator refuse
    every RLS report in that tree (``unreviewed [...]``).  Before card 234 this assertion failed on
    ``inv.build_execution_intents``; from here, the next migration fails it in its own PR.
    """

    created, dropped = migration_tables()
    census = set(
        json.loads((ROOT / aggregator.RLS_CENSUS_REPO_PATH).read_text(encoding="utf-8"))["tables"]
    )
    missing = sorted((created - dropped) - census)
    assert missing == [], (
        f"{missing} are created by a migration and not in {aggregator.RLS_CENSUS_REPO_PATH}; "
        "regenerate it with tools/collect_rls_evidence.py --disposable + "
        "tools/write_rls_table_census.py and repin RLS_CENSUS_BLOB"
    )


def test_the_census_file_is_self_consistent_and_pinned():
    """The file says what it contains, and the aggregator pins the bytes on disk.

    Both halves matter: the loader recomputes the digest and refuses a file that disagrees with
    itself, and it compares the blob -- so a regenerated census with a stale pin is also a refusal.
    """

    path = ROOT / aggregator.RLS_CENSUS_REPO_PATH
    raw = path.read_bytes()
    assert b"\r\n" not in raw, "the census must be LF so the disk blob and git agree"
    blob = hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()
    assert blob == aggregator.RLS_CENSUS_BLOB, "RLS_CENSUS_BLOB does not pin this file"
    assert blob == git("hash-object", aggregator.RLS_CENSUS_REPO_PATH)
    document = json.loads(raw.decode("utf-8"))
    assert document["count"] == len(document["tables"]) == len(set(document["tables"]))
    assert document["sha256"] == aggregator._rls_census_digest(document["tables"])
    assert aggregator.rls_table_census() == frozenset(document["tables"])
    # The provenance says which migration head it was measured at, so a reader can tell whether
    # it predates a migration in the tree.
    assert document["measuredFrom"]["migrationHead"].startswith("00")


def test_the_census_names_the_migration_head_it_was_measured_at():
    """The provenance is checkable: that head must be a migration this tree has."""

    document = json.loads(
        (ROOT / aggregator.RLS_CENSUS_REPO_PATH).read_text(encoding="utf-8")
    )
    head = document["measuredFrom"]["migrationHead"]
    assert (PY_DIR / head).is_file() or (PY_DIR / f"{head}.py").is_file(), head


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
