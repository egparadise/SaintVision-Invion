#!/usr/bin/env python3
"""Download AC-11 GitHub provenance inputs without PowerShell text transcoding."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile
from io import BytesIO
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "egparadise/SaintVision-Invion"
NUMERIC = re.compile(r"^[0-9]+$")


class DownloadError(RuntimeError):
    """Redacted, fail-closed download error."""


def _strict_json(raw: bytes, label: str) -> dict[str, Any]:
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise DownloadError(f"{label} contains a duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError):
        raise DownloadError(f"{label} is not UTF-8 JSON") from None
    if not isinstance(value, dict):
        raise DownloadError(f"{label} is not a JSON object")
    return value


def _gh_bytes(path: str) -> bytes:
    result = subprocess.run(
        ["gh", "api", path],
        cwd=ROOT,
        capture_output=True,
        check=False,
        shell=False,
    )
    if result.returncode != 0:
        raise DownloadError("GitHub API download failed")
    return result.stdout


def _write_private(path: Path, raw: bytes) -> None:
    if path.exists():
        raise DownloadError(f"refusing to overwrite existing {path.name}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(raw)
    finally:
        os.close(descriptor)


def download_inputs(
    run_id: str,
    artifact_id: str,
    output_directory: Path,
    *,
    downloader: Callable[[str], bytes] = _gh_bytes,
) -> tuple[Path, Path, Path]:
    if not NUMERIC.fullmatch(run_id) or not NUMERIC.fullmatch(artifact_id):
        raise DownloadError("run and artifact IDs must contain digits only")
    run = _strict_json(
        downloader(f"repos/{REPOSITORY}/actions/runs/{run_id}"), "run metadata"
    )
    artifact = _strict_json(
        downloader(f"repos/{REPOSITORY}/actions/artifacts/{artifact_id}"),
        "artifact metadata",
    )
    workflow_run = artifact.get("workflow_run")
    if (
        str(run.get("id")) != run_id
        or str(artifact.get("id")) != artifact_id
        or not isinstance(workflow_run, dict)
        or str(workflow_run.get("id")) != run_id
    ):
        raise DownloadError("GitHub metadata identity differs from requested IDs")
    archive = downloader(f"repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip")
    if not archive or not zipfile.is_zipfile(BytesIO(archive)):
        raise DownloadError("artifact download is not a ZIP archive")

    output_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_path = output_directory / "run.json"
    artifact_path = output_directory / "artifact.json"
    archive_path = output_directory / "artifact.zip"
    _write_private(
        run_path,
        (json.dumps(run, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"),
    )
    _write_private(
        artifact_path,
        (json.dumps(artifact, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        ),
    )
    _write_private(archive_path, archive)
    return run_path, artifact_path, archive_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        download_inputs(args.run_id, args.artifact_id, args.output_dir)
    except (DownloadError, OSError) as exc:
        print(f"AC-11 input download refused: {exc}", file=__import__("sys").stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
