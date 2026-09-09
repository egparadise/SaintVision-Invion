"""Monthly partition management for the range-partitioned tables.

CR-06. Without a partition an INSERT fails, and because the Evidence write and
the success transition share a transaction (ADR-008), a missing partition would
stop every Run from completing. So:

* partitions are created ``lead_months`` ahead (default 3, which survives two
  consecutive failures of a monthly job);
* there is **no DEFAULT partition** — a row landing in one would block
  attaching the real partition later, and Evidence is designed so that a
  missing record holds completion rather than being quietly absorbed;
* startup refuses to serve when fewer than ``minimum_months`` remain, rather
  than discovering it at the first failed insert.

The creation job and the retention drop job are deliberately separate
transactions: a failing drop must never prevent a create.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from .models import PARTITIONED_TABLES


class PartitionExhausted(RuntimeError):
    """Fewer partitions remain than the configured minimum."""


def month_floor(moment: dt.datetime) -> dt.datetime:
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def add_months(moment: dt.datetime, count: int) -> dt.datetime:
    total = moment.month - 1 + count
    year = moment.year + total // 12
    month = total % 12 + 1
    return moment.replace(year=year, month=month)


def partition_name(table: str, month_start: dt.datetime) -> str:
    return f"{table}_p{month_start:%Y%m}"


@dataclass(frozen=True, slots=True)
class PartitionStatus:
    table: str
    months_ahead: int
    latest_bound: dt.datetime | None


def ensure_partitions(
    connection: Connection,
    *,
    now: dt.datetime,
    lead_months: int = 3,
    tables: dict[str, str] | None = None,
) -> list[str]:
    """Create any missing monthly partitions from this month forward.

    Returns the names created. Idempotent: re-running creates nothing.
    """
    targets = PARTITIONED_TABLES if tables is None else tables
    created: list[str] = []
    start = month_floor(now)
    for table in targets:
        for offset in range(lead_months + 1):
            lower = add_months(start, offset)
            upper = add_months(lower, 1)
            name = partition_name(table, lower)
            exists = connection.execute(
                text("SELECT to_regclass(:qualified) IS NOT NULL"),
                {"qualified": f"public.{name}"},
            ).scalar_one()
            if exists:
                continue
            connection.execute(
                text(
                    f"CREATE TABLE {name} PARTITION OF {table} "
                    f"FOR VALUES FROM ('{lower:%Y-%m-%d}') TO ('{upper:%Y-%m-%d}')"
                )
            )
            created.append(name)
    return created


def partition_status(
    connection: Connection, *, now: dt.datetime, tables: dict[str, str] | None = None
) -> list[PartitionStatus]:
    """Report how many whole months of partitions remain for each table."""
    targets = PARTITIONED_TABLES if tables is None else tables
    start = month_floor(now)
    out: list[PartitionStatus] = []
    for table in targets:
        months = 0
        latest: dt.datetime | None = None
        # Walk forward from this month; the first gap ends the run, because a
        # partition beyond a gap does not help an insert landing in the gap.
        for offset in range(0, 60):
            lower = add_months(start, offset)
            exists = connection.execute(
                text("SELECT to_regclass(:qualified) IS NOT NULL"),
                {"qualified": f"public.{partition_name(table, lower)}"},
            ).scalar_one()
            if not exists:
                break
            months = offset + 1
            latest = add_months(lower, 1)
        out.append(PartitionStatus(table=table, months_ahead=months, latest_bound=latest))
    return out


def assert_partitions_available(
    connection: Connection,
    *,
    now: dt.datetime,
    minimum_months: int = 1,
    tables: dict[str, str] | None = None,
) -> list[PartitionStatus]:
    """Startup gate. Raises rather than letting the first insert discover it."""
    statuses = partition_status(connection, now=now, tables=tables)
    short = [s for s in statuses if s.months_ahead < minimum_months]
    if short:
        detail = ", ".join(f"{s.table}={s.months_ahead}mo" for s in short)
        raise PartitionExhausted(
            f"partition lead below minimum {minimum_months} month(s): {detail}"
        )
    return statuses


def drop_expired_partitions(
    connection: Connection,
    *,
    now: dt.datetime,
    retention_months: int,
    table: str,
) -> list[str]:
    """Drop whole partitions older than the retention window.

    Called in its own transaction, never together with ``ensure_partitions``.
    Only partitions strictly older than the cutoff month are dropped, so the
    month containing the cutoff is kept whole.
    """
    cutoff = add_months(month_floor(now), -retention_months)
    rows = connection.execute(
        text(
            "SELECT c.relname FROM pg_class c "
            "JOIN pg_inherits i ON i.inhrelid = c.oid "
            "JOIN pg_class p ON p.oid = i.inhparent "
            "WHERE p.relname = :table ORDER BY c.relname"
        ),
        {"table": table},
    ).scalars()
    dropped: list[str] = []
    prefix = f"{table}_p"
    for name in rows:
        if not name.startswith(prefix):
            continue
        stamp = name[len(prefix) :]
        if len(stamp) != 6 or not stamp.isdigit():
            continue
        month_start = dt.datetime(
            int(stamp[:4]), int(stamp[4:]), 1, tzinfo=cutoff.tzinfo
        )
        if month_start < cutoff:
            connection.execute(text(f"DROP TABLE {name}"))
            dropped.append(name)
    return dropped
