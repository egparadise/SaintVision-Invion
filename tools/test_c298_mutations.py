#!/usr/bin/env python3
"""Kill Card 298 standalone leaf-runtime boundary mutations one at a time."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "deploy/lan/leaf_rotation_standalone_runtime.py"
SHELL = ROOT / "deploy/lan/prepare-leaf-rotation-runtime.sh"
TEST = "tests/test_lan_leaf_rotation_standalone_runtime.py"

MUTANTS = (
    ("M1", RUNTIME, "    if _sha256(raw) != LOCK_SHA256:\n", "    if False:\n"),
    (
        "M2",
        RUNTIME,
        "        if all(observed[name] == expected[name] for name in observed)\n",
        '        if key == next(iter(lock["platforms"]))\n',
    ),
    (
        "M3",
        RUNTIME,
        '            if not 0 < len(value) <= MAX_WHEEL_BYTES or _sha256(value) != item["sha256"]:\n',
        "            if not 0 < len(value) <= MAX_WHEEL_BYTES:\n",
    ),
    (
        "M4",
        RUNTIME,
        "    if set(observed) != set(expected) or any(\n"
        "        observed[name] != value for name, value in expected.items()\n"
        "    ):\n",
        "    if set(observed) != set(expected):\n",
    ),
    (
        "M5",
        RUNTIME,
        "    sys.path[:] = list(dict.fromkeys(str(path) for path in paths))\n",
        "    sys.path.extend(str(path) for path in paths)\n",
    ),
    (
        "M6",
        RUNTIME,
        '            if any(part.endswith(".data") for part in path.parts):\n',
        "            if False:\n",
    ),
    (
        "M7",
        RUNTIME,
        "            if stat.S_IFMT(mode) not in {0, stat.S_IFREG}:\n",
        "            if False:\n",
    ),
    (
        "M8",
        SHELL,
        '  python3 -I -B "$script_dir/leaf_rotation_standalone_runtime.py" install \\\n',
        '  python3 -I "$script_dir/leaf_rotation_standalone_runtime.py" install \\\n',
    ),
    (
        "M9",
        RUNTIME,
        "    if _sha256(worker_raw) != WORKER_SHA256:\n",
        "    if False:\n",
    ),
    (
        "M10",
        RUNTIME,
        "sys.dont_write_bytecode = True\n",
        "sys.dont_write_bytecode = False\n",
    ),
    (
        "M11",
        RUNTIME,
        "        if response.status != 200 or response.geturl() != url:\n",
        "        if response.status != 200:\n",
    ),
    (
        "M12",
        RUNTIME,
        "        if runtime_dir.resolve() not in origin.parents:\n",
        "        if False:\n",
    ),
    (
        "M13",
        RUNTIME,
        '    if (\n        cryptography.__version__ != "50.0.1"\n'
        '        or cffi.__version__ != "2.0.0"\n'
        '        or pycparser.__version__ != "2.23"\n    ):\n',
        "    if False:\n",
    ),
    (
        "M14",
        RUNTIME,
        "            if total > MAX_RUNTIME_BYTES or path.as_posix() in result:\n",
        "            if total > MAX_RUNTIME_BYTES:\n",
    ),
    (
        "M15",
        RUNTIME,
        '                or info.filename.startswith("/")\n',
        "                or False\n",
    ),
    (
        "M16",
        RUNTIME,
        '                or "\\\\" in info.filename\n',
        "                or False\n",
    ),
    (
        "M17",
        RUNTIME,
        "        if manifest != expected_manifest or manifest_raw != _canonical(expected_manifest):\n",
        "        if manifest != expected_manifest:\n",
    ),
    (
        "M18",
        RUNTIME,
        '    if (\n        receipt["fileCount"] != len(expected)\n'
        '        or receipt["filesSha256"] != files_digest\n'
        '        or receipt["workerModulesSha256"] != worker_digest\n    ):\n'
        '        raise ValueError("Standalone runtime receipt does not describe installed files")\n'
        "    return receipt\n",
        "    if False:\n"
        '        raise ValueError("Standalone runtime receipt does not describe installed files")\n'
        "    return receipt\n",
    ),
    (
        "M19",
        RUNTIME,
        "            if name in expected:\n",
        "            if False:\n",
    ),
    (
        "M20",
        RUNTIME,
        "            if total > MAX_RUNTIME_BYTES or path.as_posix() in result:\n",
        "            if path.as_posix() in result:\n",
    ),
    (
        "M21",
        RUNTIME,
        "    if not runtime_dir.is_absolute():\n",
        "    if False:\n",
    ),
    (
        "M22",
        RUNTIME,
        "    if output.exists() or output.is_symlink():\n",
        "    if output.exists():\n",
    ),
    (
        "M23",
        RUNTIME,
        "    if runtime_dir.is_symlink():\n",
        "    if False:\n",
    ),
    (
        "M24",
        RUNTIME,
        "            if (root_path / name).is_symlink():\n",
        "            if False:\n",
    ),
    (
        "M25",
        RUNTIME,
        "            if path.is_symlink() or not path.is_file():\n",
        "            if not path.is_file():\n",
    ),
)

LINUX_ONLY_MUTANTS = {"M22", "M23", "M24", "M25"}


def main() -> int:
    results = []
    originals = {path: path.read_bytes() for _, path, _, _ in MUTANTS}
    try:
        for mutant_id, path, before, after in MUTANTS:
            if os.name == "nt" and mutant_id in LINUX_ONLY_MUTANTS:
                results.append(
                    {
                        "id": mutant_id,
                        "killed": None,
                        "skipped": "requires Linux symlink semantics",
                    }
                )
                continue
            original = originals[path]
            text = original.decode("utf-8")
            if text.count(before) != 1:
                raise RuntimeError(f"{mutant_id} anchor count differs")
            path.write_text(text.replace(before, after), encoding="utf-8", newline="\n")
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", TEST, "-x"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            killed = completed.returncode == 1
            results.append({"id": mutant_id, "killed": killed, "exitCode": completed.returncode})
            path.write_bytes(original)
            if path.read_bytes() != original:
                raise RuntimeError(f"{mutant_id} restore differs")
            if not killed:
                print(completed.stdout[-2000:], file=sys.stderr)
                print(completed.stderr[-2000:], file=sys.stderr)
                raise RuntimeError(f"{mutant_id} survived or errored")
    finally:
        for path, original in originals.items():
            path.write_bytes(original)
    killed = sum(item.get("killed") is True for item in results)
    skipped = sum("skipped" in item for item in results)
    print(
        json.dumps(
            {
                "total": len(results),
                "killed": killed,
                "skipped": skipped,
                "results": results,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
