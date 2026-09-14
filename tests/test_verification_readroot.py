"""Actual OS files, links and concurrent mutations at the worker read boundary."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from saintvision.errors import InvError
from saintvision.services.verification import hash_file
from saintvision.storage.readroot import ReadRoot

NATIVE = "windows" if sys.platform == "win32" else "linux"


@pytest.fixture
def storage(tmp_path):
    root = tmp_path / "authorized"
    root.mkdir()
    data = root / "backup.bin"
    data.write_bytes(b"original backup")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "backup.bin").write_bytes(b"foreign bytes")
    return root, data, outside, ReadRoot(root)


def observe(path, root):
    return hash_file(path, allowed_root=root, os_type=NATIVE, chunk_bytes=3)


def test_root_is_required(storage):
    with pytest.raises(InvError, match="authorized read root"):
        hash_file(storage[1], os_type=NATIVE)


def test_an_explicit_root_reads_nested_files(storage):
    root, _, _, authorized = storage
    folder = root / "nested"
    folder.mkdir()
    target = folder / "bytes"
    target.write_bytes(b"ok")
    assert observe(target, authorized).sha256 == hashlib.sha256(b"ok").hexdigest()


def test_an_outside_file_is_not_read(storage, monkeypatch):
    root, _, outside, authorized = storage
    opened = []
    real = os.fdopen

    def track(*args, **kwargs):
        opened.append(True)
        return real(*args, **kwargs)

    monkeypatch.setattr(os, "fdopen", track)
    with pytest.raises(InvError):
        observe(outside / "backup.bin", authorized)
    assert opened == []


def test_sibling_with_root_prefix_is_not_authorized(storage):
    root, _, _, authorized = storage
    sibling = root.with_name(root.name + "-other")
    sibling.mkdir()
    path = sibling / "bytes"
    path.write_bytes(b"private")
    with pytest.raises(InvError):
        observe(path, authorized)


def test_parent_traversal_is_not_reinterpreted(storage):
    root, _, _, authorized = storage
    with pytest.raises(InvError):
        observe(root / ".." / root.name / "backup.bin", authorized)


def test_encoded_path_is_not_reinterpreted(storage):
    root, _, _, authorized = storage
    with pytest.raises(InvError):
        observe(root / "%62ackup.bin", authorized)


def test_hardlinked_file_is_refused(storage):
    root, _, outside, authorized = storage
    link = root / "hardlink"
    os.link(outside / "backup.bin", link)
    with pytest.raises(InvError):
        observe(link, authorized)


def test_replaced_authorized_root_is_refused(storage):
    root, target, _, authorized = storage
    root.rename(root.with_name("old-root"))
    root.mkdir()
    target.write_bytes(b"replacement")
    with pytest.raises(InvError):
        observe(target, authorized)


def directory_link(link, destination):
    if sys.platform == "win32":
        # Junction creation needs no symlink privilege. Paths are owned pytest
        # directories, single-quoted with embedded quotes escaped.
        quote = lambda p: "'" + str(p).replace("'", "''") + "'"
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path "
                + quote(link)
                + " -Target "
                + quote(destination)
                + " | Out-Null",
            ],
            capture_output=True,
        )
        assert result.returncode == 0, "owned test junction creation failed"
    else:
        link.symlink_to(destination, target_is_directory=True)


def test_linked_child_directory_is_refused(storage):
    root, _, outside, authorized = storage
    link = root / "link"
    directory_link(link, outside)
    try:
        with pytest.raises(InvError):
            observe(link / "backup.bin", authorized)
    finally:
        os.rmdir(link) if sys.platform == "win32" else link.unlink()


def test_linked_root_cannot_be_authorized(storage):
    root, _, outside, _ = storage
    link = root / "root-link"
    directory_link(link, outside)
    try:
        with pytest.raises(OSError):
            ReadRoot(link)
    finally:
        os.rmdir(link) if sys.platform == "win32" else link.unlink()


def test_filesystem_root_is_not_an_authorization(storage):
    with pytest.raises(OSError):
        ReadRoot(Path(storage[0].anchor))


@pytest.mark.parametrize("chunk", [True, 1.5, 4 * 1024 * 1024 + 1])
def test_chunk_memory_budget_is_bounded(storage, chunk):
    with pytest.raises(InvError):
        hash_file(storage[1], allowed_root=storage[3], os_type=NATIVE, chunk_bytes=chunk)


def intercept_read(monkeypatch, action):
    real = os.fdopen
    called = []

    def opened(*args, **kwargs):
        handle = real(*args, **kwargs)
        original = handle.read

        def read(size):
            result = original(size)
            if not called:
                called.append(True)
                action()
            return result

        handle.read = read
        return handle

    monkeypatch.setattr(os, "fdopen", opened)
    return called


@pytest.mark.parametrize("mutation", ["write", "replace", "root-rename"])
def test_during_read_mutation_is_blocked_or_observation_rejected(storage, monkeypatch, mutation):
    root, target, outside, authorized = storage

    def mutate():
        if mutation == "write":
            target.write_bytes(b"modified backup")
        elif mutation == "replace":
            os.replace(outside / "backup.bin", target)
        else:
            root.rename(root.with_name("moved"))

    if sys.platform == "win32":

        def attempt():
            with pytest.raises(OSError):
                mutate()

        called = intercept_read(monkeypatch, attempt)
        assert observe(target, authorized).sha256 == hashlib.sha256(b"original backup").hexdigest()
    else:
        called = intercept_read(monkeypatch, mutate)
        with pytest.raises(InvError):
            observe(target, authorized)
    assert called == [True]


if sys.platform == "linux":

    def test_same_size_write_is_rejected_even_when_stat_version_is_unchanged(storage, monkeypatch):
        import stat

        _, target, _, authorized = storage
        original_stat = os.fstat
        versions = []

        def coarse_stat(fd):
            current = original_stat(fd)
            if stat.S_ISREG(current.st_mode):
                if not versions:
                    versions.append(current)
                return versions[0]
            return current

        monkeypatch.setattr(os, "fstat", coarse_stat)
        intercept_read(monkeypatch, lambda: target.write_bytes(b"modified backup"))
        with pytest.raises(InvError, match="file changed during read"):
            observe(target, authorized)

    def test_a_continuously_growing_file_does_not_extend_read_budget(storage, monkeypatch):
        _, target, _, authorized = storage
        initial_size = target.stat().st_size
        real = os.fdopen
        read_bytes = []

        def opened(*args, **kwargs):
            handle = real(*args, **kwargs)
            original = handle.read

            def read(size):
                with open(target, "ab") as writer:
                    writer.write(b"growth" * 100)
                result = original(size)
                read_bytes.append(len(result))
                assert sum(read_bytes) <= initial_size + 1
                return result

            handle.read = read
            return handle

        monkeypatch.setattr(os, "fdopen", opened)
        with pytest.raises(InvError):
            observe(target, authorized)
        assert sum(read_bytes) == initial_size + 1

    def test_nested_directory_replacement_during_read_is_rejected(storage, monkeypatch):
        root, _, _, authorized = storage
        folder = root / "nested"
        folder.mkdir()
        target = folder / "bytes"
        target.write_bytes(b"original backup")

        def replace():
            folder.rename(root / "old-nested")
            folder.mkdir()
            target.write_bytes(b"other backup")

        intercept_read(monkeypatch, replace)
        with pytest.raises(InvError):
            observe(target, authorized)

    @pytest.mark.parametrize("kind", ["symlink", "fifo", "directory"])
    def test_nonregular_final_objects_are_refused(storage, kind):
        root, _, outside, authorized = storage
        target = root / "special"
        if kind == "symlink":
            target.symlink_to(outside / "backup.bin")
        elif kind == "fifo":
            os.mkfifo(target)
        else:
            target.mkdir()
        with pytest.raises(InvError):
            observe(target, authorized)


if sys.platform == "win32":

    def test_existing_writer_prevents_read(storage):
        _, target, _, authorized = storage
        with open(target, "r+b"):
            with pytest.raises(InvError):
                observe(target, authorized)
