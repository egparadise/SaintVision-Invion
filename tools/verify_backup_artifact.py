"""Fail-closed verifier for a PostgreSQL physical-backup tar artifact.

This verifier deliberately validates structure instead of trusting a producer
exit code.  It does not restore the cluster; restore evidence remains a hosted
or physical-lab concern.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import tarfile


REQUIRED_MEMBERS = ("PG_VERSION", "backup_label", "global/pg_control")


class BackupArtifactInvalid(ValueError):
    """The bytes cannot be accepted as a physical PostgreSQL backup."""


@dataclass(frozen=True)
class BackupArtifactReceipt:
    byte_size: int
    sha256: str
    member_count: int


def verify_physical_backup_archive(path: Path) -> BackupArtifactReceipt:
    """Validate a regular tar archive and return a redaction-safe receipt."""

    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise BackupArtifactInvalid("backup artifact must be a regular file")
    byte_size = path.stat().st_size
    if byte_size <= 0:
        raise BackupArtifactInvalid("backup artifact is empty")

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    try:
        with tarfile.open(path, mode="r:*") as archive:
            members = archive.getmembers()
            names: dict[str, tarfile.TarInfo] = {}
            for member in members:
                candidate = PurePosixPath(member.name.removeprefix("./"))
                if candidate.is_absolute() or ".." in candidate.parts or member.issym() or member.islnk():
                    raise BackupArtifactInvalid("backup archive contains an unsafe member")
                normalized = candidate.as_posix()
                if normalized in names:
                    raise BackupArtifactInvalid("backup archive contains duplicate members")
                names[normalized] = member
            if any(name not in names or not names[name].isfile() for name in REQUIRED_MEMBERS):
                raise BackupArtifactInvalid("backup archive is missing required PostgreSQL members")

            version = archive.extractfile(names["PG_VERSION"])
            label = archive.extractfile(names["backup_label"])
            control = archive.extractfile(names["global/pg_control"])
            if version is None or label is None or control is None:
                raise BackupArtifactInvalid("backup archive members are unreadable")
            try:
                version_text = version.read(32).decode("ascii").strip()
                label_text = label.read(65536).decode("ascii")
            except UnicodeError as exc:
                raise BackupArtifactInvalid("backup metadata is not ASCII") from exc
            control_bytes = control.read(8193)
            if not version_text.isdigit() or "START WAL LOCATION" not in label_text or len(control_bytes) != 8192:
                raise BackupArtifactInvalid("backup metadata is structurally invalid")
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise BackupArtifactInvalid("backup artifact is not a readable tar archive") from exc

    return BackupArtifactReceipt(byte_size=byte_size, sha256=digest.hexdigest(), member_count=len(members))
