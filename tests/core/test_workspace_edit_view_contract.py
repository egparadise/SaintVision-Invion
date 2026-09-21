"""Bind the kernel WorkspaceEditView response (/v1/projects/{p}/runs/{id}/checkouts/{cid}/files).

Why this matters (VF-GM-03): WorkspaceEditor._view() serves the inv:// File Explorer checkout and
validates its output with validate_contract("WorkspaceEditView", ...). Its `sha256` field is a REAL
content hash -- hashlib.sha256(raw).hexdigest() over the actual checkout bytes -- and each snapshot file
carries its own byte sha256 and dataBase64. This is the integrity truth the File Explorer must display:
a hash of the file BYTES, not a hash of a URI+contentHash (the circular path VF-GM-03 flagged). Binding
the response to a shared fixture gives the frontend the authoritative shape so it stops synthesizing
integrity/health it did not observe.

NOTE (Gemini handoff): the File Explorer (MonacoWorkspaceEditor.tsx) currently renders hardcoded
INITIAL_FILES via the EditorFile type and does NOT fetch this endpoint. To show real integrity it must
consume WorkspaceEditView.sha256 / snapshot.files[].sha256 rather than deriving or synthesizing hashes.
"""
import json
from pathlib import Path

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "contracts" / "fixtures" / "workspace-edit-view-response.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_shared_fixture_matches_kernel_contract():
    # The exact validator WorkspaceEditor._view() runs on the served checkout response.
    validate_contract("WorkspaceEditView", _fixture())


def test_every_envelope_field_is_load_bearing():
    value = _fixture()
    for field in list(value):
        broken = {k: v for k, v in value.items() if k != field}
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("WorkspaceEditView", broken)


def test_every_snapshot_field_is_load_bearing():
    for field in list(_fixture()["snapshot"]):
        broken = _fixture()
        del broken["snapshot"][field]
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("WorkspaceEditView", broken)


def test_every_snapshot_file_field_is_load_bearing():
    # WorkspaceSnapshotFile requires path, executable, sha256, sizeBytes, dataBase64 -- the per-file
    # integrity fields the File Explorer must read rather than invent.
    for field in list(_fixture()["snapshot"]["files"][0]):
        broken = _fixture()
        del broken["snapshot"]["files"][0][field]
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("WorkspaceEditView", broken)


def test_content_sha256_must_be_a_64_hex_digest():
    # sha256 is a real byte digest (^[0-9a-f]{64}$); a non-hash value must be rejected -- the whole point
    # of VF-GM-03 is that this is a content hash, not a URI/contentHash echo.
    for bad in ("not-a-hash", "AABB", "g" * 64):
        value = _fixture()
        value["sha256"] = bad
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("WorkspaceEditView", value)
