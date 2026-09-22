"""Read-only Tier-A PITR opt-in rehearsal.

This harness joins the live, read-only ``pitr_readiness`` observation with a
filesystem-only ``pitr_archive_retention`` plan.  It never invokes compose,
changes PostgreSQL settings, restarts PostgreSQL, or applies a retention plan.
Its report is preparation evidence only; ``pitrVerified`` and
``ac12Satisfied`` are always false.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pitr_archive_retention import DEFAULT_DAYS, load_archive, load_backups, plan
from pitr_readiness import assess, read_settings


def rehearse(
    settings: dict[str, str | None],
    archive_dir: Path,
    backups_dir: Path,
    *,
    retention_days: int = DEFAULT_DAYS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build one non-mutating readiness + retention report."""

    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    archive_exists = archive_dir.is_dir()
    backups_exist = backups_dir.is_dir()
    readiness = assess(settings)
    retention = plan(
        load_archive(archive_dir),
        load_backups(backups_dir),
        retention_days=retention_days,
        now=observed_at,
    )

    inputs_valid = archive_exists and backups_exist
    observation_complete = inputs_valid and readiness["verdict"] != "inconclusive"
    return {
        "schemaVersion": 1,
        "kind": "PitrOptInDryRun",
        "mode": "dry-run",
        "decision": "tier-a-deferred",
        "observedAt": observed_at.astimezone(timezone.utc).isoformat(),
        "harnessVerdict": "observed" if observation_complete else "inconclusive",
        "readiness": readiness,
        "retention": retention.as_dict(),
        "inputs": {
            "archiveDirectoryReadable": archive_exists,
            "backupsDirectoryReadable": backups_exist,
        },
        "mutations": {
            "postgresRestarted": False,
            "postgresSettingsChanged": False,
            "composeApplied": False,
            "retentionApplied": False,
        },
        "acceptance": {
            "pitrVerified": False,
            "ac12Satisfied": False,
            "reason": (
                "Dry-run preparation cannot prove continuous WAL delivery, "
                "target-time recovery, RPO, RTO, or safe service resumption"
            ),
        },
    }


def _write_report(report: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.name + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(output)
    print(rendered, end="")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    parser.add_argument("--dsn-env", default="INV_PITR_DSN", help="environment variable holding the libpq DSN")
    parser.add_argument("--archive", required=True, help="existing WAL archive directory (read-only observation)")
    parser.add_argument("--backups", required=True, help="existing base-backup directory (read-only observation)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"retention days (default: {DEFAULT_DAYS})")
    parser.add_argument("--now", help="ISO 8601 observation time for a reproducible plan")
    parser.add_argument("--output", type=Path, help="optional JSON report path")
    parser.add_argument(
        "--require-possible",
        action="store_true",
        help="fail unless configuration readiness is possible; still does not claim PITR verification",
    )
    args = parser.parse_args(argv)

    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    try:
        dsn = os.environ.get(args.dsn_env)
        if not dsn:
            raise ValueError("connection input unavailable")
        settings = read_settings(dsn)
    except Exception:
        settings = {}

    try:
        report = rehearse(
            settings,
            Path(args.archive),
            Path(args.backups),
            retention_days=args.days,
            now=now,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    _write_report(report, args.output)
    if report["harnessVerdict"] != "observed":
        return 2
    if args.require_possible and report["readiness"]["verdict"] != "possible":
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
