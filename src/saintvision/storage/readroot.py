"""Open-time local worker boundary. Roots come from trusted configuration.

No HTTP path may authorize its own parent. Supports Linux and Windows local
filesystems; refuses links, cross-device children and changing files.
The observation is not a filesystem snapshot or protection against an OS admin.
"""

from contextlib import contextmanager, ExitStack
import os
from pathlib import Path
import stat
import sys


def _identity(info):
    return info.st_dev, info.st_ino


def _version(info):
    return (
        _identity(info),
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_nlink,
        info.st_mode,
    )


def _absolute(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise PermissionError("absolute unambiguous path required")
    if sys.platform == "win32":
        # Local drive paths only; forbid device paths, ADS and DOS aliases.
        if not path.drive or path.drive.startswith("\\"):
            raise PermissionError("local drive required")
        for part in path.parts[1:]:
            if ":" in part or part.endswith((" ", ".")):
                raise PermissionError("ambiguous path")
    return path


def _windows_open(path, directory):
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    drive_type = kernel.GetDriveTypeW
    drive_type.argtypes = [wintypes.LPCWSTR]
    drive_type.restype = wintypes.UINT
    if drive_type(path.anchor) != 3:  # DRIVE_FIXED; no mapped network shares.
        raise PermissionError("local fixed drive required")
    create = kernel.CreateFileW
    create.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    # Share READ only: reject concurrent write/delete opens and retain all
    # ancestor handles until verification ends. Never follow a reparse point.
    handle = create(
        str(path), 0x80 if directory else 0x80000000, 1, None, 3, 0x02000000 | 0x00200000, None
    )
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        close(handle)
        raise
    return fd


@contextmanager
def _walk(path):
    """Hold the entire directory chain; inspect each opened object."""
    with ExitStack() as stack:
        if sys.platform not in ("linux", "win32"):
            raise PermissionError("unsupported platform")
        parent = None
        current = Path(path.anchor)
        for index, part in enumerate((path.anchor, *path.parts[1:])):
            if index:
                current /= part
            if sys.platform == "win32":
                fd = _windows_open(current, True)
            else:
                fd = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent
                )
            stack.callback(os.close, fd)
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise PermissionError("linked or non-directory ancestor")
            parent = fd
        yield parent


class ReadRoot:
    """Explicit worker authorization pinned to the selected root's identity.

    Recreate only after trusted reconfiguration, never after a failed read.
    Do not infer this root from a job's requested filename.
    """

    def __init__(self, path):
        self.path = _absolute(path)
        if self.path == Path(self.path.anchor):
            raise PermissionError("whole filesystem authorization is forbidden")
        with _walk(self.path) as fd:
            self.identity = _identity(os.fstat(fd))

    @contextmanager
    def open(self, path):
        target = _absolute(path)
        try:
            relative = target.relative_to(self.path)
        except ValueError:
            raise PermissionError("outside authorized root") from None
        if not relative.parts:
            raise IsADirectoryError("expected a file")
        with ExitStack() as stack:
            root_fd = stack.enter_context(_walk(self.path))
            if _identity(os.fstat(root_fd)) != self.identity:
                raise PermissionError("authorized root replaced")
            parent = root_fd
            current = self.path
            chain = []
            for part in relative.parts[:-1]:
                current /= part
                fd = (
                    _windows_open(current, True)
                    if sys.platform == "win32"
                    else os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                        dir_fd=parent,
                    )
                )
                stack.callback(os.close, fd)
                info = os.fstat(fd)
                if (
                    not stat.S_ISDIR(info.st_mode)
                    or info.st_dev != self.identity[0]
                    or getattr(info, "st_file_attributes", 0) & 0x400
                ):
                    raise PermissionError("invalid child directory")
                chain.append((parent, part, _identity(info)))
                parent = fd
            fd = (
                _windows_open(target, False)
                if sys.platform == "win32"
                else os.open(
                    relative.name,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                    dir_fd=parent,
                )
            )
            try:
                # A validation reread must reach the filesystem, not an old
                # BufferedReader cache after seek(0).
                handle = os.fdopen(fd, "rb", buffering=0)
            except BaseException:
                os.close(fd)
                raise
            stack.enter_context(handle)
            before = os.fstat(fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_dev != self.identity[0]
                or getattr(before, "st_file_attributes", 0) & 0x400
            ):
                raise PermissionError("expected a single-link regular file")
            yield handle, before.st_size
            if _version(before) != _version(os.fstat(fd)):
                raise PermissionError("file changed during read")
            # Linux permits rename/unlink while descriptors remain open. Verify
            # named identities again before allowing an observation to escape.
            if sys.platform == "linux":
                for directory, name, identity in chain:
                    if (
                        _identity(os.stat(name, dir_fd=directory, follow_symlinks=False))
                        != identity
                    ):
                        raise PermissionError("directory replaced during read")
                named = os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
                if _version(named) != _version(before):
                    raise PermissionError("file replaced during read")
            with _walk(self.path) as check:
                if _identity(os.fstat(check)) != self.identity:
                    raise PermissionError("root replaced during read")
