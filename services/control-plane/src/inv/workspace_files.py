"""Real, bounded Workspace snapshots and new-generation Linux restoration.

Private service-owned roots and cooperative writer locks are mandatory. Restores
publish a new generation with read-only files; they never overwrite a live/user directory.
The Workspace adapter must quiesce writers before snapshot and explicitly create
a writable execution copy before resuming a process. No process is started here.
"""

from contextlib import contextmanager
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import unicodedata
from uuid import UUID, uuid4
from .contracts import validate_contract
from .errors import DomainError

MAX_CONTENT = 16 * 1024 * 1024
MAX_ARCHIVE = 24 * 1024 * 1024
MAX_ENTRIES = 2048
FORMAT = "workspace-snapshot:1"


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def portable_path(value):
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 1024
        or unicodedata.normalize("NFC", value) != value
    ):
        raise DomainError("SEC-0020", "Invalid snapshot path", 422)
    parts = value.split("/")
    if len(parts) > 16:
        raise DomainError("SEC-0020", "Snapshot path exceeds depth bound", 422)
    for part in parts:
        if (
            not part
            or part in {".", ".."}
            or len(part.encode("utf-8")) > 255
            or any(ord(c) < 32 or c in '\\:%<>"|?*' for c in part)
            or part.endswith((".", " "))
            or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)
        ):
            raise DomainError("SEC-0020", "Nonportable snapshot path", 422)
    return parts


def decode_snapshot(raw, workspace_id):
    validate_contract("WorkspaceId", workspace_id)
    if not isinstance(raw, bytes) or len(raw) > MAX_ARCHIVE:
        raise DomainError("STORE-0020", "Snapshot exceeds byte bound", 422)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {
            "format",
            "workspaceId",
            "directories",
            "files",
        }:
            raise ValueError()
        if (
            data["format"] != FORMAT
            or data["workspaceId"] != workspace_id
            or canonical(data) != raw
        ):
            raise ValueError()
        dirs, files = data["directories"], data["files"]
        if (
            not isinstance(dirs, list)
            or not isinstance(files, list)
            or len(dirs) + len(files) > MAX_ENTRIES
        ):
            raise ValueError()
        names, directory_names, total = set(), set(), 0
        for path in dirs:
            portable_path(path)
            if path.casefold() in names:
                raise ValueError()
            names.add(path.casefold())
            directory_names.add(path)
        content = {}
        for f in files:
            if not isinstance(f, dict) or set(f) != {
                "path",
                "executable",
                "sha256",
                "sizeBytes",
                "dataBase64",
            }:
                raise ValueError()
            path = f["path"]
            portable_path(path)
            if (
                path.casefold() in names
                or type(f["executable"]) is not bool
                or type(f["sizeBytes"]) is not int
                or not 0 <= f["sizeBytes"] <= MAX_CONTENT
            ):
                raise ValueError()
            names.add(path.casefold())
            chunk = base64.b64decode(f["dataBase64"], validate=True)
            total += len(chunk)
            if (
                total > MAX_CONTENT
                or len(chunk) != f["sizeBytes"]
                or hashlib.sha256(chunk).hexdigest() != f["sha256"]
                or base64.b64encode(chunk).decode() != f["dataBase64"]
            ):
                raise ValueError()
            content[path] = chunk
        paths = dirs + [f["path"] for f in files]
        if dirs != sorted(dirs) or [f["path"] for f in files] != sorted(content):
            raise ValueError()
        for path in paths:
            parts = path.split("/")
            if any("/".join(parts[:n]) not in directory_names for n in range(1, len(parts))):
                raise ValueError()
        return data, content
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise DomainError("VERIFY-0023", "Invalid immutable snapshot manifest", 422) from None


class PrivateTree:
    def __init__(self, root):
        if sys.platform != "linux":
            raise DomainError("STORE-0001", "Workspace handle provider requires Linux", 503)
        self.root = Path(root)
        if not self.root.is_absolute():
            raise ValueError("Explicit private Workspace root required")
        fd = self._open()
        try:
            info = os.fstat(fd)
            self.identity = info.st_dev, info.st_ino
        finally:
            os.close(fd)

    def _open(self):
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            self.check(os.fstat(fd), directory=True)
            return fd
        except BaseException:
            os.close(fd)
            raise

    @staticmethod
    def check(info, *, directory=False, device=None):
        if (
            not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o7077
            or (not directory and info.st_nlink != 1)
            or (device is not None and info.st_dev != device)
        ):
            raise DomainError("SEC-0021", "Unsafe Workspace handle", 403)

    @contextmanager
    def locked(self):
        import fcntl

        fd = self._open()
        try:
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) != self.identity:
                raise DomainError("SEC-0021", "Workspace root identity changed", 403)
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield fd
        finally:
            os.close(fd)

    def capture(self, workspace_id):
        validate_contract("WorkspaceId", workspace_id)
        directories, files, total = [], [], 0
        with self.locked() as root_fd:

            def visit(fd, prefix=""):
                nonlocal total
                before = sorted(os.listdir(fd))
                for name in before:
                    path = prefix + name
                    portable_path(path)
                    if len(directories) + len(files) >= MAX_ENTRIES:
                        raise DomainError("STORE-0020", "Too many snapshot entries", 422)
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        child = os.open(
                            name,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=fd,
                        )
                        try:
                            self.check(os.fstat(child), directory=True, device=self.identity[0])
                            directories.append(path)
                            visit(child, path + "/")
                        finally:
                            os.close(child)
                    else:
                        child = os.open(
                            name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd
                        )
                        with os.fdopen(child, "rb") as stream:
                            opened = os.fstat(stream.fileno())
                            self.check(opened, device=self.identity[0])
                            if opened.st_size > MAX_CONTENT - total:
                                raise DomainError(
                                    "STORE-0020", "Snapshot content exceeds bound", 422
                                )
                            chunk = stream.read(opened.st_size + 1)
                            after = os.fstat(stream.fileno())
                            if len(chunk) != opened.st_size or (
                                opened.st_size,
                                opened.st_mtime_ns,
                                opened.st_ctime_ns,
                            ) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                                raise DomainError("STORE-0021", "Workspace changed during snapshot")
                        total += len(chunk)
                        files.append(
                            {
                                "path": path,
                                "executable": bool(opened.st_mode & 0o100),
                                "sizeBytes": len(chunk),
                                "sha256": hashlib.sha256(chunk).hexdigest(),
                                "dataBase64": base64.b64encode(chunk).decode(),
                            }
                        )
                if sorted(os.listdir(fd)) != before:
                    raise DomainError("STORE-0021", "Workspace changed during snapshot")

            visit(root_fd)
        raw = canonical(
            {
                "format": FORMAT,
                "workspaceId": workspace_id,
                "directories": sorted(directories),
                "files": sorted(files, key=lambda f: f["path"]),
            }
        )
        decode_snapshot(raw, workspace_id)
        return raw


class RestoreGenerations(PrivateTree):
    @staticmethod
    def file_mode(file):
        return 0o500 if file["executable"] else 0o400

    @contextmanager
    def parent(self, root_fd, path):
        parts = portable_path(path)
        fd = os.dup(root_fd)
        try:
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                self.check(os.fstat(child), directory=True, device=self.identity[0])
                os.close(fd)
                fd = child
            yield fd, parts[-1]
        finally:
            os.close(fd)

    def publish(self, root_fd, restore_id, raw, workspace_id, *, allow_create=True):
        data, contents = decode_snapshot(raw, workspace_id)
        generation = "generation-" + UUID(str(restore_id)).hex
        expected = canonical(
            {"sha256": hashlib.sha256(raw).hexdigest(), "workspaceId": workspace_id}
        )
        try:
            existing = os.open(
                generation, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd
            )
        except FileNotFoundError:
            existing = None
        if existing is not None:
            try:
                self.check(os.fstat(existing), directory=True, device=self.identity[0])
                self._verify(existing, expected, data, contents)
            finally:
                os.close(existing)
            return generation
        if not allow_create:
            raise DomainError("STORE-0022", "Committed restore generation is missing")
        staging = "stage-" + uuid4().hex
        os.mkdir(staging, 0o700, dir_fd=root_fd)
        staged = os.open(staging, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            os.mkdir("files", 0o700, dir_fd=staged)
            files_fd = os.open("files", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=staged)
            try:
                for path in data["directories"]:
                    with self.parent(files_fd, path) as (parent, name):
                        os.mkdir(name, 0o700, dir_fd=parent)
                for f in data["files"]:
                    with self.parent(files_fd, f["path"]) as (parent, name):
                        fd = os.open(
                            name,
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600,
                            dir_fd=parent,
                        )
                        with os.fdopen(fd, "wb") as stream:
                            stream.write(contents[f["path"]])
                            stream.flush()
                            os.fchmod(stream.fileno(), self.file_mode(f))
                            os.fsync(stream.fileno())
                for path in reversed(data["directories"]):
                    with self.parent(files_fd, path) as (parent, name):
                        child = os.open(
                            name,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=parent,
                        )
                        try:
                            os.fsync(child)
                        finally:
                            os.close(child)
                os.fsync(files_fd)
            finally:
                os.close(files_fd)
            marker = os.open(
                "receipt.json",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o400,
                dir_fd=staged,
            )
            with os.fdopen(marker, "wb") as stream:
                stream.write(expected)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(staged)
            self._verify(staged, expected, data, contents)
            os.rename(staging, generation, src_dir_fd=root_fd, dst_dir_fd=root_fd)
            os.fsync(root_fd)
        finally:
            os.close(staged)
            # Only this call's random private staging directory is eligible.
            # Generation publication and preexisting/user directories are never removed.
            if shutil.rmtree.avoids_symlink_attacks:
                try:
                    shutil.rmtree(staging, dir_fd=root_fd)
                except FileNotFoundError:
                    pass
        return generation

    def _verify(self, fd, expected, data, contents):
        if set(os.listdir(fd)) != {"files", "receipt.json"}:
            raise DomainError("VERIFY-0023", "Unexpected restore metadata")
        marker = os.open("receipt.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(marker, "rb") as stream:
            self.check(os.fstat(stream.fileno()), device=self.identity[0])
            if stream.read(1025) != expected:
                raise DomainError("IDEM-0001", "Restore generation identity differs")
        files_fd = os.open("files", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
        try:
            self.check(os.fstat(files_fd), directory=True, device=self.identity[0])
            expected_dirs = set(data["directories"])
            modes = {f["path"]: self.file_mode(f) for f in data["files"]}
            seen_dirs, seen_files = set(), set()

            def walk(current, prefix=""):
                for name in os.listdir(current):
                    path = prefix + name
                    info = os.stat(name, dir_fd=current, follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        if path not in expected_dirs:
                            raise DomainError("VERIFY-0023", "Unexpected restore directory")
                        child = os.open(
                            name,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=current,
                        )
                        try:
                            self.check(os.fstat(child), directory=True, device=self.identity[0])
                            seen_dirs.add(path)
                            walk(child, path + "/")
                        finally:
                            os.close(child)
                    else:
                        if path not in contents:
                            raise DomainError("VERIFY-0023", "Unexpected restore file")
                        child = os.open(
                            name,
                            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                            dir_fd=current,
                        )
                        with os.fdopen(child, "rb") as stream:
                            info = os.fstat(stream.fileno())
                            self.check(info, device=self.identity[0])
                            if stat.S_IMODE(info.st_mode) != modes[path]:
                                raise DomainError("VERIFY-0023", "Restored file permissions differ")
                            if stream.read(len(contents[path]) + 1) != contents[path]:
                                raise DomainError("VERIFY-0023", "Restored bytes differ")
                        seen_files.add(path)

            walk(files_fd)
            if seen_dirs != expected_dirs or seen_files != set(contents):
                raise DomainError("VERIFY-0023", "Restore generation is incomplete")
        finally:
            os.close(files_fd)


class WorkingGenerations(RestoreGenerations):
    """Service-owned writable checkout; immutable restore bytes stay separate.

    Before DB publication, replay must still match initial bytes. After publication
    only the pinned directory identity and immutable marker are checked: legitimate
    edits must survive restart and must never be reset by replaying checkout.
    """

    @staticmethod
    def file_mode(file):
        return 0o700 if file["executable"] else 0o600

    def inspect_committed(self, root_fd, generation, workspace_id, sha256, expected_identity=None):
        if not re.fullmatch(r"generation-[0-9a-f]{32}", generation):
            raise DomainError("SEC-0020", "Invalid working generation")
        fd = os.open(generation, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            info = os.fstat(fd)
            self.check(info, directory=True, device=self.identity[0])
            if set(os.listdir(fd)) != {"files", "receipt.json"}:
                raise DomainError("VERIFY-0023", "Working generation metadata differs")
            marker = os.open("receipt.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(marker, "rb") as stream:
                marker_info = os.fstat(stream.fileno())
                self.check(marker_info, device=self.identity[0])
                if marker_info.st_mode & 0o222 or stream.read(1025) != canonical(
                    {"sha256": sha256, "workspaceId": workspace_id}
                ):
                    raise DomainError("VERIFY-0023", "Working generation marker differs")
            files = os.open("files", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                files_info = os.fstat(files)
                self.check(files_info, directory=True, device=self.identity[0])
                identity = [*self.identity, info.st_ino, files_info.st_ino]
                if expected_identity is not None and identity != expected_identity:
                    raise DomainError("STORE-0022", "Committed working generation was replaced")
                return identity
            finally:
                os.close(files)
        finally:
            os.close(fd)
