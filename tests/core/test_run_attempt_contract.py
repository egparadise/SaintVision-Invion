"""Bind the kernel RunAttemptList response to the shared fixture the frontend validates.

Why this matters: the kernel serves /v1/projects/{p}/runs/{id}/attempts and result_view.attempts()
validates its own output with _checked("RunAttemptList", ...) against core.schema.json. The frontend
hand-declares parallel RunAttemptList / RunAttemptItem interfaces (apps/web/src/contracts/types.ts)
whose shapes have drifted from the contract (see the Gemini handoff doc). Without a shared fixture, a
backend shape change -- or a frontend mock diverging from the guaranteed shape -- stays green on both
sides. This fixture is the single shared example: the backend validates its live response against
core.schema.json and the frontend validates this same fixture against the mirrored
contracts/v1alpha1/core.schema.json#/$defs/RunAttemptList, so a required field cannot be dropped on
one side without breaking the other.

The list envelope requires 5 fields; each attempt (RunAttemptObservation, additionalProperties:false)
requires 8. Both levels are exercised so item-level drift is caught, not only the envelope.
"""
import json
from pathlib import Path

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "contracts" / "fixtures" / "run-attempt-list.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_shared_fixture_matches_kernel_contract():
    # The exact validator result_view.attempts() runs on the live backend response.
    validate_contract("RunAttemptList", _fixture())


def test_every_top_level_field_is_load_bearing():
    # Dropping any envelope field the contract requires must be rejected.
    value = _fixture()
    for field in list(value):
        broken = {k: v for k, v in value.items() if k != field}
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("RunAttemptList", broken)


def test_every_attempt_field_is_load_bearing():
    # RunAttemptObservation requires all eight fields; dropping any from an attempt must be rejected --
    # this is where the contract's richness (and the frontend hand-type's drift) lives.
    value = _fixture()
    attempt = value["attempts"][0]
    for field in list(attempt):
        broken = json.loads(FIXTURE.read_text(encoding="utf-8"))
        del broken["attempts"][0][field]
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("RunAttemptList", broken)


def test_source_is_pinned_to_the_execution_kernel_constant():
    # The contract pins source to the const "execution-kernel"; the frontend hand-type widened it to
    # `'execution-kernel' | string`, so this guards the backend side against that same widening.
    value = _fixture()
    value["source"] = "somewhere-else"
    with pytest.raises(DomainError, match="VAL-0002"):
        validate_contract("RunAttemptList", value)
