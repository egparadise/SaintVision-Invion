"""Bounded local object provider; service-owned Linux directory, no user paths.

Every operation opens the same directory inode and takes an independent flock.
This serializes threads/processes, publication, readers and GC on this provider.
The account owning this private directory is trusted; this is not a sandbox for
host administrators or a replacement for the pending S3 product adapter.
"""

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
from uuid import uuid4
from .errors import DomainError

PART_BYTES = 16 * 1024 * 1024
MAX_BYTES = 64 * 1024 * 1024


class LocalObjects:
    def __init__(self, root):
        if sys.platform != "linux":
            raise DomainError(
                "STORE-0001", "Local provider requires Linux handle checks", 503
            )
        self.root = Path(root)
        if not self.root.is_absolute():
            raise ValueError("Explicit absolute object directory required")
        fd = self._open()
        try:
            info = os.fstat(fd)
            self.identity = (info.st_dev, info.st_ino)
        finally:
            os.close(fd)

    def _open(self):
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            os.close(fd)
            raise DomainError(
                "STORE-0001", "Private service-owned directory required", 503
            )
        return fd

    @contextmanager
    def locked(self):
        import fcntl

        fd = self._open()
        try:
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) != self.identity:
                raise DomainError("STORE-0001", "Object directory changed", 503)
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield ObjectHandle(fd)
        finally:
            os.close(fd)


class ObjectHandle:
    def __init__(self, fd):
        self.fd = fd

    @staticmethod
    def name(name):
        if not re.fullmatch(r"(?:obj-[0-9a-f]{32}|part-[0-9a-f]{32}-[0-3])", name):
            raise DomainError("STORE-0002", "Invalid object key", 422)
        return name

    def read(self, name, digest, size):
        name = self.name(name)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o222
                or info.st_size != size
                or not 0 <= size <= MAX_BYTES
            ):
                raise DomainError("STORE-0003", "Object handle or size is invalid", 422)
            data = stream.read(size + 1)
            if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
                raise DomainError("VERIFY-0010", "Stored object checksum differs", 422)
            return data

    def put(self, name, data, digest):
        name = self.name(name)
        if len(data) > MAX_BYTES or hashlib.sha256(data).hexdigest() != digest:
            raise DomainError("VERIFY-0010", "Object content differs", 422)
        # The filesystem may have committed before its metadata transaction.
        try:
            prior = self.read(name, digest, len(data))
        except FileNotFoundError:
            prior = None
        if prior is not None:
            return
        temporary = "tmp-" + uuid4().hex
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=self.fd,
        )
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fchmod(stream.fileno(), 0o400)
                os.fsync(stream.fileno())
            # No participating writer can replace a published key under flock.
            os.rename(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
            os.fsync(self.fd)
        finally:
            try:
                os.unlink(temporary, dir_fd=self.fd)
            except FileNotFoundError:
                pass

    def remove(self, name):
        name = self.name(name)
        try:
            os.unlink(name, dir_fd=self.fd)
        except FileNotFoundError:
            pass
        os.fsync(self.fd)
