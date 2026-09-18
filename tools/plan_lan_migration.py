"""Read pilot migration metadata and emit a non-executable, hash-bound gap plan."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import psycopg
from psycopg.rows import dict_row

from lan_pilot import load
from migration_graph import chain


class MigrationPlanDatabaseError(Exception):
    """A database/driver failure without DSN or SQL diagnostics."""

    def __init__(self, sqlstate=None):
        self.sqlstate = sqlstate if isinstance(sqlstate, str) and len(sqlstate) == 5 and sqlstate.isalnum() else "unknown"
        super().__init__("Migration metadata database operation failed")


def gap_plan(current, revisions=None):
    ordered = chain(revisions)
    by_id = {r.revision: r for r in ordered}
    if not current or len(set(current)) != len(current) or set(current) - by_id.keys():
        raise ValueError("Missing, duplicate or unknown database revision")

    def ancestors(name):
        parents = by_id[name].down_revision
        parents = (parents,) if isinstance(parents, str) else (parents or ())
        result = {name}
        for parent in parents:
            result |= ancestors(parent)
        return result

    applied = set()
    for name in current:
        lineage = ancestors(name)
        if (set(current) - {name}) & lineage:
            raise ValueError("Database heads overlap; reconcile migration metadata")
        applied |= lineage
    pending = [r for r in ordered if r.revision not in applied]
    return dict(currentHeads=sorted(current), targetHead=ordered[-1].revision,
                pending=[dict(revision=r.revision, file=r.path.name,
                              sha256=hashlib.sha256(r.path.read_bytes()).hexdigest(),
                              irreversible=r.irreversible) for r in pending],
                migrationAuthorized=False, schemaIntegrityAssessed=False,
                requiredBeforeApply=["verified-backup-and-restore", "data-upgrade-rehearsal",
                                     "independent-review", "service-compatibility", "maintenance-plan"])


def inspect(state_path):
    state = load(state_path)
    # Explicit metadata-only admin connection; never used for tenant row reads.
    try:
        with psycopg.connect(state["adminDSN"], row_factory=dict_row) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '2s'")
            current = [r["version_num"] for r in conn.execute("SELECT version_num FROM public.alembic_version")]
            stamp = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    except psycopg.Error as error:
        raise MigrationPlanDatabaseError(getattr(error, "sqlstate", None)) from None
    report = gap_plan(current)
    report.update(observedAt=stamp.isoformat(), scope="read-only-admin-migration-metadata")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect(args.state)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except MigrationPlanDatabaseError as error:
        print(json.dumps({"error": "migration_metadata_database_error", "sqlstate": error.sqlstate}), file=sys.stderr)
        return 2
    except ValueError:
        print(json.dumps({"error": "migration_metadata_refused"}), file=sys.stderr)
        return 2
    except (TypeError, KeyError, AttributeError) as error:
        print(json.dumps({"error": "migration_metadata_internal_error", "errorType": type(error).__name__}), file=sys.stderr)
        return 3
    except Exception as error:
        print(json.dumps({"error": "migration_metadata_internal_error", "errorType": type(error).__name__}), file=sys.stderr)
        return 2
    print(json.dumps({k: report[k] for k in ("currentHeads", "targetHead", "migrationAuthorized")}))
    return 1 if report["pending"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
