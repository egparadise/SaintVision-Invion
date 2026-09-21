"""Bind the kernel StorageObservationView response (/v1/projects/{p}/runs/{id}/storage-samples/{req}).

Why this matters (integrity): storage_view.result() serves the storage-sample observation and validates
its output with validate_contract("StorageObservationView", ...). The verify_sample() proof-of-possession
result surfaces here as the nested RecordedStorageObservation, whose integrityVerified is a const true --
i.e. when an observation is RECORDED it means the sample content was actually verified. Crucially the
envelope pins currentHealth to the const "unknown" and operationalAcceptanceAssessed to const false: the
backend deliberately refuses to assert health/acceptance. Binding this to a shared fixture gives the
frontend the authoritative shape so the storage/health UI shows counts + "unknown", not a synthesized
"healthy".

NOTE: the frontend does not currently fetch /storage-samples (StorageObservationView is served + anchored
but not yet wired) -- binding now locks the contract for when the sample-health UI is wired, same as the
run-logs / workspace-edit-view bindings.
"""
import json
from pathlib import Path

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "contracts" / "fixtures" / "storage-observation-response.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_shared_fixture_matches_kernel_contract():
    validate_contract("StorageObservationView", _fixture())


def test_every_envelope_field_is_load_bearing():
    # All 11 fields are required (additionalProperties:false), including observation whose value may be
    # null -- required means the key must be present. Dropping any must be rejected.
    value = _fixture()
    for field in list(value):
        broken = {k: v for k, v in value.items() if k != field}
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("StorageObservationView", broken)


def test_every_recorded_observation_field_is_load_bearing():
    # RecordedStorageObservation requires all ten fields -- the sample-integrity counts the UI must read
    # (sampled/mismatches/unverifiable/examined/unsampled) rather than synthesize.
    for field in list(_fixture()["observation"]):
        broken = _fixture()
        del broken["observation"][field]
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("StorageObservationView", broken)


def test_backend_refuses_to_assert_health_or_acceptance():
    # currentHealth is const "unknown" and operationalAcceptanceAssessed is const false: the backend
    # never claims health. A fixture asserting either must be rejected -- this is the anti-synthesis guard.
    for field, bad in (("currentHealth", "healthy"), ("operationalAcceptanceAssessed", True)):
        value = _fixture()
        value[field] = bad
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("StorageObservationView", value)


def test_recorded_observation_integrity_is_pinned_verified():
    # RecordedStorageObservation.integrityVerified is const true: a recorded sample means verify_sample
    # passed. An observation claiming integrityVerified false must be rejected.
    value = _fixture()
    value["observation"]["integrityVerified"] = False
    with pytest.raises(DomainError, match="VAL-0002"):
        validate_contract("StorageObservationView", value)
