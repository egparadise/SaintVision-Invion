"""A real LOGIN inv_app reproduces 0026 and refuses it at each published head."""

import json
import os
from pathlib import Path
import subprocess
import sys


def test_applied_subject_function_is_scoped_after_historical_upgrade(postgres):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "tools/check_subject_tenant.py"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, "Disposable subject boundary verification failed"
    value = json.loads(result.stdout)
    assert value["stages"][0]["crossTenant"] is True
    assert all(row["crossTenant"] is False for row in value["stages"][1:])
    assert value["currentAccountChecks"]
    if os.getenv("INV_TEST_EVIDENCE_DIR"):
        target = Path(os.environ["INV_TEST_EVIDENCE_DIR"]) / "subject-boundary.json"
        target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
