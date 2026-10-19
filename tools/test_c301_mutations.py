#!/usr/bin/env python3
"""Kill the Card 301 worker-module closure mutations one at a time."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "deploy" / "lan" / "leaf_rotation_standalone_runtime.py"
TEST = "tests/test_lan_leaf_rotation_standalone_runtime.py"
MUTANTS = (
    (
        "M1-missing-worker-config",
        '    "worker_config.py": "bb2b750ac294a2558f0214f8822c02da2f015486767f361b385ccc58e3c18992",\n',
        "",
    ),
    (
        "M2-external-module-shadow",
        "        installed_worker.parent,\n",
        "        worker_script.resolve().parent,\n",
    ),
)


def main() -> int:
    original = RUNTIME.read_bytes()
    results = []
    try:
        for identifier, before, after in MUTANTS:
            source = original.decode("utf-8")
            if source.count(before) != 1:
                raise RuntimeError(f"{identifier} anchor count differs")
            RUNTIME.write_text(source.replace(before, after), encoding="utf-8", newline="\n")
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", TEST, "-x"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            killed = completed.returncode == 1
            results.append({"id": identifier, "killed": killed})
            RUNTIME.write_bytes(original)
            if not killed or RUNTIME.read_bytes() != original:
                raise RuntimeError(f"{identifier} survived, errored, or restored differently")
    finally:
        RUNTIME.write_bytes(original)
    print(json.dumps({"total": len(results), "killed": len(results), "results": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
