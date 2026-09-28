"""Live tracking-sink conformance against a real MLflow server (opt-in lane).

Runs only where ``INV_MLFLOW_LIVE_URI`` names a server the ``mlflow-live``
job started (``run-mlflow`` label). Elsewhere it skips with that reason; in
the lane a server that does not answer is a failure, not a skip -- the lane
exists to observe the real thing.

The URI is plain http to a loopback address, which the configuration path
refuses (``TRACK-0004``); the sink is built directly with
``allow_insecure_loopback=True`` for this lane only.
"""

from __future__ import annotations

import os

import pytest

from saintvision.adapters.contract import AttestationResult
from saintvision.adapters.mlflow_sink import MlflowSink
from saintvision.adapters.tracking import canonical_record, run_tracking_conformance
from saintvision.ids import new_id
from saintvision.tracking.codes import MirrorStatus

LIVE_URI = os.environ.get("INV_MLFLOW_LIVE_URI", "").strip()

pytestmark = pytest.mark.skipif(
    not LIVE_URI, reason="Set INV_MLFLOW_LIVE_URI (the run-mlflow lane starts the server)"
)


@pytest.fixture(scope="module")
def sink() -> MlflowSink:
    live = MlflowSink(LIVE_URI, experiment_prefix="inv-ci", allow_insecure_loopback=True, timeout_seconds=10)
    probe = live.probe()
    assert probe.reachable, f"the lane's MLflow server at {LIVE_URI} does not answer"
    return live


def test_the_live_server_reports_a_version(sink):
    probe = sink.probe()
    assert probe.reachable and probe.api_version, probe


def test_the_real_sink_passes_the_tracking_conformance_suite_live(sink):
    report = run_tracking_conformance(sink, secret_handle=None)
    assert report.conformant, [(c.name, c.detail) for c in report.failures()]
    assert report.passed == 12


def test_mirror_find_attest_round_trip_and_idempotent_redelivery(sink):
    intent_id = new_id("mirror_intent")
    record = canonical_record(intent_id)
    first = sink.mirror(record)
    assert first.status is MirrorStatus.MIRRORED and first.reference_id
    assert sink.find(intent_id) == first.reference_id
    again = sink.mirror(record)
    assert again.reference_id == first.reference_id                  # no second run for the same intent
    attestation = sink.attest(first.reference_id)
    assert attestation.result is AttestationResult.VERIFIED
    assert attestation.response_sha256 == record.payload_sha256
    assert sink.attest("no-such-run").result is AttestationResult.UNVERIFIABLE
