"""Path safety.

The Storage plan names the classes to cover: decoding, absolute paths, UNC and
drive forms, ``..``, and junctions/symlinks, per OS. Each row below is one of
those, and the reason it is dangerous is in the id.
"""

from __future__ import annotations

import os
import sys

import pytest

from saintvision.storage.pathsafe import (
    UnsafePath,
    build_uri,
    normalize_contribution_path,
    resolve_within,
    validate_relative_path,
)

ACCEPTED_ROOTS = [
    (r"C:\inv\data", "windows", r"C:\inv\data"),
    (r"D:\Lab\Share\node01", "windows", r"D:\Lab\Share\node01"),
    (r"C:\inv\data\.\sub", "windows", r"C:\inv\data\sub"),
    ("/srv/inv/data", "linux", "/srv/inv/data"),
    ("/srv/inv/./data/", "linux", "/srv/inv/data"),
    ("/home/lab/contrib", "linux", "/home/lab/contrib"),
]

REJECTED_ROOTS = [
    # id, path, os
    ("windows_system_dir", r"C:\Windows\System32", "windows"),
    ("windows_program_files", r"C:\Program Files\app", "windows"),
    ("windows_unc_share", r"\\fileserver\share", "windows"),
    ("windows_device_namespace", "\\\\?\\C:\\inv", "windows"),
    ("windows_dot_device_namespace", "\\\\.\\PhysicalDrive0", "windows"),
    ("windows_drive_relative", r"C:inv\data", "windows"),
    ("windows_whole_drive", "C:\\", "windows"),
    ("windows_reserved_con", r"C:\inv\CON", "windows"),
    ("windows_reserved_com1_with_ext", r"C:\inv\COM1.txt", "windows"),
    ("windows_alternate_data_stream", r"C:\inv\data\file.txt:hidden", "windows"),
    ("windows_trailing_dot_segment", "C:\\inv\\data.\\x", "windows"),
    ("windows_traverses_into_system", r"C:\inv\..\Windows", "windows"),
    ("windows_no_drive", r"\inv\data", "windows"),
    ("posix_relative", "inv/data", "linux"),
    ("posix_root", "/", "linux"),
    ("posix_proc", "/proc/self/environ", "linux"),
    ("posix_etc", "/etc/shadow", "linux"),
    ("posix_traversal_escapes_to_etc", "/srv/../etc", "linux"),
    ("posix_backslash_not_a_separator", "/srv/inv\\data", "linux"),
    ("posix_percent_encoded_traversal", "/srv/%2e%2e/etc", "linux"),
    ("posix_double_encoded_traversal", "/srv/%252e%252e/etc", "linux"),
    ("empty", "", "linux"),
    ("whitespace_only", "   ", "linux"),
    ("nul_byte", "/srv/inv\x00/data", "linux"),
    ("control_character", "/srv/inv\x01data", "linux"),
]


@pytest.mark.parametrize("declared,os_type,expected", ACCEPTED_ROOTS)
def test_accepted_contribution_roots(declared, os_type, expected):
    assert normalize_contribution_path(declared, os_type).normalized == expected


@pytest.mark.parametrize(
    "path,os_type",
    [(p, o) for _, p, o in REJECTED_ROOTS],
    ids=[i for i, _, _ in REJECTED_ROOTS],
)
def test_rejected_contribution_roots(path, os_type):
    with pytest.raises(UnsafePath):
        normalize_contribution_path(path, os_type)


def test_unknown_os_type_is_rejected():
    with pytest.raises(UnsafePath):
        normalize_contribution_path("/srv/inv", "solaris")


def test_normalisation_is_idempotent():
    once = normalize_contribution_path(r"C:\inv\data\.\sub", "windows").normalized
    twice = normalize_contribution_path(once, "windows").normalized
    assert once == twice


def test_unicode_spellings_normalise_to_one_path():
    # NFD and NFC spellings of the same Korean folder name must be one
    # contribution, or the unique constraint on normalized_path is defeated.
    composed = "/srv/inv/\uD55C"          # 한
    decomposed = "/srv/inv/\u1112\u1161\u11AB"
    assert (
        normalize_contribution_path(composed, "linux").normalized
        == normalize_contribution_path(decomposed, "linux").normalized
    )


RELATIVE_ACCEPTED = [
    ("a/b/c.txt", "linux", "a/b/c.txt"),
    ("a\\b\\c.txt", "windows", "a/b/c.txt"),
    ("./a/./b", "linux", "a/b"),
]

RELATIVE_REJECTED = [
    ("parent_escape", "../secrets", "linux"),
    ("nested_parent_escape", "a/b/../../../etc", "linux"),
    ("absolute_posix", "/etc/passwd", "linux"),
    ("absolute_windows", "\\Windows", "windows"),
    ("drive_qualified", "C:/Windows", "windows"),
    ("encoded_parent", "%2e%2e/secrets", "linux"),
    ("double_encoded_parent", "%252e%252e/secrets", "linux"),
    ("reserved_device", "sub/NUL", "windows"),
    ("colon_stream", "file.txt:stream", "linux"),
    ("empty_after_normalisation", "./.", "linux"),
]


@pytest.mark.parametrize("relative,os_type,expected", RELATIVE_ACCEPTED)
def test_accepted_relative_paths(relative, os_type, expected):
    assert validate_relative_path(relative, os_type) == expected


@pytest.mark.parametrize(
    "relative,os_type",
    [(p, o) for _, p, o in RELATIVE_REJECTED],
    ids=[i for i, _, _ in RELATIVE_REJECTED],
)
def test_rejected_relative_paths(relative, os_type):
    with pytest.raises(UnsafePath):
        validate_relative_path(relative, os_type)


def test_resolve_within_accepts_a_contained_path(tmp_path):
    (tmp_path / "sub").mkdir()
    target = tmp_path / "sub" / "f.txt"
    target.write_text("x", encoding="utf-8")
    resolved = resolve_within(tmp_path, "sub/f.txt", os_type="linux")
    assert resolved == target.resolve()


def test_resolve_within_rejects_traversal(tmp_path):
    with pytest.raises(UnsafePath):
        resolve_within(tmp_path, "../outside.txt", os_type="linux")


@pytest.mark.skipif(
    sys.platform == "win32" and not os.environ.get("INV_TEST_SYMLINKS"),
    reason="creating a symlink on Windows needs privilege; set INV_TEST_SYMLINKS to run",
)
def test_resolve_within_rejects_a_symlink_pointing_outside(tmp_path):
    """The check a syntactic validator cannot make.

    ``inside/link`` is a legal relative path with no ``..`` in it. Only
    resolution reveals that it lands outside the root.
    """
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("s", encoding="utf-8")
    (root / "link").symlink_to(outside, target_is_directory=True)

    assert validate_relative_path("link/secret.txt", "linux") == "link/secret.txt"
    with pytest.raises(UnsafePath):
        resolve_within(root, "link/secret.txt", os_type="linux")


def test_build_uri_per_namespace():
    assert (
        build_uri("dataset", name="mnist", version="1.0.0", relative_path="train/x.bin")
        == "inv://datasets/mnist@1.0.0/train/x.bin"
    )
    assert (
        build_uri("model", name="resnet", version="2", relative_path="w.safetensors")
        == "inv://models/resnet@2/w.safetensors"
    )
    # ADR-010: artifacts are addressed by run and artifact id, not name@version.
    assert (
        build_uri("artifact", run_id="run_01", artifact_id="art_02")
        == "inv://artifacts/run_01/art_02"
    )
    assert (
        build_uri("workspace", workspace_id="wsp_01", relative_path="src/main.py")
        == "inv://workspaces/wsp_01/src/main.py"
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"kind": "dataset", "name": "mnist"},          # no version
        {"kind": "dataset", "version": "1"},           # no name
        {"kind": "dataset", "name": "a@b", "version": "1"},  # '@' in name
        {"kind": "artifact", "run_id": "run_01"},      # no artifact id
        {"kind": "workspace", "workspace_id": "wsp"},  # no path
        {"kind": "nonsense"},
    ],
)
def test_build_uri_rejects_incomplete_input(kwargs):
    kind = kwargs.pop("kind")
    with pytest.raises(ValueError):
        build_uri(kind, **kwargs)
