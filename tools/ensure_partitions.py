"""Create the monthly partitions the next few months will need.

``ensure_partitions`` has existed since the first migration and only migrations
call it, so a deployment has exactly the partitions that existed the day it was
last migrated. They were created three months ahead. A range-partitioned table
does not degrade when it runs past its last bound — it refuses the insert — so
the Evidence write fails outright, and the first anyone hears of it is a P1 for
something that was on a calendar for months.

This is the runner. It does not decide anything ``ensure_partitions`` does not
already decide; it exists because a mechanism nobody invokes is not a mechanism.

**Reporting is the default.** Creating a partition is DDL against a live
database, so ``--apply`` is explicit and ``--check`` is what runs unattended.
``--check`` exits non-zero when the runway is shorter than the margin, which is
what makes it usable as a guard rather than something to read.

**A command is not a schedule.** An operator who has to remember this is the same
arrangement that produced the gap it closes. The cadence belongs in whatever runs
periodic work on the control plane host; until that exists, ``tools/alarm_check.py``
is the safety net and it warns in days of runway rather than after the fact.

Usage:
    python tools/ensure_partitions.py --dsn DSN --check [--margin-days 45]
    python tools/ensure_partitions.py --dsn DSN --apply [--lead-months 3]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

#: How much runway a --check run insists on. Longer than the P1 alarm's 30 days
#: on purpose: this is meant to fail while there is still time to act calmly,
#: not to agree with the alarm about how bad things already are.
DEFAULT_MARGIN_DAYS = 45


def _engine(dsn: str):
    from sqlalchemy import create_engine

    url = dsn
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return create_engine(url, future=True)


def survey(dsn: str, now: dt.datetime) -> list[dict[str, Any]]:
    from saintvision.db.partitions import partition_status

    engine = _engine(dsn)
    try:
        with engine.connect() as connection:
            return [
                {
                    "table": status.table,
                    "monthsAhead": status.months_ahead,
                    "latestBound": status.latest_bound,
                    "runwayDays": (
                        (status.latest_bound - now).days if status.latest_bound else -1
                    ),
                }
                for status in partition_status(connection, now=now)
            ]
    finally:
        engine.dispose()


def create(dsn: str, now: dt.datetime, lead_months: int) -> list[str]:
    from saintvision.db.partitions import ensure_partitions

    engine = _engine(dsn)
    try:
        # Its own transaction, and idempotent: re-running creates nothing, so a
        # scheduled invocation that overlaps a manual one is harmless.
        with engine.begin() as connection:
            return ensure_partitions(connection, now=now, lead_months=lead_months)
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True, help="schema owner DSN; this issues DDL")
    parser.add_argument("--lead-months", type=int, default=3)
    parser.add_argument("--margin-days", type=int, default=DEFAULT_MARGIN_DAYS)
    parser.add_argument("--json", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report only; creates nothing")
    mode.add_argument("--apply", action="store_true", help="create the missing partitions")
    args = parser.parse_args()
    if args.lead_months < 1:
        parser.error("--lead-months must be at least 1")

    now = dt.datetime.now(dt.timezone.utc)
    created: list[str] = []
    if args.apply:
        created = create(args.dsn, now, args.lead_months)
    after = survey(args.dsn, now)
    short = [t for t in after if t["runwayDays"] < args.margin_days]

    if args.json:
        print(json.dumps({"created": created, "tables": after, "short": short}, indent=2, default=str))
        return 1 if short else 0

    if args.apply:
        print(f"created {len(created)} partition(s)")
        for name in created:
            print(f"  + {name}")
        if not created:
            print("  (nothing was missing)")
    for table in after:
        bound = table["latestBound"]
        mark = "SHORT " if table["runwayDays"] < args.margin_days else "ok    "
        print(
            f"  {mark} {table['table']}: {table['runwayDays']} day(s) of runway, "
            f"to {bound:%Y-%m-%d}" if bound else f"  {mark} {table['table']}: no partition"
        )
    if short:
        print(
            f"\nUnder the {args.margin_days} day margin. Run with --apply, and put "
            f"that on a schedule: a range-partitioned table refuses the insert "
            f"when it runs out, so this becomes a failed Evidence write rather "
            f"than a slow query."
        )
    return 1 if short else 0


if __name__ == "__main__":
    raise SystemExit(main())
