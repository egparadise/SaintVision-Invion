"""Serving-path rejection checks for the EvidenceEnvelope anchors.

The schema tests prove that EvidenceEnvelope rejects malformed data in isolation.  These
tests drive the two write paths whose validation happens before any database or provider
work, so removing the serving anchor cannot leave a green test that only exercises the
schema directly.
"""

from uuid import uuid4

import pytest

from inv.errors import DomainError
from inv.results import ResultStore
from inv.runs import RunStore


def test_result_prepare_rejects_invalid_evidence_at_serving_anchor():
    with pytest.raises(DomainError, match="EvidenceEnvelope: invalid contract"):
        ResultStore(None, None).prepare(
            str(uuid4()),
            "project-test",
            "run-test",
            str(uuid4()),
            str(uuid4()),
            {},
            proofs={},
        )


def test_run_complete_rejects_invalid_evidence_at_serving_anchor():
    with pytest.raises(DomainError, match="EvidenceEnvelope: invalid contract"):
        RunStore(None).complete(
            str(uuid4()),
            "run-test",
            expected_version=1,
            evidence={},
            artifact_path="unused",
            expected_size=0,
            proofs={},
        )
