"""Path validation for contributed folders and the files inside them.

PLAN-STORAGE-001 requires that percent/unicode decoding, absolute paths, UNC and
drive-relative forms, ``..`` traversal, and junctions/symlinks are all checked
per OS, and that the boundary is re-checked at open time.

Two separate jobs live here and must not be confused:

``normalize_contribution_path``
    Validates the *root* a node owner is contributing. Runs on the control
    plane against a string the node reported; the path does not exist locally,
    so this is a syntactic check only.

``resolve_within``
    Validates a path *inside* a root at the moment of use. Runs on the node
    where the filesystem is real, so it also resolves links and re-checks
    containment after resolution — the check the syntactic pass cannot make.

A syntactic check alone is not sufficient and this module does not pretend
otherwise: ``normalize_contribution_path`` returns a path that is still
untrusted until ``resolve_within`` confirms it on the host.
"""

from __future__ import annotations

import ntpath
import os
import posixpath
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Final, Literal

OsType = Literal["windows", "linux"]

#: Reserved DOS device names. Still special on modern Windows regardless of
#: extension, and reachable through a path segment.
_WINDOWS_RESERVED: Final[frozenset[str]] = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

#: Roots no contribution may sit on or inside. These are the "preserve the
#: user's OS and files" boundaries from the final plan, not a complete
#: hardening list; the node also applies its own local policy.
_WINDOWS_DENIED_ROOTS: Final[tuple[str, ...]] = (
    r"c:\windows",
    r"c:\program files",
    r"c:\program files (x86)",
    r"c:\programdata",
    r"c:\$recycle.bin",
    r"c:\system volume information",
)
_POSIX_DENIED_ROOTS: Final[tuple[str, ...]] = (
    "/proc",
    "/sys",
    "/dev",
    "/boot",
    "/etc",
    "/run",
)

_CONTROL_CHARS: Final[re.Pattern[str]] = re.compile(r"[\x00-\x1f\x7f]")


class UnsafePath(ValueError):
    """The path is rejected. The message names the rule, not the input."""

    def __init__(self, rule: str) -> None:
        super().__init__(rule)
        self.rule = rule


@dataclass(frozen=True, slots=True)
class NormalizedPath:
    declared: str
    normalized: str
    os_type: OsType


def _decode_fully(raw: str, *, max_rounds: int = 3) -> str:
    """Percent-decode until stable, then NFC-normalise.

    Decoding once is not enough: ``%252e%252e`` survives a single pass. Decoding
    until stable is; if it never stabilises the input is hostile.
    """
    current = raw
    for _ in range(max_rounds):
        decoded = urllib.parse.unquote(current)
        if decoded == current:
            break
        current = decoded
    else:
        if urllib.parse.unquote(current) != current:
            raise UnsafePath("path does not stabilise under repeated percent-decoding")
    # NFC so that visually identical paths compare equal; a decomposed and a
    # composed spelling of the same folder must not be two contributions.
    return unicodedata.normalize("NFC", current)


def _reject_common(value: str) -> None:
    if not value or not value.strip():
        raise UnsafePath("path is empty")
    if _CONTROL_CHARS.search(value):
        raise UnsafePath("path contains control characters")
    if "\x00" in value:
        raise UnsafePath("path contains a NUL byte")


def _normalize_windows(value: str) -> str:
    if value.startswith("\\\\?\\") or value.startswith("\\\\.\\"):
        raise UnsafePath("Win32 device namespace path is not accepted")
    if value.startswith("\\\\"):
        raise UnsafePath("UNC path is not accepted as a contribution root")
    if ":" in value[2:]:
        # Anything after the drive colon is an alternate data stream.
        raise UnsafePath("alternate data stream suffix is not accepted")

    pure = PureWindowsPath(value)
    if not pure.drive:
        raise UnsafePath("contribution root must name a drive")
    if not pure.is_absolute():
        # "C:folder" has a drive but is relative to that drive's cwd.
        raise UnsafePath("drive-relative path is not accepted")

    normalized = ntpath.normpath(value)
    if ".." in PureWindowsPath(normalized).parts:
        raise UnsafePath("path escapes upward after normalisation")

    for part in PureWindowsPath(normalized).parts[1:]:
        stem = part.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED:
            raise UnsafePath(f"reserved device name in path: {stem}")
        if part != part.rstrip(" ."):
            raise UnsafePath("path segment ends with a space or dot")

    lowered = normalized.lower().rstrip("\\")
    for denied in _WINDOWS_DENIED_ROOTS:
        if lowered == denied or lowered.startswith(denied + "\\"):
            raise UnsafePath("path is inside a protected system location")
    if re.fullmatch(r"[a-z]:\\?", lowered):
        raise UnsafePath("a whole drive cannot be contributed")
    return normalized


def _normalize_posix(value: str) -> str:
    if not value.startswith("/"):
        raise UnsafePath("contribution root must be absolute")
    normalized = posixpath.normpath(value)
    if ".." in PurePosixPath(normalized).parts:
        raise UnsafePath("path escapes upward after normalisation")
    if normalized == "/":
        raise UnsafePath("the filesystem root cannot be contributed")
    for denied in _POSIX_DENIED_ROOTS:
        if normalized == denied or normalized.startswith(denied + "/"):
            raise UnsafePath("path is inside a protected system location")
    return normalized


def normalize_contribution_path(declared: str, os_type: OsType) -> NormalizedPath:
    """Validate and canonicalise a contributed folder root.

    Syntactic only — the path is not resolved, because the control plane is not
    the machine that holds it.
    """
    if os_type not in ("windows", "linux"):
        raise UnsafePath(f"unsupported os_type: {os_type!r}")
    decoded = _decode_fully(declared)
    _reject_common(decoded)
    if os_type == "windows":
        normalized = _normalize_windows(decoded)
    else:
        if "\\" in decoded:
            raise UnsafePath("backslash is not a separator on this OS")
        normalized = _normalize_posix(decoded)
    return NormalizedPath(declared=declared, normalized=normalized, os_type=os_type)


def validate_relative_path(relative: str, os_type: OsType) -> str:
    """Validate a path relative to a contribution root.

    Returns the POSIX-form relative path used in ``inv://`` URIs, so the same
    catalogue entry means the same file on either OS.
    """
    decoded = _decode_fully(relative)
    _reject_common(decoded)
    if decoded.startswith("/") or decoded.startswith("\\"):
        raise UnsafePath("relative path must not start at a root")
    if PureWindowsPath(decoded).drive:
        raise UnsafePath("relative path must not carry a drive")
    unified = decoded.replace("\\", "/")
    parts = [p for p in unified.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise UnsafePath("relative path escapes its root")
    for part in parts:
        stem = part.split(".", 1)[0].upper()
        if os_type == "windows":
            if stem in _WINDOWS_RESERVED:
                raise UnsafePath(f"reserved device name in path: {stem}")
            if part != part.rstrip(" ."):
                raise UnsafePath("path segment ends with a space or dot")
        if ":" in part:
            raise UnsafePath("path segment contains a colon")
    if not parts:
        raise UnsafePath("relative path is empty after normalisation")
    return "/".join(parts)


def resolve_within(root: str | os.PathLike[str], relative: str, *, os_type: OsType) -> Path:
    """Resolve ``relative`` under ``root`` on the local filesystem.

    Runs where the files actually are. Resolution follows symlinks and Windows
    junctions, then containment is re-checked against the *resolved* root — a
    link inside the root that points outside it is caught here and nowhere
    else.

    The returned path is still opened with ``O_NOFOLLOW`` semantics by the
    caller where the platform offers them; this function narrows the target, it
    does not eliminate the race between check and open.
    """
    safe_relative = validate_relative_path(relative, os_type)
    root_path = Path(root)
    resolved_root = root_path.resolve(strict=False)
    candidate = (resolved_root / safe_relative).resolve(strict=False)
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        raise UnsafePath("resolved path escapes the contribution root") from None
    return candidate


def build_uri(kind: str, *, name: str = "", version: str = "", relative_path: str = "",
              run_id: str = "", artifact_id: str = "", workspace_id: str = "") -> str:
    """Build an ``inv://`` URI in the grammar its namespace defines (ADR-010).

    Artifacts are addressed by run and artifact id, not by name and version, so
    a single grammar for all namespaces would be wrong.
    """
    if kind in ("dataset", "model"):
        plural = "datasets" if kind == "dataset" else "models"
        if not name or not version:
            raise ValueError(f"{kind} URI requires a name and a version")
        if "@" in name or "/" in name:
            raise ValueError("name must not contain '@' or '/'")
        tail = f"/{relative_path}" if relative_path else ""
        return f"inv://{plural}/{name}@{version}{tail}"
    if kind == "artifact":
        if not run_id or not artifact_id:
            raise ValueError("artifact URI requires runId and artifactId")
        return f"inv://artifacts/{run_id}/{artifact_id}"
    if kind == "workspace":
        if not workspace_id or not relative_path:
            raise ValueError("workspace URI requires a workspaceId and a relative path")
        return f"inv://workspaces/{workspace_id}/{relative_path}"
    raise ValueError(f"unknown URI kind: {kind!r}")
