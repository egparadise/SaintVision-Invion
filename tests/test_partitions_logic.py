"""Partition month arithmetic (CR-06), without a database.

The DDL side is covered by ``test_database.py``; this pins the date maths that
decides how far ahead partitions exist, because an off-by-one month here is what
would exhaust them in production.
"""

from __future__ import annotations

import datetime as dt

import pytest

from saintvision.db.partitions import add_months, month_floor, partition_name

UTC = dt.timezone.utc


def test_month_floor_discards_everything_below_the_month():
    moment = dt.datetime(2026, 9, 9, 16, 20, 5, 123456, tzinfo=UTC)
    assert month_floor(moment) == dt.datetime(2026, 9, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    "start,count,expected",
    [
        ((2026, 9, 1), 1, (2026, 10, 1)),
        ((2026, 9, 1), 3, (2026, 12, 1)),
        # The year boundary is where naive month arithmetic breaks.
        ((2026, 10, 1), 3, (2027, 1, 1)),
        ((2026, 12, 1), 1, (2027, 1, 1)),
        ((2026, 1, 1), -1, (2025, 12, 1)),
        ((2026, 3, 1), -3, (2025, 12, 1)),
        ((2026, 9, 1), 0, (2026, 9, 1)),
        ((2026, 9, 1), 12, (2027, 9, 1)),
    ],
)
def test_add_months_crosses_year_boundaries(start, count, expected):
    got = add_months(dt.datetime(*start, tzinfo=UTC), count)
    assert got == dt.datetime(*expected, tzinfo=UTC)


def test_partition_name_is_stable_and_sortable():
    assert partition_name("audit_events", dt.datetime(2026, 9, 1, tzinfo=UTC)) == "audit_events_p202609"
    # Zero-padded so lexical order matches chronological order, which the drop
    # job relies on.
    assert partition_name("audit_events", dt.datetime(2027, 1, 1, tzinfo=UTC)) == "audit_events_p202701"
    names = [
        partition_name("t", dt.datetime(2026, m, 1, tzinfo=UTC)) for m in (9, 10, 11, 12)
    ] + [partition_name("t", dt.datetime(2027, 1, 1, tzinfo=UTC))]
    assert names == sorted(names)


def test_three_month_lead_survives_two_missed_jobs():
    """The reason the lead is 3 and not 1 (CR-06).

    With a lead of 3 created in September, a monthly job that fails in October
    and again in November still leaves December covered.
    """
    start = month_floor(dt.datetime(2026, 9, 15, tzinfo=UTC))
    covered = {add_months(start, offset) for offset in range(4)}
    assert dt.datetime(2026, 12, 1, tzinfo=UTC) in covered
    assert dt.datetime(2027, 1, 1, tzinfo=UTC) not in covered
