"""Hashing real bytes.

The digest written to a backup or replica record used to be a string a caller
supplied; the format was checked, the provenance was not. These tests pin the
worker that now reads the file.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import sys

import pytest

from saintvision.errors import InvError
from saintvision.services import verification

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 10, 7, 0, 0, tzinfo=UTC)


def _os_type() -> str:
    return "windows" if sys.platform == "win32" else "linux"


@pytest.fixture
def payload(tmp_path):
    """A file bigger than one chunk, so the chunked path is actually exercised."""
    data = bytes(range(256)) * 40_000  # ~10 MiB
    target = tmp_path / "backup.bin"
    target.write_bytes(data)
    return {
        "path": target,
        "data": data,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }


def _hash(path, **kwargs):
    return verification.hash_file(path, os_type=_os_type(), **kwargs)


def test_the_digest_matches_the_file(payload):
    observation = _hash(payload["path"])
    assert observation.sha256 == payload["sha256"]
    assert observation.byte_size == payload["size"]


def test_a_large_file_is_read_in_chunks(payload, monkeypatch):
    """A base backup is measured in gigabytes; read() on one is an outage."""
    reads: list[int] = []
    real_open = open

    def counting_open(*args, **kwargs):
        handle = real_open(*args, **kwargs)
        real_read = handle.read

        def read(size=-1):
            chunk = real_read(size)
            reads.append(len(chunk))
            return chunk

        handle.read = read  # type: ignore[method-assign]
        return handle

    monkeypatch.setattr("builtins.open", counting_open)
    observation = _hash(payload["path"])

    assert observation.sha256 == payload["sha256"]
    # Several reads, none of them the whole file.
    assert len(reads) > 2
    assert max(reads) <= verification.CHUNK_BYTES


def test_the_size_counted_is_what_was_hashed(payload):
    """Not what stat() said. A file growing under the reader would otherwise
    produce a digest and a size describing different content."""
    observation = _hash(payload["path"])
    assert observation.byte_size == os.path.getsize(payload["path"])
    assert observation.sha256 == hashlib.sha256(
        payload["path"].read_bytes()
    ).hexdigest()


def test_a_smaller_chunk_gives_the_same_digest(payload):
    coarse = _hash(payload["path"])
    fine = _hash(payload["path"], chunk_bytes=997)
    assert coarse.sha256 == fine.sha256
    assert coarse.byte_size == fine.byte_size


def test_a_zero_byte_file_hashes_to_the_empty_digest(tmp_path):
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    observation = _hash(empty)
    assert observation.byte_size == 0
    assert observation.sha256 == hashlib.sha256(b"").hexdigest()


def test_a_missing_file_is_a_failure_not_a_skip(tmp_path):
    """A pass that ignores what it could not open reports success for a backup
    nobody has ever read."""
    with pytest.raises(InvError) as caught:
        _hash(tmp_path / "absent.bin")
    assert "does not exist" in caught.value.message


def test_a_directory_is_a_failure(tmp_path):
    with pytest.raises(InvError):
        _hash(tmp_path)


@pytest.mark.parametrize(
    "path",
    ["/etc/shadow", "/proc/self/environ"] if sys.platform != "win32"
    else [r"C:\Windows\System32\config\SAM", r"C:\Windows\win.ini"],
)
def test_a_protected_path_is_refused_before_it_is_opened(path):
    """A verification job must not be steerable into the OS by a crafted record."""
    with pytest.raises(InvError) as caught:
        verification.hash_file(path, os_type=_os_type())
    assert "refusing to read that path" in caught.value.message


def test_a_relative_path_is_refused(tmp_path):
    with pytest.raises(InvError):
        verification.hash_file("backup.bin", os_type=_os_type())


def test_a_nonpositive_chunk_is_refused(payload):
    with pytest.raises(InvError):
        _hash(payload["path"], chunk_bytes=0)


def test_the_observation_reports_how_long_the_read_took(payload):
    """A verification that takes an hour is a finding about the storage even
    when the digest matches."""
    ticks = iter([100.0, 142.5])
    observation = verification.hash_file(
        payload["path"], os_type=_os_type(), monotonic=lambda: next(ticks)
    )
    assert observation.duration_seconds == pytest.approx(42.5)


def test_matches_checks_both_digest_and_size(payload):
    observation = _hash(payload["path"])
    assert observation.matches(
        expected_sha256=payload["sha256"], expected_size=payload["size"]
    )
    # A truncated file has a perfectly valid SHA-256 of the wrong content.
    assert not observation.matches(
        expected_sha256=payload["sha256"], expected_size=payload["size"] - 1
    )
    assert not observation.matches(expected_sha256="0" * 64, expected_size=None)
