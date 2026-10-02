#!/usr/bin/env python3
"""Write the reviewed RLS table census from a collector observation.  Never edited by hand.

``tools/rls-table-census.json`` is the reviewed population the AC-11 evaluator binds an RLS report
to (#322 F-R7).  It is therefore a measurement, not a list someone maintains: this tool takes the
JSON the collector wrote -- or the normalized hosted SEC-RLS-001 report that preserves that
collector's ``table_census`` block -- and writes the reviewed file from it.  A normalized hosted
report is accepted only for the current exact HEAD and its source run ID; the current migration
head is read from ``tools/migration_graph.py`` rather than supplied by a caller.

Why a tool rather than an edit (card 234): the file went stale the first time a migration added a
table (``0059`` added ``inv.build_execution_intents``), and the evaluator refused every RLS report
until it was regenerated.  A hand edit would be a claim; this is a copy of what was observed, with
the provenance of the observation attached and the resulting Git blob printed so the pin in
``aggregate_ac11_evidence.py`` can be rotated in the same reviewed change.

Rerun:
  INV_TEST_ADMIN_DSN=<admin dsn> python tools/collect_rls_evidence.py --disposable --out-dir <dir>
  python tools/write_rls_table_census.py --observation <dir>/<the json it wrote> [--run-id N]

Exit 0: written (the blob is on stdout); 2: the observation is unusable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = REPO_ROOT / "tools/rls-table-census.json"
SCHEMA_VERSION = "1.0.0"
NOTE = (
    "The tenant/inv tables the pinned collector observed in the live catalogue of a migrated "
    "database, recorded so the AC-11 evaluator can bind a report to a reviewed population instead "
    "of to the population the report itself chose (#322 r2 F-R7). A migration that adds or removes "
    "a table in these schemas makes this file stale: regenerate it with "
    "tools/collect_rls_evidence.py --disposable and tools/write_rls_table_census.py, and repin "
    "RLS_CENSUS_BLOB in tools/aggregate_ac11_evidence.py in the same reviewed change. "
    "tests/test_rls_table_census_ratchet.py fails when a migration creates a table this file does "
    "not list, so the next one is caught in its own PR (card 234)."
)


def census_from_observation(
    observation: Any,
    run_id: str | None,
    *,
    migration_head: str | None = None,
) -> dict[str, Any]:
    """The reviewed document, rebuilt from the collector's own census block."""

    if not isinstance(observation, dict):
        raise ValueError("the observation must be an object")
    census = observation.get("table_census")
    database = observation.get("database")
    if not isinstance(census, dict):
        raise ValueError("the observation carries no table_census block")
    if isinstance(database, dict):
        source_head_sha = str(observation.get("git_sha") or "unknown")
        observed_migration_head = str(database.get("migration_head") or "unknown")
    else:
        if (
            observation.get("threatId") != "SEC-RLS-001"
            or observation.get("reportAvailable") is not True
            or not isinstance(observation.get("sourceHeadSha"), str)
            or not observation["sourceHeadSha"]
        ):
            raise ValueError("the normalized hosted observation is not a measured RLS report")
        if run_id is not None and str(observation.get("sourceRunId")) != str(run_id):
            raise ValueError("the hosted observation sourceRunId differs")
        if not migration_head:
            raise ValueError("the normalized hosted observation requires a migration head")
        source_head_sha = observation["sourceHeadSha"]
        observed_migration_head = migration_head
    tables = census.get("tables")
    if not isinstance(tables, list) or not tables or len(set(tables)) != len(tables):
        raise ValueError("table_census.tables must be a non-empty list of distinct names")
    digest = hashlib.sha256(chr(10).join(sorted(tables)).encode("utf-8")).hexdigest()
    if census.get("count") != len(tables) or census.get("sha256") != digest:
        raise ValueError("table_census does not agree with its own names")
    schemas = census.get("schemas")
    if not isinstance(schemas, list) or not schemas:
        raise ValueError("table_census.schemas must be a non-empty list")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "note": NOTE,
        "measuredFrom": {
            "runId": run_id or "local",
            "sourceHeadSha": source_head_sha,
            "migrationHead": observed_migration_head,
        },
        "schemas": sorted(schemas),
        "count": len(tables),
        "sha256": digest,
        "tables": sorted(tables),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--run-id", default=None, help="the hosted run that observed it, if any")
    args = parser.parse_args(argv)
    try:
        observation = json.loads(args.observation.read_text(encoding="utf-8"))
        migration_head = None
        if not isinstance(observation.get("database"), dict):
            source_head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            if observation.get("sourceHeadSha") != source_head:
                raise ValueError("the hosted observation is not for the current exact head")
            migration_head = subprocess.run(
                [sys.executable, "tools/migration_graph.py", "--head"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        document = census_from_observation(observation, args.run_id, migration_head=migration_head)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
        ValueError,
    ) as error:
        print(f"the collector observation is unusable: {error}", file=sys.stderr)
        return 2
    rendered = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    # LF on purpose: the evaluator hashes the bytes on disk and the ratchet compares that with
    # `git hash-object`, so a CRLF write would make the two disagree (measured in card 225).
    args.out.write_text(rendered, encoding="utf-8", newline="\n")
    raw = args.out.read_bytes()
    blob = hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()
    print(f"{args.out}: {document['count']} tables, sha256 {document['sha256']}")
    print(f'RLS_CENSUS_BLOB = "{blob}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
