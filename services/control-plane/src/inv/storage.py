"""Provider-neutral URI, path and content integrity boundaries."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, unquote
import hmac
import re
from .errors import DomainError


@dataclass(frozen=True)
class InvURI:
    namespace: str
    name: str
    version: str | None
    subpath: str


def parse_uri(value: str) -> InvURI:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "inv"
        or parsed.netloc not in {"datasets", "models", "artifacts", "workspaces"}
        or parsed.query
        or parsed.fragment
    ):
        raise DomainError("VAL-0010", "Invalid INV URI", 422)
    decoded = unquote(parsed.path, errors="strict")
    if (
        "%" in decoded
        or "\\" in decoded
        or ":" in decoded
        or any(ord(c) < 32 for c in decoded)
    ):
        raise DomainError("SEC-0011", "Unsafe INV path", 403)
    parts = decoded.lstrip("/").split("/")
    if decoded.startswith("//") or any(p in {"", ".", ".."} for p in parts):
        raise DomainError("SEC-0011", "Unsafe INV path", 403)
    root, *tail = parts
    name, separator, version = root.partition("@")
    if parsed.netloc in {"datasets", "models"}:
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", name):
            raise DomainError("VAL-0010", "Invalid asset name", 422)
        if separator and not re.fullmatch(
            r"(?:latest|[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?)", version
        ):
            raise DomainError("VAL-0010", "Invalid asset version", 422)
    else:
        prefix = "run" if parsed.netloc == "artifacts" else "wsp"
        if separator or not re.fullmatch(prefix + r"_[0-9A-HJKMNP-TV-Z]{26}", name):
            raise DomainError("VAL-0010", "Invalid scope identifier", 422)
        if parsed.netloc == "artifacts" and (
            len(tail) != 1 or not re.fullmatch(r"art_[0-9A-HJKMNP-TV-Z]{26}", tail[0])
        ):
            raise DomainError("VAL-0010", "Invalid artifact identifier", 422)
    return InvURI(parsed.netloc, name, version if separator else None, "/".join(tail))


def resolve_scoped(root: Path, relative: str) -> Path:
    # Preflight only: privileged executors must also validate the opened handle against
    # reparse-point/symlink replacement before reads/writes (TOCTOU).
    if not relative or "\\" in relative or ":" in relative or "\x00" in relative:
        raise DomainError("SEC-0012", "Unsafe relative path", 403)
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts:
        raise DomainError("SEC-0012", "Path escapes workspace", 403)
    base = root.resolve(strict=True)
    resolved = (base / relative).resolve()
    if not resolved.is_relative_to(base):
        raise DomainError("SEC-0012", "Link escapes workspace", 403)
    return resolved


def verify_content(path: Path, expected_hash: str, expected_size: int) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash) or expected_size < 0:
        raise DomainError("VAL-0013", "Invalid checksum contract", 422)
    digest, total = sha256(), 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            total += len(chunk)
            if total > expected_size:
                raise DomainError("VERIFY-0010", "Artifact exceeds declared size", 422)
    if total != expected_size or not hmac.compare_digest(
        digest.hexdigest(), expected_hash
    ):
        raise DomainError("VERIFY-0010", "Artifact content does not match", 422)
