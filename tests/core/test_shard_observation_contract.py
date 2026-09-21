"""Bind the kernel ShardObservation response (/v1/projects/{p}/runs/{id}/shards) to a shared fixture.

Why this matters (VF-GM-04): RunDetail.tsx fetches this response and shardObservation.shardRows()
projects it into the shards table -- deriving `verified`, `physicallyStopped`, and shard identity from
the member fields. The UI must show only what the kernel actually observed, not synthesize shards or
healthy replicas the backend did not report. This fixture pins the observed shape: what ShardObservation
guarantees (13 envelope fields) and what each observed member guarantees (ShardObservedMember: index,
runId, nodeId, phase, state, evidenceId) versus the result manifest members (ShardResultMember). With a
shared example, the frontend can validate against the mirrored schema and stop inventing fields.

NOTE (handed to Codex): unlike result_view, ShardRuntime._status() returns this response WITHOUT calling
validate_contract("ShardObservation", ...) -- the /shards endpoint is served with no backend contract
anchor. shards.py is the shard recovery/concurrency runtime (Codex lane); adding that anchor there is
recommended to make this a two-sided binding. This test binds fixture<->schema meanwhile.
"""
import json
from pathlib import Path

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "contracts" / "fixtures" / "shard-observation-response.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_shared_fixture_matches_kernel_contract():
    validate_contract("ShardObservation", _fixture())


def test_every_envelope_field_is_load_bearing():
    # All 13 ShardObservation fields are required (additionalProperties:false), including the ones whose
    # value may be null (sourcePlanId/parentRunId/parentState/aggregateManifestSha256/resultManifest/
    # resultManifestSha256) -- required means the key must be present. Dropping any must be rejected.
    value = _fixture()
    for field in list(value):
        broken = {k: v for k, v in value.items() if k != field}
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("ShardObservation", broken)


def test_every_observed_shard_member_field_is_load_bearing():
    # ShardObservedMember requires index, runId, nodeId, phase, state, evidenceId -- this is what the UI
    # reads to decide observed-vs-not; dropping any must be rejected.
    for field in list(_fixture()["shards"][0]):
        broken = _fixture()
        del broken["shards"][0][field]
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("ShardObservation", broken)


def test_every_result_manifest_member_field_is_load_bearing():
    # ShardResultMember requires index, runId, evidenceId, objectId, sha256, sizeBytes.
    for field in list(_fixture()["resultManifest"][0]):
        broken = _fixture()
        del broken["resultManifest"][0][field]
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("ShardObservation", broken)


def test_member_state_must_be_a_run_state():
    # ShardObservedMember.state is RunState (closed enum); an out-of-set value must be rejected.
    broken = _fixture()
    broken["shards"][0]["state"] = "not-a-run-state"
    with pytest.raises(DomainError, match="VAL-0002"):
        validate_contract("ShardObservation", broken)
