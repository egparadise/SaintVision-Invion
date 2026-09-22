"""Tier-A WAL-archive / base-backup retention planner (VF-CL-04, decision 2026-09-22: 7 days, pilot).

The local archive (``docker-compose.pitr.yml`` ``/wal_archive``) grows without bound;
the runbook needs a cleanup that can never destroy point-in-time recoverability.
This tool PLANS a cleanup from two directories and only deletes with ``--apply``:

* ``--archive DIR``  -- WAL segments (24 hex), ``*.backup`` labels, ``*.history``,
  ``*.partial`` as written by ``archive_command``.
* ``--backups DIR``  -- one sub-directory per physical base backup (``pg_basebackup -D``),
  each holding a ``backup_label`` whose ``START WAL LOCATION: ... (file <SEG>)`` names
  the first WAL segment that backup needs.

Invariants (tested in ``tests/test_pitr_archive_retention.py``):

1. The NEWEST base backup is always retained, whatever its age -- retention must never
   leave the archive with no restorable base.
2. A base backup is a deletion candidate only when it is older than ``--days`` AND it is
   not the newest.
3. Every WAL segment at or after the START segment of the OLDEST RETAINED backup is kept
   (same timeline), so recovery from that backup to "now" stays complete. Only segments
   strictly before it, and their ``*.backup`` labels, are candidates.
4. ``*.history`` and ``*.partial`` files are never candidates. Segments on a timeline other
   than the oldest retained backup's are never candidates (conservative: a timeline switch
   is an operator event, not this tool's).
5. With no retained backup (empty backups dir) NOTHING in the archive is a candidate --
   an archive without a base is unrecoverable already, and deleting WAL cannot help.

The default is a dry run that prints the plan as JSON. ``--apply`` deletes exactly the
planned paths after printing that same plan, and reports what was removed. Nothing is
ever downloaded, and no DSN is read: this is a filesystem-only operator tool.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEGMENT = re.compile(r"^[0-9A-F]{24}$")
LABEL = re.compile(r"^([0-9A-F]{24})\.[0-9A-F]{8}\.backup$")
START_WAL = re.compile(r"START WAL LOCATION:.*\(file ([0-9A-F]{24})\)")
START_TIME = re.compile(r"START TIME:\s*(.+)$", re.M)

DEFAULT_DAYS = 7  # decision 2026-09-22 (coordinator, user delegation) -- pilot value


@dataclass(frozen=True)
class BaseBackup:
    name: str
    start_segment: str
    taken_at: datetime


@dataclass
class Plan:
    retention_days: int
    now: str
    retained_backups: list[str] = field(default_factory=list)
    oldest_retained_start_segment: str | None = None
    delete_backups: list[str] = field(default_factory=list)
    delete_archive: list[str] = field(default_factory=list)
    kept_archive: int = 0
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "scope": "filesystem-plan-only",
            "retentionDays": self.retention_days,
            "now": self.now,
            "retainedBackups": self.retained_backups,
            "oldestRetainedStartSegment": self.oldest_retained_start_segment,
            "deleteBackups": self.delete_backups,
            "deleteArchive": self.delete_archive,
            "keptArchiveEntries": self.kept_archive,
            "reason": self.reason,
        }


def _timeline(segment: str) -> str:
    return segment[:8]


def _position(segment: str) -> str:
    return segment[8:]


def parse_backup_label(text: str, fallback_time: datetime) -> tuple[str, datetime]:
    m = START_WAL.search(text)
    if not m:
        raise ValueError("backup_label without START WAL LOCATION")
    t = START_TIME.search(text)
    taken = fallback_time
    if t:
        raw = t.group(1).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                taken = datetime.strptime(raw, fmt)
                if taken.tzinfo is None:
                    taken = taken.replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
    return m.group(1), taken


def load_backups(backups_dir: Path) -> list[BaseBackup]:
    found: list[BaseBackup] = []
    if not backups_dir.is_dir():
        return found
    for child in sorted(backups_dir.iterdir()):
        label = child / "backup_label"
        if not child.is_dir() or not label.is_file():
            continue
        fallback = datetime.fromtimestamp(child.stat().st_mtime, timezone.utc)
        start, taken = parse_backup_label(label.read_text(encoding="utf-8", errors="replace"), fallback)
        found.append(BaseBackup(child.name, start, taken))
    return found


def load_archive(archive_dir: Path) -> list[str]:
    if not archive_dir.is_dir():
        return []
    return sorted(p.name for p in archive_dir.iterdir() if p.is_file())


def plan(archive: list[str], backups: list[BaseBackup], *, retention_days: int, now: datetime) -> Plan:
    """Pure planning function. ``archive`` is a list of file NAMES; ``backups`` parsed labels."""
    result = Plan(retention_days=retention_days, now=now.isoformat())
    if retention_days < 1:
        raise ValueError("retention_days must be >= 1")
    if not backups:
        result.kept_archive = len(archive)
        result.reason = "no base backup: nothing is deletable (archive without a base is not recoverable; deleting WAL cannot help)"
        return result
    cutoff = now - timedelta(days=retention_days)
    newest = max(backups, key=lambda b: (b.taken_at, b.name))
    retained = [b for b in backups if b.taken_at >= cutoff or b is newest]
    result.retained_backups = sorted(b.name for b in retained)
    result.delete_backups = sorted(b.name for b in backups if b not in retained)
    # The boundary is the SMALLEST start segment among retained backups -- not the start of
    # the oldest-by-time backup. If label times and WAL positions ever disagree, keeping WAL
    # from the smallest position is the only choice that keeps every retained backup
    # restorable (found by the property test, not by inspection).
    boundary = min(b.start_segment for b in retained)
    result.oldest_retained_start_segment = boundary
    tli = _timeline(boundary)
    for name in archive:
        seg = None
        if SEGMENT.match(name):
            seg = name
        else:
            m = LABEL.match(name)
            if m:
                seg = m.group(1)
        if seg is None:  # .history, .partial, anything else: never a candidate
            result.kept_archive += 1
            continue
        if _timeline(seg) != tli or _position(seg) >= _position(boundary):
            result.kept_archive += 1
            continue
        result.delete_archive.append(name)
    result.delete_archive.sort()
    result.reason = (
        f"retain backups newer than {cutoff.isoformat()} plus the newest; "
        f"keep WAL from {boundary} onward on timeline {tli}"
    )
    return result


def apply(plan_: Plan, archive_dir: Path, backups_dir: Path) -> dict:
    removed = {"archive": [], "backups": []}
    for name in plan_.delete_archive:
        target = archive_dir / name
        if target.is_file():
            target.unlink()
            removed["archive"].append(name)
    for name in plan_.delete_backups:
        target = backups_dir / name
        if target.is_dir():
            shutil.rmtree(target)
            removed["backups"].append(name)
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive", required=True, help="WAL archive directory")
    parser.add_argument("--backups", required=True, help="directory of base-backup sub-directories")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"retention in days (default {DEFAULT_DAYS}, pilot decision)")
    parser.add_argument("--apply", action="store_true", help="delete the planned paths (default: dry run)")
    parser.add_argument("--now", default=None, help="override the clock (ISO 8601, UTC) for reproducible plans")
    args = parser.parse_args(argv)
    now = datetime.fromisoformat(args.now).astimezone(timezone.utc) if args.now else datetime.now(timezone.utc)
    archive_dir, backups_dir = Path(args.archive), Path(args.backups)
    plan_ = plan(load_archive(archive_dir), load_backups(backups_dir), retention_days=args.days, now=now)
    report = plan_.as_dict()
    report["mode"] = "apply" if args.apply else "dry-run"
    print(json.dumps(report, indent=2))
    if args.apply:
        removed = apply(plan_, archive_dir, backups_dir)
        print(json.dumps({"removed": removed}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
