from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import warnings
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "deploy/lan/leaf_rotation_standalone_runtime.py"
SPEC = importlib.util.spec_from_file_location("leaf_rotation_standalone_runtime", MODULE_PATH)
assert SPEC and SPEC.loader
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def _wheel(files: dict[str, bytes]) -> bytes:
    from io import BytesIO

    target = BytesIO()
    with zipfile.ZipFile(target, "w") as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    return target.getvalue()


def _fixture_lock(monkeypatch: pytest.MonkeyPatch) -> tuple[bytes, dict, dict[str, bytes]]:
    wheels = {
        "cryptography.whl": _wheel({"cryptography/__init__.py": b'__version__="50.0.1"\n'}),
        "cffi.whl": _wheel({"cffi/__init__.py": b'__version__="2.0.0"\n'}),
        "pycparser.whl": _wheel({"pycparser/__init__.py": b'__version__="2.23"\n'}),
    }
    key = "fixture-cpython"
    lock = {
        "schemaVersion": "saintvision-leaf-rotation-runtime-lock:1",
        "source": {},
        "platforms": {
            key: {
                "implementation": sys.implementation.name,
                "python": list(sys.version_info[:2]),
                "machine": "fixture-machine",
                "sysconfigPlatform": "fixture-platform",
                "soabi": "fixture-soabi",
                "wheels": list(wheels),
            }
        },
        "wheels": {
            name: {
                "project": name.removesuffix(".whl"),
                "version": "fixture",
                "sha256": hashlib.sha256(value).hexdigest(),
                "url": "https://files.pythonhosted.org/fixture/" + name,
            }
            for name, value in wheels.items()
        },
    }
    raw = runtime._canonical(lock)
    monkeypatch.setattr(runtime, "load_lock", lambda: (raw, lock))
    monkeypatch.setattr(runtime, "_platform_key", lambda _lock: key)
    return raw, lock, wheels


def _bundle(path: Path, raw: bytes, lock: dict, wheels: dict[str, bytes]) -> None:
    manifest = {
        "schemaVersion": runtime.BUNDLE_SCHEMA,
        "lockSha256": runtime.LOCK_SHA256,
        "wheels": {
            name: lock["wheels"].get(name, {"sha256": hashlib.sha256(value).hexdigest()})["sha256"]
            for name, value in sorted(wheels.items())
        },
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(runtime.LOCK_NAME, raw)
        archive.writestr("runtime-bundle.json", runtime._canonical(manifest))
        for name, value in wheels.items():
            archive.writestr("wheels/" + name, value)


def test_reviewed_lock_is_exactly_two_observed_abis_and_four_pypi_wheels():
    _raw, lock = runtime.load_lock()
    assert set(lock["platforms"]) == {
        "cpython-312-x86_64-linux-gnu",
        "cpython-314-x86_64-linux-gnu",
    }
    assert {tuple(item["python"]) for item in lock["platforms"].values()} == {(3, 12), (3, 14)}
    assert {item["machine"] for item in lock["platforms"].values()} == {"x86_64"}
    assert len(lock["wheels"]) == 4
    assert {item["project"] for item in lock["wheels"].values()} == {
        "cryptography",
        "cffi",
        "pycparser",
    }
    assert all(
        item["url"].startswith("https://files.pythonhosted.org/")
        for item in lock["wheels"].values()
    )
    assert (
        hashlib.sha256((ROOT / "deploy/lan/worker_leaf_rotation.py").read_bytes()).hexdigest()
        == runtime.WORKER_SHA256
    )


def test_lock_digest_and_unreviewed_abi_are_fail_closed(tmp_path, monkeypatch):
    damaged_lock = tmp_path / runtime.LOCK_NAME
    damaged_lock.write_bytes((ROOT / "deploy/lan" / runtime.LOCK_NAME).read_bytes() + b" ")
    fake_module = tmp_path / "leaf_rotation_standalone_runtime.py"
    fake_module.write_text("# location anchor\n", encoding="utf-8")
    monkeypatch.setattr(runtime, "__file__", str(fake_module))
    with pytest.raises(ValueError, match="lock digest"):
        runtime.load_lock()

    monkeypatch.undo()
    _raw, lock = runtime.load_lock()
    monkeypatch.setattr(runtime.platform, "machine", lambda: "aarch64")
    with pytest.raises(RuntimeError, match="ABI or architecture"):
        runtime._platform_key(lock)


def test_install_is_atomic_idempotent_and_rejects_changed_installed_file(tmp_path, monkeypatch):
    raw, lock, wheels = _fixture_lock(monkeypatch)
    bundle = tmp_path / "runtime.zip"
    _bundle(bundle, raw, lock, wheels)
    destination = tmp_path / "installed"
    first = runtime.install(bundle, destination)
    second = runtime.install(bundle, destination)
    assert first == second
    assert first["fileCount"] == 6
    assert set(path.name for path in destination.parent.iterdir()) == {"runtime.zip", "installed"}
    (destination / "cryptography/__init__.py").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="files differ"):
        runtime.install(bundle, destination)


@pytest.mark.parametrize("damage", ["digest", "missing", "extra", "duplicate", "abi"])
def test_install_rejects_hash_mismatch_missing_wheel_and_wrong_abi(tmp_path, monkeypatch, damage):
    raw, lock, wheels = _fixture_lock(monkeypatch)
    bundle = tmp_path / "runtime.zip"
    if damage == "digest":
        wheels["cffi.whl"] += b"damage"
    elif damage == "missing":
        wheels.pop("cffi.whl")
    elif damage == "extra":
        wheels["unreviewed.whl"] = _wheel({"unreviewed.py": b"pass\n"})
    elif damage == "abi":
        monkeypatch.setattr(
            runtime,
            "_platform_key",
            lambda _lock: (_ for _ in ()).throw(RuntimeError("ABI rejected")),
        )
    _bundle(bundle, raw, lock, wheels)
    if damage == "duplicate":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(bundle, "a") as archive:
                archive.writestr(runtime.LOCK_NAME, raw)
    with pytest.raises((ValueError, RuntimeError)):
        runtime.install(bundle, tmp_path / "installed")
    assert not (tmp_path / "installed").exists()


def test_wheel_unpack_rejects_traversal_symlink_and_data_relocation():
    bad = {
        "traversal": _wheel({"../escape": b"x"}),
        "data": _wheel({"package.data/purelib/escape": b"x"}),
    }
    for raw in bad.values():
        with pytest.raises(ValueError):
            runtime._wheel_members(raw)
    from io import BytesIO

    target = BytesIO()
    with zipfile.ZipFile(target, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "target")
    with pytest.raises(ValueError, match="non-regular"):
        runtime._wheel_members(target.getvalue())


def test_isolated_runner_ignores_pythonpath_system_cryptography(tmp_path):
    runtime_dir = tmp_path / "runtime"
    hostile = tmp_path / "hostile"
    worker_dir = tmp_path / "worker"
    result = tmp_path / "result.json"
    for root, version in ((runtime_dir, "50.0.1"), (hostile, "41.0.7")):
        for package, package_version in (
            ("cryptography", version),
            ("cffi", "2.0.0"),
            ("pycparser", "2.23"),
        ):
            package_dir = root / package
            package_dir.mkdir(parents=True, exist_ok=True)
            (package_dir / "__init__.py").write_text(
                f'__version__ = "{package_version}"\n', encoding="utf-8"
            )
    worker_dir.mkdir()
    worker = worker_dir / "worker_leaf_rotation.py"
    worker.write_text(
        '"""Crash-safe installation test worker."""\n'
        "import cryptography, json, pathlib, sys\n"
        "pathlib.Path(sys.argv[1]).write_text(json.dumps({"
        "'version': cryptography.__version__, 'origin': cryptography.__file__, "
        "'paths': sys.path}), encoding='utf-8')\n",
        encoding="utf-8",
    )
    harness = tmp_path / "harness.py"
    harness.write_text(
        "import hashlib, importlib.util, pathlib, sys\n"
        f"spec=importlib.util.spec_from_file_location('standalone', {str(MODULE_PATH)!r})\n"
        "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)\n"
        "module.load_lock=lambda: (b'', {'platforms': {'fixture': {}}})\n"
        "module._platform_key=lambda lock: 'fixture'\n"
        "module.validate_runtime=lambda *args: {}\n"
        f"module.WORKER_SHA256=hashlib.sha256(pathlib.Path({str(worker)!r}).read_bytes()).hexdigest()\n"
        f"module.run_worker(pathlib.Path({str(runtime_dir)!r}), pathlib.Path({str(worker)!r}), [{str(result)!r}])\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, "-I", str(harness)],
        env={**os.environ, "PYTHONPATH": str(hostile)},
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(result.read_text("utf-8"))
    assert observed["version"] == "50.0.1"
    assert Path(observed["origin"]).is_relative_to(runtime_dir)
    assert all(str(hostile) not in path for path in observed["paths"])


def test_runner_rejects_an_unreviewed_worker_before_import(tmp_path, monkeypatch):
    worker = tmp_path / "worker_leaf_rotation.py"
    worker.write_text('"""Crash-safe installation decoy."""\n', encoding="utf-8")
    monkeypatch.setattr(runtime, "load_lock", lambda: (b"", {"platforms": {"fixture": {}}}))
    monkeypatch.setattr(runtime, "_platform_key", lambda _lock: "fixture")
    monkeypatch.setattr(runtime, "validate_runtime", lambda *_args: {})
    with pytest.raises(ValueError, match="Worker script digest"):
        runtime.run_worker(tmp_path, worker, ["runtime-preflight"])


def test_shell_keeps_venv_fallback_and_uses_isolated_standalone_runner():
    source = (ROOT / "deploy/lan/prepare-leaf-rotation-runtime.sh").read_text("utf-8")
    assert "python3 -m venv" in source
    assert "cryptography==50.0.1" in source
    assert 'python3 -I "$script_dir/leaf_rotation_standalone_runtime.py" install' in source
    assert 'python3 -I "$script_dir/leaf_rotation_standalone_runtime.py" run' in source
    assert "sudo" not in source
    assert source.index(" install \\") < source.index(" run \\")
