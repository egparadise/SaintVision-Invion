"""Hashing the actual bytes.

ADR-011 requires a trusted worker to compute SHA-256 over the real bytes, and
forbids accepting an ETag, a client-declared hash, or any metadata field in its
place. Until now ``verify_backup`` and ``mark_replica_ready`` took a digest
string from their caller — the format was validated, the provenance was not.
This module is what actually reads the file.

Three properties it is built for:

* **It never loads the file into memory.** A base backup is measured in
  gigabytes; ``read()`` on one is an outage. Everything is chunked.
* **Size is verified alongside the digest.** A truncated file has a perfectly
  valid SHA-256 — of the wrong content — and comparing only digests would call
  it corrupt without saying why, or miss it entirely if the record was written
  from the same truncated copy.
* **An unreadable file is a failure, not a skip.** A verification pass that
  silently ignores what it could not open reports success for a backup nobody
  has ever read.

The worker runs where the bytes are: on the node holding the replica, or on the
host holding the backup. The Control Plane cannot hash a file it cannot see,
and this module does not pretend it can — :func:`hash_file` is called by the
worker process, and the record functions take its result.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from sqlalchemy.orm import Session

from ..errors import VAL_SCHEMA, InvError
from ..storage.pathsafe import UnsafePath, normalize_contribution_path

#: 4 MiB. Large enough that syscall overhead is irrelevant, small enough that a
#: dozen concurrent verifications do not add up to anything notable.
CHUNK_BYTES: Final[int] = 4 * 1024 * 1024


class VerificationFailed(InvError):
    """The bytes are not what the record says they are."""

    def __init__(self, message: str, *, cause_ref: str | None = None, **extra) -> None:
        super().__init__(VAL_SCHEMA, message, cause_ref=cause_ref, extra=extra)


@dataclass(frozen=True, slots=True)
class ByteObservation:
    """What a worker actually saw on disk. Facts, not claims."""

    sha256: str
    byte_size: int
    #: How long the read took. A verification that takes an hour is a finding
    #: about the storage even when the digest matches.
    duration_seconds: float
    chunk_bytes: int = CHUNK_BYTES

    def matches(self, *, expected_sha256: str | None, expected_size: int | None) -> bool:
        if expected_sha256 is not None and self.sha256 != expected_sha256:
            return False
        if expected_size is not None and self.byte_size != expected_size:
            return False
        return True


def hash_file(
    path: str | os.PathLike[str],
    *,
    os_type: str = "linux",
    chunk_bytes: int = CHUNK_BYTES,
    monotonic=None,
) -> ByteObservation:
    """Read a file and return what is actually in it.

    The path is normalised through the same safety check contributed folders
    use, so a verification job cannot be pointed at ``/etc/shadow`` or walked
    out of its root by a crafted record.

    Reads in chunks and counts the bytes it read rather than trusting
    ``stat()``: the size that matters is the size that was hashed, and a file
    growing under the reader would otherwise produce a digest and a size that
    describe different content.
    """
    from time import monotonic as _monotonic

    clock = monotonic or _monotonic
    if chunk_bytes <= 0:
        raise InvError(VAL_SCHEMA, "chunk_bytes must be positive")

    try:
        checked = normalize_contribution_path(str(path), os_type)
    except UnsafePath as exc:
        raise VerificationFailed(f"refusing to read that path: {exc.rule}") from None

    target = Path(checked.normalized)
    started = clock()
    digest = hashlib.sha256()
    total = 0
    try:
        with open(target, "rb") as handle:
            while True:
                chunk = handle.read(chunk_bytes)
                if not chunk:
                    break
                digest.update(chunk)
                total += len(chunk)
    except FileNotFoundError:
        raise VerificationFailed("the file does not exist", path_checked=str(target)) from None
    except IsADirectoryError:
        raise VerificationFailed("the path is a directory") from None
    except PermissionError:
        # Not a skip. A pass that ignores what it could not open reports success
        # for a backup nobody has read.
        raise VerificationFailed("the file could not be read") from None
    except OSError as exc:
        raise VerificationFailed(f"the file could not be read: {exc.strerror}") from None

    return ByteObservation(
        sha256=digest.hexdigest(),
        byte_size=total,
        duration_seconds=clock() - started,
        chunk_bytes=chunk_bytes,
    )


def verify_backup_bytes(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    backup_id: str,
    path: str | os.PathLike[str],
    now: dt.datetime,
    os_type: str = "linux",
    expected_sha256: str | None = None,
) -> ByteObservation:
    """Hash a backup on disk and record the result.

    This is the connection ADR-011 asks for: the digest written to
    ``backup_records`` is one this process computed over the bytes, not one a
    caller supplied.

    ``expected_sha256`` is optional and is a *re-verification* check — a backup
    verified last week should still hash the same. Passing it turns silent bit
    rot into a failure.
    """
    from .pilot import verify_backup

    observation = hash_file(path, os_type=os_type)

    if expected_sha256 is not None and observation.sha256 != expected_sha256:
        raise VerificationFailed(
            "the backup no longer hashes to its recorded digest",
            cause_ref=backup_id,
            observedSha256=observation.sha256,
            byteSize=observation.byte_size,
        )

    row = verify_backup(
        session,
        tenant_id=tenant_id,
        backup_id=backup_id,
        checksum_sha256=observation.sha256,
        now=now,
    )
    if row.byte_size and row.byte_size != observation.byte_size:
        # The digest is of a different amount of data than was recorded. Do not
        # leave the row verified on the strength of it.
        raise VerificationFailed(
            "the backup on disk is a different size than the record",
            cause_ref=backup_id,
            recordedBytes=row.byte_size,
            observedBytes=observation.byte_size,
        )
    if not row.byte_size:
        row.byte_size = observation.byte_size
        session.flush()
    return observation


def verify_replica_bytes(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    replica_id: str,
    path: str | os.PathLike[str],
    now: dt.datetime,
    os_type: str = "linux",
) -> ByteObservation:
    """Hash a replica on the node holding it and promote it if it matches.

    The comparison inside ``mark_replica_ready`` is against the catalogue, so
    this function does not need to know the expected digest — it supplies what
    it measured and lets the catalogue judge. A mismatch marks the replica
    corrupt there, which is the right place for that decision.
    """
    from .locality import mark_replica_ready

    observation = hash_file(path, os_type=os_type)
    mark_replica_ready(
        session,
        tenant_id=tenant_id,
        replica_id=replica_id,
        checksum_sha256=observation.sha256,
        now=now,
    )
    return observation


def verify_pending_backups(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    now: dt.datetime,
    resolve_path,
    limit: int = 10,
) -> dict[str, list[str]]:
    """Verify unverified backups, reporting both outcomes.

    ``resolve_path`` maps a ``BackupRecord`` to a local path, because how a
    ``location_ref`` becomes a filename depends on where the worker runs and
    that is not this module's business.

    Returns verified and failed ids separately. A sweep that returned only a
    count would let a run of failures look like progress.
    """
    from sqlalchemy import select

    from ..db.models import BackupRecord

    rows = session.scalars(
        select(BackupRecord)
        .where(
            BackupRecord.tenant_id == tenant_id,
            BackupRecord.verified.is_(False),
        )
        .order_by(BackupRecord.started_at)
        .limit(limit)
    ).all()

    verified: list[str] = []
    failed: list[str] = []
    for row in rows:
        path = resolve_path(row)
        if path is None:
            failed.append(row.backup_id)
            continue
        try:
            verify_backup_bytes(
                session, tenant_id=tenant_id, backup_id=row.backup_id, path=path, now=now
            )
        except InvError:
            # Recorded as a failure and the sweep continues: one unreadable
            # backup must not hide the state of the rest.
            failed.append(row.backup_id)
        else:
            verified.append(row.backup_id)
    return {"verified": verified, "failed": failed}
