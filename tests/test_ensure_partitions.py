"""The runner for a mechanism that only migrations ever invoked.

``ensure_partitions`` has been there since the first migration, so a deployment
holds exactly the partitions that existed when it was last migrated — three
months' worth. A range-partitioned table refuses the insert when it runs past its
last bound, so this arrives as a failed Evidence write rather than as a warning.

What is tested here is mostly that ``--check`` can fail. A guard that only ever
returns zero is the thing this tool was written to replace.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.postgres

TOOL = Path(__file__).resolve().parents[1] / "tools" / "ensure_partitions.py"


@pytest.fixture
def dsn(migrated, database_url) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://")


def _run(dsn: str, *args: str) -> tuple[dict, int]:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--dsn", dsn, "--json", *args],
        capture_output=True,
        text=True,
    )
    assert completed.stdout, completed.stderr
    return json.loads(completed.stdout), completed.returncode


def test_check_creates_nothing(dsn: str) -> None:
    """DDL against a live database is not something a report should do."""
    before, _ = _run(dsn, "--check")
    after, _ = _run(dsn, "--check")
    assert before["created"] == [] and after["created"] == []
    assert before["tables"] == after["tables"]


def test_check_fails_when_the_runway_is_shorter_than_the_margin(dsn: str) -> None:
    """The point of the tool. A guard that cannot fail is not a guard."""
    report, code = _run(dsn, "--check", "--margin-days", "3650")
    assert code == 1
    assert report["short"], "every table should be under a ten year margin"


def test_check_passes_when_the_runway_clears_the_margin(dsn: str) -> None:
    report, code = _run(dsn, "--check", "--margin-days", "1")
    assert code == 0
    assert report["short"] == []


def _lead_beyond_current(dsn: str, extra: int) -> str:
    """A lead that is guaranteed to be new work on this database.

    The PostgreSQL database is session-scoped and shared, and the test order is
    randomised, so a fixed lead is only "more than exists" until another test
    extends past it. Deriving it from the current state keeps each test true
    whatever ran first.
    """
    report, _ = _run(dsn, "--check")
    return str(max(t["monthsAhead"] for t in report["tables"]) + extra)


def test_apply_creates_the_missing_partitions_and_is_idempotent(dsn: str) -> None:
    lead = _lead_beyond_current(dsn, 2)
    first, _ = _run(dsn, "--apply", "--lead-months", lead)
    assert first["created"], "a lead beyond the current runway must create something"
    again, _ = _run(dsn, "--apply", "--lead-months", lead)
    assert again["created"] == [], "re-running must create nothing"


def test_apply_extends_the_runway_it_reports(dsn: str) -> None:
    """The number an operator acts on has to move when they act."""
    before, _ = _run(dsn, "--check")
    baseline = {t["table"]: t["runwayDays"] for t in before["tables"]}
    after, _ = _run(dsn, "--apply", "--lead-months", _lead_beyond_current(dsn, 3))
    for table in after["tables"]:
        assert table["runwayDays"] > baseline[table["table"]]


def test_every_partitioned_table_is_covered_not_just_evidence(dsn: str) -> None:
    """Evidence is the one that hurts most, but it is not the only one.

    audit_events records who did what, and losing writes there during an
    incident removes the record of the incident.
    """
    report, _ = _run(dsn, "--check")
    covered = {t["table"] for t in report["tables"]}
    assert {"evidence_envelopes", "audit_events", "resource_snapshots"} <= covered


def test_runway_is_measured_in_days_not_whole_months(dsn: str) -> None:
    """Whole-month counting reaches zero only after inserts start failing.

    The margin is in days for the same reason the alarm's threshold is: a
    warning has to arrive while there is still time to act.
    """
    report, _ = _run(dsn, "--check")
    for table in report["tables"]:
        bound = dt.datetime.fromisoformat(table["latestBound"])
        remaining = (bound - dt.datetime.now(dt.timezone.utc)).days
        # Within a day of the tool's own arithmetic, and not a multiple of 30.
        assert abs(table["runwayDays"] - remaining) <= 1
