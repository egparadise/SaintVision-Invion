#!/usr/bin/env python3
"""Kill Card 298 standalone leaf-runtime boundary mutations one at a time."""

from __future__ import annotations

import json
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
        '  python3 -I "$script_dir/leaf_rotation_standalone_runtime.py" install \\\n',
        '  python3 "$script_dir/leaf_rotation_standalone_runtime.py" install \\\n',
    ),
    (
        "M9",
        RUNTIME,
        "    if _sha256(worker_raw) != WORKER_SHA256:\n",
        "    if False:\n",
    ),
)


def main() -> int:
    results = []
    originals = {path: path.read_bytes() for _, path, _, _ in MUTANTS}
    try:
        for mutant_id, path, before, after in MUTANTS:
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
    print(json.dumps({"total": len(results), "killed": len(results), "results": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
