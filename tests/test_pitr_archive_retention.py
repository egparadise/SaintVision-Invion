"""Retention planner invariants (VF-CL-04, 7-day pilot decision 2026-09-22).

No database: the planner is a pure function over file names and parsed backup labels, plus
one filesystem round-trip for the CLI (dry-run must not delete; --apply deletes exactly the
plan). The property test walks many synthetic archives and asserts the one invariant that
makes the tool safe: no WAL segment at or after the oldest retained backup's start segment
is ever a deletion candidate.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from pitr_archive_retention import (  # noqa: E402
    BaseBackup,
    RetentionApplyRefused,
    apply,
    load_backups,
    plan,
)

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
TOOL = Path(__file__).resolve().parents[1] / "tools" / "pitr_archive_retention.py"


def seg(n: int, tli: int = 1) -> str:
    return f"{tli:08X}{0:08X}{n:08X}"


def backup(name: str, start: int, days_ago: float, tli: int = 1) -> BaseBackup:
    return BaseBackup(name, seg(start, tli), NOW - timedelta(days=days_ago))


def test_no_backups_means_nothing_is_deletable():
    archive = [seg(i) for i in range(1, 6)] + ["00000001.history"]
    p = plan(archive, [], retention_days=7, now=NOW)
    assert p.delete_archive == [] and p.delete_backups == []
    assert p.kept_archive == len(archive)
    assert "no base backup" in p.reason


def test_newest_backup_is_retained_even_when_older_than_retention():
    old = backup("b-old", start=3, days_ago=30)
    p = plan([seg(i) for i in range(1, 8)], [old], retention_days=7, now=NOW)
    assert p.retained_backups == ["b-old"] and p.delete_backups == []
    assert p.oldest_retained_start_segment == seg(3)
    assert p.delete_archive == [seg(1), seg(2)]


def test_boundary_segment_itself_is_kept():
    b = backup("b", start=5, days_ago=1)
    p = plan([seg(4), seg(5), seg(6)], [b], retention_days=7, now=NOW)
    assert seg(5) not in p.delete_archive and seg(6) not in p.delete_archive
    assert p.delete_archive == [seg(4)]


def test_expired_backups_and_their_wal_go_but_retained_window_is_complete():
    backups = [
        backup("b1", 2, days_ago=20),
        backup("b2", 10, days_ago=9),
        backup("b3", 20, days_ago=2),
    ]
    archive = [seg(i) for i in range(1, 30)] + [
        f"{seg(2)}.00000028.backup",
        f"{seg(20)}.00000028.backup",
    ]
    p = plan(archive, backups, retention_days=7, now=NOW)
    assert p.delete_backups == ["b1", "b2"] and p.retained_backups == ["b3"]
    assert set(p.delete_archive) == {seg(i) for i in range(1, 20)} | {f"{seg(2)}.00000028.backup"}
    assert f"{seg(20)}.00000028.backup" not in p.delete_archive


def test_history_partial_and_other_timelines_are_never_candidates():
    b = backup("b", start=9, days_ago=0.5)
    archive = ["00000002.history", f"{seg(3)}.partial", seg(3, tli=2), seg(3), "README.txt"]
    p = plan(archive, [b], retention_days=7, now=NOW)
    assert p.delete_archive == [seg(3)]


def test_retention_days_must_be_positive():
    with pytest.raises(ValueError):
        plan([], [backup("b", 1, 0)], retention_days=0, now=NOW)


def test_property_retained_window_wal_is_never_a_candidate():
    rng = random.Random(20260922)
    for _ in range(300):
        n_backups = rng.randint(0, 5)
        backups = [
            backup(f"b{i}", start=rng.randint(1, 60), days_ago=rng.uniform(0, 30))
            for i in range(n_backups)
        ]
        archive = [seg(i) for i in range(1, 70) if rng.random() < 0.8]
        archive += [f"{seg(rng.randint(1, 69))}.00000028.backup" for _ in range(rng.randint(0, 3))]
        archive += ["00000001.history", f"{seg(rng.randint(1, 69))}.partial"]
        days = rng.randint(1, 14)
        p = plan(archive, backups, retention_days=days, now=NOW)
        if not backups:
            assert p.delete_archive == [] and p.delete_backups == []
            continue
        newest = max(backups, key=lambda b: (b.taken_at, b.name))
        assert newest.name in p.retained_backups
        retained = [b for b in backups if b.name in p.retained_backups]
        boundary = min(b.start_segment for b in retained)
        assert p.oldest_retained_start_segment == boundary
        for name in p.delete_archive:
            base = name[:24]
            assert name.endswith(".backup") or len(name) == 24
            assert base[8:] < boundary[8:], (name, boundary)
            assert not name.endswith((".history", ".partial"))
        for name in archive:
            if len(name) == 24 and name[8:] >= boundary[8:]:
                assert name not in p.delete_archive


def _write_backup(root: Path, name: str, start: str, when: datetime) -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "backup_label").write_text(
        f"START WAL LOCATION: 0/3000028 (file {start})\nSTART TIME: {when:%Y-%m-%d %H:%M:%S} UTC\n",
        encoding="utf-8",
    )


def test_cli_dry_run_deletes_nothing_and_apply_deletes_exactly_the_plan(tmp_path):
    archive = tmp_path / "wal_archive"
    backups = tmp_path / "backups"
    archive.mkdir()
    for i in range(1, 8):
        (archive / seg(i)).write_bytes(b"x")
    (archive / "00000001.history").write_bytes(b"h")
    _write_backup(backups, "old", seg(2), NOW - timedelta(days=20))
    _write_backup(backups, "recent", seg(5), NOW - timedelta(days=1))
    assert [b.name for b in load_backups(backups)] == ["old", "recent"]
    cmd = [
        sys.executable,
        str(TOOL),
        "--archive",
        str(archive),
        "--backups",
        str(backups),
        "--days",
        "7",
        "--now",
        NOW.isoformat(),
    ]
    dry = subprocess.run(cmd, capture_output=True, text=True, check=True)
    report = json.loads(dry.stdout)
    assert report["mode"] == "dry-run" and report["deleteBackups"] == ["old"]
    assert report["deleteArchive"] == [seg(1), seg(2), seg(3), seg(4)]
    assert sorted(p.name for p in archive.iterdir()) == sorted(
        [seg(i) for i in range(1, 8)] + ["00000001.history"]
    )
    assert (backups / "old").is_dir()
    applied = subprocess.run(cmd + ["--apply"], capture_output=True, text=True, check=True)
    first, second = applied.stdout.split("}\n{", 1)
    removed = json.loads("{" + second)["removed"]
    assert json.loads(first + "}")["mode"] == "apply"
    assert removed == {"archive": [seg(1), seg(2), seg(3), seg(4)], "backups": ["old"]}
    assert sorted(p.name for p in archive.iterdir()) == sorted(
        [seg(5), seg(6), seg(7), "00000001.history"]
    )
    assert not (backups / "old").exists() and (backups / "recent").is_dir()


def test_apply_is_idempotent_on_already_absent_paths(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    forged = plan([], [], retention_days=7, now=NOW)
    forged.delete_archive = ["000000010000000000000001"]
    forged.delete_backups = ["gone"]
    with pytest.raises(RetentionApplyRefused, match="plan changed before apply"):
        apply(forged, tmp_path / "a", tmp_path / "b")

    # Idempotency is a disk-derived plan, never permission to invent absent
    # candidates.  A completed receipt is archived before the next empty cycle.
    current = plan([], [], retention_days=7, now=NOW)
    assert apply(current, tmp_path / "a", tmp_path / "b") == {
        "archive": [],
        "backups": [],
    }
    assert apply(current, tmp_path / "a", tmp_path / "b") == {
        "archive": [],
        "backups": [],
    }
    archived = list((tmp_path / "b").glob(".pitr-retention-apply-journal.completed-*.json"))
    assert len(archived) == 1


# ---------------------------------------------------------------------------
# F-VFCL04-01 / F-VFCL04-02 (PR #147): label time handling is fail-closed
# ---------------------------------------------------------------------------

from pitr_archive_retention import UnknownAge, parse_backup_label, parse_start_time  # noqa: E402


def _label(start: str, start_time: str | None) -> str:
    text = f"START WAL LOCATION: 0/3000028 (file {start})\n"
    if start_time is not None:
        text += f"START TIME: {start_time}\n"
    return text


def test_revival_f01_unparseable_start_time_is_refused_not_guessed_from_mtime(tmp_path):
    """Before: three strptime formats failed silently -> directory mtime decided the age.
    An old-looking mtime made the backup a deletion candidate and could poison ``newest``."""
    old = tmp_path / "backups" / "old"
    old.mkdir(parents=True)
    (old / "backup_label").write_text(_label(seg(2), "yesterday-ish"), encoding="utf-8")
    with pytest.raises(ValueError, match=r"old/backup_label: START TIME not in"):
        load_backups(tmp_path / "backups")


def test_revival_f01_cli_refuses_the_whole_plan_and_apply_deletes_nothing(tmp_path):
    archive = tmp_path / "wal_archive"
    backups = tmp_path / "backups"
    archive.mkdir()
    for i in range(1, 8):
        (archive / seg(i)).write_bytes(b"x")
    _write_backup(backups, "recent", seg(5), NOW - timedelta(days=1))
    bad = backups / "bad"
    bad.mkdir()
    (bad / "backup_label").write_text(_label(seg(2), "2026-09-01 10:00:00 KST"), encoding="utf-8")
    cmd = [
        sys.executable,
        str(TOOL),
        "--archive",
        str(archive),
        "--backups",
        str(backups),
        "--days",
        "7",
        "--now",
        NOW.isoformat(),
        "--apply",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 3, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert (
        report["mode"] == "refused"
        and "KST" in report["error"]
        and "bad/backup_label" in report["error"]
    )
    assert report["deleteBackups"] == [] and report["deleteArchive"] == []
    assert sorted(p.name for p in archive.iterdir()) == [seg(i) for i in range(1, 8)]
    assert (backups / "bad").is_dir() and (backups / "recent").is_dir()


def test_revival_f01_missing_start_time_means_unknown_age_retained_and_never_newest():
    """Before: no START TIME -> mtime fallback.  Now: unknown age -> always retained, never the
    newest pick, and its start segment still bounds the WAL that is kept."""
    unknown = BaseBackup("unknown", seg(3), None)
    known_old = backup("known-old", start=10, days_ago=20)
    known_new = backup("known-new", start=20, days_ago=2)
    p = plan(
        [seg(i) for i in range(1, 30)], [unknown, known_old, known_new], retention_days=7, now=NOW
    )
    assert p.unknown_age_backups == ["unknown"]
    assert "unknown" in p.retained_backups and "unknown" not in p.delete_backups
    assert p.delete_backups == ["known-old"]  # the newest is still chosen among KNOWN ages
    assert p.oldest_retained_start_segment == seg(
        3
    )  # boundary did not advance past the unknown one
    assert p.delete_archive == [seg(1), seg(2)]
    assert "1 of unknown age" in p.reason


def test_unknown_age_only_means_everything_retained_and_no_newest_needed():
    p = plan([seg(1), seg(2), seg(3)], [BaseBackup("u", seg(2), None)], retention_days=7, now=NOW)
    assert p.retained_backups == ["u"] and p.delete_backups == [] and p.delete_archive == [seg(1)]


def test_parse_backup_label_marks_unknown_age_without_touching_the_filesystem():
    start, taken = parse_backup_label(_label(seg(4), None))
    assert start == seg(4) and isinstance(taken, UnknownAge)
    assert [b.taken_at for b in []] == []


@pytest.mark.parametrize(
    "raw, expected_utc",
    [
        ("2026-09-28 10:00:00 UTC", datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)),
        ("2026-09-28 10:00:00 GMT", datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)),
        ("2026-09-28 10:00:00 +0900", datetime(2026, 9, 28, 1, 0, tzinfo=timezone.utc)),
        ("2026-09-28 10:00:00 +09:00", datetime(2026, 9, 28, 1, 0, tzinfo=timezone.utc)),
        ("2026-09-28 10:00:00 -0500", datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)),
        ("2026-09-28 10:00:00+0900", datetime(2026, 9, 28, 1, 0, tzinfo=timezone.utc)),
    ],
)
def test_revival_f02_numeric_offsets_and_explicit_utc_parse_to_the_right_instant(raw, expected_utc):
    assert parse_start_time(raw) == expected_utc


@pytest.mark.parametrize(
    "raw",
    [
        "2026-09-28 10:00:00 KST",  # PostgreSQL server-zone abbreviation: was stamped UTC (9 h error) or fell back
        "2026-09-28 10:00:00 EST",
        "2026-09-28 10:00:00 CET",
        "2026-09-28 10:00:00",  # naive: ambiguous, was silently stamped UTC
        "2026-09-28T10:00:00Z",  # ISO form PostgreSQL never writes
        "yesterday-ish",
    ],
)
def test_revival_f02_named_non_utc_and_naive_times_are_rejected_never_stamped_utc(raw):
    with pytest.raises(ValueError):
        parse_start_time(raw)
    start, taken = None, None
    with pytest.raises(ValueError):
        start, taken = parse_backup_label(_label(seg(1), raw))
    assert start is None and taken is None


def test_revival_f02_result_does_not_depend_on_the_runner_local_zone(monkeypatch):
    """The old %Z path accepted only UTC/GMT and the runner's own tzname, so a KST label parsed
    on a KST runner and failed elsewhere.  The new rule is the same everywhere."""
    import time as _time

    monkeypatch.setattr(_time, "tzname", ("KST", "KST"), raising=False)
    with pytest.raises(ValueError, match="named non-UTC"):
        parse_start_time("2026-09-28 10:00:00 KST")
    assert parse_start_time("2026-09-28 10:00:00 +0900") == datetime(
        2026, 9, 28, 1, 0, tzinfo=timezone.utc
    )


def test_property_unknown_age_backups_are_retained_and_bound_the_wal_and_never_pick_newest():
    rng = random.Random(20260928)
    for _ in range(300):
        n_known = rng.randint(0, 4)
        n_unknown = rng.randint(0, 3)
        backups = [
            backup(f"k{i}", start=rng.randint(1, 60), days_ago=rng.uniform(0, 30))
            for i in range(n_known)
        ]
        backups += [BaseBackup(f"u{i}", seg(rng.randint(1, 60)), None) for i in range(n_unknown)]
        archive = [seg(i) for i in range(1, 70) if rng.random() < 0.8]
        days = rng.randint(1, 14)
        p = plan(archive, backups, retention_days=days, now=NOW)
        if not backups:
            assert p.delete_archive == [] and p.delete_backups == []
            continue
        unknown_names = {b.name for b in backups if b.taken_at is None}
        assert set(p.unknown_age_backups) == unknown_names
        assert unknown_names <= set(p.retained_backups)
        assert not (unknown_names & set(p.delete_backups))
        known = [b for b in backups if b.taken_at is not None]
        if known:
            newest = max(known, key=lambda b: (b.taken_at, b.name))
            assert newest.name in p.retained_backups
        else:
            assert p.delete_backups == []
        retained = [b for b in backups if b.name in p.retained_backups]
        boundary = min(b.start_segment for b in retained)
        assert p.oldest_retained_start_segment == boundary
        for b in backups:
            if b.taken_at is None:
                assert b.start_segment[8:] >= boundary[8:]
        for name in p.delete_archive:
            assert name[8:24] < boundary[8:]


def test_revival_f01_filesystem_seam_missing_start_time_never_reads_directory_mtime(tmp_path):
    """Kills the seam mutant that swaps ``UnknownAge`` back for ``child.stat().st_mtime`` in
    ``load_backups``: a real label without START TIME whose directory mtime is far older than
    the cutoff must still come back with ``taken_at is None`` and be retained by ``plan``."""
    import os

    backups = tmp_path / "backups"
    no_time = backups / "no-time"
    no_time.mkdir(parents=True)
    (no_time / "backup_label").write_text(_label(seg(3), None), encoding="utf-8")
    ancient = (NOW - timedelta(days=400)).timestamp()
    os.utime(no_time, (ancient, ancient))
    os.utime(no_time / "backup_label", (ancient, ancient))
    _write_backup(backups, "known-old", seg(10), NOW - timedelta(days=20))
    _write_backup(backups, "known-new", seg(20), NOW - timedelta(days=2))

    loaded = load_backups(backups)
    by_name = {b.name: b for b in loaded}
    assert by_name["no-time"].taken_at is None  # not a datetime built from st_mtime
    assert by_name["no-time"].start_segment == seg(3)
    assert by_name["known-new"].taken_at == NOW - timedelta(days=2)

    p = plan([seg(i) for i in range(1, 30)], loaded, retention_days=7, now=NOW)
    assert p.unknown_age_backups == ["no-time"]
    assert "no-time" in p.retained_backups and "no-time" not in p.delete_backups
    assert p.delete_backups == ["known-old"]  # newest still chosen among KNOWN ages only
    assert p.oldest_retained_start_segment == seg(
        3
    )  # boundary did not advance past the unknown one
    assert p.delete_archive == [seg(1), seg(2)]


@pytest.mark.parametrize(
    "raw, expected_utc",
    [
        (
            "2026-09-22 01:30:00+00",
            datetime(2026, 9, 22, 1, 30, tzinfo=timezone.utc),
        ),  # PostgreSQL nameless-zone abbreviation / timestamptz text
        ("2026-09-22 01:30:00 +00", datetime(2026, 9, 22, 1, 30, tzinfo=timezone.utc)),
        ("2026-09-22 10:30:00 +09", datetime(2026, 9, 22, 1, 30, tzinfo=timezone.utc)),
        ("2026-09-22 07:00:00 +05:30", datetime(2026, 9, 22, 1, 30, tzinfo=timezone.utc)),
        ("2026-09-21 20:30:00 -05", datetime(2026, 9, 22, 1, 30, tzinfo=timezone.utc)),
    ],
)
def test_f02_hour_only_and_half_hour_numeric_offsets_are_accepted(raw, expected_utc):
    """hosted Backend on head 29a2b131 (run 36362748049) rejected the ``+00`` form PostgreSQL writes for
    nameless zones; it is a numeric offset, not a named abbreviation, and must be accepted."""
    assert parse_start_time(raw) == expected_utc


@pytest.mark.parametrize(
    "raw", ["2026-09-22 01:30:00 +0", "2026-09-22 01:30:00 +000", "2026-09-22 01:30:00 +09:0"]
)
def test_f02_malformed_numeric_offsets_are_still_rejected(raw):
    with pytest.raises(ValueError):
        parse_start_time(raw)
