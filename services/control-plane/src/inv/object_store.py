"""Bounded local object provider; service-owned Linux directory, no user paths.

Every operation opens the same directory inode and takes an independent flock.
This serializes threads/processes, publication, readers and GC on this provider.
The account owning this private directory is trusted; this is not a sandbox for
host administrators or a replacement for the pending S3 product adapter.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
from typing import Protocol
from uuid import uuid4
from .errors import DomainError

PART_BYTES = 16 * 1024 * 1024
MAX_BYTES = 64 * 1024 * 1024
LOCAL_PROVIDER_ID = "local-bounded-v1"


def _local_provider_unavailable(error: OSError) -> DomainError:
    """Translate host filesystem failures without exposing paths or errno details."""

    return DomainError("STORE-0001", "Object provider unavailable", 503, True)


@dataclass(frozen=True)
class ObjectDigest:
    sha256: str
    size_bytes: int


class ObjectStore(Protocol):
    """Provider-neutral immutable byte store over a persisted opaque locator."""

    provider_id: str

    def validate_locator(self, locator: str) -> str: ...

    def put(self, locator: str, body: bytes, expected_sha256: str) -> None: ...

    def get(self, locator: str, expected_sha256: str, expected_size: int) -> bytes: ...

    def exists(self, locator: str) -> bool: ...

    def hash(self, locator: str) -> ObjectDigest: ...

    def delete(self, locator: str) -> None: ...


class ObjectStoreRegistry:
    """Exact provider-id selection; never falls back across providers."""

    def __init__(self, providers=()):
        self._providers = {}
        for provider in providers:
            provider_id = getattr(provider, "provider_id", None)
            if not isinstance(provider_id, str) or provider_id in self._providers:
                raise ValueError("Unique stable ObjectStore provider id required")
            self._providers[provider_id] = provider

    def resolve(self, provider_id):
        provider = self._providers.get(provider_id)
        if provider is None:
            raise DomainError("STORE-0001", "Object provider unavailable", 503, True)
        return provider


def provider_id(provider):
    """Return the stable identity of an opened provider/session."""

    return getattr(provider, "provider_id", LOCAL_PROVIDER_ID)


def require_object_provider(provider, row):
    """Reject metadata/provider drift before bytes or object state are touched."""

    if row["provider_id"] != provider_id(provider):
        raise DomainError("STORE-0001", "Object provider unavailable", 503, True)
    return provider


def registered_provider(provider):
    """Adapt the legacy local handle only at the registry boundary."""

    return provider if hasattr(provider, "provider_id") else LocalObjectStore(provider)


class LocalObjects:
    def __init__(self, root):
        if sys.platform != "linux":
            raise DomainError("STORE-0001", "Local provider requires Linux handle checks", 503)
        self.root = Path(root)
        if not self.root.is_absolute():
            raise ValueError("Explicit absolute object directory required")
        fd = self._open()
        try:
            try:
                info = os.fstat(fd)
            except OSError as error:
                raise _local_provider_unavailable(error) from error
            self.identity = (info.st_dev, info.st_ino)
        finally:
            active_error = sys.exc_info()[0] is not None
            try:
                os.close(fd)
            except OSError as error:
                if not active_error:
                    raise _local_provider_unavailable(error) from error

    def _open(self):
        try:
            fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError as error:
            raise _local_provider_unavailable(error) from error
        try:
            info = os.fstat(fd)
        except OSError as error:
            try:
                os.close(fd)
            except OSError:
                # Preserve the first provider failure; neither host detail is public.
                pass
            raise _local_provider_unavailable(error) from error
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            try:
                os.close(fd)
            except OSError:
                pass
            raise DomainError("STORE-0001", "Private service-owned directory required", 503)
        return fd

    @contextmanager
    def locked(self):
        import fcntl

        fd = self._open()
        try:
            try:
                info = os.fstat(fd)
            except OSError as error:
                raise _local_provider_unavailable(error) from error
            if (info.st_dev, info.st_ino) != self.identity:
                raise DomainError("STORE-0001", "Object directory changed", 503)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
            except OSError as error:
                raise _local_provider_unavailable(error) from error
            # Provider calls are translated by _LegacyObjectSession.  Do not catch
            # the whole consumer body here: workspace/generation code can run while
            # this lock is held, and its unrelated OSError must keep its own meaning.
            yield ObjectHandle(fd)
        finally:
            active_error = sys.exc_info()[0] is not None
            try:
                os.close(fd)
            except OSError as error:
                if not active_error:
                    raise _local_provider_unavailable(error) from error


class LocalObjectStore:
    """ObjectStore compatibility wrapper for the bounded local provider.

    Tenant/project authorization remains at the service and RLS layer. The
    locator is the existing immutable flat ``obj-<uuidhex>`` key and is never
    synthesized from requester input here.
    """

    provider_id = LOCAL_PROVIDER_ID

    def __init__(self, legacy: LocalObjects):
        self.legacy = legacy

    def validate_locator(self, locator):
        return ObjectHandle.name(locator)

    def put(self, locator, body, expected_sha256):
        try:
            with self.legacy.locked() as files:
                if files.exists(locator):
                    observed = files.hash(locator)
                    if observed.sha256 != expected_sha256 or observed.size_bytes != len(body):
                        raise DomainError("STORE-0005", "Immutable object already differs", 409)
                    files.read(locator, expected_sha256, len(body))
                    return
                files.put(locator, body, expected_sha256)
        except OSError as error:
            raise _local_provider_unavailable(error) from error

    def get(self, locator, expected_sha256, expected_size):
        try:
            with self.legacy.locked() as files:
                return files.read(locator, expected_sha256, expected_size)
        except FileNotFoundError:
            raise FileNotFoundError from None
        except OSError as error:
            raise _local_provider_unavailable(error) from error

    def exists(self, locator):
        try:
            with self.legacy.locked() as files:
                return files.exists(locator)
        except OSError as error:
            raise _local_provider_unavailable(error) from error

    def hash(self, locator):
        try:
            with self.legacy.locked() as files:
                return files.hash(locator)
        except FileNotFoundError:
            raise FileNotFoundError from None
        except OSError as error:
            raise _local_provider_unavailable(error) from error

    def delete(self, locator):
        try:
            with self.legacy.locked() as files:
                files.remove(locator)
                if files.exists(locator):
                    raise DomainError("STORE-0001", "Object remained after deletion", 503, True)
        except OSError as error:
            raise _local_provider_unavailable(error) from error


class _LegacyObjectSession:
    provider_id = LOCAL_PROVIDER_ID

    def __init__(self, files, provider_id=LOCAL_PROVIDER_ID):
        self.files = files
        self.provider_id = provider_id

    def validate_locator(self, locator):
        return ObjectHandle.name(locator)

    def put(self, locator, body, expected_sha256):
        try:
            self.files.put(locator, body, expected_sha256)
        except OSError as error:
            # ENOENT while creating/renaming means the pinned provider directory
            # disappeared.  A put cannot use "object missing" as a normal result.
            raise _local_provider_unavailable(error) from error

    def get(self, locator, expected_sha256, expected_size):
        try:
            return self.files.read(locator, expected_sha256, expected_size)
        except FileNotFoundError:
            # Missing committed bytes are interpreted by the calling service.
            raise
        except OSError as error:
            raise _local_provider_unavailable(error) from error

    def exists(self, locator):
        try:
            return self.files.exists(locator)
        except OSError as error:
            raise _local_provider_unavailable(error) from error

    def hash(self, locator):
        try:
            return self.files.hash(locator)
        except FileNotFoundError:
            raise
        except OSError as error:
            raise _local_provider_unavailable(error) from error

    def delete(self, locator):
        try:
            self.files.remove(locator)
        except OSError as error:
            # Delete is an explicit provider mutation.  ENOENT here means its
            # pinned root/entry changed after the caller's existence decision.
            raise _local_provider_unavailable(error) from error


@contextmanager
def object_store_session(provider):
    """Hold the legacy flock across a service transaction; S3 needs no global lock."""

    legacy = provider.legacy if isinstance(provider, LocalObjectStore) else provider
    locked = getattr(legacy, "locked", None)
    if locked is None:
        yield provider
    else:
        with locked() as files:
            yield _LegacyObjectSession(files, provider_id(provider))


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

    def exists(self, name):
        name = self.name(name)
        try:
            info = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o222
            or not 0 <= info.st_size <= MAX_BYTES
        ):
            raise DomainError("STORE-0003", "Object handle or size is invalid", 422)
        return True

    def hash(self, name):
        name = self.name(name)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o222
                or not 0 <= info.st_size <= MAX_BYTES
            ):
                raise DomainError("STORE-0003", "Object handle or size is invalid", 422)
            value = hashlib.sha256()
            size = 0
            while True:
                chunk = stream.read(min(PART_BYTES, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise DomainError("STORE-0003", "Object handle or size is invalid", 422)
                value.update(chunk)
            if size != info.st_size:
                raise DomainError("STORE-0003", "Object handle or size is invalid", 422)
            return ObjectDigest(value.hexdigest(), size)

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
