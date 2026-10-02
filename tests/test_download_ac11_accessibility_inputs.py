"""Windows-safe download tests for AC-11 accessibility provenance inputs."""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import download_ac11_accessibility_inputs as tool  # noqa: E402


RUN_ID = "12345"
ARTIFACT_ID = "67890"


def _zip() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as bundle:
        bundle.writestr("report.json", "{}")
    return stream.getvalue()


def _downloader(path: str) -> bytes:
    if path.endswith(f"runs/{RUN_ID}"):
        return json.dumps({"id": int(RUN_ID)}).encode()
    if path.endswith(f"artifacts/{ARTIFACT_ID}"):
        return json.dumps({"id": int(ARTIFACT_ID), "workflow_run": {"id": int(RUN_ID)}}).encode()
    if path.endswith(f"artifacts/{ARTIFACT_ID}/zip"):
        return _zip()
    raise AssertionError(path)


def test_download_writes_utf8_without_bom_and_an_intact_zip(tmp_path: Path):
    run, artifact, archive = tool.download_inputs(RUN_ID, ARTIFACT_ID, tmp_path, downloader=_downloader)
    assert not run.read_bytes().startswith(b"\xef\xbb\xbf")
    assert not artifact.read_bytes().startswith(b"\xef\xbb\xbf")
    assert zipfile.is_zipfile(archive)
    assert json.loads(run.read_text(encoding="utf-8"))["id"] == int(RUN_ID)


@pytest.mark.parametrize("mutation", ["wrong-run", "corrupt-zip", "overwrite"])
def test_download_fails_closed_for_identity_corruption_or_overwrite(tmp_path: Path, mutation: str):
    def downloader(path: str) -> bytes:
        if mutation == "wrong-run" and path.endswith(f"runs/{RUN_ID}"):
            return b'{"id":999}'
        if mutation == "corrupt-zip" and path.endswith("/zip"):
            return b"not-a-zip"
        return _downloader(path)

    if mutation == "overwrite":
        (tmp_path / "run.json").write_text("occupied", encoding="utf-8")
    with pytest.raises(tool.DownloadError):
        tool.download_inputs(RUN_ID, ARTIFACT_ID, tmp_path, downloader=downloader)


def test_cli_rejects_non_numeric_identifiers(tmp_path: Path):
    assert tool.main(["--run-id", "1x", "--artifact-id", ARTIFACT_ID,
                      "--output-dir", str(tmp_path)]) == 2
