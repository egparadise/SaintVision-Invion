from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import types
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


def _reviewed_worker_modules() -> dict[str, bytes]:
    return {name: (ROOT / "deploy" / "lan" / name).read_bytes() for name in runtime.WORKER_MODULES}


def _bundle(
    path: Path,
    raw: bytes,
    lock: dict,
    wheels: dict[str, bytes],
    worker_modules: dict[str, bytes] | None = None,
) -> None:
    worker_modules = worker_modules or _reviewed_worker_modules()
    manifest = {
        "schemaVersion": runtime.BUNDLE_SCHEMA,
        "lockSha256": runtime.LOCK_SHA256,
        "wheels": {
            name: lock["wheels"].get(name, {"sha256": hashlib.sha256(value).hexdigest()})["sha256"]
            for name, value in sorted(wheels.items())
        },
        "workerModules": {
            name: hashlib.sha256(value).hexdigest()
            for name, value in sorted(worker_modules.items())
        },
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(runtime.LOCK_NAME, raw)
        archive.writestr("runtime-bundle.json", runtime._canonical(manifest))
        for name, value in wheels.items():
            archive.writestr("wheels/" + name, value)
        for name, value in worker_modules.items():
            archive.writestr("worker/" + name, value)


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
    assert runtime.WORKER_MODULES == {
        "worker_config.py": hashlib.sha256(
            (ROOT / "deploy/lan/worker_config.py").read_bytes()
        ).hexdigest(),
        "worker_leaf_rotation.py": runtime.WORKER_SHA256,
    }


def test_worker_local_import_closure_is_exact_and_missing_module_fails_before_download(
    tmp_path,
    monkeypatch,
):
    assert set(runtime._worker_sources()) == {
        "worker_leaf_rotation.py",
        "worker_config.py",
    }
    monkeypatch.setattr(
        runtime,
        "WORKER_MODULES",
        {"worker_leaf_rotation.py": runtime.WORKER_SHA256},
    )
    downloaded = []
    monkeypatch.setattr(runtime, "_download", lambda url: downloaded.append(url))
    with pytest.raises(ValueError, match="local-module closure"):
        runtime.build_bundle(tmp_path / "must-not-exist.zip")
    assert downloaded == []
    assert not (tmp_path / "must-not-exist.zip").exists()


@pytest.mark.parametrize("damage", ["missing", "digest", "extra"])
def test_bundle_rejects_any_worker_module_set_or_digest_drift(tmp_path, monkeypatch, damage):
    raw, lock, wheels = _fixture_lock(monkeypatch)
    modules = _reviewed_worker_modules()
    if damage == "missing":
        modules.pop("worker_config.py")
    elif damage == "digest":
        modules["worker_config.py"] += b"\n# drift"
    else:
        modules["unreviewed.py"] = b"pass\n"
    bundle = tmp_path / "runtime.zip"
    _bundle(bundle, raw, lock, wheels, modules)
    with pytest.raises(ValueError):
        runtime.install(bundle, tmp_path / "installed")
    assert not (tmp_path / "installed").exists()


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
    assert first["fileCount"] == 8
    assert set(path.name for path in destination.parent.iterdir()) == {"runtime.zip", "installed"}
    (destination / "cryptography/__init__.py").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="files differ"):
        runtime.install(bundle, destination)


def test_repeated_preflight_install_and_worker_cycle_writes_no_bytecode(tmp_path, monkeypatch):
    raw, lock, wheels = _fixture_lock(monkeypatch)
    bundle = tmp_path / "runtime.zip"
    _bundle(bundle, raw, lock, wheels)
    destination = tmp_path / "installed"
    first = runtime.install(bundle, destination)
    worker = tmp_path / "worker_leaf_rotation.py"
    observed = tmp_path / "worker-count.txt"
    worker.write_text(
        "import cffi, cryptography, pathlib, pycparser, sys\n"
        "target=pathlib.Path(sys.argv[1])\n"
        "target.write_text(str(int(target.read_text() or '0') + 1) if target.exists() else '1')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime, "WORKER_SHA256", hashlib.sha256(worker.read_bytes()).hexdigest())
    saved_path = list(sys.path)
    saved_modules = {name: sys.modules.get(name) for name in ("cryptography", "cffi", "pycparser")}
    for name in saved_modules:
        sys.modules.pop(name, None)
    try:
        runtime.run_worker(destination, worker, [str(observed)])
        second = runtime.install(bundle, destination)
        runtime.run_worker(destination, worker, [str(observed)])
        third = runtime.install(bundle, destination)
    finally:
        sys.path[:] = saved_path
        for name, module in saved_modules.items():
            sys.modules.pop(name, None)
            if module is not None:
                sys.modules[name] = module
    assert first == second == third
    assert observed.read_text("utf-8") == "2"
    assert not list(destination.rglob("__pycache__"))
    assert sys.dont_write_bytecode is True


def test_bytecode_cleanup_is_narrow_verified_and_idempotent(tmp_path, monkeypatch):
    raw, lock, wheels = _fixture_lock(monkeypatch)
    bundle = tmp_path / "runtime.zip"
    _bundle(bundle, raw, lock, wheels)
    destination = tmp_path / "installed"
    runtime.install(bundle, destination)
    source = destination / "cryptography/__init__.py"
    cache = Path(importlib.util.cache_from_source(str(source)))
    cache.parent.mkdir()
    cache.write_bytes(b"interpreter cache from the pre-Card-300 entrypoint")
    cleaned = runtime.clean_bytecode_cache(destination)
    assert cleaned == {
        "cleaned": True,
        "removedBytecodeFiles": 1,
        "runtimeValidated": True,
    }
    assert runtime.clean_bytecode_cache(destination)["removedBytecodeFiles"] == 0

    cache.parent.mkdir()
    (cache.parent / "unreviewed.pyc").write_bytes(b"not derived from a pinned source")
    with pytest.raises(ValueError, match="non-bytecode drift"):
        runtime.clean_bytecode_cache(destination)

    (cache.parent / "unreviewed.pyc").unlink()
    cache.write_bytes(b"still present if receipt authority is wrong")
    receipt = destination / ".saintvision-runtime.json"
    damaged = json.loads(receipt.read_text("utf-8"))
    damaged["platformKey"] = "unreviewed-platform"
    receipt.write_text(json.dumps(damaged), encoding="utf-8")
    with pytest.raises(ValueError, match="receipt authority"):
        runtime.clean_bytecode_cache(destination)
    assert cache.is_file()


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
    installed_worker_dir = runtime_dir / "worker"
    installed_worker_dir.mkdir()
    (installed_worker_dir / runtime.WORKER_ENTRY).write_bytes(worker.read_bytes())
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


def test_runner_imports_local_module_only_from_installed_pinned_worker_directory(tmp_path):
    runtime_dir = tmp_path / "runtime"
    external = tmp_path / "external"
    result = tmp_path / "result.txt"
    for package, version in (
        ("cryptography", "50.0.1"),
        ("cffi", "2.0.0"),
        ("pycparser", "2.23"),
    ):
        package_dir = runtime_dir / package
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    installed_worker_dir = runtime_dir / "worker"
    installed_worker_dir.mkdir()
    (installed_worker_dir / runtime.WORKER_ENTRY).write_text(
        "# installed entry\n", encoding="utf-8"
    )
    (installed_worker_dir / "worker_config.py").write_text(
        'AUTHORITY = "installed-pinned"\n', encoding="utf-8"
    )
    external.mkdir()
    worker = external / runtime.WORKER_ENTRY
    worker.write_text(
        "import pathlib, sys, worker_config\n"
        "pathlib.Path(sys.argv[1]).write_text(worker_config.AUTHORITY, encoding='utf-8')\n",
        encoding="utf-8",
    )
    (external / "worker_config.py").write_text(
        'AUTHORITY = "external-unreviewed"\n', encoding="utf-8"
    )
    harness = tmp_path / "local-module-harness.py"
    harness.write_text(
        "import hashlib, importlib.util, pathlib\n"
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
        [sys.executable, "-I", "-B", str(harness)], text=True, capture_output=True
    )
    assert completed.returncode == 0, completed.stderr
    assert result.read_text("utf-8") == "installed-pinned"


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
    assert 'python3 -I -B "$script_dir/leaf_rotation_standalone_runtime.py" install' in source
    assert 'python3 -I -B "$script_dir/leaf_rotation_standalone_runtime.py" run' in source
    assert "sudo" not in source
    assert source.index(" install \\") < source.index(" run \\")


class _DownloadResponse:
    def __init__(self, *, status: int, url: str, value: bytes):
        self.status = status
        self._url = url
        self._value = value

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self) -> str:
        return self._url

    def read(self, _limit: int) -> bytes:
        return self._value


def _rewrite_zip_member(path: Path, target: str, replacement: bytes) -> None:
    with zipfile.ZipFile(path) as archive:
        entries = [(info, archive.read(info)) for info in archive.infolist()]
    temporary = path.with_suffix(".rewrite")
    with zipfile.ZipFile(temporary, "w") as archive:
        for info, value in entries:
            archive.writestr(info, replacement if info.filename == target else value)
    temporary.replace(path)


def test_download_rejects_redirect_even_when_response_is_success(monkeypatch):
    requested = "https://files.pythonhosted.org/reviewed.whl"
    response = _DownloadResponse(
        status=200,
        url="https://unreviewed.invalid/redirected.whl",
        value=b"wheel",
    )
    monkeypatch.setattr(runtime.urllib.request, "urlopen", lambda *_args, **_kwargs: response)
    with pytest.raises(RuntimeError, match="redirected"):
        runtime._download(requested)


@pytest.mark.parametrize(
    ("damage", "message"),
    [
        ("origin", "outside the pinned directory"),
        ("version", "dependency version differs"),
    ],
)
def test_runner_rejects_preimported_dependency_origin_and_version(
    tmp_path, monkeypatch, damage, message
):
    runtime_dir = tmp_path / "runtime"
    installed_worker = runtime_dir / "worker" / runtime.WORKER_ENTRY
    installed_worker.parent.mkdir(parents=True)
    installed_worker.write_text("# pinned worker\n", encoding="utf-8")
    worker = tmp_path / runtime.WORKER_ENTRY
    worker.write_text("raise AssertionError('must not execute')\n", encoding="utf-8")
    monkeypatch.setattr(runtime, "WORKER_SHA256", hashlib.sha256(worker.read_bytes()).hexdigest())
    monkeypatch.setattr(runtime, "load_lock", lambda: (b"", {"platforms": {"fixture": {}}}))
    monkeypatch.setattr(runtime, "_platform_key", lambda _lock: "fixture")
    monkeypatch.setattr(runtime, "validate_runtime", lambda *_args: {})

    versions = {"cryptography": "50.0.1", "cffi": "2.0.0", "pycparser": "2.23"}
    for name, version in versions.items():
        module = types.ModuleType(name)
        package = runtime_dir / name / "__init__.py"
        package.parent.mkdir(parents=True, exist_ok=True)
        package.write_text("# fixture\n", encoding="utf-8")
        module.__file__ = str(package)
        module.__version__ = version
        monkeypatch.setitem(sys.modules, name, module)
    if damage == "origin":
        sys.modules["cryptography"].__file__ = str(tmp_path / "ambient/cryptography.py")
    else:
        sys.modules["cryptography"].__version__ = "49.0.0"

    saved_path = list(sys.path)
    saved_argv = list(sys.argv)
    try:
        with pytest.raises(RuntimeError, match=message):
            runtime.run_worker(runtime_dir, worker, ["runtime-preflight"])
    finally:
        sys.path[:] = saved_path
        sys.argv[:] = saved_argv


def test_wheel_unpack_rejects_duplicate_member_name():
    from io import BytesIO

    target = BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("package/__init__.py", b"first")
            archive.writestr("package/__init__.py", b"second")
    with pytest.raises(ValueError, match="duplicated"):
        runtime._wheel_members(target.getvalue())


def test_wheel_unpack_rejects_absolute_path():
    with pytest.raises(ValueError, match="unsafe member path"):
        runtime._wheel_members(_wheel({"/absolute.py": b"x"}))


def test_wheel_unpack_rejects_backslash_path(monkeypatch):
    # zipfile normalizes os.sep while writing on Windows. Model the Linux Node's
    # ZIP parser so the hostile backslash spelling survives into ZipInfo.
    monkeypatch.setattr(zipfile.os, "sep", "/")
    raw = _wheel({r"package\escape.py": b"x"})
    with pytest.raises(ValueError, match="unsafe member path"):
        runtime._wheel_members(raw)


def test_bundle_manifest_must_use_canonical_bytes(tmp_path, monkeypatch):
    raw, lock, wheels = _fixture_lock(monkeypatch)
    bundle = tmp_path / "runtime.zip"
    _bundle(bundle, raw, lock, wheels)
    with zipfile.ZipFile(bundle) as archive:
        manifest = json.loads(archive.read("runtime-bundle.json"))
    _rewrite_zip_member(
        bundle,
        "runtime-bundle.json",
        json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"),
    )
    with pytest.raises(ValueError, match="manifest differs"):
        runtime.install(bundle, tmp_path / "installed")


@pytest.mark.parametrize(
    ("field", "value"),
    [("fileCount", -1), ("filesSha256", "0" * 64), ("workerModulesSha256", "0" * 64)],
)
def test_runtime_receipt_must_describe_recomputed_installed_files(
    tmp_path, monkeypatch, field, value
):
    raw, lock, wheels = _fixture_lock(monkeypatch)
    bundle = tmp_path / "runtime.zip"
    _bundle(bundle, raw, lock, wheels)
    destination = tmp_path / "installed"
    runtime.install(bundle, destination)
    receipt = destination / ".saintvision-runtime.json"
    damaged = json.loads(receipt.read_text("utf-8"))
    damaged[field] = value
    receipt.write_bytes(runtime._canonical(damaged))
    with pytest.raises(ValueError, match="does not describe installed files"):
        runtime.validate_runtime(destination, lock, "fixture-cpython")


def test_selected_wheels_must_not_install_colliding_files(tmp_path, monkeypatch):
    _raw, lock, wheels = _fixture_lock(monkeypatch)
    wheels["cffi.whl"] = _wheel({"cryptography/__init__.py": b"collision"})
    lock["wheels"]["cffi.whl"]["sha256"] = hashlib.sha256(wheels["cffi.whl"]).hexdigest()
    with pytest.raises(ValueError, match="colliding files"):
        runtime._expected_files(
            lock,
            wheels,
            "fixture-cpython",
            _reviewed_worker_modules(),
        )


def test_wheel_uncompressed_runtime_size_is_bounded(monkeypatch):
    monkeypatch.setattr(runtime, "MAX_RUNTIME_BYTES", 1)
    with pytest.raises(ValueError, match="oversized"):
        runtime._wheel_members(_wheel({"package.py": b"xx"}))


def test_install_rejects_relative_runtime_directory_before_reading_bundle():
    with pytest.raises(ValueError, match="must be absolute"):
        runtime.install(Path("missing-bundle.zip"), Path("relative-runtime"))


@pytest.mark.skipif(os.name == "nt", reason="Windows runner cannot create the reviewed symlinks")
def test_build_refuses_dangling_output_symlink(tmp_path, monkeypatch):
    _raw, lock, wheels = _fixture_lock(monkeypatch)
    monkeypatch.setattr(
        runtime,
        "_download",
        lambda url: wheels[url.rsplit("/", 1)[-1]],
    )
    output = tmp_path / "runtime.zip"
    output.symlink_to(tmp_path / "missing-target.zip")
    with pytest.raises(ValueError, match="replace an existing runtime bundle"):
        runtime.build_bundle(output)


@pytest.mark.skipif(os.name == "nt", reason="Windows runner cannot create the reviewed symlinks")
def test_install_refuses_runtime_directory_symlink(tmp_path, monkeypatch):
    raw, lock, wheels = _fixture_lock(monkeypatch)
    bundle = tmp_path / "runtime.zip"
    _bundle(bundle, raw, lock, wheels)
    real = tmp_path / "real-runtime"
    real.mkdir()
    destination = tmp_path / "installed"
    destination.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="must not be a symlink"):
        runtime.install(bundle, destination)


@pytest.mark.skipif(os.name == "nt", reason="Windows runner cannot create the reviewed symlinks")
@pytest.mark.parametrize("kind", ["directory", "file"])
def test_installed_tree_refuses_directory_and_file_symlinks(tmp_path, kind):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    external = tmp_path / "external"
    if kind == "directory":
        external.mkdir()
        (runtime_dir / "linked").symlink_to(external, target_is_directory=True)
    else:
        external.write_bytes(b"outside")
        (runtime_dir / "linked.py").symlink_to(external)
    with pytest.raises(ValueError, match="symlink|non-regular"):
        runtime._installed_files(runtime_dir)
