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
6. Label time handling is fail-closed (F-VFCL04-01 / F-VFCL04-02, PR #147):
   a ``START TIME`` that is present but not parseable raises ``ValueError`` -- the whole
   plan is refused (CLI exit 3), the same policy this module already applied to a missing
   ``START WAL LOCATION``; a label WITHOUT ``START TIME`` gives the backup an UNKNOWN age
   (never the directory mtime): an unknown-age backup is always retained, never a
   deletion candidate, never the "newest" pick, and its start segment still bounds the
   WAL that is kept.  Accepted time forms are a numeric offset (``+00``/``+09``/``+0900``/
   ``+09:00``/``-05:30`` -- PostgreSQL abbreviates nameless zones as ``+HH``) or an
   explicit ``UTC``/``GMT``; a named non-UTC abbreviation (``KST``, ``EST``, ...) is
   rejected instead of being stamped UTC, and a naive time is rejected as ambiguous.

The default is a dry run that prints the plan as JSON. ``--apply`` deletes exactly the
planned paths after printing that same plan, and reports what was removed. Nothing is
ever downloaded, and no DSN is read: this is a filesystem-only operator tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

SEGMENT = re.compile(r"^[0-9A-F]{24}$")
LABEL = re.compile(r"^([0-9A-F]{24})\.[0-9A-F]{8}\.backup$")
START_WAL = re.compile(r"START WAL LOCATION:.*\(file ([0-9A-F]{24})\)")
START_TIME = re.compile(r"START TIME:\s*(.+)$", re.M)
_TIME_WITH_ZONE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\s*(\S+))?$")
_NUMERIC_OFFSET = re.compile(
    r"^[+-]\d{2}(?::?\d{2})?$"
)  # +00, +09, +0900, +09:00, -05:30 (PostgreSQL forms)
UTC_NAMES = ("UTC", "GMT", "Z")

DEFAULT_DAYS = 7  # decision 2026-09-22 (coordinator, user delegation) -- pilot value
APPLY_JOURNAL_SCHEMA = "inv.pitr-retention-apply-receipt.v1"
PARTIAL_FAILURE_CLASS = "RETENTION_APPLY_PARTIAL"


class RetentionApplyRefused(ValueError):
    """A stale or malformed journal/plan was rejected before another deletion."""


class RetentionApplyPartial(RuntimeError):
    """An apply attempt stopped after recording its partial progress."""

    def __init__(self, receipt: dict):
        super().__init__(PARTIAL_FAILURE_CLASS)
        self.receipt = receipt


@dataclass(frozen=True)
class BaseBackup:
    name: str
    start_segment: str
    taken_at: datetime | None  # None = unknown age (label had no START TIME): always retained


@dataclass
class UnknownAge:
    """Marker returned by ``parse_backup_label`` when the label carries no START TIME."""

    reason: str = "backup_label has no START TIME; age unknown, backup retained"


@dataclass
class Plan:
    retention_days: int
    now: str
    retained_backups: list[str] = field(default_factory=list)
    oldest_retained_start_segment: str | None = None
    delete_backups: list[str] = field(default_factory=list)
    delete_archive: list[str] = field(default_factory=list)
    kept_archive: int = 0
    unknown_age_backups: list[str] = field(default_factory=list)
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
            "unknownAgeBackups": self.unknown_age_backups,
            "reason": self.reason,
        }


def _timeline(segment: str) -> str:
    return segment[:8]


def _position(segment: str) -> str:
    return segment[8:]


def parse_start_time(raw: str) -> datetime:
    """Parse a PostgreSQL ``START TIME`` value into an aware UTC datetime, or raise.

    PostgreSQL writes ``%Y-%m-%d %H:%M:%S %Z`` in the SERVER time zone, so the zone token
    may be any abbreviation (``KST``, ``CET``, ...).  Only two forms carry an unambiguous
    instant: a numeric offset and an explicit ``UTC``/``GMT``.  Anything else is refused --
    a named non-UTC abbreviation must not be stamped UTC (up to hours of error, in the
    unsafe direction half of the time), and a naive time is ambiguous.
    """
    raw = raw.strip()
    m = _TIME_WITH_ZONE.match(raw)
    if not m:
        raise ValueError(f"START TIME not in '<date> <time> <zone>' form: {raw!r}")
    clock, zone = m.group(1), m.group(2)
    naive = datetime.strptime(clock, "%Y-%m-%d %H:%M:%S")
    if zone is None:
        raise ValueError(f"START TIME has no time zone; refusing to assume UTC: {raw!r}")
    if zone.upper() in UTC_NAMES:
        return naive.replace(tzinfo=timezone.utc)
    if _NUMERIC_OFFSET.match(zone):
        # PostgreSQL abbreviates zones without a name as ``+HH``/``-HH`` (e.g. ``+00``, ``+04``) and
        # renders timestamptz text as ``+00``/``+05:30``; normalise every form to ``+HHMM``.
        compact = zone.replace(":", "")
        if len(compact) == 3:
            compact += "00"
        return datetime.strptime(clock + " " + compact, "%Y-%m-%d %H:%M:%S %z").astimezone(
            timezone.utc
        )
    raise ValueError(
        f"START TIME zone {zone!r} is a named non-UTC abbreviation; only a numeric offset or UTC/GMT "
        f"is accepted (PostgreSQL writes the server zone; set timezone=UTC or log_timezone for labels): {raw!r}"
    )


def parse_backup_label(text: str) -> tuple[str, datetime | UnknownAge]:
    """Return ``(start_segment, taken_at)``; ``taken_at`` is ``UnknownAge`` when no START TIME.

    Both a missing START WAL LOCATION and an unparseable START TIME raise ``ValueError``
    (fail-closed: the operator gets an explicit error, never a plan built on a guessed
    age).  No filesystem time is ever substituted for the label time.
    """
    m = START_WAL.search(text)
    if not m:
        raise ValueError("backup_label without START WAL LOCATION")
    t = START_TIME.search(text)
    if not t:
        return m.group(1), UnknownAge()
    return m.group(1), parse_start_time(t.group(1))


def load_backups(backups_dir: Path) -> list[BaseBackup]:
    found: list[BaseBackup] = []
    if not backups_dir.is_dir():
        return found
    for child in sorted(backups_dir.iterdir()):
        label = child / "backup_label"
        if not child.is_dir() or not label.is_file():
            continue
        try:
            start, taken = parse_backup_label(label.read_text(encoding="utf-8", errors="replace"))
        except ValueError as error:
            raise ValueError(f"{child.name}/backup_label: {error}") from None
        found.append(
            BaseBackup(child.name, start, None if isinstance(taken, UnknownAge) else taken)
        )
    return found


def load_archive(archive_dir: Path) -> list[str]:
    if not archive_dir.is_dir():
        return []
    return sorted(p.name for p in archive_dir.iterdir() if p.is_file())


def plan(
    archive: list[str], backups: list[BaseBackup], *, retention_days: int, now: datetime
) -> Plan:
    """Pure planning function. ``archive`` is a list of file NAMES; ``backups`` parsed labels."""
    result = Plan(retention_days=retention_days, now=now.isoformat())
    if retention_days < 1:
        raise ValueError("retention_days must be >= 1")
    if not backups:
        result.kept_archive = len(archive)
        result.reason = "no base backup: nothing is deletable (archive without a base is not recoverable; deleting WAL cannot help)"
        return result
    cutoff = now - timedelta(days=retention_days)
    # Unknown-age backups (label without START TIME) are always retained and never take
    # part in the "newest" choice: a guessed age must not decide what gets deleted, and a
    # backup of unknown age must not shadow a known-age one as "the newest".
    known = [b for b in backups if b.taken_at is not None]
    unknown = [b for b in backups if b.taken_at is None]
    result.unknown_age_backups = sorted(b.name for b in unknown)
    newest = max(known, key=lambda b: (b.taken_at, b.name)) if known else None
    retained = [b for b in known if b.taken_at >= cutoff or b is newest] + unknown
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
        f"retain backups newer than {cutoff.isoformat()} plus the newest"
        + (f" plus {len(unknown)} of unknown age" if unknown else "")
        + f"; keep WAL from {boundary} onward on timeline {tli}"
    )
    return result


def _plan_contract(plan_: Plan) -> dict:
    """Stable semantic plan; wall-clock text and prose do not change a retry identity."""

    return {
        "retentionDays": plan_.retention_days,
        "retainedBackups": sorted(plan_.retained_backups),
        "oldestRetainedStartSegment": plan_.oldest_retained_start_segment,
        "deleteBackups": sorted(plan_.delete_backups),
        "deleteArchive": sorted(plan_.delete_archive),
        "unknownAgeBackups": sorted(plan_.unknown_age_backups),
    }


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _root_identity(root: Path) -> dict:
    try:
        info = root.stat(follow_symlinks=False)
    except OSError as error:
        raise RetentionApplyRefused("retention root is unavailable") from error
    if not stat.S_ISDIR(info.st_mode):
        raise RetentionApplyRefused("retention root must be a real directory")
    return {"device": int(info.st_dev), "inode": int(info.st_ino)}


def _label_sha256(backups_dir: Path, name: str) -> str:
    target = _candidate_path(backups_dir, name, "backups") / "backup_label"
    try:
        info = target.stat(follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            raise RetentionApplyRefused("backup label must be a regular file")
        return hashlib.sha256(target.read_bytes()).hexdigest()
    except FileNotFoundError as error:
        raise RetentionApplyRefused("backup label changed after planning") from error
    except OSError as error:
        raise RetentionApplyRefused("backup label is unavailable") from error


def _candidate_path(root: Path, name: str, kind: str) -> Path:
    if not isinstance(name, str) or not name or name in {".", ".."} or Path(name).name != name:
        raise RetentionApplyRefused("retention candidate is not a single path component")
    if kind == "archive" and not (SEGMENT.fullmatch(name) or LABEL.fullmatch(name)):
        raise RetentionApplyRefused("archive candidate is outside the closed WAL name set")
    return root / name


def _path_exists_no_follow(path: Path) -> bool:
    try:
        path.stat(follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def _candidate_identity(root: Path, name: str, kind: str) -> dict:
    path = _candidate_path(root, name, kind)
    try:
        info = path.stat(follow_symlinks=False)
    except OSError as error:
        raise RetentionApplyRefused("retention candidate is unavailable") from error
    expected_type = stat.S_ISREG if kind == "archive" else stat.S_ISDIR
    if not expected_type(info.st_mode):
        raise RetentionApplyRefused("retention candidate changed type")
    return {"device": int(info.st_dev), "inode": int(info.st_ino)}


def _journal_path(backups_dir: Path, journal_path: Path | None) -> Path:
    return journal_path or backups_dir / ".pitr-retention-apply-journal.json"


def _write_journal(path: Path, journal: dict) -> None:
    parent = path.parent
    if path.is_symlink() or not parent.is_dir():
        raise OSError("journal path is not a regular file target")
    temporary = parent / f".{path.name}.tmp-{os.getpid()}-{uuid4().hex}"
    data = (json.dumps(journal, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        # POSIX lets us fsync the directory entry after the atomic replace.
        # Windows refuses opening directories through os.open; the file bytes
        # were flushed and os.replace is atomic there, but no Python directory
        # handle exists to flush. Hosted/operator Linux exercises the stronger
        # boundary, while PG-free Windows tests can still verify replay logic.
        if os.name != "nt":
            directory_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _receipt(journal: dict) -> dict:
    return {
        "schemaVersion": journal["schemaVersion"],
        "status": journal["status"],
        "failureClass": journal["failureClass"],
        "planSha256": journal["planSha256"],
        "attemptCount": journal["attemptCount"],
        "removed": journal["receipt"]["removed"],
        "alreadyAbsent": journal["receipt"]["alreadyAbsent"],
        "incompleteCandidates": journal["receipt"]["incompleteCandidates"],
    }


def _refresh_incomplete(journal: dict) -> None:
    journal["receipt"]["incompleteCandidates"] = [
        {"kind": target["kind"], "name": target["name"]}
        for target in journal["targets"]
        if target["state"] == "pending"
    ]


def _new_journal(plan_: Plan, archive_dir: Path, backups_dir: Path) -> dict:
    contract = _plan_contract(plan_)
    # Close the plan/apply TOCTOU before the first durable journal or deletion.
    current = plan(
        load_archive(archive_dir),
        load_backups(backups_dir),
        retention_days=plan_.retention_days,
        now=datetime.fromisoformat(plan_.now),
    )
    if _plan_contract(current) != contract:
        raise RetentionApplyRefused("retention plan changed before apply")
    retained_labels = {name: _label_sha256(backups_dir, name) for name in plan_.retained_backups}
    candidate_labels = {name: _label_sha256(backups_dir, name) for name in plan_.delete_backups}
    targets = [
        {
            "kind": "archive",
            "name": name,
            "state": "pending",
            "identity": _candidate_identity(archive_dir, name, "archive"),
        }
        for name in plan_.delete_archive
    ] + [
        {
            "kind": "backups",
            "name": name,
            "state": "pending",
            "identity": _candidate_identity(backups_dir, name, "backups"),
        }
        for name in plan_.delete_backups
    ]
    journal = {
        "schemaVersion": APPLY_JOURNAL_SCHEMA,
        "planSha256": _digest(contract),
        "plan": contract,
        "roots": {"archive": _root_identity(archive_dir), "backups": _root_identity(backups_dir)},
        "retainedLabelSha256": retained_labels,
        "candidateBackupLabelSha256": candidate_labels,
        "targets": targets,
        "status": "running",
        "attemptCount": 1,
        "failureClass": None,
        "receipt": {
            "removed": {"archive": [], "backups": []},
            "alreadyAbsent": {"archive": [], "backups": []},
            "incompleteCandidates": [],
        },
    }
    _refresh_incomplete(journal)
    return journal


def _load_journal(path: Path) -> dict:
    try:
        info = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise RetentionApplyRefused("retention journal must be a single regular file")
        journal = json.loads(path.read_text(encoding="utf-8"))
    except RetentionApplyRefused:
        raise
    except (OSError, json.JSONDecodeError) as error:
        raise RetentionApplyRefused("retention journal is unreadable") from error
    expected = {
        "schemaVersion",
        "planSha256",
        "plan",
        "roots",
        "retainedLabelSha256",
        "candidateBackupLabelSha256",
        "targets",
        "status",
        "attemptCount",
        "failureClass",
        "receipt",
    }
    if not isinstance(journal, dict) or set(journal) != expected:
        raise RetentionApplyRefused("retention journal has an unknown schema")
    plan_keys = {
        "retentionDays",
        "retainedBackups",
        "oldestRetainedStartSegment",
        "deleteBackups",
        "deleteArchive",
        "unknownAgeBackups",
    }
    plan_value = journal["plan"]
    if (
        journal["schemaVersion"] != APPLY_JOURNAL_SCHEMA
        or not isinstance(plan_value, dict)
        or set(plan_value) != plan_keys
        or not isinstance(journal["planSha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", journal["planSha256"])
        or journal["planSha256"] != _digest(plan_value)
    ):
        raise RetentionApplyRefused("retention journal plan binding is invalid")
    list_keys = ("retainedBackups", "deleteBackups", "deleteArchive", "unknownAgeBackups")
    if (
        not isinstance(plan_value["retentionDays"], int)
        or isinstance(plan_value["retentionDays"], bool)
        or plan_value["retentionDays"] < 1
        or any(
            not isinstance(plan_value[key], list)
            or any(not isinstance(item, str) for item in plan_value[key])
            for key in list_keys
        )
        or (
            plan_value["oldestRetainedStartSegment"] is not None
            and not isinstance(plan_value["oldestRetainedStartSegment"], str)
        )
    ):
        raise RetentionApplyRefused("retention journal plan shape is invalid")
    roots = journal["roots"]
    if (
        not isinstance(roots, dict)
        or set(roots) != {"archive", "backups"}
        or any(
            not isinstance(identity, dict)
            or set(identity) != {"device", "inode"}
            or any(
                not isinstance(value, int) or isinstance(value, bool) or value < 0
                for value in identity.values()
            )
            for identity in roots.values()
        )
    ):
        raise RetentionApplyRefused("retention journal root identity is invalid")
    for key in ("retainedLabelSha256", "candidateBackupLabelSha256"):
        labels = journal[key]
        if not isinstance(labels, dict) or any(
            not isinstance(name, str)
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            for name, digest in labels.items()
        ):
            raise RetentionApplyRefused("retention journal label binding is invalid")
    targets = journal["targets"]
    if not isinstance(targets, list) or any(
        not isinstance(target, dict)
        or set(target) != {"kind", "name", "state", "identity"}
        or target["kind"] not in {"archive", "backups"}
        or not isinstance(target["name"], str)
        or target["state"] not in {"pending", "removed", "already-absent"}
        or not isinstance(target["identity"], dict)
        or set(target["identity"]) != {"device", "inode"}
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in target["identity"].values()
        )
        for target in targets
    ):
        raise RetentionApplyRefused("retention journal targets are invalid")
    receipt = journal["receipt"]
    if (
        journal["status"] not in {"running", "partial", "completed"}
        or not isinstance(journal["attemptCount"], int)
        or isinstance(journal["attemptCount"], bool)
        or journal["attemptCount"] < 1
        or journal["failureClass"] not in {None, PARTIAL_FAILURE_CLASS}
        or not isinstance(receipt, dict)
        or set(receipt) != {"removed", "alreadyAbsent", "incompleteCandidates"}
    ):
        raise RetentionApplyRefused("retention journal receipt is invalid")
    for key in ("removed", "alreadyAbsent"):
        bucket = receipt[key]
        if (
            not isinstance(bucket, dict)
            or set(bucket) != {"archive", "backups"}
            or any(
                not isinstance(names, list) or any(not isinstance(name, str) for name in names)
                for names in bucket.values()
            )
        ):
            raise RetentionApplyRefused("retention journal receipt is invalid")
    expected_receipt = {
        "removed": {
            kind: [
                target["name"]
                for target in targets
                if target["kind"] == kind and target["state"] == "removed"
            ]
            for kind in ("archive", "backups")
        },
        "alreadyAbsent": {
            kind: [
                target["name"]
                for target in targets
                if target["kind"] == kind and target["state"] == "already-absent"
            ]
            for kind in ("archive", "backups")
        },
        "incompleteCandidates": [
            {"kind": target["kind"], "name": target["name"]}
            for target in targets
            if target["state"] == "pending"
        ],
    }
    if receipt != expected_receipt:
        raise RetentionApplyRefused("retention journal receipt does not match target state")
    expected_failure = PARTIAL_FAILURE_CLASS if journal["status"] == "partial" else None
    if journal["failureClass"] != expected_failure:
        raise RetentionApplyRefused("retention journal failure class is invalid")
    return journal


def _validate_resume(journal: dict, plan_: Plan, archive_dir: Path, backups_dir: Path) -> None:
    if journal["roots"] != {
        "archive": _root_identity(archive_dir),
        "backups": _root_identity(backups_dir),
    }:
        raise RetentionApplyRefused("retention root identity changed")
    original = journal["plan"]
    current = _plan_contract(plan_)
    for key in (
        "retentionDays",
        "retainedBackups",
        "oldestRetainedStartSegment",
        "unknownAgeBackups",
    ):
        if current[key] != original[key]:
            raise RetentionApplyRefused("retention label or boundary changed")
    if not set(current["deleteArchive"]).issubset(original["deleteArchive"]) or not set(
        current["deleteBackups"]
    ).issubset(original["deleteBackups"]):
        raise RetentionApplyRefused("retention candidates changed")
    retained = {name: _label_sha256(backups_dir, name) for name in original["retainedBackups"]}
    if retained != journal["retainedLabelSha256"]:
        raise RetentionApplyRefused("retained backup label changed")
    target_keys = [(target.get("kind"), target.get("name")) for target in journal["targets"]]
    expected_keys = [("archive", name) for name in original["deleteArchive"]] + [
        ("backups", name) for name in original["deleteBackups"]
    ]
    if target_keys != expected_keys or any(
        target.get("state") not in {"pending", "removed", "already-absent"}
        for target in journal["targets"]
    ):
        raise RetentionApplyRefused("retention journal targets are invalid")
    for target in journal["targets"]:
        root = archive_dir if target["kind"] == "archive" else backups_dir
        path = _candidate_path(root, target["name"], target["kind"])
        if target["state"] != "pending" and _path_exists_no_follow(path):
            raise RetentionApplyRefused("a completed retention candidate reappeared")
        if target["state"] != "pending" or not _path_exists_no_follow(path):
            continue
        if _candidate_identity(root, target["name"], target["kind"]) != target["identity"]:
            raise RetentionApplyRefused("retention candidate identity changed")
        if target["kind"] == "backups":
            label = path / "backup_label"
            # rmtree can remove the label before a process dies. The journal's
            # directory inode proves this is still the authorised candidate;
            # a surviving label must retain its exact bytes as well.
            if _path_exists_no_follow(label) and (
                _label_sha256(backups_dir, target["name"])
                != journal["candidateBackupLabelSha256"][target["name"]]
            ):
                raise RetentionApplyRefused("candidate backup label changed")


def _delete_candidate(target: dict, archive_dir: Path, backups_dir: Path) -> bool:
    root = archive_dir if target["kind"] == "archive" else backups_dir
    path = _candidate_path(root, target["name"], target["kind"])
    try:
        info = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return False
    if {"device": int(info.st_dev), "inode": int(info.st_ino)} != target["identity"]:
        raise RetentionApplyRefused("retention candidate identity changed")
    if target["kind"] == "archive":
        if not stat.S_ISREG(info.st_mode):
            raise RetentionApplyRefused("archive candidate changed type")
        path.unlink()
    else:
        if not stat.S_ISDIR(info.st_mode):
            raise RetentionApplyRefused("backup candidate changed type")
        shutil.rmtree(path)
    return True


def apply(
    plan_: Plan, archive_dir: Path, backups_dir: Path, *, journal_path: Path | None = None
) -> dict:
    """Apply one semantic plan with a durable, resumable per-candidate journal."""

    journal_file = _journal_path(backups_dir, journal_path)
    invocation_removed = {"archive": [], "backups": []}
    if journal_file.exists() or journal_file.is_symlink():
        journal = _load_journal(journal_file)
        _validate_resume(journal, plan_, archive_dir, backups_dir)
        journal["attemptCount"] += 1
        journal["status"] = "running"
        journal["failureClass"] = None
    else:
        journal = _new_journal(plan_, archive_dir, backups_dir)
    try:
        _write_journal(journal_file, journal)
        for target in journal["targets"]:
            if target["state"] != "pending":
                continue
            removed = _delete_candidate(target, archive_dir, backups_dir)
            state = "removed" if removed else "already-absent"
            target["state"] = state
            journal["receipt"]["removed" if removed else "alreadyAbsent"][target["kind"]].append(
                target["name"]
            )
            if removed:
                invocation_removed[target["kind"]].append(target["name"])
            _refresh_incomplete(journal)
            _write_journal(journal_file, journal)
        journal["status"] = "completed"
        journal["failureClass"] = None
        _refresh_incomplete(journal)
        _write_journal(journal_file, journal)
        return invocation_removed
    except (OSError, RetentionApplyRefused) as error:
        journal["status"] = "partial"
        journal["failureClass"] = PARTIAL_FAILURE_CLASS
        _refresh_incomplete(journal)
        try:
            _write_journal(journal_file, journal)
        except OSError:
            pass
        raise RetentionApplyPartial(_receipt(journal)) from error


def load_apply_receipt(path: Path) -> dict:
    return _receipt(_load_journal(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive", required=True, help="WAL archive directory")
    parser.add_argument("--backups", required=True, help="directory of base-backup sub-directories")
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"retention in days (default {DEFAULT_DAYS}, pilot decision)",
    )
    parser.add_argument(
        "--apply", action="store_true", help="delete the planned paths (default: dry run)"
    )
    parser.add_argument(
        "--journal",
        default=None,
        help="durable apply journal (default: BACKUPS/.pitr-retention-apply-journal.json)",
    )
    parser.add_argument(
        "--now", default=None, help="override the clock (ISO 8601, UTC) for reproducible plans"
    )
    args = parser.parse_args(argv)
    now = (
        datetime.fromisoformat(args.now).astimezone(timezone.utc)
        if args.now
        else datetime.now(timezone.utc)
    )
    archive_dir, backups_dir = Path(args.archive), Path(args.backups)
    try:
        backups = load_backups(backups_dir)
    except ValueError as error:
        # Fail closed: an unreadable label time means no plan at all -- nothing is deleted
        # and the operator sees which label and why.  Exit 3 (argparse already owns 2).
        print(
            json.dumps(
                {
                    "scope": "filesystem-plan-only",
                    "mode": "refused",
                    "error": str(error),
                    "deleteBackups": [],
                    "deleteArchive": [],
                },
                indent=2,
            )
        )
        return 3
    plan_ = plan(load_archive(archive_dir), backups, retention_days=args.days, now=now)
    report = plan_.as_dict()
    report["mode"] = "apply" if args.apply else "dry-run"
    print(json.dumps(report, indent=2))
    if args.apply:
        journal_path = _journal_path(backups_dir, Path(args.journal) if args.journal else None)
        try:
            removed = apply(plan_, archive_dir, backups_dir, journal_path=journal_path)
        except RetentionApplyRefused as error:
            print(json.dumps({"mode": "refused", "error": str(error)}, indent=2))
            return 3
        except RetentionApplyPartial as error:
            print(
                json.dumps(
                    {"removed": error.receipt["removed"], "receipt": error.receipt}, indent=2
                )
            )
            return 4
        print(
            json.dumps({"removed": removed, "receipt": load_apply_receipt(journal_path)}, indent=2)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
