"""Build the reviewed offline Node leaf-rotation runtime bundle."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deploy" / "lan"))

from leaf_rotation_standalone_runtime import main  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) == 1 or sys.argv[1] != "build":
        sys.argv.insert(1, "build")
    raise SystemExit(main())
