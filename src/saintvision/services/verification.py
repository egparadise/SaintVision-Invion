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
from ..storage.readroot import ReadRoot
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
    allowed_root: ReadRoot | None = None,
    os_type: str = "linux",
    chunk_bytes: int = CHUNK_BYTES,
    monotonic=None,
) -> ByteObservation:
    """Read a file and return what is actually in it.

    A trusted worker must supply its preconfigured ReadRoot. Authorization is
    checked on opened handles, never inferred from the requested path. Two
    bounded reads must agree: timestamp granularity alone cannot detect rapid
    same-size writes. This is an observation, not a filesystem snapshot.
    """
    from time import monotonic as _monotonic

    clock = monotonic or _monotonic
    if type(chunk_bytes) is not int or not 1 <= chunk_bytes <= CHUNK_BYTES:
        raise InvError(VAL_SCHEMA, "chunk_bytes must be an integer between 1 and 4 MiB")

    try:
        checked = normalize_contribution_path(str(path), os_type)
    except UnsafePath as exc:
        raise VerificationFailed(f"refusing to read that path: {exc.rule}") from None

    if not isinstance(allowed_root, ReadRoot):
        raise VerificationFailed("an authorized read root is required")
    # Do not silently reinterpret encoded aliases or traversal during syntax
    # normalization; use the original path for the actual boundary.
    if Path(str(path)) != Path(checked.normalized):
        raise VerificationFailed("refusing to read that path: ambiguous path")
    target = Path(str(path))
    started = clock()
    try:
        with allowed_root.open(target) as (handle, initial_size):
            first_digest = None
            for _ in range(2):
                handle.seek(0)
                digest = hashlib.sha256()
                total = 0
                while total <= initial_size:
                    chunk = handle.read(min(chunk_bytes, initial_size + 1 - total))
                    if not chunk:
                        break
                    digest.update(chunk)
                    total += len(chunk)
                if total != initial_size:
                    raise VerificationFailed("file changed during read")
                if first_digest is not None and first_digest != digest.digest():
                    raise VerificationFailed("file changed during read")
                first_digest = digest.digest()
    except FileNotFoundError:
        raise VerificationFailed("the file does not exist") from None
    except IsADirectoryError:
        raise VerificationFailed("the path is a directory") from None
    except PermissionError:
        # Not a skip. A pass that ignores what it could not open reports success
        # for a backup nobody has read.
        raise VerificationFailed("the file could not be read") from None
    except OSError:
        raise VerificationFailed("the file could not be read") from None

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
    allowed_root: ReadRoot | None = None,
    os_type: str = "linux",
    expected_sha256: str | None = None,
) -> ByteObservation:
    """Hash a backup on disk and record the result.

    This is the connection ADR-011 asks for: the digest written to
    ``backup_records`` is one this process computed over the bytes, not one a
    caller supplied.

    The stored digest is always a re-verification constraint. A caller hint can
    add a constraint, never replace that baseline. Lock metadata before reading
    bytes, so concurrent first verifiers cannot replace each other's digest.
    A rejected observation does not alter a previous successful observation.
    """
    from .pilot import verify_backup
    from sqlalchemy import select
    from ..db.models import BackupRecord

    row = session.scalars(
        select(BackupRecord)
        .where(BackupRecord.tenant_id == tenant_id, BackupRecord.backup_id == backup_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise VerificationFailed("backup is unavailable in this tenant")
    if (
        expected_sha256 is not None
        and row.checksum_sha256 is not None
        and expected_sha256 != row.checksum_sha256
    ):
        raise VerificationFailed("expected digest disagrees with recorded backup")

    observation = hash_file(path, allowed_root=allowed_root, os_type=os_type)

    baseline = row.checksum_sha256 if row.checksum_sha256 is not None else expected_sha256
    if baseline is not None and observation.sha256 != baseline:
        raise VerificationFailed(
            "the backup no longer hashes to its recorded digest",
            cause_ref=backup_id,
            observedSha256=observation.sha256,
            byteSize=observation.byte_size,
        )

    if row.byte_size and row.byte_size != observation.byte_size:
        # Validate before any successful-verification write. Catching this
        # application exception and committing must not promote a bad backup.
        raise VerificationFailed(
            "the backup on disk is a different size than the record",
            cause_ref=backup_id,
            recordedBytes=row.byte_size,
            observedBytes=observation.byte_size,
        )
    with session.begin_nested():
        verify_backup(
            session,
            tenant_id=tenant_id,
            backup_id=backup_id,
            checksum_sha256=observation.sha256,
            now=now,
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
    allowed_root: ReadRoot | None = None,
    os_type: str = "linux",
) -> ByteObservation:
    """Hash a replica on the node holding it and promote it if it matches.

    The comparison inside ``mark_replica_ready`` is against the catalogue, so
    this function does not need to know the expected digest — it supplies what
    it measured and lets the catalogue judge. A mismatch marks the replica
    corrupt there, which is the right place for that decision.
    """
    from .locality import mark_replica_ready

    observation = hash_file(path, allowed_root=allowed_root, os_type=os_type)
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
    allowed_root: ReadRoot | None = None,
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

    if type(limit) is not int or not 1 <= limit <= 100:
        raise VerificationFailed("verification limit must be between 1 and 100")

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
        try:
            with session.begin_nested():
                path = resolve_path(row)
                if path is None:
                    raise VerificationFailed("backup location is unavailable")
                verify_backup_bytes(
                    session,
                    tenant_id=tenant_id,
                    backup_id=row.backup_id,
                    path=path,
                    now=now,
                    allowed_root=allowed_root,
                    os_type="windows" if os.name == "nt" else "linux",
                )
        except (InvError, OSError):
            # Recorded as a failure and the sweep continues: one unreadable
            # backup must not hide the state of the rest.
            failed.append(row.backup_id)
        else:
            verified.append(row.backup_id)
    return {"verified": verified, "failed": failed}
