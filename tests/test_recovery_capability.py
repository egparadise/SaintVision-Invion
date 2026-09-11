"""What recovery a server is configured for, as opposed to what a drill measured.

A drill that takes a backup and restores it moments later reports a recovery
point of a few seconds however the server is configured. That number says the
restore worked; it is not the recovery point an incident would face, and signing
off an RPO target against it is signing off against a measurement that could not
have failed.

These tests cover the decision that separates the two, including the branch a
live server cannot easily be talked into.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from recovery_drill import _meets_operational_rpo, rpo_bound_from  # noqa: E402


def _settings(**overrides) -> dict[str, str]:
    base = {
        "wal_level": "replica",
        "archive_mode": "off",
        "archive_command": "(disabled)",
        "archive_timeout": "0",
        "data_checksums": "off",
        "full_page_writes": "on",
    }
    base.update(overrides)
    return base


def test_no_archiving_establishes_no_bound() -> None:
    """The state of this deployment: a restore works, PITR does not exist."""
    archiving, bound, basis = rpo_bound_from(_settings())
    assert archiving is False
    assert bound is None
    assert "no point-in-time recovery" in basis
    # And it says what it does not know, rather than filling in a plausible
    # number from the drill's own backup.
    assert "will not guess" in basis


def test_archiving_with_a_timeout_establishes_the_bound() -> None:
    archiving, bound, basis = rpo_bound_from(
        _settings(archive_mode="on", archive_command="/usr/bin/wal-push %p", archive_timeout="300")
    )
    assert (archiving, bound) == (True, 300)
    assert "300s" in basis


def test_archive_mode_always_counts_as_archiving() -> None:
    _, bound, _ = rpo_bound_from(
        _settings(archive_mode="always", archive_command="/bin/true", archive_timeout="60")
    )
    assert bound == 60


def test_archiving_on_with_no_timeout_establishes_nothing() -> None:
    """The awkward middle, and the reason this decision is a pure function.

    A server started with ``-c archive_timeout=300`` ignores ALTER SYSTEM, so
    this branch cannot be reached from a live instance without rebuilding one --
    which is how it went untested the first time.

    Switching archiving on is not the same as bounding the recovery point: with
    no timeout, a quiet period leaves a committed transaction sitting in a
    segment nobody ships.
    """
    archiving, bound, basis = rpo_bound_from(
        _settings(archive_mode="on", archive_command="/bin/true", archive_timeout="0")
    )
    assert archiving is True
    assert bound is None
    assert "indefinitely" in basis


def test_archive_mode_on_with_an_empty_command_is_not_archiving() -> None:
    """``archive_mode=on`` alone ships nothing. It is the pair that matters."""
    archiving, bound, _ = rpo_bound_from(_settings(archive_mode="on", archive_command="   "))
    assert (archiving, bound) == (False, None)


@pytest.mark.parametrize("target", [900, 60, 1])
def test_an_unestablished_bound_never_meets_a_target(target: int) -> None:
    report = {"recoveryCapability": {"operationalRpoBoundSeconds": None}}
    assert _meets_operational_rpo(report, target) is False


def test_a_bound_is_compared_against_the_target() -> None:
    report = {"recoveryCapability": {"operationalRpoBoundSeconds": 300}}
    assert _meets_operational_rpo(report, 900) is True
    assert _meets_operational_rpo(report, 300) is True
    assert _meets_operational_rpo(report, 60) is False


def test_no_target_asked_means_no_target_enforced() -> None:
    """The gate is opt-in, so an ordinary functional drill is not blocked by it.

    Asking for acceptance evidence is a deliberate act, and so is this flag.
    """
    report = {"recoveryCapability": {"operationalRpoBoundSeconds": None}}
    assert _meets_operational_rpo(report, None) is True
