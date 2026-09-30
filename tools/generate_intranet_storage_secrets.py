#!/usr/bin/env python3
"""Create missing intranet ObjectStore secret files without printing values."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets


def _exclusive_private_file(path: Path, body: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)
    if os.name != "nt":
        os.chmod(path, 0o600)


def create_pitr_credentials(directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("secret directory must be a real directory")
    if os.name != "nt":
        os.chmod(directory, 0o700)

    access_key = "pitr-" + secrets.token_hex(8)
    secret_key = secrets.token_urlsafe(36)
    env_path = directory / "pitr-service-user.env"
    json_path = directory / "pitr-object-store-credential.json"
    _exclusive_private_file(
        env_path,
        f"PITR_KEY={access_key}\nPITR_SECRET={secret_key}\n".encode("ascii"),
    )
    try:
        _exclusive_private_file(
            json_path,
            (
                json.dumps(
                    {"accessKeyId": access_key, "secretAccessKey": secret_key},
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("ascii"),
        )
    except Exception:
        env_path.unlink(missing_ok=True)
        raise
    return env_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        paths = create_pitr_credentials(args.directory)
    except (OSError, ValueError):
        print("secret bootstrap refused; no credential value was printed")
        return 2
    print("created=" + ",".join(path.name for path in paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
