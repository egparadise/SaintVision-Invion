"""Packet source-mode checks use Git objects, without any OS symlink privilege."""

from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile

import pytest

from tools import build_fleet5_setup_packet as builder


def _git(repo, *args, data=None):
    return subprocess.run(["git", *args], cwd=repo, input=data,
                          capture_output=True, check=True).stdout.strip()


def _source(tmp_path, monkeypatch, mode="100644"):
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    repo = tmp_path / "repository"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "core.longpaths", "true")  # This disposable repository only.
    plan = repo / builder.PLAN
    plan.parent.mkdir(parents=True)
    plan.write_text(json.dumps({"taskId": builder.TASK, "executed": False,
                               "actualF5": {"queryExecuted": False, "counts": {"nodes": None},
                                            "physicalAcceptance": False}}), encoding="utf-8")
    regular = repo / "regular.bin"
    regular.write_bytes(b"regular committed source\x00\xff")
    _git(repo, "add", "--", ".")
    if mode == "120000":
        blob = _git(repo, "hash-object", "-w", "--stdin", data=b"../outside-sentinel")
        # No on-disk link exists: the index records the real Git symlink mode.
        _git(repo, "update-index", "--add", "--cacheinfo", "120000," + blob.decode() + ",source-link")
    elif mode == "100755":
        blob = _git(repo, "rev-parse", ":regular.bin").decode()
        _git(repo, "update-index", "--cacheinfo", "100755," + blob + ",regular.bin")
    tree = _git(repo, "write-tree").decode()
    source = _git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                  "commit-tree", tree, data=b"disposable packet source fixture\n").decode()
    monkeypatch.setattr(builder, "ROOT", repo)
    return repo, source


def test_git_symlink_mode_refused_before_any_output_without_materializing_link(tmp_path, monkeypatch):
    sentinel = tmp_path / "outside-sentinel"
    sentinel.write_bytes(b"untouched")
    repo, source = _source(tmp_path, monkeypatch, "120000")
    assert not (repo / "source-link").exists()
    assert b"120000 blob" in _git(repo, "ls-tree", "-r", source)
    with redirect_stdout(io.StringIO()), pytest.raises(ValueError, match="120000"):
        builder.build(source)
    assert not (repo / ".work").exists(), "Refused source must produce no output directory/archive"
    assert not (repo / "source-link").exists()
    assert sentinel.read_bytes() == b"untouched"


@pytest.mark.parametrize("mode", ["100644", "100755"])
def test_regular_git_modes_have_exact_blob_and_packet_readback(tmp_path, monkeypatch, mode):
    repo, source = _source(tmp_path, monkeypatch, mode)
    with redirect_stdout(io.StringIO()):
        output = builder.build(source)
    manifest = json.loads((output / "candidate-source-manifest.json").read_bytes())
    inventory = json.loads((output / "source-inventory.json").read_bytes())
    entry = next(item for item in inventory if item["path"] == "regular.bin")
    assert entry["mode"] == mode
    expected = _git(repo, "cat-file", "blob", entry["gitBlobSHA1"])
    with zipfile.ZipFile(output / manifest["sourceArchive"]["name"]) as archive:
        assert archive.read("regular.bin") == expected
    receipt = json.loads((output / "packet-receipt.json").read_bytes())
    packet = output / receipt["packet"]
    assert hashlib.sha256(packet.read_bytes()).hexdigest() == receipt["sha256"]
    assert receipt["packetReadbackVerified"] is True
    assert manifest["archiveInventory"]["everyGitBlobCompared"] is True
    assert manifest["setupPlan"]["executed"] is False
