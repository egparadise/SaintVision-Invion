"""Regression cases prepared for the later execution phase; not run at delivery."""

import base64
import hashlib
from copy import deepcopy
import pytest
from inv.errors import DomainError
from inv.remote_git import GitHubRepository, export_snapshot, git_files
from inv.terminal import TerminalText
from inv.workspace_editor import edited_snapshot
from inv.workspace_files import FORMAT, canonical, decode_snapshot

WORKSPACE = "wsp_" + "0" * 26


def snapshot(files):
    directories = set()
    entries = []
    for path, data in sorted(files.items()):
        parts = path.split("/")
        directories.update("/".join(parts[:n]) for n in range(1, len(parts)))
        entries.append(
            {
                "path": path,
                "executable": False,
                "sizeBytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "dataBase64": base64.b64encode(data).decode(),
            }
        )
    return canonical(
        {
            "format": FORMAT,
            "workspaceId": WORKSPACE,
            "directories": sorted(directories),
            "files": entries,
        }
    )


def test_editor_compare_and_swap_never_mutates_original():
    original = snapshot({"src/main.py": b"old"})
    edit = {
        "path": "src/main.py",
        "expectedSha256": hashlib.sha256(b"old").hexdigest(),
        "dataBase64": base64.b64encode(b"new").decode(),
        "executable": False,
    }
    changed = edited_snapshot(original, WORKSPACE, [edit])
    assert decode_snapshot(changed, WORKSPACE)[1]["src/main.py"] == b"new"
    assert decode_snapshot(original, WORKSPACE)[1]["src/main.py"] == b"old"
    with pytest.raises(DomainError):
        edited_snapshot(changed, WORKSPACE, [edit])


@pytest.mark.parametrize(
    "path", ["../escape", "src/MAIN.py", "src/main.py/child", "C:/outside", "x\\y"]
)
def test_editor_rejects_escape_case_alias_and_file_directory_collision(path):
    with pytest.raises(DomainError):
        edited_snapshot(
            snapshot({"src/main.py": b"old"}),
            WORKSPACE,
            [{"path": path, "expectedSha256": None, "dataBase64": "eA==", "executable": False}],
        )


def test_remote_export_excludes_local_git_credentials_and_deletes_only_base_files():
    before = snapshot({"gone": b"old", "same": b"same"})
    raw = snapshot(
        {".git/config": b"credential must not be exported", "new": b"new", "same": b"same"}
    )
    after = export_snapshot(raw, WORKSPACE)
    assert set(git_files(after, WORKSPACE)) == {"new", "same"}
    assert GitHubRepository.changes(before, after, WORKSPACE) == {
        "additions": [{"path": "new", "contents": "bmV3"}],
        "deletions": [{"path": "gone"}],
    }


def test_remote_git_refuses_executable_and_empty_directory_loss():
    import json

    manifest = json.loads(snapshot({"file": b"x"}))
    for change in ("executable", "empty-directory"):
        current = deepcopy(manifest)
        if change == "executable":
            current["files"][0]["executable"] = True
        else:
            current["directories"] = ["empty"]
        with pytest.raises(DomainError):
            git_files(canonical(current), WORKSPACE)


def frame(cursor, data):
    return {"cursor": cursor + len(data), "dataBase64": base64.b64encode(data).decode()}


def test_terminal_redacts_secret_split_across_frames_and_preserves_utf8():
    text = TerminalText()
    first = b"Authorization: Be"
    assert text.accept(frame(0, first)) == ""
    second = b"arer secret-value\n" + "한글\n".encode()
    assert text.accept(frame(len(first), second)) == "[redacted]\n한글\n"
    with pytest.raises(DomainError):
        text.accept(frame(0, b"replayed\n"))


def test_terminal_private_key_multiline_and_ansi_are_not_forwarded():
    text = TerminalText()
    data = b"-----BEGIN PRIVATE KEY-----\nprivate bytes\n-----END PRIVATE KEY-----\n\x1b[31mok\x1b[0m\n"
    assert text.accept(frame(0, data)) == "[redacted]\n[redacted]\n[redacted]\nok\n"


def test_remote_reconcile_refuses_different_parent_message_or_content():
    repository = object.__new__(GitHubRepository)
    raw = snapshot({"file": b"approved"})
    operation = "00000000-0000-4000-8000-000000000001"
    expected = "a" * 40
    valid = {
        "parents": [{"sha": expected}],
        "message": "SaintVision approved Workspace update\n\nSaintVision-Operation: " + operation,
    }
    for kind in ("parent", "message", "content"):
        info = deepcopy(valid)
        content = raw
        if kind == "parent":
            info["parents"][0]["sha"] = "b" * 40
        if kind == "message":
            info["message"] += " different"
        if kind == "content":
            content = snapshot({"file": b"unapproved"})
        repository.snapshot = lambda *_: (content, info)
        with pytest.raises(DomainError):
            repository.reconcile(operation, expected, raw, WORKSPACE, candidate="c" * 40)
