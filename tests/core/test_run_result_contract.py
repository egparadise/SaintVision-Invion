"""Bind the kernel RunResultView / RunArtifactList responses to the shared fixtures the frontend
validates.

Why this matters: the kernel serves /v1/projects/{p}/runs/{id}/result and .../artifacts, and
DeveloperStudio decides -- on a result failure -- whether to fall back to /artifacts and whether to
mark the artifacts UNVERIFIED, entirely from the SHAPE of these two responses. That shape was not tied
to a fixture the frontend shares, so a backend change to it would silently diverge from the UI's
discrimination while the frontend's mock-based tests stayed green. These fixtures are the single shared
example: the backend already validates its own output with validate_contract() against the same
core.schema.json (result_view.result()/artifacts()), and the frontend validates this same fixture
against the mirrored contracts/v1alpha1/core.schema.json -- so a required field cannot be dropped on one
side without breaking the other.
"""
import json
from pathlib import Path

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = {
    "RunResultView": ROOT / "contracts" / "fixtures" / "run-result-view.json",
    "RunArtifactList": ROOT / "contracts" / "fixtures" / "run-artifact-list.json",
}


@pytest.mark.parametrize("name", list(FIXTURES))
def test_shared_fixture_matches_kernel_contract(name):
    # The exact validator result_view.result()/artifacts() runs on the live backend response.
    validate_contract(name, json.loads(FIXTURES[name].read_text(encoding="utf-8")))


@pytest.mark.parametrize("name", list(FIXTURES))
def test_every_top_level_field_is_load_bearing(name):
    # Dropping any field the contract requires must be rejected -- otherwise the fixture (and the
    # frontend discrimination that reads its shape) could pass while the response silently lost a field.
    value = json.loads(FIXTURES[name].read_text(encoding="utf-8"))
    for field in list(value):
        broken = {k: v for k, v in value.items() if k != field}
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract(name, broken)
