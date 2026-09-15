"""Inventory must not mistake old, incomplete or corrupt public bundles for delivery."""
import hashlib
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from check_lan_storage_readiness import REQUIRED_FILES, bundle_view, evaluate


@pytest.mark.parametrize("fault", ["missing", "old", "checksum", "duplicate", "complete"])
def test_bundle_delivery_boundaries(tmp_path, fault):
    if fault != "missing":
        path = tmp_path / "worker.zip"
        with ZipFile(path, "w") as z:
            for name in REQUIRED_FILES if fault != "old" else ("Start-Worker.ps1",):
                z.writestr(name, "fixture")
            if fault == "duplicate":
                with pytest.warns(UserWarning, match="Duplicate"):
                    z.writestr(REQUIRED_FILES[0], "another fixture")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        (tmp_path / "worker.sha256").write_text("0" * 64 if fault == "checksum" else digest)
    report = dict(epochMatches=True, killSwitch=False,
                  nodes=[dict(fresh=True, profileVersion="lan-workspace-v1")],
                  relations=[], bundles=bundle_view(tmp_path))
    assert ("public-storage-replacement-bundle-missing" in evaluate(report)) == (fault != "complete")


def test_live_failures_remain_separate_from_unknowns():
    report = dict(epochMatches=False, killSwitch=True,
                  nodes=[dict(fresh=False, profileVersion="lan-observe-v1")],
                  relations=[dict(present=False, selectAllowed=None),
                             dict(present=True, selectAllowed=False)], bundles=[])
    assert set(evaluate(report)) == {
        "pilot-epoch-mismatch", "tenant-kill-switch-active-or-unknown",
        "node-observation-unavailable-or-stale", "workspace-profile-not-observed",
        "storage-relations-missing", "observer-role-cannot-inspect-storage-registration",
        "public-storage-replacement-bundle-missing",
    }
