"""PITR readiness assessment (VF-CL-04 operations).

The ``assess`` verdict is a pure function and is tested without a database; the
integration case confirms the tool reads a real cluster and returns the honest
"absent" for a default one, which is the whole point -- a default PostgreSQL has
no point-in-time recovery, and the tool must say so rather than imply a backup
covers it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from pitr_readiness import assess, read_settings  # noqa: E402


_POSSIBLE = {"archive_mode": "on", "archive_command": "cp %p /arc/%f", "wal_level": "replica", "archive_library": ""}


def test_a_fully_configured_cluster_is_possible():
    assert assess(_POSSIBLE)["verdict"] == "possible"


def test_archive_mode_off_is_absent():
    v = assess({**_POSSIBLE, "archive_mode": "off"})
    assert v["verdict"] == "absent"
    assert any("archive_mode" in r for r in v["reasons"])


@pytest.mark.parametrize("command", ["", "(disabled)", "off"])
def test_an_empty_or_disabled_archive_command_is_absent(command):
    v = assess({**_POSSIBLE, "archive_command": command})
    assert v["verdict"] == "absent"
    assert any("archive_command" in r for r in v["reasons"])


def test_wal_level_below_replica_is_absent():
    v = assess({**_POSSIBLE, "wal_level": "minimal"})
    assert v["verdict"] == "absent"
    assert any("wal_level" in r for r in v["reasons"])


def test_an_unread_setting_is_inconclusive_never_absent():
    """A None (unread) setting must not read as a checked 'off'."""
    v = assess({**_POSSIBLE, "archive_command": None})
    assert v["verdict"] == "inconclusive"
    assert v["verdict"] != "absent"


def test_always_counts_as_on_and_logical_exceeds_replica():
    assert assess({**_POSSIBLE, "archive_mode": "always", "wal_level": "logical"})[
        "verdict"
    ] == "possible"


@pytest.mark.postgres
def test_a_default_cluster_reads_as_absent(database_url):
    """The honest verdict on a stock PostgreSQL: archive_mode off -> no PITR.

    This mirrors the CL-05 finding at the tool level: the check is able to produce
    the negative, so a passing 'possible' elsewhere would mean something.
    """
    # psycopg wants a libpq DSN, not the SQLAlchemy '+psycopg' URL.
    dsn = database_url.replace("postgresql+psycopg://", "postgresql://")
    settings = read_settings(dsn)
    assert settings["archive_mode"] is not None  # the setting was actually read
    verdict = assess(settings)
    assert verdict["verdict"] == "absent"
    assert any("archive_mode" in r for r in verdict["reasons"])
