"""Build, install, and run the offline Node leaf-rotation Python runtime.

The installer intentionally uses only the Python standard library.  Package
selection and hashes are anchored in the reviewed lock next to this file; the
Node never invokes pip or reaches the network.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import runpy
import shutil
import stat
import sys
import sysconfig
import tempfile
import urllib.request
import zipfile

LOCK_NAME = "leaf-rotation-runtime-lock.json"
LOCK_SHA256 = "06710d854ff52578949249065dd009de6561bc779c4b21c5355262e59a527a8c"
WORKER_SHA256 = "bca76df80a7bf80a6847e9b115679b1aa3e698d8b3a80ff843aacdd1370cd9b4"
BUNDLE_SCHEMA = "saintvision-leaf-rotation-runtime-bundle:1"
INSTALL_SCHEMA = "saintvision-leaf-rotation-runtime-install:1"
MAX_WHEEL_BYTES = 16 * 1024 * 1024
MAX_RUNTIME_BYTES = 64 * 1024 * 1024


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _regular(path: Path, *, limit: int) -> bytes:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
        raise ValueError(f"{path.name} must be a bounded regular file")
    return path.read_bytes()


def _write_file(path: Path, value: bytes) -> None:
    path.write_bytes(value)
    os.chmod(path, 0o600)
    with path.open("r+b") as stream:
        os.fsync(stream.fileno())


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def load_lock() -> tuple[bytes, dict]:
    path = Path(__file__).with_name(LOCK_NAME)
    raw = _regular(path, limit=65536)
    if _sha256(raw) != LOCK_SHA256:
        raise ValueError("Leaf-rotation runtime lock digest differs from reviewed code")
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "source",
        "platforms",
        "wheels",
    }:
        raise ValueError("Leaf-rotation runtime lock shape differs")
    if value["schemaVersion"] != "saintvision-leaf-rotation-runtime-lock:1":
        raise ValueError("Leaf-rotation runtime lock version differs")
    platforms = value["platforms"]
    wheels = value["wheels"]
    if not isinstance(platforms, dict) or set(platforms) != {
        "cpython-312-x86_64-linux-gnu",
        "cpython-314-x86_64-linux-gnu",
    }:
        raise ValueError("Leaf-rotation runtime platform set differs")
    if not isinstance(wheels, dict) or len(wheels) != 4:
        raise ValueError("Leaf-rotation runtime wheel set differs")
    for filename, item in wheels.items():
        if (
            not isinstance(filename, str)
            or not filename.endswith(".whl")
            or not isinstance(item, dict)
            or set(item) != {"project", "version", "sha256", "url"}
            or not isinstance(item["sha256"], str)
            or len(item["sha256"]) != 64
            or not item["url"].startswith("https://files.pythonhosted.org/")
            or not item["url"].endswith("/" + filename)
        ):
            raise ValueError("Leaf-rotation runtime wheel authority differs")
    return raw, value


def _platform_key(lock: dict) -> str:
    observed = {
        "implementation": sys.implementation.name,
        "python": list(sys.version_info[:2]),
        "machine": platform.machine(),
        "sysconfigPlatform": sysconfig.get_platform(),
        "soabi": sysconfig.get_config_var("SOABI"),
    }
    matches = [
        key
        for key, expected in lock["platforms"].items()
        if all(observed[name] == expected[name] for name in observed)
    ]
    if len(matches) != 1:
        raise RuntimeError("Node Python ABI or architecture is not in the reviewed runtime lock")
    return matches[0]


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "SaintVision-leaf-runtime/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.status != 200 or response.geturl() != url:
            raise RuntimeError("Pinned wheel source redirected or did not return success")
        value = response.read(MAX_WHEEL_BYTES + 1)
    if not 0 < len(value) <= MAX_WHEEL_BYTES:
        raise RuntimeError("Pinned wheel is empty or oversized")
    return value


def build_bundle(output: Path) -> dict:
    lock_raw, lock = load_lock()
    if output.exists() or output.is_symlink():
        raise ValueError("Refusing to replace an existing runtime bundle")
    output.parent.mkdir(parents=True, exist_ok=True)
    downloaded: dict[str, bytes] = {}
    for filename, item in lock["wheels"].items():
        raw = _download(item["url"])
        if _sha256(raw) != item["sha256"]:
            raise RuntimeError("Pinned wheel digest differs from PyPI metadata")
        downloaded[filename] = raw
    manifest = {
        "schemaVersion": BUNDLE_SCHEMA,
        "lockSha256": LOCK_SHA256,
        "wheels": {name: lock["wheels"][name]["sha256"] for name in sorted(downloaded)},
    }
    temporary = output.with_name(output.name + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, raw in ((LOCK_NAME, lock_raw), ("runtime-bundle.json", _canonical(manifest))):
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o100600 << 16
                archive.writestr(info, raw)
            for filename in sorted(downloaded):
                info = zipfile.ZipInfo("wheels/" + filename, (1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o100600 << 16
                archive.writestr(info, downloaded[filename])
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    raw = _regular(output, limit=MAX_RUNTIME_BYTES)
    return {"bundle": str(output), "sha256": _sha256(raw), "bytes": len(raw), "wheelCount": 4}


def _bundle(bundle: Path, lock_raw: bytes, lock: dict) -> tuple[str, dict[str, bytes]]:
    raw = _regular(bundle, limit=MAX_RUNTIME_BYTES)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        expected = {LOCK_NAME, "runtime-bundle.json"} | {
            "wheels/" + name for name in lock["wheels"]
        }
        names = archive.namelist()
        if len(names) != len(expected) or set(names) != expected:
            raise ValueError("Offline runtime bundle member set differs")
        if archive.read(LOCK_NAME) != lock_raw:
            raise ValueError("Offline runtime bundle lock differs")
        manifest_raw = archive.read("runtime-bundle.json")
        manifest = json.loads(manifest_raw)
        expected_manifest = {
            "schemaVersion": BUNDLE_SCHEMA,
            "lockSha256": LOCK_SHA256,
            "wheels": {name: lock["wheels"][name]["sha256"] for name in sorted(lock["wheels"])},
        }
        if manifest != expected_manifest or manifest_raw != _canonical(expected_manifest):
            raise ValueError("Offline runtime bundle manifest differs")
        wheels = {}
        for filename, item in lock["wheels"].items():
            value = archive.read("wheels/" + filename)
            if not 0 < len(value) <= MAX_WHEEL_BYTES or _sha256(value) != item["sha256"]:
                raise ValueError("Offline runtime wheel digest differs")
            wheels[filename] = value
    return _sha256(raw), wheels


def _wheel_members(raw: bytes) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    total = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                info.is_dir()
                or not info.filename
                or info.filename.startswith("/")
                or "\\" in info.filename
                or any(part in {"", ".", ".."} for part in path.parts)
            ):
                if info.is_dir():
                    continue
                raise ValueError("Wheel contains an unsafe member path")
            if stat.S_IFMT(mode) not in {0, stat.S_IFREG}:
                raise ValueError("Wheel contains a non-regular member")
            if any(part.endswith(".data") for part in path.parts):
                raise ValueError("Wheel data relocation is outside the reviewed runtime shape")
            value = archive.read(info)
            total += len(value)
            if total > MAX_RUNTIME_BYTES or path.as_posix() in result:
                raise ValueError("Wheel contents are oversized or duplicated")
            result[path.as_posix()] = value
    if not result:
        raise ValueError("Wheel contains no runtime files")
    return result


def _expected_files(lock: dict, wheels: dict[str, bytes], key: str) -> dict[str, bytes]:
    expected: dict[str, bytes] = {}
    for filename in lock["platforms"][key]["wheels"]:
        raw = wheels[filename]
        expected[".wheels/" + filename] = raw
        for name, value in _wheel_members(raw).items():
            if name in expected:
                raise ValueError("Selected wheels install colliding files")
            expected[name] = value
    return expected


def _installed_files(runtime_dir: Path) -> dict[str, bytes]:
    found = {}
    for root, directories, files in os.walk(runtime_dir, followlinks=False):
        root_path = Path(root)
        for name in directories:
            if (root_path / name).is_symlink():
                raise ValueError("Standalone runtime contains a symlink")
        for name in files:
            path = root_path / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Standalone runtime contains a non-regular file")
            relative = path.relative_to(runtime_dir).as_posix()
            if relative != ".saintvision-runtime.json":
                found[relative] = path.read_bytes()
    return found


def validate_runtime(
    runtime_dir: Path, lock: dict, key: str, bundle_sha256: str | None = None
) -> dict:
    receipt_path = runtime_dir / ".saintvision-runtime.json"
    receipt_raw = _regular(receipt_path, limit=16384)
    receipt = json.loads(receipt_raw)
    if not isinstance(receipt, dict) or set(receipt) != {
        "schemaVersion",
        "platformKey",
        "lockSha256",
        "bundleSha256",
        "fileCount",
        "filesSha256",
    }:
        raise ValueError("Standalone runtime receipt shape differs")
    if (
        receipt["schemaVersion"] != INSTALL_SCHEMA
        or receipt["platformKey"] != key
        or receipt["lockSha256"] != LOCK_SHA256
        or (bundle_sha256 is not None and receipt["bundleSha256"] != bundle_sha256)
    ):
        raise ValueError("Standalone runtime receipt authority differs")
    wheel_names = lock["platforms"][key]["wheels"]
    wheels = {}
    for filename in wheel_names:
        raw = _regular(runtime_dir / ".wheels" / filename, limit=MAX_WHEEL_BYTES)
        if _sha256(raw) != lock["wheels"][filename]["sha256"]:
            raise ValueError("Installed runtime wheel digest differs")
        wheels[filename] = raw
    expected = _expected_files(lock, wheels, key)
    observed = _installed_files(runtime_dir)
    if set(observed) != set(expected) or any(
        observed[name] != value for name, value in expected.items()
    ):
        raise ValueError("Installed standalone runtime files differ from pinned wheels")
    files_digest = _sha256(_canonical({name: _sha256(expected[name]) for name in sorted(expected)}))
    if receipt["fileCount"] != len(expected) or receipt["filesSha256"] != files_digest:
        raise ValueError("Standalone runtime receipt does not describe installed files")
    return receipt


def install(bundle: Path, runtime_dir: Path) -> dict:
    if not runtime_dir.is_absolute():
        raise ValueError("Runtime directory must be absolute")
    lock_raw, lock = load_lock()
    key = _platform_key(lock)
    bundle_sha256, all_wheels = _bundle(bundle, lock_raw, lock)
    selected = {name: all_wheels[name] for name in lock["platforms"][key]["wheels"]}
    if runtime_dir.is_symlink():
        raise ValueError("Runtime directory must not be a symlink")
    if runtime_dir.exists():
        return validate_runtime(runtime_dir, lock, key, bundle_sha256)
    runtime_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix="." + runtime_dir.name + ".tmp-", dir=runtime_dir.parent)
    )
    try:
        os.chmod(temporary, 0o700)
        expected = _expected_files(lock, selected, key)
        for name, value in expected.items():
            target = temporary / PurePosixPath(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_file(target, value)
        files_digest = _sha256(
            _canonical({name: _sha256(expected[name]) for name in sorted(expected)})
        )
        receipt = {
            "schemaVersion": INSTALL_SCHEMA,
            "platformKey": key,
            "lockSha256": LOCK_SHA256,
            "bundleSha256": bundle_sha256,
            "fileCount": len(expected),
            "filesSha256": files_digest,
        }
        _write_file(temporary / ".saintvision-runtime.json", _canonical(receipt))
        for directory in sorted(
            (path for path in temporary.rglob("*") if path.is_dir()), reverse=True
        ):
            _fsync_directory(directory)
        _fsync_directory(temporary)
        os.replace(temporary, runtime_dir)
        _fsync_directory(runtime_dir.parent)
        validate_runtime(runtime_dir, lock, key, bundle_sha256)
        return receipt
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def run_worker(runtime_dir: Path, worker_script: Path, arguments: list[str]) -> None:
    _lock_raw, lock = load_lock()
    key = _platform_key(lock)
    validate_runtime(runtime_dir, lock, key)
    worker_raw = _regular(worker_script, limit=1024 * 1024)
    if _sha256(worker_raw) != WORKER_SHA256:
        raise ValueError("Worker script digest differs from the reviewed leaf-rotation entry point")
    stdlib = Path(sysconfig.get_path("stdlib")).resolve()
    platstdlib = Path(sysconfig.get_path("platstdlib")).resolve()
    paths = [
        runtime_dir.resolve(),
        worker_script.resolve().parent,
        stdlib,
        platstdlib,
        stdlib / "lib-dynload",
    ]
    sys.path[:] = list(dict.fromkeys(str(path) for path in paths))
    import cffi
    import cryptography
    import pycparser

    for module in (cryptography, cffi, pycparser):
        origin = Path(module.__file__).resolve()
        if runtime_dir.resolve() not in origin.parents:
            raise RuntimeError(
                "Standalone runtime imported a dependency outside the pinned directory"
            )
    if (
        cryptography.__version__ != "50.0.1"
        or cffi.__version__ != "2.0.0"
        or pycparser.__version__ != "2.23"
    ):
        raise RuntimeError("Standalone runtime dependency version differs")
    sys.argv = [str(worker_script), *arguments]
    runpy.run_path(str(worker_script), run_name="__main__")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--output", type=Path, required=True)
    install_command = commands.add_parser("install")
    install_command.add_argument("--bundle", type=Path, required=True)
    install_command.add_argument("--runtime-dir", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--runtime-dir", type=Path, required=True)
    run.add_argument("--worker-script", type=Path, required=True)
    run.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == "build":
        result = build_bundle(args.output)
    elif args.command == "install":
        result = install(args.bundle, args.runtime_dir)
    else:
        arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
        run_worker(args.runtime_dir, args.worker_script, arguments)
        return 0
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            f"Standalone leaf-rotation runtime rejected ({type(error).__name__}); no credentials printed.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
