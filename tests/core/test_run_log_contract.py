"""Bind the kernel RunLogView response to the shared fixture the frontend validates.

Why this matters: the kernel serves /v1/projects/{p}/runs/{id}/logs and result_view.logs()
validates its own output with _checked("RunLogView", ...) against core.schema.json. The frontend
hand-declares a parallel RunLogView interface (apps/web/src/contracts/types.ts) that the log panel
reads, and that hand-type has drifted looser than the contract (source widened to `| string`,
truncated/absentReason marked optional though the contract requires them). Without a shared fixture,
a backend shape change -- or the frontend mock diverging from the guaranteed shape -- stays green on
both sides. This fixture is the single shared example: the backend validates its live response against
core.schema.json and the frontend validates this same fixture against the mirrored
contracts/v1alpha1/core.schema.json#/$defs/RunLogView, so a required field cannot be dropped on one
side without breaking the other.
"""
import json
from pathlib import Path

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "contracts" / "fixtures" / "run-log-view.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_shared_fixture_matches_kernel_contract():
    # The exact validator result_view.logs() runs on the live backend response (_checked -> validate_contract).
    validate_contract("RunLogView", _fixture())


def test_every_top_level_field_is_load_bearing():
    # RunLogView requires all seven fields; dropping any must be rejected -- otherwise the fixture (and the
    # frontend log panel that reads its shape) could pass while the response silently lost a field.
    value = _fixture()
    for field in list(value):
        broken = {k: v for k, v in value.items() if k != field}
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("RunLogView", broken)


def test_source_is_pinned_to_the_execution_kernel_constant():
    # The contract pins source to the const "execution-kernel"; the frontend hand-type widened it to
    # `'execution-kernel' | string`, so this guards the backend side against that same widening.
    value = _fixture()
    value["source"] = "somewhere-else"
    with pytest.raises(DomainError, match="VAL-0002"):
        validate_contract("RunLogView", value)
