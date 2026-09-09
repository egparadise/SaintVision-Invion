import base64
import hashlib
from copy import deepcopy
import pytest
from inv.errors import DomainError
from inv.ids import new_id
from inv.workspace_files import canonical, decode_snapshot, portable_path, FORMAT


def manifest():
    wid = new_id("wsp")
    return {
        "format": FORMAT,
        "workspaceId": wid,
        "directories": ["src"],
        "files": [
            {
                "path": "src/main.py",
                "executable": False,
                "sha256": hashlib.sha256(b"print(1)").hexdigest(),
                "sizeBytes": 8,
                "dataBase64": base64.b64encode(b"print(1)").decode(),
            }
        ],
    }


def test_snapshot_manifest_preserves_real_bytes_and_identity():
    doc = manifest()
    parsed, contents = decode_snapshot(canonical(doc), doc["workspaceId"])
    assert parsed == doc and contents == {"src/main.py": b"print(1)"}
    with pytest.raises(DomainError):
        decode_snapshot(canonical(doc), new_id("wsp"))


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "../escape",
        "a/../b",
        "a//b",
        "C:/escape",
        "a\\b",
        "%2e%2e/file",
        "NUL",
        "aux.txt",
        "COM1.log",
        "a.",
        "a ",
        "\x00",
        "a/",
        "a/" * 16 + "z",
    ],
)
def test_nonportable_or_escaping_paths_are_rejected(path):
    with pytest.raises(DomainError):
        portable_path(path)


@pytest.mark.parametrize(
    "change",
    [
        "hash",
        "size",
        "type",
        "duplicate",
        "case",
        "file-parent",
        "unknown",
        "noncanonical",
    ],
)
def test_manifest_conflicts_and_tampering_are_rejected(change):
    doc = manifest()
    if change == "hash":
        doc["files"][0]["sha256"] = "0" * 64
    if change == "size":
        doc["files"][0]["sizeBytes"] = 7
    if change == "type":
        doc["files"][0]["executable"] = 1
    if change == "duplicate":
        doc["files"].append(deepcopy(doc["files"][0]))
    if change == "case":
        doc["directories"].append("SRC")
    if change == "file-parent":
        doc["directories"] = []
    if change == "unknown":
        doc["symlinks"] = []
    raw = canonical(doc) + (b" " if change == "noncanonical" else b"")
    with pytest.raises(DomainError):
        decode_snapshot(raw, doc["workspaceId"])
