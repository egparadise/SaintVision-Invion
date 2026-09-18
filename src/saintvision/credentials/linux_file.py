"""Linux descriptor-bound secret reads with a mandatory current registry lookup.

No default registry or ambient credential fallback. No public network route.
The host service owner and adapter callback are trusted. Final registry lookup
is admission: revocation prevents later admissions, not an already admitted
external effect. No DB transaction or file lock spans the callback.
"""

from dataclasses import dataclass
from hashlib import sha256
import hmac
import os
from pathlib import Path
import re
import stat
import sys
from .contract import CredentialContext, CredentialDenied

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_REFERENCE = re.compile(r"svcred:1:(" + _UUID + r"):(" + _UUID + r")")


@dataclass(frozen=True, repr=False)
class CredentialBinding:
    file_name: str
    device: int
    inode: int
    content_sha256: str


class LinuxFileCredentials:
    def __init__(self, root, registry):
        try:
            if sys.platform != "linux":
                raise CredentialDenied()
            self._root = Path(root)
            if not self._root.is_absolute() or ".." in self._root.parts:
                raise CredentialDenied()
            self._registry = registry
            fd = self._open_root()
            try:
                self._identity = self._identity_of(os.fstat(fd))
            finally:
                os.close(fd)
        except Exception:
            raise CredentialDenied() from None

    @staticmethod
    def _identity_of(info):
        return info.st_dev, info.st_ino

    def _open_root(self):
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = os.open("/", flags)
        try:
            for part in self._root.parts[1:]:
                nxt = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = nxt
            info = os.fstat(fd)
            if info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise CredentialDenied()
            if hasattr(self, "_identity") and self._identity_of(info) != self._identity:
                raise CredentialDenied()
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _lookup(self, args):
        reference, context, purpose, destination = args
        match = _REFERENCE.fullmatch(reference) if isinstance(reference, str) else None
        if not match or type(context) is not CredentialContext or purpose == "encryption.unwrap":
            raise CredentialDenied()
        binding = self._registry.lookup(*match.groups(), context, purpose, destination)
        if (
            not isinstance(binding, CredentialBinding)
            or not re.fullmatch(r"[0-9a-f]{32}[.]secret", binding.file_name)
            or not re.fullmatch(r"[0-9a-f]{64}", binding.content_sha256)
        ):
            raise CredentialDenied()
        return binding

    def resolve(self, reference, authenticated_context, purpose, destination_alias):
        try:
            args = (reference, authenticated_context, purpose, destination_alias)
            binding = self._lookup(args)
            return _Handle(self, args, binding)
        except Exception:
            raise CredentialDenied() from None

    def _read(self, binding):
        root_fd = self._open_root()
        fd = None
        try:
            fd = os.open(
                binding.file_name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                dir_fd=root_fd,
            )
            before = os.fstat(fd)
            self._check_file(before, binding)
            chunks, count = [], 0
            while True:
                part = os.read(fd, min(8192, 65537 - count))
                if not part:
                    break
                count += len(part)
                if count > 65536:
                    raise CredentialDenied()
                chunks.append(part)
            content = b"".join(chunks)
            after = os.fstat(fd)
            self._check_file(after, binding)
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise CredentialDenied()
            if not hmac.compare_digest(sha256(content).hexdigest(), binding.content_sha256):
                raise CredentialDenied()
            # Re-resolve the name without following links; a captured descriptor
            # must not bless a newly substituted path or root.
            current = os.stat(binding.file_name, dir_fd=root_fd, follow_symlinks=False)
            self._check_file(current, binding)
            check_root = self._open_root()
            os.close(check_root)
            return content
        finally:
            if fd is not None:
                os.close(fd)
            os.close(root_fd)

    def _check_file(self, info, binding):
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
            or not 0 < info.st_size <= 65536
            or self._identity_of(info) != (binding.device, binding.inode)
        ):
            raise CredentialDenied()

    def _use(self, args, binding, callback):
        try:
            if self._lookup(args) != binding:
                raise CredentialDenied()
            content = self._read(binding)
            # Observe grants/revocation committed while file bytes were read.
            if self._lookup(args) != binding:
                raise CredentialDenied()
            return callback(content)  # Exactly one attempt, with no lock held.
        except Exception:
            raise CredentialDenied() from None


class _Handle:
    __slots__ = ("_provider", "_args", "_binding")

    def __init__(self, provider, args, binding):
        self._provider, self._args, self._binding = provider, args, binding

    def __repr__(self):
        return "<credential handle>"

    def use(self, callback):
        return self._provider._use(self._args, self._binding, callback)
