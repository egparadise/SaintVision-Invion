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

from pitr_archive_retention import BaseBackup, apply, load_backups, plan  # noqa: E402

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
    backups = [backup("b1", 2, days_ago=20), backup("b2", 10, days_ago=9), backup("b3", 20, days_ago=2)]
    archive = [seg(i) for i in range(1, 30)] + [f"{seg(2)}.00000028.backup", f"{seg(20)}.00000028.backup"]
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
            backup(f"b{i}", start=rng.randint(1, 60), days_ago=rng.uniform(0, 30)) for i in range(n_backups)
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
    cmd = [sys.executable, str(TOOL), "--archive", str(archive), "--backups", str(backups), "--days", "7", "--now", NOW.isoformat()]
    dry = subprocess.run(cmd, capture_output=True, text=True, check=True)
    report = json.loads(dry.stdout)
    assert report["mode"] == "dry-run" and report["deleteBackups"] == ["old"]
    assert report["deleteArchive"] == [seg(1), seg(2), seg(3), seg(4)]
    assert sorted(p.name for p in archive.iterdir()) == sorted([seg(i) for i in range(1, 8)] + ["00000001.history"])
    assert (backups / "old").is_dir()
    applied = subprocess.run(cmd + ["--apply"], capture_output=True, text=True, check=True)
    first, second = applied.stdout.split("}\n{", 1)
    removed = json.loads("{" + second)["removed"]
    assert json.loads(first + "}")["mode"] == "apply"
    assert removed == {"archive": [seg(1), seg(2), seg(3), seg(4)], "backups": ["old"]}
    assert sorted(p.name for p in archive.iterdir()) == sorted([seg(5), seg(6), seg(7), "00000001.history"])
    assert not (backups / "old").exists() and (backups / "recent").is_dir()


def test_apply_is_idempotent_on_already_absent_paths(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    p = plan([], [], retention_days=7, now=NOW)
    p.delete_archive = ["000000010000000000000001"]
    p.delete_backups = ["gone"]
    assert apply(p, tmp_path / "a", tmp_path / "b") == {"archive": [], "backups": []}
