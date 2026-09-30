"""Real PostgreSQL evidence for the S04-DB C1-K collector."""

from __future__ import annotations

import json

import pytest
from inv.dispatch import DeliveryQueue

from tools import collect_s04_kernel_approval_evidence as collector
from test_approvals import approval
from test_dispatch_queue import queued
from test_tool_admission import gateway


pytestmark = pytest.mark.postgres


def test_real_product_approval_claim_delivery_and_attempt_chain_is_observed(gateway):
    a = gateway
    before = collector.collect_database(a.e.owner)
    queued(a)
    attempt = DeliveryQueue(a.e.db).acquire(a.e.tenant, command_id=a.command["commandId"])
    assert attempt is not None and attempt.operation == "execute"

    measured = collector.collect_database(a.e.owner)
    evidence = collector.build_evidence(
        database=measured,
        provenance={
            "commit_sha": "1" * 40,
            "branch": "hosted-core",
            "working_tree_clean_status": True,
            "content_clean_diff": True,
            "executor": "pytest-real-pg",
        },
        source_env="INV_TEST_ADMIN_DSN",
    )

    assert [evidence["observations"][key]["status"] for key in ("K1", "K2", "K3")] == [
        "MEASURED_PASS",
        "MEASURED_PASS",
        "MEASURED_PASS",
    ]
    assert evidence["observations"]["K1"]["metrics"]["claimCount"] == len(before["k1"]) + 1
    assert evidence["observations"]["K2"]["metrics"]["deliveryCount"] == len(before["k2"]) + 1
    assert (
        evidence["observations"]["K3"]["metrics"]["executionAttemptCount"] == len(before["k3"]) + 1
    )
    assert evidence["observations"]["K4"]["status"] == "NOT_REGISTERED"
    assert evidence["verdict"] == "NOT_OBSERVED"
    assert evidence["acceptanceClaim"] is False

    rendered = json.dumps(evidence, ensure_ascii=False)
    for identifier in (
        a.e.tenant,
        a.e.project,
        a.e.node,
        a.run["runId"],
        a.row["approvalId"],
        a.command["commandId"],
    ):
        assert identifier not in rendered
